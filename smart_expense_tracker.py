
import csv
import hashlib
import math
import os
import sqlite3
import tkinter as tk
from datetime import date, datetime, timedelta
from tkinter import filedialog, messagebox, ttk

DB_FILE = "smart_expense_tracker.db"
CATEGORIES = [
    "Food", "Transport", "Bills", "Shopping", "Entertainment",
    "Health", "Education", "Travel", "Rent", "Other"
]


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


class Database:
    def __init__(self, path=DB_FILE):
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.init_db()

    def init_db(self):
        self.conn.executescript("""
        PRAGMA foreign_keys = ON;

        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS budgets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            month TEXT NOT NULL,
            amount REAL NOT NULL CHECK(amount >= 0),
            UNIQUE(user_id, month),
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            category TEXT NOT NULL,
            amount REAL NOT NULL CHECK(amount > 0),
            description TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        """)
        self.conn.commit()

    def close(self):
        self.conn.close()

    def create_user(self, username, password):
        try:
            cur = self.conn.execute(
                "INSERT INTO users(username,password_hash,created_at) VALUES(?,?,?)",
                (username, hash_password(password), datetime.now().isoformat(timespec="seconds"))
            )
            self.conn.commit()
            return cur.lastrowid
        except sqlite3.IntegrityError:
            return None

    def authenticate(self, username, password):
        return self.conn.execute(
            "SELECT * FROM users WHERE username=? AND password_hash=?",
            (username, hash_password(password))
        ).fetchone()

    def add_expense(self, user_id, d, category, amount, description):
        self.conn.execute(
            """INSERT INTO expenses(user_id,date,category,amount,description,created_at)
               VALUES(?,?,?,?,?,?)""",
            (user_id, d, category, amount, description, datetime.now().isoformat(timespec="seconds"))
        )
        self.conn.commit()

    def update_expense(self, expense_id, user_id, d, category, amount, description):
        self.conn.execute(
            """UPDATE expenses
               SET date=?, category=?, amount=?, description=?
               WHERE id=? AND user_id=?""",
            (d, category, amount, description, expense_id, user_id)
        )
        self.conn.commit()

    def delete_expense(self, expense_id, user_id):
        self.conn.execute(
            "DELETE FROM expenses WHERE id=? AND user_id=?",
            (expense_id, user_id)
        )
        self.conn.commit()

    def get_expense(self, expense_id, user_id):
        return self.conn.execute(
            "SELECT * FROM expenses WHERE id=? AND user_id=?",
            (expense_id, user_id)
        ).fetchone()

    def get_expenses(self, user_id, start=None, end=None, category="All"):
        sql = "SELECT * FROM expenses WHERE user_id=?"
        params = [user_id]
        if start:
            sql += " AND date>=?"
            params.append(start)
        if end:
            sql += " AND date<=?"
            params.append(end)
        if category and category != "All":
            sql += " AND category=?"
            params.append(category)
        sql += " ORDER BY date DESC, id DESC"
        return self.conn.execute(sql, params).fetchall()

    def get_month_expenses(self, user_id, month):
        return self.conn.execute(
            "SELECT * FROM expenses WHERE user_id=? AND substr(date,1,7)=? ORDER BY date",
            (user_id, month)
        ).fetchall()

    def get_total(self, user_id, month=None):
        if month:
            row = self.conn.execute(
                "SELECT COALESCE(SUM(amount),0) AS total FROM expenses WHERE user_id=? AND substr(date,1,7)=?",
                (user_id, month)
            ).fetchone()
        else:
            row = self.conn.execute(
                "SELECT COALESCE(SUM(amount),0) AS total FROM expenses WHERE user_id=?",
                (user_id,)
            ).fetchone()
        return float(row["total"])

    def get_budget(self, user_id, month):
        row = self.conn.execute(
            "SELECT amount FROM budgets WHERE user_id=? AND month=?",
            (user_id, month)
        ).fetchone()
        return float(row["amount"]) if row else 0.0

    def set_budget(self, user_id, month, amount):
        self.conn.execute(
            """INSERT INTO budgets(user_id,month,amount) VALUES(?,?,?)
               ON CONFLICT(user_id,month) DO UPDATE SET amount=excluded.amount""",
            (user_id, month, amount)
        )
        self.conn.commit()

    def category_totals(self, user_id, month):
        return self.conn.execute(
            """SELECT category, SUM(amount) total
               FROM expenses
               WHERE user_id=? AND substr(date,1,7)=?
               GROUP BY category ORDER BY total DESC""",
            (user_id, month)
        ).fetchall()

    def monthly_totals(self, user_id, months=6):
        today = date.today().replace(day=1)
        result = []
        y, m = today.year, today.month
        for i in range(months - 1, -1, -1):
            mm = m - i
            yy = y
            while mm <= 0:
                yy -= 1
                mm += 12
            month = f"{yy:04d}-{mm:02d}"
            result.append((month, self.get_total(user_id, month)))
        return result

    def all_category_values(self, user_id, category, month=None):
        if month:
            rows = self.conn.execute(
                """SELECT amount FROM expenses
                   WHERE user_id=? AND category=? AND substr(date,1,7)=?""",
                (user_id, category, month)
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT amount FROM expenses WHERE user_id=? AND category=?",
                (user_id, category)
            ).fetchall()
        return [float(r["amount"]) for r in rows]


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Smart Expense Tracker")
        self.geometry("1180x760")
        self.minsize(1000, 650)
        self.db = Database()
        self.user = None
        self.selected_expense = None
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.configure(bg="#eef2f7")
        self.show_login()

    def on_close(self):
        self.db.close()
        self.destroy()

    def clear(self):
        for w in self.winfo_children():
            w.destroy()

    def style(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TButton", padding=7, font=("Segoe UI", 10))
        style.configure("Accent.TButton", padding=8, font=("Segoe UI", 10, "bold"))
        style.configure("TLabel", font=("Segoe UI", 10))
        style.configure("Header.TLabel", font=("Segoe UI", 22, "bold"))
        style.configure("Sub.TLabel", font=("Segoe UI", 11))
        style.configure("Treeview", rowheight=29, font=("Segoe UI", 10))
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))

    def show_login(self):
        self.clear()
        self.style()
        frame = tk.Frame(self, bg="#eef2f7")
        frame.pack(expand=True)
        card = tk.Frame(frame, bg="white", padx=45, pady=35, relief="solid", bd=1)
        card.pack()

        tk.Label(card, text="Smart Expense Tracker", font=("Segoe UI", 26, "bold"),
                 bg="white", fg="#172033").pack(pady=(0, 8))
        tk.Label(card, text="Budget prediction • anomaly detection • analytics",
                 font=("Segoe UI", 10), bg="white", fg="#667085").pack(pady=(0, 25))

        tk.Label(card, text="Username", bg="white", anchor="w").pack(fill="x")
        self.login_user = ttk.Entry(card, width=34)
        self.login_user.pack(pady=(4, 12), ipady=4)

        tk.Label(card, text="Password", bg="white", anchor="w").pack(fill="x")
        self.login_pass = ttk.Entry(card, width=34, show="•")
        self.login_pass.pack(pady=(4, 18), ipady=4)
        self.login_pass.bind("<Return>", lambda e: self.login())

        ttk.Button(card, text="Login", style="Accent.TButton",
                   command=self.login).pack(fill="x", pady=4)
        ttk.Button(card, text="Create New Account",
                   command=self.register).pack(fill="x", pady=4)

        self.login_user.focus()

    def register(self):
        win = tk.Toplevel(self)
        win.title("Create Account")
        win.geometry("390x330")
        win.transient(self)
        win.grab_set()

        f = tk.Frame(win, padx=30, pady=25)
        f.pack(fill="both", expand=True)
        tk.Label(f, text="Create Account", font=("Segoe UI", 18, "bold")).pack(pady=(0, 20))

        tk.Label(f, text="Username").pack(anchor="w")
        u = ttk.Entry(f)
        u.pack(fill="x", pady=(3, 12))

        tk.Label(f, text="Password (minimum 4 characters)").pack(anchor="w")
        p = ttk.Entry(f, show="•")
        p.pack(fill="x", pady=(3, 12))

        tk.Label(f, text="Confirm Password").pack(anchor="w")
        cp = ttk.Entry(f, show="•")
        cp.pack(fill="x", pady=(3, 20))

        def save():
            username = u.get().strip()
            password = p.get()
            if len(username) < 3:
                messagebox.showerror("Invalid", "Username must be at least 3 characters.", parent=win)
                return
            if len(password) < 4:
                messagebox.showerror("Invalid", "Password must be at least 4 characters.", parent=win)
                return
            if password != cp.get():
                messagebox.showerror("Invalid", "Passwords do not match.", parent=win)
                return
            if self.db.create_user(username, password) is None:
                messagebox.showerror("Unavailable", "That username already exists.", parent=win)
                return
            messagebox.showinfo("Success", "Account created. You can now log in.", parent=win)
            win.destroy()

        ttk.Button(f, text="Create Account", style="Accent.TButton", command=save).pack(fill="x")
        u.focus()

    def login(self):
        username = self.login_user.get().strip()
        password = self.login_pass.get()
        if not username or not password:
            messagebox.showwarning("Login", "Enter username and password.")
            return
        user = self.db.authenticate(username, password)
        if not user:
            messagebox.showerror("Login Failed", "Incorrect username or password.")
            return
        self.user = user
        self.show_dashboard()

    def show_dashboard(self):
        self.clear()
        self.style()

        top = tk.Frame(self, bg="#172033", height=68)
        top.pack(fill="x")
        top.pack_propagate(False)
        tk.Label(top, text="Smart Expense Tracker", fg="white", bg="#172033",
                 font=("Segoe UI", 18, "bold")).pack(side="left", padx=25)
        tk.Label(top, text=f"Welcome, {self.user['username']}", fg="#d9e2f2", bg="#172033",
                 font=("Segoe UI", 10)).pack(side="left", padx=15)
        ttk.Button(top, text="Logout", command=self.logout).pack(side="right", padx=20, pady=15)

        nav = tk.Frame(self, bg="white", height=52)
        nav.pack(fill="x")
        nav.pack_propagate(False)
        for text, cmd in [
            ("Dashboard", self.show_dashboard),
            ("Expenses", self.show_expenses),
            ("Budget", self.show_budget),
            ("Analytics", self.show_analytics),
        ]:
            ttk.Button(nav, text=text, command=cmd).pack(side="left", padx=8, pady=8)

        body = tk.Frame(self, bg="#eef2f7", padx=25, pady=20)
        body.pack(fill="both", expand=True)

        month = date.today().strftime("%Y-%m")
        total = self.db.get_total(self.user["id"], month)
        budget = self.db.get_budget(self.user["id"], month)
        remaining = budget - total if budget else 0
        predicted = self.predict_month_end(month)
        percent = (total / budget * 100) if budget else 0

        cards = tk.Frame(body, bg="#eef2f7")
        cards.pack(fill="x")
        self.metric(cards, "This Month", f"৳ {total:,.2f}", "Actual spending")
        self.metric(cards, "Budget", f"৳ {budget:,.2f}" if budget else "Not set", "Monthly limit")
        self.metric(cards, "Predicted", f"৳ {predicted:,.2f}", "End-of-month estimate")
        self.metric(cards, "Remaining", f"৳ {remaining:,.2f}" if budget else "—",
                    "Budget remaining")

        content = tk.Frame(body, bg="#eef2f7")
        content.pack(fill="both", expand=True, pady=20)

        left = tk.LabelFrame(content, text="Budget Status", bg="white", padx=18, pady=15,
                             font=("Segoe UI", 11, "bold"))
        left.pack(side="left", fill="both", expand=True, padx=(0, 10))

        if budget:
            status = "OVER BUDGET" if total > budget else ("AT RISK" if predicted > budget else "ON TRACK")
            color = "#b42318" if status == "OVER BUDGET" else ("#b54708" if status == "AT RISK" else "#027a48")
            tk.Label(left, text=status, fg=color, bg="white",
                     font=("Segoe UI", 18, "bold")).pack(pady=(15, 8))
            tk.Label(left, text=f"Actual: ৳ {total:,.2f}\nBudget: ৳ {budget:,.2f}\n"
                                f"Predicted: ৳ {predicted:,.2f}",
                     bg="white", fg="#344054", font=("Segoe UI", 12),
                     justify="center").pack(pady=8)
            bar = ttk.Progressbar(left, maximum=100, value=min(percent, 100))
            bar.pack(fill="x", padx=20, pady=12)
            tk.Label(left, text=f"{percent:.1f}% of budget used",
                     bg="white", fg="#667085").pack()
        else:
            tk.Label(left, text="Set a monthly budget", bg="white",
                     font=("Segoe UI", 17, "bold"), fg="#344054").pack(pady=35)
            ttk.Button(left, text="Go to Budget", command=self.show_budget).pack()

        right = tk.LabelFrame(content, text="Smart Insights", bg="white", padx=18, pady=15,
                              font=("Segoe UI", 11, "bold"))
        right.pack(side="left", fill="both", expand=True, padx=(10, 0))

        insights = self.get_insights(month)
        for icon, text in insights:
            tk.Label(right, text=f"{icon}  {text}", bg="white", fg="#344054",
                     font=("Segoe UI", 11), wraplength=440, justify="left",
                     anchor="w").pack(fill="x", pady=8)

    def metric(self, parent, title, value, subtitle):
        f = tk.Frame(parent, bg="white", padx=18, pady=14, relief="solid", bd=1)
        f.pack(side="left", fill="x", expand=True, padx=5)
        tk.Label(f, text=title, bg="white", fg="#667085",
                 font=("Segoe UI", 10)).pack(anchor="w")
        tk.Label(f, text=value, bg="white", fg="#172033",
                 font=("Segoe UI", 17, "bold")).pack(anchor="w", pady=4)
        tk.Label(f, text=subtitle, bg="white", fg="#98a2b3",
                 font=("Segoe UI", 9)).pack(anchor="w")

    def predict_month_end(self, month):
        rows = self.db.get_month_expenses(self.user["id"], month)
        if not rows:
            return 0.0
        y, m = map(int, month.split("-"))
        first = date(y, m, 1)
        if m == 12:
            next_month = date(y + 1, 1, 1)
        else:
            next_month = date(y, m + 1, 1)
        days_in_month = (next_month - first).days
        today = date.today()
        if month != today.strftime("%Y-%m"):
            return sum(float(r["amount"]) for r in rows)
        elapsed = max(1, today.day)
        total = sum(float(r["amount"]) for r in rows)
        return total / elapsed * days_in_month

    def get_insights(self, month):
        rows = self.db.get_month_expenses(self.user["id"], month)
        insights = []
        if not rows:
            return [("ℹ", "No expenses recorded this month yet. Add your first expense.")]

        total = sum(float(r["amount"]) for r in rows)
        predicted = self.predict_month_end(month)
        budget = self.db.get_budget(self.user["id"], month)

        if budget and predicted > budget:
            insights.append(("⚠", f"Projected overspend: ৳ {predicted-budget:,.2f} above your budget."))
        elif budget:
            insights.append(("✓", f"You're projected to stay ৳ {budget-predicted:,.2f} below budget."))

        cats = self.db.category_totals(self.user["id"], month)
        if cats:
            top = cats[0]
            insights.append(("↗", f"{top['category']} is your largest category at ৳ {float(top['total']):,.2f}."))

        anomalies = self.detect_anomalies(month)
        if anomalies:
            insights.append(("!", f"{len(anomalies)} unusual expense(s) detected. Check Analytics."))

        daily = total / max(1, date.today().day if month == date.today().strftime("%Y-%m") else 30)
        insights.append(("•", f"Current average daily spending is about ৳ {daily:,.2f}."))
        return insights

    def show_expenses(self):
        self.clear()
        self.style()
        self.page_header("Expenses", "Add, edit, delete, filter, and export your expenses.",
                         self.show_dashboard)

        outer = tk.Frame(self, bg="#eef2f7", padx=20, pady=10)
        outer.pack(fill="both", expand=True)

        form = tk.LabelFrame(outer, text="Expense Entry", bg="white", padx=12, pady=10,
                             font=("Segoe UI", 10, "bold"))
        form.pack(fill="x")

        self.exp_date = ttk.Entry(form, width=15)
        self.exp_cat = ttk.Combobox(form, values=CATEGORIES, state="readonly", width=17)
        self.exp_amount = ttk.Entry(form, width=15)
        self.exp_desc = ttk.Entry(form, width=40)
        self.exp_cat.set(CATEGORIES[0])
        self.exp_date.insert(0, date.today().isoformat())

        fields = [("Date YYYY-MM-DD", self.exp_date), ("Category", self.exp_cat),
                  ("Amount", self.exp_amount), ("Description", self.exp_desc)]
        for i, (label, widget) in enumerate(fields):
            tk.Label(form, text=label, bg="white").grid(row=0, column=i, sticky="w", padx=6)
            widget.grid(row=1, column=i, padx=6, pady=4, ipady=3)

        self.add_btn = ttk.Button(form, text="Add Expense", command=self.save_expense)
        self.add_btn.grid(row=1, column=4, padx=8)
        ttk.Button(form, text="Clear", command=self.clear_form).grid(row=1, column=5)

        filters = tk.Frame(outer, bg="#eef2f7", pady=10)
        filters.pack(fill="x")
        tk.Label(filters, text="From", bg="#eef2f7").pack(side="left")
        self.filter_start = ttk.Entry(filters, width=12)
        self.filter_start.pack(side="left", padx=5)
        tk.Label(filters, text="To", bg="#eef2f7").pack(side="left")
        self.filter_end = ttk.Entry(filters, width=12)
        self.filter_end.pack(side="left", padx=5)
        tk.Label(filters, text="Category", bg="#eef2f7").pack(side="left", padx=(10, 0))
        self.filter_cat = ttk.Combobox(filters, values=["All"] + CATEGORIES, state="readonly", width=15)
        self.filter_cat.set("All")
        self.filter_cat.pack(side="left", padx=5)
        ttk.Button(filters, text="Apply", command=self.refresh_expenses).pack(side="left", padx=5)
        ttk.Button(filters, text="Reset", command=self.reset_filters).pack(side="left", padx=5)
        ttk.Button(filters, text="Export CSV", command=self.export_csv).pack(side="right", padx=5)

        table_frame = tk.Frame(outer, bg="white")
        table_frame.pack(fill="both", expand=True)
        cols = ("id", "date", "category", "amount", "description")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings", selectmode="browse")
        headings = {"id":"ID", "date":"Date", "category":"Category",
                    "amount":"Amount", "description":"Description"}
        widths = {"id":60, "date":110, "category":140, "amount":120, "description":420}
        for c in cols:
            self.tree.heading(c, text=headings[c])
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.column("amount", anchor="e")
        scroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", self.select_expense)

        actions = tk.Frame(outer, bg="#eef2f7", pady=10)
        actions.pack(fill="x")
        self.total_label = tk.Label(actions, text="", bg="#eef2f7",
                                    font=("Segoe UI", 11, "bold"))
        self.total_label.pack(side="left")
        ttk.Button(actions, text="Update Selected", command=self.update_selected).pack(side="right", padx=4)
        ttk.Button(actions, text="Delete Selected", command=self.delete_selected).pack(side="right", padx=4)
        self.refresh_expenses()

    def page_header(self, title, subtitle, back_cmd):
        head = tk.Frame(self, bg="#172033", height=82)
        head.pack(fill="x")
        head.pack_propagate(False)
        ttk.Button(head, text="← Dashboard", command=back_cmd).pack(side="left", padx=18, pady=22)
        tk.Label(head, text=title, fg="white", bg="#172033",
                 font=("Segoe UI", 19, "bold")).pack(side="left", padx=12)
        tk.Label(head, text=subtitle, fg="#c9d2e3", bg="#172033",
                 font=("Segoe UI", 9)).pack(side="left", padx=8)

    def validate_date(self, value):
        try:
            datetime.strptime(value, "%Y-%m-%d")
            return True
        except ValueError:
            return False

    def save_expense(self):
        d = self.exp_date.get().strip()
        cat = self.exp_cat.get()
        desc = self.exp_desc.get().strip()
        try:
            amount = float(self.exp_amount.get())
        except ValueError:
            messagebox.showerror("Invalid Amount", "Amount must be a valid number.")
            return
        if not self.validate_date(d):
            messagebox.showerror("Invalid Date", "Use YYYY-MM-DD format.")
            return
        if amount <= 0:
            messagebox.showerror("Invalid Amount", "Amount must be greater than zero.")
            return

        self.db.add_expense(self.user["id"], d, cat, amount, desc)
        self.clear_form()
        self.refresh_expenses()
        messagebox.showinfo("Saved", "Expense added successfully.")

    def clear_form(self):
        self.selected_expense = None
        self.exp_date.delete(0, "end")
        self.exp_date.insert(0, date.today().isoformat())
        self.exp_cat.set(CATEGORIES[0])
        self.exp_amount.delete(0, "end")
        self.exp_desc.delete(0, "end")
        if hasattr(self, "add_btn"):
            self.add_btn.config(text="Add Expense", command=self.save_expense)

    def select_expense(self, _event=None):
        sel = self.tree.selection()
        if not sel:
            return
        expense_id = int(self.tree.item(sel[0], "values")[0])
        row = self.db.get_expense(expense_id, self.user["id"])
        if not row:
            return
        self.selected_expense = expense_id
        self.exp_date.delete(0, "end"); self.exp_date.insert(0, row["date"])
        self.exp_cat.set(row["category"])
        self.exp_amount.delete(0, "end"); self.exp_amount.insert(0, str(row["amount"]))
        self.exp_desc.delete(0, "end"); self.exp_desc.insert(0, row["description"] or "")
        self.add_btn.config(text="Save New Expense", command=self.save_expense)

    def update_selected(self):
        if not self.selected_expense:
            messagebox.showwarning("Update", "Select an expense first.")
            return
        try:
            amount = float(self.exp_amount.get())
        except ValueError:
            messagebox.showerror("Invalid Amount", "Amount must be numeric.")
            return
        d = self.exp_date.get().strip()
        if not self.validate_date(d) or amount <= 0:
            messagebox.showerror("Invalid", "Check date and amount.")
            return
        self.db.update_expense(
            self.selected_expense, self.user["id"], d, self.exp_cat.get(),
            amount, self.exp_desc.get().strip()
        )
        self.clear_form()
        self.refresh_expenses()

    def delete_selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Delete", "Select an expense first.")
            return
        expense_id = int(self.tree.item(sel[0], "values")[0])
        if messagebox.askyesno("Confirm Delete", "Delete this expense?"):
            self.db.delete_expense(expense_id, self.user["id"])
            self.clear_form()
            self.refresh_expenses()

    def refresh_expenses(self):
        if not hasattr(self, "tree"):
            return
        for item in self.tree.get_children():
            self.tree.delete(item)
        start = self.filter_start.get().strip() or None
        end = self.filter_end.get().strip() or None
        cat = self.filter_cat.get()
        rows = self.db.get_expenses(self.user["id"], start, end, cat)
        total = 0
        for r in rows:
            amount = float(r["amount"])
            total += amount
            self.tree.insert("", "end", values=(r["id"], r["date"], r["category"],
                                               f"{amount:,.2f}", r["description"] or ""))
        self.total_label.config(text=f"Filtered total: ৳ {total:,.2f}   |   Records: {len(rows)}")

    def reset_filters(self):
        self.filter_start.delete(0, "end")
        self.filter_end.delete(0, "end")
        self.filter_cat.set("All")
        self.refresh_expenses()

    def export_csv(self):
        rows = self.db.get_expenses(
            self.user["id"],
            self.filter_start.get().strip() or None,
            self.filter_end.get().strip() or None,
            self.filter_cat.get()
        )
        if not rows:
            messagebox.showwarning("Export", "There are no records to export.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")]
        )
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(["ID", "Date", "Category", "Amount", "Description"])
            for r in rows:
                writer.writerow([r["id"], r["date"], r["category"], r["amount"], r["description"] or ""])
        messagebox.showinfo("Exported", f"CSV exported to:\n{path}")

    def show_budget(self):
        self.clear()
        self.style()
        self.page_header("Budget", "Set your monthly limit and see the prediction.", self.show_dashboard)

        outer = tk.Frame(self, bg="#eef2f7", padx=30, pady=25)
        outer.pack(fill="both", expand=True)

        card = tk.LabelFrame(outer, text="Monthly Budget", bg="white", padx=25, pady=25,
                             font=("Segoe UI", 11, "bold"))
        card.pack(fill="x")

        month_var = tk.StringVar(value=date.today().strftime("%Y-%m"))
        amount_var = tk.StringVar()
        current = self.db.get_budget(self.user["id"], month_var.get())
        if current:
            amount_var.set(str(current))

        tk.Label(card, text="Month (YYYY-MM)", bg="white").grid(row=0, column=0, sticky="w", padx=8)
        ttk.Entry(card, textvariable=month_var, width=16).grid(row=1, column=0, padx=8, pady=6, ipady=4)
        tk.Label(card, text="Budget Amount", bg="white").grid(row=0, column=1, sticky="w", padx=8)
        ttk.Entry(card, textvariable=amount_var, width=18).grid(row=1, column=1, padx=8, pady=6, ipady=4)

        result = tk.Label(card, text="", bg="white", fg="#344054",
                          font=("Segoe UI", 11), justify="left")
        result.grid(row=2, column=0, columnspan=3, sticky="w", pady=18, padx=8)

        def refresh():
            month = month_var.get().strip()
            if len(month) != 7 or month[4] != "-":
                messagebox.showerror("Invalid", "Month must be YYYY-MM.")
                return
            budget = self.db.get_budget(self.user["id"], month)
            total = self.db.get_total(self.user["id"], month)
            predicted = self.predict_month_end(month)
            result.config(text=f"Actual spending: ৳ {total:,.2f}\n"
                               f"Budget: ৳ {budget:,.2f}\n"
                               f"Predicted month-end: ৳ {predicted:,.2f}\n"
                               f"Difference vs budget: ৳ {budget-predicted:,.2f}")

        def save():
            month = month_var.get().strip()
            try:
                amount = float(amount_var.get())
            except ValueError:
                messagebox.showerror("Invalid", "Budget must be numeric.")
                return
            if len(month) != 7 or month[4] != "-" or amount < 0:
                messagebox.showerror("Invalid", "Enter a valid month and non-negative budget.")
                return
            self.db.set_budget(self.user["id"], month, amount)
            refresh()
            messagebox.showinfo("Saved", "Budget saved.")

        ttk.Button(card, text="Save Budget", style="Accent.TButton", command=save).grid(row=1, column=2, padx=15)
        ttk.Button(card, text="Refresh", command=refresh).grid(row=3, column=0, padx=8, sticky="w")
        refresh()

        tip = tk.LabelFrame(outer, text="How prediction works", bg="white", padx=20, pady=20,
                            font=("Segoe UI", 11, "bold"))
        tip.pack(fill="x", pady=20)
        tk.Label(tip, text=("For the current month, the app divides your spending so far by the number "
                            "of elapsed days and projects that daily rate across the full month. "
                            "For previous months, the actual total is shown."),
                 bg="white", fg="#475467", font=("Segoe UI", 10), wraplength=850,
                 justify="left").pack(anchor="w")

    def detect_anomalies(self, month):
        rows = self.db.get_month_expenses(self.user["id"], month)
        by_cat = {}
        for r in rows:
            by_cat.setdefault(r["category"], []).append(r)

        anomalies = []
        for category, items in by_cat.items():
            values = [float(x["amount"]) for x in items]
            if len(values) < 3:
                continue
            mean = sum(values) / len(values)
            variance = sum((x - mean) ** 2 for x in values) / len(values)
            std = math.sqrt(variance)
            if std == 0:
                continue
            for item in items:
                z = (float(item["amount"]) - mean) / std
                if abs(z) >= 2:
                    anomalies.append((item, z, mean, std))
        return sorted(anomalies, key=lambda x: abs(x[1]), reverse=True)

    def show_analytics(self):
        self.clear()
        self.style()
        self.page_header("Analytics", "Understand spending patterns and unusual transactions.",
                         self.show_dashboard)

        outer = tk.Frame(self, bg="#eef2f7", padx=20, pady=15)
        outer.pack(fill="both", expand=True)

        month = date.today().strftime("%Y-%m")
        top = tk.Frame(outer, bg="#eef2f7")
        top.pack(fill="x")
        tk.Label(top, text=f"Analysis for {month}", bg="#eef2f7",
                 font=("Segoe UI", 16, "bold"), fg="#172033").pack(side="left")
        ttk.Button(top, text="Expenses", command=self.show_expenses).pack(side="right")

        charts = tk.Frame(outer, bg="#eef2f7")
        charts.pack(fill="both", expand=True, pady=12)

        cat_box = tk.LabelFrame(charts, text="Spending by Category", bg="white", padx=10, pady=10,
                                font=("Segoe UI", 10, "bold"))
        cat_box.pack(side="left", fill="both", expand=True, padx=(0, 8))
        self.draw_category_chart(cat_box, month)

        month_box = tk.LabelFrame(charts, text="Last 6 Months", bg="white", padx=10, pady=10,
                                  font=("Segoe UI", 10, "bold"))
        month_box.pack(side="left", fill="both", expand=True, padx=(8, 0))
        self.draw_month_chart(month_box)

        anomaly_box = tk.LabelFrame(outer, text="Spending Anomaly Detection", bg="white",
                                    padx=12, pady=10, font=("Segoe UI", 10, "bold"))
        anomaly_box.pack(fill="both", expand=True)
        anomalies = self.detect_anomalies(month)

        if not anomalies:
            tk.Label(anomaly_box, text="✓ No strong anomalies detected for this month.",
                     bg="white", fg="#027a48", font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=8)
        else:
            for item, z, mean, std in anomalies[:8]:
                tk.Label(
                    anomaly_box,
                    text=(f"⚠ {item['date']} • {item['category']} • ৳ {float(item['amount']):,.2f} "
                          f"(z-score {z:.2f}; category average ৳ {mean:,.2f})"),
                    bg="white", fg="#b42318", font=("Segoe UI", 10)
                ).pack(anchor="w", pady=3)

        tk.Label(anomaly_box,
                 text="Method: category-level z-score. A transaction is flagged when |z| ≥ 2 and "
                      "there are at least 3 transactions in that category for the month.",
                 bg="white", fg="#667085", font=("Segoe UI", 9),
                 wraplength=1000, justify="left").pack(anchor="w", pady=(8, 2))

    def draw_category_chart(self, parent, month):
        canvas = tk.Canvas(parent, bg="white", highlightthickness=0, height=260)
        canvas.pack(fill="both", expand=True)
        data = [(r["category"], float(r["total"])) for r in self.db.category_totals(self.user["id"], month)]
        if not data:
            canvas.create_text(180, 120, text="No data for this month.", fill="#667085",
                               font=("Segoe UI", 11))
            return
        maxv = max(v for _, v in data)
        width = 520
        height = 250
        bar_h = max(18, min(28, int(210 / len(data))))
        y = 15
        for cat, val in data[:8]:
            canvas.create_text(5, y + 8, text=cat, anchor="w", fill="#344054", font=("Segoe UI", 9))
            x0 = 105
            bar_w = (val / maxv) * 300 if maxv else 0
            canvas.create_rectangle(x0, y, x0 + bar_w, y + bar_h - 4, fill="#4f7cff", outline="")
            canvas.create_text(x0 + bar_w + 7, y + 7, text=f"৳{val:,.0f}", anchor="w",
                               fill="#344054", font=("Segoe UI", 9))
            y += bar_h + 4

    def draw_month_chart(self, parent):
        canvas = tk.Canvas(parent, bg="white", highlightthickness=0, height=260)
        canvas.pack(fill="both", expand=True)
        data = self.db.monthly_totals(self.user["id"], 6)
        maxv = max([v for _, v in data] + [1])
        base_y = 230
        chart_h = 185
        x = 30
        bar_w = 48
        gap = 24
        for month, val in data:
            h = (val / maxv) * chart_h
            canvas.create_rectangle(x, base_y-h, x+bar_w, base_y, fill="#344054", outline="")
            canvas.create_text(x+bar_w/2, base_y+15, text=month[2:], fill="#667085",
                               font=("Segoe UI", 9))
            canvas.create_text(x+bar_w/2, base_y-h-10, text=f"{val:,.0f}", fill="#344054",
                               font=("Segoe UI", 8))
            x += bar_w + gap

    def logout(self):
        self.user = None
        self.show_login()


if __name__ == "__main__":
    App().mainloop()
