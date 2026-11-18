"""Extract a single USD service invoice from a layout-preserving text export."""
import argparse
import datetime
from decimal import Decimal, ROUND_HALF_UP
import json
from pathlib import Path
import re
import subprocess
import sys


MONEY = r"-?\$?(?:[0-9]+|[0-9]{1,3}(?:,[0-9]{3})+)\.[0-9]{2}"
AMOUNTS = ("subtotal", "tax", "total")
LABELS = {"shop": "shop", "invoice number": "invoice_number", "invoice date": "invoice_date", "currency": "currency"}
HEADER = re.compile(r"description\s+(?:qty|quantity)\s+(?:rate|unit price)\s+(?:amount|extended)", re.I)
ITEM = re.compile(rf"(.+?)\s{{2,}}([0-9]+(?:\.[0-9]+)?)\s+({MONEY})\s+({MONEY})")
SUMMARY = re.compile(r"(subtotal|tax|total)\s*:?\s+(.+)", re.I)


def cents(value):
    return int(Decimal(value.replace("$", "").replace(",", "")) * 100)


def extract(source):
    fields = {}
    totals = {}
    items = []
    flags = []
    table = False
    saw_header = False

    def flag(reason, line=None):
        record = {"reason": reason}
        if line is not None:
            record["line"] = line
        flags.append(record)

    for line_num, raw in enumerate(source.splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        if HEADER.fullmatch(line):
            table = True
            saw_header = True
            continue

        label, separator, value = line.partition(":")
        field = LABELS.get(label.casefold())
        if separator and field:
            if field in fields:
                flag(f"Repeated {field}", line_num)
            else:
                fields[field] = value.strip()
            continue

        summary = SUMMARY.fullmatch(line)
        if summary:
            table = False
            key, value = summary.groups()
            key = key.lower()
            if key in totals:
                flag(f"Repeated {key}", line_num)
            elif re.fullmatch(MONEY, value):
                totals[key] = cents(value)
            else:
                flag(f"Invalid {key} amount: {value}", line_num)
            continue

        if table:
            match = ITEM.fullmatch(line)
            if not match:
                flag(f"Unreadable charge row: {line}", line_num)
                continue
            description, quantity, rate, amount = match.groups()
            rate_cents, amount_cents = cents(rate), cents(amount)
            rounded = (Decimal(quantity) * rate_cents).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
            if rounded != amount_cents:
                flag(f"Quantity times rate gives {rounded} cents, line shows {amount_cents}", line_num)
            items.append({"description": description, "quantity": quantity, "unit_price_cents": rate_cents,
                          "amount_cents": amount_cents, "source_line": line_num})
        elif saw_header and ITEM.fullmatch(line):
            flag("Charge row outside the table", line_num)

    for field in LABELS.values():
        if not fields.get(field):
            flag(f"Missing {field}")
    if fields.get("currency") and fields["currency"] != "USD":
        flag("Expected USD currency")
    if fields.get("invoice_date"):
        try:
            datetime.date.fromisoformat(fields["invoice_date"])
        except ValueError:
            flag("Invalid invoice date")
    if not saw_header:
        flag("Missing charge table header")
    if not items:
        flag("No readable charge lines")
    for key in AMOUNTS:
        if key not in totals:
            flag(f"Missing {key}")
    line_sum = sum(item["amount_cents"] for item in items)
    if "subtotal" in totals and line_sum != totals["subtotal"]:
        flag(f"Charge lines sum to {line_sum} cents, subtotal shows {totals['subtotal']}")
    if all(key in totals for key in AMOUNTS):
        calculated = totals["subtotal"] + totals["tax"]
        if calculated != totals["total"]:
            flag(f"Subtotal plus tax gives {calculated} cents, total shows {totals['total']}")
    return {**fields, "charges": items, "charge_sum_cents": line_sum,
            "totals_cents": totals, "needs_review": bool(flags), "exceptions": flags}


def read_input(path):
    if path.suffix.lower() != ".pdf":
        return path.read_text(encoding="utf-8")
    try:
        result = subprocess.run(["pdftotext", "-layout", "-nopgbrk", str(path.resolve()), "-"],
                                capture_output=True, check=True)
    except FileNotFoundError as exc:
        raise ValueError("PDF input uses Poppler pdftotext. Use the matching .txt file with Python alone.") from exc
    return result.stdout.decode("utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("invoice", type=Path)
    try:
        print(json.dumps(extract(read_input(parser.parse_args().invoice)), indent=2))
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        sys.exit(str(error))
