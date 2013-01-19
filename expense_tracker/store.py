"""Validated SQLite storage. Monetary amounts are integer cents, never floats."""
from datetime import date
from decimal import Decimal
from pathlib import Path
import re
import sqlite3


def money(value):
    value = str(value).strip()
    if not re.fullmatch(r"[0-9]{1,9}(?:\.[0-9]{1,2})?", value):
        raise ValueError("Amount must be positive USD with at most two decimal places")
    cents = int(Decimal(value) * 100)
    if cents <= 0:
        raise ValueError("Amount must be greater than zero")
    return cents


def format_money(cents):
    return "{}.{:02d}".format(cents // 100, cents % 100)


def valid_date(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        raise ValueError("Date must be YYYY-MM-DD")
    date.fromisoformat(value)
    return value


def category_name(value):
    value = value.strip().lower()
    if not re.fullmatch(r"[a-z0-9][a-z0-9 -]{0,39}", value):
        raise ValueError("Category must be 1-40 ASCII letters, digits, spaces, or hyphens")
    return value


def validated(amount, spent_on, category, description=""):
    description = description.strip()
    if len(description) > 500:
        raise ValueError("Description must be at most 500 characters")
    return money(amount), valid_date(spent_on), category_name(category), description


class ExpenseStore:
    def __init__(self, path):
        path = str(path)
        if path != ":memory:":
            path = str(Path(path).expanduser())
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        with self.db:
            self.db.execute("""CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                amount_cents INTEGER NOT NULL CHECK(amount_cents > 0),
                spent_on TEXT NOT NULL, category TEXT NOT NULL, description TEXT NOT NULL
            )""")
            self.db.execute("CREATE INDEX IF NOT EXISTS expenses_date ON expenses(spent_on)")
            self.db.execute("CREATE INDEX IF NOT EXISTS expenses_category ON expenses(category)")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.db.close()

    def get(self, expense_id):
        row = self.db.execute("SELECT * FROM expenses WHERE id = ?", (expense_id,)).fetchone()
        if row is None:
            raise ValueError("Expense #{} does not exist".format(expense_id))
        return dict(row)

    def add(self, amount, spent_on, category, description=""):
        values = validated(amount, spent_on, category, description)
        with self.db:
            cursor = self.db.execute(
                "INSERT INTO expenses(amount_cents, spent_on, category, description) VALUES(?,?,?,?)", values)
        return self.get(cursor.lastrowid)

    def list_expenses(self, month=None, category=None):
        clauses, params = [], []
        if month is not None:
            if not re.fullmatch(r"[0-9]{4}-[0-9]{2}", month):
                raise ValueError("Month must be YYYY-MM")
            valid_date(month + "-01")
            clauses.append("substr(spent_on, 1, 7) = ?")
            params.append(month)
        if category is not None:
            clauses.append("category = ?")
            params.append(category_name(category))
        sql = "SELECT * FROM expenses"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        return [dict(row) for row in self.db.execute(sql + " ORDER BY spent_on DESC, id DESC", params)]
