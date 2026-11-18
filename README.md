# Invoice extraction and reconciliation

**US$149 fixed-price pilot.** For up to 25 machine-readable invoices that share one layout, you receive three CSV files. One summarizes each invoice, one lists its charges, and one shows which figures need checking against the source.

To request a pilot, email the invoice count, the columns you need and two redacted sample invoices. Keep the layout, column headings and example amounts legible so we can agree on the fields and checks before you order. Please share samples privately by email. [Email Kamal](mailto:kamal@mohiwalla.com?subject=Invoice%20reconciliation%20pilot)

The pilot covers one invoice per file with selectable text. Repeat batches, additional layouts, photos and scanned invoices are quoted separately.

## See a $10 discrepancy in the sample

These two fictional repair invoices have the same three charges. Both print a subtotal of $288.00 and tax of $16.38.

| Source invoice | Printed total | Subtotal + tax | Result |
| --- | ---: | ---: | --- |
| [BR-1042](samples/balanced.pdf) | $304.38 | $304.38 | Balanced |
| [BR-1043](samples/total-mismatch.pdf) | $314.38 | $304.38 | Review |

The summary keeps the $314.38 printed on BR-1043. Its review entry records both amounts so someone can resolve the difference with the supplier. You can inspect all six charge rows and the single exception in the example CSVs.

| Delivery file | What to check |
| --- | --- |
| [Invoice summary](example-output/invoice_summary.csv) | One row per input filename, with invoice number, date, currency, charge count, sum of readable charges, printed totals and review status. |
| [Line items](example-output/line_items.csv) | Each readable charge has its description, quantity, unit price, amount, source filename and line number in the extracted text. |
| [Issues](example-output/issues.csv) | Each exception identifies the source file and reason. When the issue belongs to a specific line, the report includes its line number. |

## How to accept a pilot delivery

1. Match the batch filenames to the summary. Every invoice has one row, including files that need review.
2. Check the agreed fields on the two scoping samples against the original invoices. Printed amounts must match the source. Unreadable fields must have an entry in the issues file.
3. Follow any arithmetic discrepancy back to its invoice. The checks compare quantity times rate to the line amount, readable charges to the subtotal, and subtotal plus tax to the printed total. A difference must leave the reported amounts intact and flag the invoice for review.

A balanced invoice means its readable figures passed those checks. Arithmetic alone cannot reveal a charge that the supplier omitted from both the table and the subtotal.

## Reproduce the example

The sample layout uses USD, an ISO invoice date and a table with description, quantity, rate and amount. The CSVs store money in integer cents, so `30438` means $304.38. Formula-like source text receives a leading apostrophe in CSV output.

Run the following from the repository root with Python 3 and Poppler's `pdftotext` installed. On Ubuntu, the Poppler package is `poppler-utils`. Use a new output directory for each run.

```sh
python3 batch.py --out my-results samples/*.pdf
diff -ru example-output my-results
python3 -m unittest -v
```

The batch prints `Invoice rows: 2; charge rows: 6; review issues: 1`. An empty diff means the generated files match the published examples. To try the matching text exports with Python alone, run `python3 batch.py --out text-results samples/*.txt`. To inspect the raw fields from a single invoice, run `python3 extract.py samples/balanced.txt`.
