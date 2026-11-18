"""Write three reconciliation reports for a batch of layout exports or text PDFs."""
import argparse
import csv
from pathlib import Path
import subprocess
import sys
import tempfile
import unicodedata

from extract import extract, read_input


SUMMARY_FIELDS = ("source_file", "shop", "invoice_number", "invoice_date", "currency", "charge_count",
                  "charge_sum_cents", "subtotal_cents", "tax_cents", "total_cents", "status", "issue_count")
CHARGE_FIELDS = ("source_file", "invoice_number", "line", "description", "quantity", "unit_price_cents", "amount_cents")
ISSUE_FIELDS = ("source_file", "invoice_number", "line", "reason")


def spreadsheet_cell(value):
    """Preserve numeric columns and force formula-like source text to literal text."""
    if isinstance(value, str):
        normalized = unicodedata.normalize("NFKC", value)
        start = next((i for i, c in enumerate(normalized) if not (c.isspace() or
                      unicodedata.category(c) in {"Cc", "Cf"})), len(normalized))
        if any(c in "\t\r\n" for c in normalized[:start]) or normalized[start:start + 1] in ("=", "+", "-", "@"):
            return "'" + value
    return value


def write_report(path, columns, records):
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, columns)
        writer.writeheader()
        for row in records:
            writer.writerow({key: spreadsheet_cell(value) for key, value in row.items()})


def reports(files, output_dir):
    if output_dir.exists() or output_dir.is_symlink():
        raise ValueError(f"Choose a new output directory. Already exists: {output_dir}")
    if not files:
        raise ValueError("Provide one or more invoice files")
    if len({p.name for p in files}) != len(files):
        raise ValueError("Source filenames must be unique within the batch")

    summaries, charges, issues = [], [], []
    for path in sorted(files, key=lambda item: item.name):
        try:
            if path.suffix.lower() not in {".pdf", ".txt"}:
                raise ValueError("Expected a .txt or .pdf input")
            invoice = extract(read_input(path))
        except (OSError, ValueError, subprocess.CalledProcessError) as error:
            if isinstance(error, subprocess.CalledProcessError):
                detail = f"PDF text extraction failed (exit {error.returncode})"
            elif isinstance(error, OSError):
                detail = error.strerror or type(error).__name__
            else:
                detail = str(error)
            invoice = {"charges": [], "totals_cents": {}, "needs_review": True,
                       "exceptions": [{"reason": f"Could not read invoice: {detail}"}]}

        origin = {"source_file": path.name, "invoice_number": invoice.get("invoice_number")}
        totals = invoice["totals_cents"]
        summaries.append({
            **origin, "shop": invoice.get("shop"), "invoice_date": invoice.get("invoice_date"),
            "currency": invoice.get("currency"), "charge_count": len(invoice["charges"]),
            "charge_sum_cents": invoice.get("charge_sum_cents"), "subtotal_cents": totals.get("subtotal"),
            "tax_cents": totals.get("tax"), "total_cents": totals.get("total"),
            "status": "review" if invoice["needs_review"] else "balanced", "issue_count": len(invoice["exceptions"]),
        })
        for item in invoice["charges"]:
            charges.append({**origin, "line": item["source_line"], **{key: item[key] for key in CHARGE_FIELDS[3:]}})
        for issue in invoice["exceptions"]:
            issues.append({**origin, "line": issue.get("line"), "reason": issue["reason"]})

    with tempfile.TemporaryDirectory(prefix=".invoice-reports-", dir=output_dir.parent) as stage:
        ready = Path(stage) / "finished"
        ready.mkdir()
        write_report(ready / "invoice_summary.csv", SUMMARY_FIELDS, summaries)
        write_report(ready / "line_items.csv", CHARGE_FIELDS, charges)
        write_report(ready / "issues.csv", ISSUE_FIELDS, issues)
        # Moving all three files together keeps a failed run out of consumers' view.
        ready.rename(output_dir)
    return len(summaries), len(charges), len(issues)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="+", type=Path)
    parser.add_argument("--out", required=True, type=Path, metavar="NEW_DIRECTORY")
    args = parser.parse_args()
    try:
        counts = reports(args.files, args.out)
    except (OSError, ValueError) as error:
        sys.exit(str(error))
    print("Invoice rows: {}; charge rows: {}; review issues: {}".format(*counts))
