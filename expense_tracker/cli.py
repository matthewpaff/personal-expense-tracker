"""A small command interface; all output amounts use USD."""
import argparse
from datetime import date
import json
from pathlib import Path
import sqlite3
import sys

from . import __version__
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
        return 0
    except ValueError as error:
        print("error: " + str(error), file=sys.stderr)
        return 2
    except (OSError, sqlite3.Error, UnicodeError) as error:
        print("error: " + str(error), file=sys.stderr)
        return 1
