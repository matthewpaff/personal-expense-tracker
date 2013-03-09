"""Strict UTF-8 CSV exchange with an all-or-nothing import."""
import csv

from .store import format_money

FIELDS = ("amount", "date", "category", "description")


def read_csv(handle):
    reader = csv.DictReader(handle, strict=True)
    try:
        if reader.fieldnames is None or len(reader.fieldnames) != len(FIELDS) or set(reader.fieldnames) != set(FIELDS):
            raise ValueError("CSV must have exactly these headers: " + ",".join(FIELDS))
        rows = []
        for row in reader:
            if None in row or any(value is None for value in row.values()):
                raise ValueError("CSV row {} has the wrong number of columns".format(reader.line_num))
            rows.append(row)
        return rows
    except csv.Error as error:
        raise ValueError("Invalid CSV: " + str(error)) from error


def write_csv(store, handle):
    writer = csv.DictWriter(handle, fieldnames=FIELDS)
    writer.writeheader()
    rows = store.list_expenses()
    for row in rows:
        writer.writerow({"amount": format_money(row["amount_cents"]), "date": row["spent_on"],
                         "category": row["category"], "description": row["description"]})
    return len(rows)
