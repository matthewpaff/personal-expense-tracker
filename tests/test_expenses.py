import io
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from expense_tracker.csvio import read_csv, write_csv
from expense_tracker.store import ExpenseStore, format_money, money


class ExpenseTests(unittest.TestCase):
    def setUp(self):
        self.store = ExpenseStore(":memory:")
        self.addCleanup(self.store.db.close)

    def test_money_is_exact_and_rejects_ambiguous_inputs(self):
        self.assertEqual(money("0.10") + money("0.20"), 30)
        self.assertEqual(format_money(1234), "12.34")
        for value in ("0", "-1", "1.234", "NaN", "1e3", "$12", "1,000", "1000000000"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                money(value)

    def test_persistence_and_filtered_summary(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "nested" / "expenses.sqlite3"
            with ExpenseStore(path) as store:
                store.add("0.10", "2026-11-01", " Food ", "Lunch")
                store.add("0.20", "2026-11-02", "food", "Snack")
                store.add("4", "2026-10-31", "travel", "Bus")
            with ExpenseStore(path) as store:
                self.assertEqual(store.summary("2026-11"), {
                    "currency": "USD", "count": 2, "total_cents": 30, "by_category_cents": {"food": 30}})
                self.assertEqual(store.list_expenses(category="TRAVEL")[0]["description"], "Bus")
                self.assertEqual(store.list_expenses()[0]["spent_on"], "2026-11-02")

    def test_validation_and_atomic_edit(self):
        row = self.store.add("10", "2024-02-29", "books", "Original")
        with self.assertRaises(ValueError):
            self.store.update(row["id"], description="Changed", spent_on="2023-02-29")
        self.assertEqual(self.store.get(row["id"]), row)
        for month in ("2026-13", "26-11", "2026-1"):
            with self.assertRaises(ValueError):
                self.store.list_expenses(month=month)
        with self.assertRaises(ValueError):
            self.store.add("5", "2026-11-01", "bad;sql")

    def test_edit_delete_and_missing_ids(self):
        row = self.store.add("2.50", "2026-11-01", "food")
        updated = self.store.update(row["id"], amount="3.25", category="travel", description="Bus")
        self.assertEqual((updated["amount_cents"], updated["description"]), (325, "Bus"))
        self.store.delete(row["id"])
        with self.assertRaises(ValueError):
            self.store.get(row["id"])

    def test_csv_round_trip_and_duplicate_policy(self):
        self.store.add("2.50", "2026-11-01", "food", 'Café, "tea"\nand cake')
        output = io.StringIO(newline="")
        self.assertEqual(write_csv(self.store, output), 1)
        rows = read_csv(io.StringIO(output.getvalue(), newline=""))
        self.assertEqual(self.store.import_rows(rows), {"inserted": 0, "skipped": 1})
        with ExpenseStore(":memory:") as other:
            self.assertEqual(other.import_rows(rows + rows), {"inserted": 1, "skipped": 1})
            self.assertEqual(other.import_rows(rows, allow_duplicates=True), {"inserted": 1, "skipped": 0})
            self.assertEqual(other.get(1)["description"], 'Café, "tea"\nand cake')

    def test_bad_csv_rows_and_headers(self):
        for data in ("amount,date,category\n", "amount,date,category,category\n",
                     "amount,date,category,description\n1,2026-11-01,food\n",
                     'amount,date,category,description\n1,2026-11-01,food,"unfinished'):
            with self.subTest(data=data), self.assertRaises(ValueError):
                read_csv(io.StringIO(data))

    def test_invalid_batch_makes_no_changes(self):
        rows = [{"amount": "1", "date": "2026-11-01", "category": "food", "description": "Valid"},
                {"amount": "2", "date": "2026-02-30", "category": "food", "description": "Invalid"}]
        with self.assertRaises(ValueError):
            self.store.import_rows(rows)
        self.assertEqual(self.store.list_expenses(), [])

    def test_database_failure_rolls_back_entire_import(self):
        self.store.db.execute("""CREATE TRIGGER fail_import BEFORE INSERT ON expenses
            WHEN NEW.description = 'fail' BEGIN SELECT RAISE(ABORT, 'test failure'); END""")
        rows = [{"amount": "1", "date": "2026-11-01", "category": "food", "description": description}
                for description in ("ok", "fail")]
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.import_rows(rows)
        self.assertEqual(self.store.list_expenses(), [])


class CommandTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.db = str(Path(self.folder.name) / "expenses.sqlite3")

    def run_cli(self, *args, input=None):
        return subprocess.run([sys.executable, "-m", "expense_tracker", "--db", self.db, *args],
                              input=input, capture_output=True, text=True, encoding="utf-8")

    def test_full_cli_workflow(self):
        added = self.run_cli("add", "12.30", "--date", "2026-11-01", "--category", "food",
                             "--description", "Café lunch")
        self.assertEqual(added.returncode, 0, added.stderr)
        self.assertIn("Café lunch", added.stdout)
        result = self.run_cli("list", "--json")
        self.assertEqual(json.loads(result.stdout)[0]["amount_cents"], 1230)
        self.assertEqual(self.run_cli("update", "1", "--amount", "15").returncode, 0)
        self.assertEqual(json.loads(self.run_cli("summary", "--json").stdout)["total_cents"], 1500)
        exported = self.run_cli("export")
        imported = self.run_cli("import", "-", input=exported.stdout)
        self.assertEqual(imported.returncode, 0, imported.stderr)
        self.assertIn("skipped 1", imported.stdout)
        self.assertEqual(self.run_cli("delete", "1").returncode, 0)

    def test_help_does_not_create_database(self):
        self.assertEqual(self.run_cli("--help").returncode, 0)
        self.assertFalse(Path(self.db).exists())

    def test_input_and_storage_errors_have_exit_codes(self):
        result = self.run_cli("add", "1.234", "--category", "food")
        self.assertEqual(result.returncode, 2)
        self.assertNotIn("Traceback", result.stderr)
        result = self.run_cli("import", str(Path(self.folder.name) / "missing.csv"))
        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.run_cli("show", "0").returncode, 2)


if __name__ == "__main__":
    unittest.main()
