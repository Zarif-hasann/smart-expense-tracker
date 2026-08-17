import csv, hashlib, math, sqlite3
from datetime import date, datetime

DB_FILE="smart_expense_tracker.db"
CATS=["Food","Transport","Bills","Shopping","Entertainment","Health","Education","Travel","Rent","Other"]

def hp(s): return hashlib.sha256(s.encode()).hexdigest()
def money(x): return f"৳ {x:,.2f}"
def pause(): input("\nPress Enter...")
def header(s):
    print("\n"*2+"="*64+"\n"+s.center(64)+"\n"+"="*64)

class Database:
    def __init__(self):
        self.c=sqlite3.connect(DB_FILE); self.c.row_factory=sqlite3.Row
        self.c.execute("PRAGMA foreign_keys=ON")
        self.c.executescript("""
        CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,username TEXT UNIQUE NOT NULL,password_hash TEXT NOT NULL,created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS budgets(id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL,month TEXT NOT NULL,amount REAL NOT NULL,UNIQUE(user_id,month),FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE);
        CREATE TABLE IF NOT EXISTS expenses(id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL,date TEXT NOT NULL,category TEXT NOT NULL,amount REAL NOT NULL,description TEXT,created_at TEXT NOT NULL,FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE);
        """); self.c.commit()

    def close(self): self.c.close()
    def add_user(self,u,p):
        try:
            x=self.c.execute("INSERT INTO users(username,password_hash,created_at) VALUES(?,?,?)",(u,hp(p),datetime.now().isoformat())).lastrowid
            self.c.commit(); return x
        except sqlite3.IntegrityError: return None
    def auth(self,u,p):
        return self.c.execute("SELECT * FROM users WHERE username=? AND password_hash=?",(u,hp(p))).fetchone()
    def add(self,uid,d,cat,a,desc):
        self.c.execute("INSERT INTO expenses(user_id,date,category,amount,description,created_at) VALUES(?,?,?,?,?,?)",(uid,d,cat,a,desc,datetime.now().isoformat())); self.c.commit()
    def one(self,eid,uid): return self.c.execute("SELECT * FROM expenses WHERE id=? AND user_id=?",(eid,uid)).fetchone()
    def update(self,eid,uid,d,cat,a,desc):
        self.c.execute("UPDATE expenses SET date=?,category=?,amount=?,description=? WHERE id=? AND user_id=?",(d,cat,a,desc,eid,uid)); self.c.commit()
    def delete(self,eid,uid): self.c.execute("DELETE FROM expenses WHERE id=? AND user_id=?",(eid,uid)); self.c.commit()
    def expenses(self,uid,start=None,end=None,cat=None):
        q="SELECT * FROM expenses WHERE user_id=?"; p=[uid]
        if start: q+=" AND date>=?"; p.append(start)
        if end: q+=" AND date<=?"; p.append(end)
        if cat and cat!="All": q+=" AND category=?"; p.append(cat)
        return self.c.execute(q+" ORDER BY date DESC,id DESC",p).fetchall()
    def month(self,uid,m): return self.c.execute("SELECT * FROM expenses WHERE user_id=? AND substr(date,1,7)=? ORDER BY date,id",(uid,m)).fetchall()
    def total(self,uid,m=None):
        q="SELECT COALESCE(SUM(amount),0) x FROM expenses WHERE user_id=?"; p=[uid]
        if m: q+=" AND substr(date,1,7)=?"; p.append(m)
        return float(self.c.execute(q,p).fetchone()["x"])
    def budget(self,uid,m):
        r=self.c.execute("SELECT amount FROM budgets WHERE user_id=? AND month=?",(uid,m)).fetchone()
        return float(r["amount"]) if r else 0
    def setbudget(self,uid,m,a):
        self.c.execute("""INSERT INTO budgets(user_id,month,amount) VALUES(?,?,?)
                          ON CONFLICT(user_id,month) DO UPDATE SET amount=excluded.amount""",(uid,m,a)); self.c.commit()
    def cats(self,uid,m):
        return self.c.execute("SELECT category,SUM(amount) total FROM expenses WHERE user_id=? AND substr(date,1,7)=? GROUP BY category ORDER BY total DESC",(uid,m)).fetchall()

def valid_date(s):
    try: datetime.strptime(s,"%Y-%m-%d"); return True
    except ValueError: return False

def valid_month(s):
    try: datetime.strptime(s,"%Y-%m"); return True
    except ValueError: return False

def amount(prompt="Amount: "):
    while True:
        try:
            x=float(input(prompt))
            if x>0: return x
        except ValueError: pass
        print("Enter a number greater than zero.")

