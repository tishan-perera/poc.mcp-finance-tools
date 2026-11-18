# Synthetic books

CSV files in this folder are the entire ledger. The server loads them into an
in-memory SQLite database and then sets `PRAGMA query_only`. Nothing in the
server writes them back.

Regenerate them from the story in [`scripts/generate_synthetic_books.py`](../../../scripts/generate_synthetic_books.py):

```bash
uv run python scripts/generate_synthetic_books.py
uv run python scripts/generate_synthetic_books.py --check
```

Halden & Quay Supply, Inc. is fictional. Every amount is invented. There are
no real account numbers, bank details, tax identifiers, or customer records.

| File | What it holds |
|---|---|
| `meta.csv` | Company name, currency, as-of date, synthetic notice, bank statement total |
| `departments.csv` | Six departments |
| `accounts.csv` | Chart of accounts |
| `periods.csv` | Opening period, January–September 2026 (closed), October 2026 (open, empty) |
| `journal_entries.csv` | Posted journal headers. The tools cannot add to this file. |
| `journal_lines.csv` | Posted lines, in cents |
| `budgets.csv` | Department / account / month budgets, in cents |
| `reconciliations.csv` | Open and cleared reconciliation items |
| `ap_invoices.csv` | Open vendor bills at the September close. The open total ties to account 2000. |
| `ar_invoices.csv` | Open customer invoices at the September close. The open total ties to account 1100. |
