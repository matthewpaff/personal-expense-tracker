# Personal Expense Tracker

A small original Python/SQLite CLI for recording expenses and understanding where
money went. Python 3.10+ with SQLite support is sufficient; no third-party packages,
package installation, or virtual environment is required.

## Start

Run from this directory:

```console
python -m expense_tracker --help
python -m expense_tracker add 12.30 --category food --description "Lunch"
python -m expense_tracker list
python -m expense_tracker summary
```

The default database is `~/.expense-tracker/expenses.sqlite3`. Parent directories
are created automatically. Help and version commands do not create a database.
Use `--db PATH` **before** the command to select a separate file.

```console
python -m expense_tracker --db demo.sqlite3 import examples/expenses.csv
python -m expense_tracker --db demo.sqlite3 summary --month 2026-11
```

## Record, find, and correct

```console
python -m expense_tracker add 24.95 --date 2026-11-01 --category books --description "Python book"
python -m expense_tracker list --month 2026-11 --category books
python -m expense_tracker show 1
python -m expense_tracker update 1 --amount 19.95 --description "Discounted book"
python -m expense_tracker delete 1
python -m expense_tracker summary --month 2026-11 --json
python -m expense_tracker list --json
```

Replace `1` with the printed expense ID. Deletion permanently removes that record.
Dates use valid `YYYY-MM-DD` values; an omitted entry date uses the local date.
Results sort by date, then ID, newest first. Categories are normalized to lowercase,
with 1–40 ASCII letters, digits, spaces, or hyphens. Descriptions allow 500 characters.

Amounts are **positive USD expenses**, stored as integer cents. The CLI accepts at
most nine integer digits and two fractional digits. It does not support refunds,
multiple currencies, budgets, or exchange rates. JSON retains integer-cent amounts;
terminal and CSV output format dollars with two decimal places.

## CSV exchange

```console
python -m expense_tracker export expenses.csv
python -m expense_tracker import expenses.csv
python -m expense_tracker import expenses.csv --allow-duplicates
python -m expense_tracker export
```

Files are UTF-8 (BOM input accepted) with exactly these headers, in any order:
`amount,date,category,description`. CSV quoting supports commas, quotes, and newlines.
Export always includes every expense. `export` without a filename writes CSV to
stdout; `import -` reads stdin. Values are data, not spreadsheet formulas; use a
text/CSV reader or import columns as text when opening untrusted data in a spreadsheet.

Import validates every row before writing and uses one transaction. Invalid rows
or storage failures leave the existing records unchanged. Exact matches on amount,
date, normalized category, and trimmed description are skipped, including duplicates
inside the same import. `--allow-duplicates` deliberately inserts those rows too.
New rows receive new IDs. Direct `add` permits repeated expenses.

Exit codes: `0` success, `1` file/database/encoding failure, `2` invalid input.
Errors go to stderr. Keep backups of the SQLite file when the application is closed.

## Development

```console
python -m unittest discover -s tests -v
```

Tests use temporary databases and exercise exact money arithmetic, persistence,
filters, edits, CSV round trips, duplicate handling, transaction rollback, Unicode,
and the actual CLI. No network or external services are needed.

The storage, CSV, and command modules are deliberately separate and small.
See [CONTRIBUTING.md](CONTRIBUTING.md) and the [MIT license](LICENSE).

[History and provenance](HISTORY.md).
