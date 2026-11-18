import csv
from pathlib import Path
import tempfile
import unittest

from batch import reports, spreadsheet_cell
from test_extract import BASE, SAMPLES


def rows(path):
    with path.open(encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


class BatchInvoices(unittest.TestCase):
    def setUp(self):
        workspace = tempfile.TemporaryDirectory()
        self.addCleanup(workspace.cleanup)
        self.work = Path(workspace.name)
        self.out = self.work / "out"

    def test_mixed_documents_and_unreadable_file(self):
        missing = self.work / "missing.txt"
        counts = reports([SAMPLES / "total-mismatch.txt", missing, SAMPLES / "balanced.txt"], self.out)
        self.assertEqual(counts, (3, 6, 2))
        self.assertEqual({f.name for f in self.out.iterdir()}, {"invoice_summary.csv", "line_items.csv", "issues.csv"})
        summary = rows(self.out / "invoice_summary.csv")
        self.assertEqual([(r["source_file"], r["status"]) for r in summary],
                         [("balanced.txt", "balanced"), ("missing.txt", "review"), ("total-mismatch.txt", "review")])
        self.assertEqual(summary[1]["total_cents"], "")
        charges = rows(self.out / "line_items.csv")
        self.assertEqual(charges[0]["unit_price_cents"], "11000")
        issues = rows(self.out / "issues.csv")
        self.assertEqual({r["source_file"] for r in issues}, {"missing.txt", "total-mismatch.txt"})

    def test_missing_charge_is_flagged(self):
        file = self.work / "lost.txt"
        lost = "\n".join(line for line in BASE.splitlines() if "Axle seal kit" not in line)
        file.write_text(lost)
        reports([file], self.out)
        summary = rows(self.out / "invoice_summary.csv")[0]
        self.assertEqual((summary["charge_sum_cents"], summary["subtotal_cents"], summary["status"]),
                         ("17900", "28800", "review"))
        self.assertIn("Charge lines sum", rows(self.out / "issues.csv")[0]["reason"])

    def test_unknown_and_zero_net_missing_rows(self):
        file = self.work / "odd.txt"
        # A damaged zero-cost charge leaves the subtotal unchanged.
        file.write_text(BASE.replace("Wheel bearing inspection", "Unpriced fee   1  0.00  O.OO\n Wheel bearing inspection"))
        reports([file], self.out)
        self.assertEqual(rows(self.out / "invoice_summary.csv")[0]["status"], "review")
        self.assertIn("Unreadable charge row", rows(self.out / "issues.csv")[0]["reason"])

    def test_existing_dir_is_preserved(self):
        self.out.mkdir()
        sentinel = self.out / "invoice_summary.csv"
        sentinel.write_text("previous")
        with self.assertRaisesRegex(ValueError, "already exists|Already exists"):
            reports([SAMPLES / "balanced.txt"], self.out)
        self.assertEqual(sentinel.read_text(), "previous")

    def test_duplicate_basename_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unique"):
            reports([SAMPLES / "balanced.txt", self.work / "balanced.txt"], self.out)
        self.assertFalse(self.out.exists())

    def test_untrusted_fields_are_literal_text(self):
        f = self.work / "=filename.txt"
        f.write_text(BASE.replace("BR-1042", "=3+1").replace("Wheel bearing inspection", "@SUM(1,2)"))
        reports([f], self.out)
        summary = rows(self.out / "invoice_summary.csv")[0]
        self.assertEqual(summary["source_file"], "'=filename.txt")
        self.assertEqual(summary["invoice_number"], "'=3+1")
        self.assertEqual(rows(self.out / "line_items.csv")[0]["description"], "'@SUM(1,2)")
        for text in ("\ttext", "\rtext", "\ntext", "  +SUM(A1)", "＝1+2", " -2+8", "\ufeff=90"):
            self.assertTrue(spreadsheet_cell(text).startswith("'"))
        self.assertEqual(spreadsheet_cell(-10), -10)


if __name__ == "__main__":
    unittest.main()
