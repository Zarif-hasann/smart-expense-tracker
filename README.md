# Smart Expense Tracker with Budget Prediction and Spending Anomaly Detection

A desktop-based personal finance management application developed in Python.

The system helps users record and manage expenses, set monthly budgets, analyze spending patterns, predict expected month-end spending, and identify unusually large transactions.

---

## Project Overview

Managing personal expenses manually can make it difficult to understand where money is being spent and whether a monthly budget is likely to be exceeded.

The Smart Expense Tracker addresses this problem by combining:

- Expense management
- Monthly budget tracking
- Spending analytics
- Budget prediction
- Spending anomaly detection
- Category-based analysis
- CSV export
- User authentication

The application provides a graphical desktop interface designed to make financial information easier to understand.

---

## Key Features

### 1. User Authentication

Users can:

- Create a new account
- Log in securely
- Log out
- Maintain separate expense records

Passwords are stored as SHA-256 hashes rather than plain-text passwords.

---

### 2. Expense Management

Users can:

- Add expenses
- Edit existing expenses
- Delete expenses
- Select expense categories
- Add descriptions
- Filter expenses by date
- Filter expenses by category
- View filtered totals

Supported categories include:

- Food
- Transport
- Bills
- Shopping
- Entertainment
- Health
- Education
- Travel
- Rent
- Other

---

### 3. Monthly Budget Management

Users can define a monthly spending budget.

The system displays:

- Current spending
- Monthly budget
- Predicted month-end spending
- Remaining budget
- Budget utilization percentage

The dashboard can classify the current situation as:

- ON TRACK
- AT RISK
- OVER BUDGET

---

### 4. Budget Prediction

The system estimates expected spending at the end of the current month.

For the current month, the prediction is calculated using the average daily spending so far:

Predicted Spending =

(Current Spending / Elapsed Days) × Days in Month

For previous months, the actual recorded total is displayed instead of making a prediction.

This gives the user an early indication of whether their current spending pattern may exceed the monthly budget.

---

### 5. Spending Anomaly Detection

The application identifies unusually large expenses using a statistical z-score method.

The system:

1. Groups expenses by category.
2. Calculates the average expense for each category.
3. Calculates the standard deviation.
4. Calculates the z-score of each transaction.
5. Flags transactions where:

   |z| >= 2

Anomaly detection is applied when a category contains at least three transactions during the selected month.

This allows the system to highlight expenses that are significantly different from the user's normal spending pattern within that category.

---

### 6. Spending Analytics

The Analytics section provides:

- Spending by category
- Six-month spending comparison
- Unusual transaction detection
- Category-level spending information

The application uses built-in Tkinter Canvas components to display visual charts.

---

### 7. CSV Export

Users can export filtered expense records to a CSV file.

The exported information includes:

- Expense ID
- Date
- Category
- Amount
- Description

---

## Dashboard

The dashboard provides a quick overview of the user's current financial situation.

It displays:

- This month's spending
- Monthly budget
- Predicted month-end spending
- Remaining budget
- Budget status
- Smart spending insights

The system also identifies the user's largest spending category and reports unusual expenses when detected.

---

## Technology Stack

| Technology | Purpose |
|---|---|
| Python | Main programming language |
| Tkinter | Graphical user interface |
| SQLite | Local database |
| CSV | Expense data export |
| hashlib | Password hashing |
| Git | Version control |
| GitHub | Source code hosting |

The current implementation uses Python's standard library, so no third-party Python package is required for the core application.

---

## Database Design

The application uses SQLite as its local database.

The database contains three main tables:

### Users

Stores user account information.

Main fields:

- ID
- Username
- Password hash
- Account creation time

### Budgets

Stores monthly budget information.

Main fields:

- ID
- User ID
- Month
- Budget amount

### Expenses

Stores individual expense records.

Main fields:

- ID
- User ID
- Date
- Category
- Amount
- Description
- Creation time

Foreign-key relationships are used between users and their budgets/expenses.

---

## System Architecture

The application follows a simple desktop application architecture:

```text
+-----------------------------+
|       Tkinter GUI           |
+-------------+---------------+
              |
              v
+-----------------------------+
|      Application Logic      |
|                             |
| - Expense Management        |
| - Budget Calculation        |
| - Prediction                |
| - Anomaly Detection         |
| - Analytics                 |
+-------------+---------------+
              |
              v
+-----------------------------+
|        SQLite Database      |
+-----------------------------+