import shutil
from pathlib import Path
import unittest

from extract import extract, read_input


SAMPLES = Path(__file__).parent / "samples"
BASE = (SAMPLES / "balanced.txt").read_text()


class RepairInvoices(unittest.TestCase):
    def test_balanced(self):
        parsed = extract(BASE)
        self.assertFalse(parsed["needs_review"])
        self.assertEqual(parsed["shop"], "Bench Road Fleet Repair")
        self.assertEqual(parsed["invoice_number"], "BR-1042")
        self.assertEqual(parsed["invoice_date"], "2026-10-21")
        self.assertEqual([row["amount_cents"] for row in parsed["charges"]], [16500, 10900, 1400])
        self.assertEqual(parsed["totals_cents"], {"subtotal": 28800, "tax": 1638, "total": 30438})

    def test_bad_total(self):
        result = extract(read_input(SAMPLES / "total-mismatch.txt"))
        self.assertEqual(result["totals_cents"]["total"], 31438)
        self.assertEqual(result["exceptions"], [{"reason": "Subtotal plus tax gives 30438 cents, total shows 31438"}])
        self.assertTrue(result["needs_review"])

    def test_unreadable_item(self):
        result = extract(BASE.replace("165.00", "l65.OO"))
        self.assertEqual(len(result["charges"]), 2)
        self.assertTrue(any("Unreadable charge row" in x["reason"] and x.get("line") for x in result["exceptions"]))

    def test_wrong_unit_price(self):
        result = extract(BASE.replace("110.00", "100.00"))
        self.assertTrue(any("Quantity times rate" in x["reason"] for x in result["exceptions"]))

    def test_duplicate_conflicting_total(self):
        result = extract(BASE + "\nTotal  400.00")
        self.assertTrue(result["needs_review"])
        self.assertEqual(result["totals_cents"]["total"], 30438)

    def test_missing_tax_and_date(self):
        result = extract(BASE.replace("Tax", "Removed").replace("2026-10-21", "2026-02-31"))
        self.assertEqual({x["reason"] for x in result["exceptions"]}, {"Missing tax", "Invalid invoice date"})

    def test_blank_export(self):
        result = extract("")
        self.assertTrue(result["needs_review"])
        self.assertIn("No readable charge lines", {x["reason"] for x in result["exceptions"]})

    @unittest.skipUnless(shutil.which("pdftotext"), "PDF entry point uses Poppler")
    def test_both_pdfs_match_text_examples(self):
        for file in SAMPLES.glob("*.pdf"):
            with self.subTest(invoice=file.name):
                self.assertEqual(extract(read_input(file)), extract(read_input(file.with_suffix(".txt"))))


if __name__ == "__main__":
    unittest.main()
