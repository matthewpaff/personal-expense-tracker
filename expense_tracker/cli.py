"""A small command interface; all output amounts use USD."""
import argparse
from contextlib import nullcontext
from datetime import date
import json
from pathlib import Path
import sqlite3
import sys

from . import __version__
from .csvio import read_csv, write_csv
from .store import ExpenseStore, format_money


def positive_id(text):
    try:
        number = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError("ID must be a positive integer")
    if number < 1:
        raise argparse.ArgumentTypeError("ID must be a positive integer")
    return number


def parser():
    p = argparse.ArgumentParser(description="Track personal expenses in USD, without dependencies.")
    p.add_argument("--version", action="version", version=__version__)
    p.add_argument("--db", default=str(Path.home() / ".expense-tracker" / "expenses.sqlite3"))
    commands = p.add_subparsers(dest="command", required=True)
    add = commands.add_parser("add", help="Record an expense")
    add.add_argument("amount")
    add.add_argument("--date", default=date.today().isoformat())
    add.add_argument("--category", required=True)
    add.add_argument("--description", default="")
    for name in ("list", "summary"):
        command = commands.add_parser(name)
        command.add_argument("--month", help="Filter by YYYY-MM")
        command.add_argument("--category")
        command.add_argument("--json", action="store_true")
    for name in ("show", "delete", "update"):
        command = commands.add_parser(name)
        command.add_argument("id", type=positive_id)
        if name == "update":
            command.add_argument("--amount")
            command.add_argument("--date")
            command.add_argument("--category")
            command.add_argument("--description")
    export = commands.add_parser("export", help="Export all expenses as UTF-8 CSV")
    export.add_argument("path", nargs="?", default="-", help="File path or - for stdout")
    importing = commands.add_parser("import", help="Import a CSV transaction, skipping exact duplicates")
    importing.add_argument("path", help="File path or - for stdin")
    importing.add_argument("--allow-duplicates", action="store_true")
    return p


def display(rows):
    if not rows:
        print("No expenses found.")
    for row in rows:
        # Keep untrusted descriptions on one terminal line.
        description = row["description"].replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")
        print("#{id}  {spent_on}  USD {amount}  {category}  {description}".format(
            **{**row, "amount": format_money(row["amount_cents"]), "description": description}))


def main(argv=None):
    args = parser().parse_args(argv)
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", newline="")
    try:
        with ExpenseStore(args.db) as store:
            if args.command == "add":
                display([store.add(args.amount, args.date, args.category, args.description)])
            elif args.command == "list":
                rows = store.list_expenses(args.month, args.category)
                if args.json:
                    print(json.dumps(rows, ensure_ascii=True, indent=2))
                else:
                    display(rows)
            elif args.command == "show":
                display([store.get(args.id)])
            elif args.command == "update":
                display([store.update(args.id, args.amount, args.date, args.category, args.description)])
            elif args.command == "delete":
                store.delete(args.id)
                print("Deleted expense #{}.".format(args.id))
            elif args.command == "summary":
                result = store.summary(args.month, args.category)
                if args.json:
                    print(json.dumps(result, indent=2))
                else:
                    print("{} expenses | Total: USD {}".format(result["count"], format_money(result["total_cents"])))
                    for category, cents in result["by_category_cents"].items():
                        print("{}: USD {}".format(category, format_money(cents)))
            elif args.command == "export":
                target = nullcontext(sys.stdout) if args.path == "-" else open(
                    args.path, "w", encoding="utf-8", newline="")
                with target as handle:
                    count = write_csv(store, handle)
                if args.path != "-":
                    print("Exported {} expenses.".format(count))
            elif args.command == "import":
                source = nullcontext(sys.stdin) if args.path == "-" else open(
                    args.path, "r", encoding="utf-8-sig", newline="")
                with source as handle:
                    rows = read_csv(handle)
                result = store.import_rows(rows, args.allow_duplicates)
                print("Imported {inserted}; skipped {skipped} duplicate(s).".format(**result))
        return 0
    except ValueError as error:
        print("error: " + str(error), file=sys.stderr)
        return 2
    except (OSError, sqlite3.Error, UnicodeError) as error:
        print("error: " + str(error), file=sys.stderr)
        return 1