def category():
    for i,x in enumerate(CATS,1): print(f"{i}. {x}")
    while True:
        try:
            n=int(input("Category: "))
            if 1<=n<=len(CATS): return CATS[n-1]
        except ValueError: pass
        print("Invalid category.")

def register(db):
    header("CREATE ACCOUNT"); u=input("Username: ").strip(); p=input("Password: "); cp=input("Confirm password: ")
    if len(u)<3 or len(p)<4 or p!=cp:
        print("Invalid username/password or passwords do not match."); pause(); return
    print("Account created." if db.add_user(u,p) else "Username already exists."); pause()

def login(db):
    header("LOGIN"); u=input("Username: ").strip(); p=input("Password: "); r=db.auth(u,p)
    if not r: print("Incorrect username or password."); pause(); return None
    return r

def add_expense(db,uid):
    header("ADD EXPENSE"); d=input(f"Date [{date.today()}]: ").strip() or str(date.today())
    if not valid_date(d): print("Invalid date."); pause(); return
    cat=category(); a=amount(); desc=input("Description: ").strip(); db.add(uid,d,cat,a,desc); print("Expense added."); pause()

def show(rows):
    if not rows: print("No expenses."); return
    print("-"*95); print(f"{'ID':<5}{'DATE':<13}{'CATEGORY':<18}{'AMOUNT':>15}  DESCRIPTION"); print("-"*95)
    total=0
    for r in rows:
        a=float(r["amount"]); total+=a
        print(f"{r['id']:<5}{r['date']:<13}{r['category']:<18}{money(a):>15}  {(r['description'] or '')[:35]}")
    print("-"*95); print(f"{'TOTAL':<36}{money(total):>15}")

def view(db,uid):
    header("VIEW EXPENSES"); print("1. All\n2. Date range\n3. Category"); c=input("Choose: ").strip()
    if c=="2":
        s=input("Start YYYY-MM-DD: "); e=input("End YYYY-MM-DD: ")
        rows=db.expenses(uid,s,e) if valid_date(s) and valid_date(e) else []
    elif c=="3": rows=db.expenses(uid,cat=category())
    else: rows=db.expenses(uid)
    show(rows); pause()

def update(db,uid):
    header("UPDATE EXPENSE")
    try: eid=int(input("Expense ID: "))
    except ValueError: print("Invalid ID."); pause(); return
    r=db.one(eid,uid)
    if not r: print("Expense not found."); pause(); return
    d=input(f"Date [{r['date']}]: ").strip() or r["date"]
    if not valid_date(d): print("Invalid date."); pause(); return
    print(f"Current category: {r['category']}"); cat=category() if input("Change category? y/n: ").lower()=="y" else r["category"]
    a=float(r["amount"]); s=input(f"Amount [{a}]: ").strip()
    if s:
        try: a=float(s)
        except ValueError: print("Invalid amount."); pause(); return
    desc=input(f"Description [{r['description'] or ''}]: ").strip() or r["description"] or ""
    db.update(eid,uid,d,cat,a,desc); print("Updated."); pause()

def delete(db,uid):
    header("DELETE EXPENSE")
    try: eid=int(input("Expense ID: "))
    except ValueError: print("Invalid ID."); pause(); return
    r=db.one(eid,uid)
    if not r: print("Not found."); pause(); return
    if input(f"Delete {r['category']} {money(float(r['amount']))}? y/n: ").lower()=="y": db.delete(eid,uid); print("Deleted.")
    else: print("Cancelled.")
    pause()

def predict(db,uid,m):
    rows=db.month(uid,m)
    if not rows: return 0
    total=sum(float(r["amount"]) for r in rows)
    if m!=date.today().strftime("%Y-%m"): return total
    y,mo=map(int,m.split("-")); first=date(y,mo,1)
    nxt=date(y+1,1,1) if mo==12 else date(y,mo+1,1)
    return total/max(1,date.today().day)*(nxt-first).days

def set_budget(db,uid):
    header("SET BUDGET"); m=input(f"Month [{date.today():%Y-%m}]: ").strip() or date.today().strftime("%Y-%m")
    if not valid_month(m): print("Invalid month."); pause(); return
    a=amount("Budget: "); db.setbudget(uid,m,a); print("Budget saved."); pause()

def budget_report(db,uid):
    header("BUDGET & PREDICTION"); m=input(f"Month [{date.today():%Y-%m}]: ").strip() or date.today().strftime("%Y-%m")
    if not valid_month(m): print("Invalid month."); pause(); return
    b=db.budget(uid,m); actual=db.total(uid,m); pred=predict(db,uid,m)
    print(f"Actual: {money(actual)}\nBudget: {money(b) if b else 'Not set'}\nPredicted: {money(pred)}")
    if b:
        print(f"Used: {actual/b*100:.1f}%")
        print("STATUS:", "OVER BUDGET" if actual>b else "AT RISK" if pred>b else "ON TRACK")
    pause()

def anomalies(db,uid,m):
    by={}
    for r in db.month(uid,m): by.setdefault(r["category"],[]).append(r)
    out=[]
    for cat,items in by.items():
        vals=[float(r["amount"]) for r in items]
        if len(vals)<3: continue
        mean=sum(vals)/len(vals); sd=math.sqrt(sum((x-mean)**2 for x in vals)/len(vals))
        if not sd: continue
        for r in items:
            z=(float(r["amount"])-mean)/sd
            if abs(z)>=2: out.append((r,z,mean))
    return sorted(out,key=lambda x:abs(x[1]),reverse=True)

def anomaly_report(db,uid):
    header("ANOMALY DETECTION"); m=input(f"Month [{date.today():%Y-%m}]: ").strip() or date.today().strftime("%Y-%m")
    if not valid_month(m): print("Invalid month."); pause(); return
    a=anomalies(db,uid,m)
    print("Method: category-level z-score; flag when |z| >= 2.")
    if not a: print("No strong anomalies detected.")
    else:
        for r,z,mean in a: print(f"{r['date']} | {r['category']:<15} | {money(float(r['amount'])):>14} | z={z:.2f} | avg={money(mean)}")
    pause()

def analytics(db,uid):
    header("ANALYTICS"); m=input(f"Month [{date.today():%Y-%m}]: ").strip() or date.today().strftime("%Y-%m")
    if not valid_month(m): print("Invalid month."); pause(); return
    total=db.total(uid,m); print(f"Total: {money(total)}\n\nCATEGORY BREAKDOWN")
    for r in db.cats(uid,m):
        x=float(r["total"]); print(f"{r['category']:<18}{money(x):>15}  {(x/total*100 if total else 0):5.1f}%")
    print("\nLAST 6 MONTHS")
    today=date.today().replace(day=1)
    for off in range(5,-1,-1):
        y=today.year; mo=today.month-off
        while mo<=0: y-=1; mo+=12
        mm=f"{y:04d}-{mo:02d}"; print(f"{mm}: {money(db.total(uid,mm))}")
    pause()

def export_csv(db,uid):
    header("EXPORT CSV"); rows=db.expenses(uid)
    if not rows: print("No expenses."); pause(); return
    fn=input("Filename [expenses.csv]: ").strip() or "expenses.csv"
    if not fn.endswith(".csv"): fn+=".csv"
    with open(fn,"w",newline="",encoding="utf-8-sig") as f:
        w=csv.writer(f); w.writerow(["ID","Date","Category","Amount","Description"])
        for r in rows: w.writerow([r["id"],r["date"],r["category"],r["amount"],r["description"] or ""])
    print(f"Exported to {fn}"); pause()

def dashboard(db,user):
    uid=user["id"]
    while True:
        m=date.today().strftime("%Y-%m"); actual=db.total(uid,m); b=db.budget(uid,m); pred=predict(db,uid,m)
        header("SMART EXPENSE TRACKER")
        print(f"User: {user['username']} | Month: {m}\n")
        print(f"Spending : {money(actual)}")
        print(f"Budget   : {money(b) if b else 'Not set'}")
        print(f"Forecast : {money(pred)}")
        if b: print("Status   :", "OVER BUDGET" if actual>b else "AT RISK" if pred>b else "ON TRACK")
        aa=anomalies(db,uid,m)
        if aa: print(f"\nWARNING: {len(aa)} unusual expense(s) detected.")
        print("""
1. Add Expense
2. View Expenses
3. Update Expense
4. Delete Expense
5. Set Monthly Budget
6. Budget Prediction
7. Anomaly Detection
8. Spending Analytics
9. Export CSV
0. Logout""")
        c=input("\nChoose: ").strip()
        funcs={"1":add_expense,"2":view,"3":update,"4":delete,"5":set_budget,"6":budget_report,"7":anomaly_report,"8":analytics,"9":export_csv}
        if c=="0": return
        if c in funcs: funcs[c](db,uid)
        else: print("Invalid option."); pause()

def main():
    db=Database()
    try:
        while True:
            header("SMART EXPENSE TRACKER")
            print("1. Login\n2. Create Account\n0. Exit")
            c=input("\nChoose: ").strip()
            if c=="1":
                u=login(db)
                if u: dashboard(db,u)
            elif c=="2": register(db)
            elif c=="0": break
            else: print("Invalid option."); pause()
    finally: db.close()

if __name__=="__main__": main()
