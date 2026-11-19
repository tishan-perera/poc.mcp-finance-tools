# MCP transcript (synthetic books)

Halden & Quay Supply, Inc. is fictional. The client below is a real MCP session over stdio. No API key is set. The draft calls do not post.

Tools the server advertises:

- `lookup_gl_account` (read-only: True) - Look up GL accounts in the synthetic ledger and return master data plus balances. Read-only. Matches an exact account code, or otherwise a case-insensitive part of the code or name. Balances are pre-close: income-statement accounts are activity, not closed to retained earnings.
- `get_trial_balance` (read-only: True) - Return the pre-close trial balance for one period of the synthetic ledger. Read-only. Debit and credit columns are ending balances. The book is in balance when those two totals match. Net income in the response is a memo, not a posted closing entry.
- `search_journal_entries` (read-only: True) - Search posted journal entries in the synthetic ledger. Read-only. With no filters, returns the latest entries up to limit. Every returned entry includes its lines and whether the entry balances.
- `list_open_reconciliations` (read-only: True) - List reconciliation items on the synthetic ledger. Read-only. Cleared items are omitted unless include_cleared is true. A cash request also returns the bank reconciliation and whether adjusted book equals adjusted bank. Off-book items are support for a person. They are not posted by this tool.
- `get_budget_variance` (read-only: True) - Compare budget to actual for income-statement accounts in the synthetic ledger. Read-only. variance is actual minus budget in the account's natural sign. favorable_amount is positive when the variance helps earnings (more revenue, or less expense). A row is material when it clears either threshold. Cost of goods is tagged to Sales in this dataset. It is not allocated further.
- `get_ap_ar_aging` (read-only: True) - Age open payables or receivables on the synthetic September close. Read-only. On the snapshot date, with no name filter, total_open ties to the control account (2000 for AP, 1100 for AR). The population is that snapshot. A different as_of only moves items between buckets.
- `draft_adjusting_entry` (read-only: True) - Draft an adjusting entry for a person to review. This does not post. Read-only. The response is a proposal with posted set to false. It is not written to the ledger, not given a journal-entry id, and not reversed in the books. A closed period is called out and left closed. The caller, or another system a person operates, would have to post it.

## `lookup_gl_account`

Request:

```json
{
  "query": "cash"
}
```

Response:

```json
{
  "ok": true,
  "synthetic": true,
  "company": "Halden & Quay Supply, Inc.",
  "currency": "USD",
  "data_notice": "All figures are invented. Halden & Quay Supply, Inc. is a fictional company. This is not a real ledger and not financial advice.",
  "query": "cash",
  "period": "2026-09",
  "through_date": "2026-09-30",
  "count": 1,
  "matches": [
    {
      "account_code": "1000",
      "account_name": "Cash",
      "account_type": "asset",
      "statement": "balance_sheet",
      "normal_balance": "debit",
      "active": true,
      "period_debits": "622360.00",
      "period_credits": "580340.00",
      "ending_debits": "6672360.00",
      "ending_credits": "5083640.00",
      "ending_balance": "1588720.00",
      "debit": "1588720.00",
      "credit": "0.00"
    }
  ]
}
```

## `get_trial_balance`

Request:

```json
{
  "period": "2026-09",
  "statement": "balance_sheet"
}
```

Response:

```json
{
  "ok": true,
  "synthetic": true,
  "company": "Halden & Quay Supply, Inc.",
  "currency": "USD",
  "data_notice": "All figures are invented. Halden & Quay Supply, Inc. is a fictional company. This is not a real ledger and not financial advice.",
  "period": "2026-09",
  "period_status": "closed",
  "through_date": "2026-09-30",
  "basis": "Pre-close. Income-statement accounts are not closed to retained earnings.",
  "row_filter": "balance_sheet",
  "rows": [
    {
      "account_code": "1000",
      "account_name": "Cash",
      "account_type": "asset",
      "statement": "balance_sheet",
      "normal_balance": "debit",
      "active": true,
      "period_debits": "622360.00",
      "period_credits": "580340.00",
      "ending_debits": "6672360.00",
      "ending_credits": "5083640.00",
      "ending_balance": "1588720.00",
      "debit": "1588720.00",
      "credit": "0.00"
    },
    {
      "account_code": "1100",
      "account_name": "Accounts Receivable",
      "account_type": "asset",
      "statement": "balance_sheet",
      "normal_balance": "debit",
      "active": true,
      "period_debits": "598000.00",
      "period_credits": "622360.00",
      "ending_debits": "5838000.00",
      "ending_credits": "5422360.00",
      "ending_balance": "415640.00",
      "debit": "415640.00",
      "credit": "0.00"
    },
    {
      "account_code": "1200",
      "account_name": "Inventory",
      "account_type": "asset",
      "statement": "balance_sheet",
      "normal_balance": "debit",
      "active": true,
      "period_debits": "309600.00",
      "period_credits": "301600.00",
      "ending_debits": "3583600.00",
      "ending_credits": "2621600.00",
      "ending_balance": "962000.00",
      "debit": "962000.00",
      "credit": "0.00"
    },
    {
      "account_code": "1300",
      "account_name": "Prepaid Expenses",
      "account_type": "asset",
      "statement": "balance_sheet",
      "normal_balance": "debit",
      "active": true,
      "period_debits": "0.00",
      "period_credits": "4000.00",
      "ending_debits": "45000.00",
      "ending_credits": "36000.00",
      "ending_balance": "9000.00",
      "debit": "9000.00",
      "credit": "0.00"
    },
    {
      "account_code": "1500",
      "account_name": "Property and Equipment",
      "account_type": "asset",
      "statement": "balance_sheet",
      "normal_balance": "debit",
      "active": true,
      "period_debits": "0.00",
      "period_credits": "0.00",
      "ending_debits": "1100000.00",
      "ending_credits": "0.00",
      "ending_balance": "1100000.00",
      "debit": "1100000.00",
      "credit": "0.00"
    },
    {
      "account_code": "1510",
      "account_name": "Accumulated Depreciation",
      "account_type": "contra_asset",
      "statement": "balance_sheet",
      "normal_balance": "credit",
      "active": true,
      "period_debits": "0.00",
      "period_credits": "14000.00",
      "ending_debits": "0.00",
      "ending_credits": "446000.00",
      "ending_balance": "446000.00",
      "debit": "0.00",
      "credit": "446000.00"
    },
    {
      "account_code": "2000",
      "account_name": "Accounts Payable",
      "account_type": "liability",
      "statement": "balance_sheet",
      "normal_balance": "credit",
      "active": true,
      "period_debits": "360740.00",
      "period_credits": "330600.00",
      "ending_debits": "3076740.00",
      "ending_credits": "3240600.00",
      "ending_balance": "163860.00",
      "debit": "0.00",
      "credit": "163860.00"
    },
    {
      "account_code": "2100",
      "account_name": "Accrued Expenses",
      "account_type": "liability",
      "statement": "balance_sheet",
      "normal_balance": "credit",
      "active": true,
      "period_debits": "0.00",
      "period_credits": "0.00",
      "ending_debits": "0.00",
      "ending_credits": "75000.00",
      "ending_balance": "75000.00",
      "debit": "0.00",
      "credit": "75000.00"
    },
    {
      "account_code": "2200",
      "account_name": "Deferred Revenue",
      "account_type": "liability",
      "statement": "balance_sheet",
      "normal_balance": "credit",
      "active": true,
      "period_debits": "0.00",
      "period_credits": "0.00",
      "ending_debits": "0.00",
      "ending_credits": "90000.00",
      "ending_balance": "90000.00",
      "debit": "0.00",
      "credit": "90000.00"
    },
    {
      "account_code": "2300",
      "account_name": "Accrued Payroll",
      "account_type": "liability",
      "statement": "balance_sheet",
      "normal_balance": "credit",
      "active": true,
      "period_debits": "0.00",
      "period_credits": "0.00",
      "ending_debits": "0.00",
      "ending_credits": "60000.00",
      "ending_balance": "60000.00",
      "debit": "0.00",
      "credit": "60000.00"
    },
    {
      "account_code": "3000",
      "account_name": "Common Stock",
      "account_type": "equity",
      "statement": "balance_sheet",
      "normal_balance": "credit",
      "active": true,
      "period_debits": "0.00",
      "period_credits": "0.00",
      "ending_debits": "0.00",
      "ending_credits": "500000.00",
      "ending_balance": "500000.00",
      "debit": "0.00",
      "credit": "500000.00"
    },
    {
      "account_code": "3100",
      "account_name": "Retained Earnings",
      "account_type": "equity",
      "statement": "balance_sheet",
      "normal_balance": "credit",
      "active": true,
      "period_debits": "0.00",
      "period_credits": "0.00",
      "ending_debits": "0.00",
      "ending_credits": "2470000.00",
      "ending_balance": "2470000.00",
      "debit": "0.00",
      "credit": "2470000.00"
    }
  ],
  "totals": {
    "debit": "9002860.00",
    "credit": "9002860.00",
    "balanced": true,
    "note": "Totals are the whole pre-close trial balance, including rows hidden by a statement filter."
  },
  "net_income": {
    "period": "37800.00",
    "ytd": "270500.00",
    "note": "Memo only. Not a posted closing entry."
  }
}
```

## `search_journal_entries`

Request:

```json
{
  "text": "heat wave"
}
```

Response:

```json
{
  "ok": true,
  "synthetic": true,
  "company": "Halden & Quay Supply, Inc.",
  "currency": "USD",
  "data_notice": "All figures are invented. Halden & Quay Supply, Inc. is a fictional company. This is not a real ledger and not financial advice.",
  "match_count": 1,
  "returned": 1,
  "limit": 20,
  "entries": [
    {
      "entry_id": "JE-2026-08-12",
      "period": "2026-08",
      "entry_date": "2026-08-31",
      "source": "utilities",
      "description": "Utility true-up for the August heat wave",
      "balanced": true,
      "total_debits": "9500.00",
      "total_credits": "9500.00",
      "lines": [
        {
          "line_no": 1,
          "account_code": "6800",
          "account_name": "Utilities",
          "department": "OPS",
          "debit": "9500.00",
          "credit": "0.00",
          "memo": "Utility true-up for the August heat wave"
        },
        {
          "line_no": 2,
          "account_code": "1000",
          "account_name": "Cash",
          "department": null,
          "debit": "0.00",
          "credit": "9500.00",
          "memo": "Utilities paid"
        }
      ]
    }
  ]
}
```

## `list_open_reconciliations`

Request:

```json
{
  "account_code": "1000"
}
```

Response:

```json
{
  "ok": true,
  "synthetic": true,
  "company": "Halden & Quay Supply, Inc.",
  "currency": "USD",
  "data_notice": "All figures are invented. Halden & Quay Supply, Inc. is a fictional company. This is not a real ledger and not financial advice.",
  "count": 3,
  "include_cleared": false,
  "items": [
    {
      "recon_id": "REC-CASH-01",
      "account_code": "1000",
      "period": "2026-09",
      "item_type": "deposit_in_transit",
      "description": "Customer deposit recorded on 2026-09-29, not on the bank statement yet.",
      "amount": "42600.00",
      "status": "open",
      "owner_role": "Cash accountant"
    },
    {
      "recon_id": "REC-CASH-02",
      "account_code": "1000",
      "period": "2026-09",
      "item_type": "outstanding_check",
      "description": "Check 1042 to Brightbox Packaging, mailed 2026-09-18, still outstanding.",
      "amount": "18450.00",
      "status": "open",
      "owner_role": "Cash accountant"
    },
    {
      "recon_id": "REC-CASH-03",
      "account_code": "1000",
      "period": "2026-09",
      "item_type": "unrecorded_bank_fee",
      "description": "September bank service charge on the statement, not yet on the books.",
      "amount": "85.00",
      "status": "open",
      "owner_role": "Cash accountant"
    }
  ],
  "cash_bank_reconciliation": {
    "as_of": "2026-09-30",
    "book_cash": "1588720.00",
    "bank_statement": "1564485.00",
    "deposits_in_transit": "42600.00",
    "outstanding_checks": "18450.00",
    "unrecorded_bank_fees": "85.00",
    "adjusted_book": "1588635.00",
    "adjusted_bank": "1588635.00",
    "ties": true,
    "note": "Adjusted book equals adjusted bank when ties is true. Synthetic statement."
  }
}
```

## `get_budget_variance`

Request:

```json
{
  "period": "2026-06",
  "department": "SALES",
  "ytd": false
}
```

Response:

```json
{
  "ok": true,
  "synthetic": true,
  "company": "Halden & Quay Supply, Inc.",
  "currency": "USD",
  "data_notice": "All figures are invented. Halden & Quay Supply, Inc. is a fictional company. This is not a real ledger and not financial advice.",
  "period": "2026-06",
  "ytd": false,
  "department": "SALES",
  "materiality_pct": 10.0,
  "materiality_amount": "5000.00",
  "rows": [
    {
      "department": "SALES",
      "account_code": "4000",
      "account_name": "Product Revenue",
      "account_type": "revenue",
      "actual": "505000.00",
      "budget": "510000.00",
      "variance": "-5000.00",
      "favorable_amount": "-5000.00",
      "direction": "unfavorable",
      "material": true
    },
    {
      "department": "SALES",
      "account_code": "4100",
      "account_name": "Service Revenue",
      "account_type": "revenue",
      "actual": "75750.00",
      "budget": "76500.00",
      "variance": "-750.00",
      "favorable_amount": "-750.00",
      "direction": "unfavorable",
      "material": false
    },
    {
      "department": "SALES",
      "account_code": "5000",
      "account_name": "Cost of Goods Sold",
      "account_type": "expense",
      "actual": "292900.00",
      "budget": "295800.00",
      "variance": "-2900.00",
      "favorable_amount": "2900.00",
      "direction": "favorable",
      "material": false
    },
    {
      "department": "SALES",
      "account_code": "5100",
      "account_name": "Freight In",
      "account_type": "expense",
      "actual": "12625.00",
      "budget": "12750.00",
      "variance": "-125.00",
      "favorable_amount": "125.00",
      "direction": "favorable",
      "material": false
    },
    {
      "department": "SALES",
      "account_code": "6000",
      "account_name": "Salaries and Wages",
      "account_type": "expense",
      "actual": "32000.00",
      "budget": "32000.00",
      "variance": "0.00",
      "favorable_amount": "0.00",
      "direction": "flat",
      "material": false
    },
    {
      "department": "SALES",
      "account_code": "6100",
      "account_name": "Employee Benefits",
      "account_type": "expense",
      "actual": "5760.00",
      "budget": "5760.00",
      "variance": "0.00",
      "favorable_amount": "0.00",
      "direction": "flat",
      "material": false
    },
    {
      "department": "SALES",
      "account_code": "6300",
      "account_name": "Software",
      "account_type": "expense",
      "actual": "3000.00",
      "budget": "3000.00",
      "variance": "0.00",
      "favorable_amount": "0.00",
      "direction": "flat",
      "material": false
    },
    {
      "department": "SALES",
      "account_code": "6400",
      "account_name": "Travel",
      "account_type": "expense",
      "actual": "16000.00",
      "budget": "7000.00",
      "variance": "9000.00",
      "favorable_amount": "-9000.00",
      "direction": "unfavorable",
      "material": true
    }
  ],
  "totals": {
    "actual": "943035.00",
    "budget": "942810.00",
    "favorable_amount": "-11725.00",
    "direction": "unfavorable",
    "note": "favorable_amount is positive when the mix of revenue and expense variances helps earnings. Actual and budget here add natural amounts across accounts, so that pair is not a profit total."
  },
  "material_rows": [
    {
      "department": "SALES",
      "account_code": "4000",
      "account_name": "Product Revenue",
      "account_type": "revenue",
      "actual": "505000.00",
      "budget": "510000.00",
      "variance": "-5000.00",
      "favorable_amount": "-5000.00",
      "direction": "unfavorable",
      "material": true
    },
    {
      "department": "SALES",
      "account_code": "6400",
      "account_name": "Travel",
      "account_type": "expense",
      "actual": "16000.00",
      "budget": "7000.00",
      "variance": "9000.00",
      "favorable_amount": "-9000.00",
      "direction": "unfavorable",
      "material": true
    }
  ]
}
```

## `get_ap_ar_aging`

Request:

```json
{
  "subledger": "ar"
}
```

Response:

```json
{
  "ok": true,
  "synthetic": true,
  "company": "Halden & Quay Supply, Inc.",
  "currency": "USD",
  "data_notice": "All figures are invented. Halden & Quay Supply, Inc. is a fictional company. This is not a real ledger and not financial advice.",
  "subledger": "ar",
  "as_of": "2026-09-30",
  "snapshot_as_of": "2026-09-30",
  "snapshot_note": "Open items are the books at the snapshot date. A different as_of only changes which bucket those items fall into.",
  "control_account": "1100",
  "buckets": [
    {
      "bucket": "current",
      "label": "Current",
      "count": 4,
      "amount": "211800.00"
    },
    {
      "bucket": "1_30",
      "label": "1-30 days",
      "count": 2,
      "amount": "83550.00"
    },
    {
      "bucket": "31_60",
      "label": "31-60 days",
      "count": 1,
      "amount": "36750.00"
    },
    {
      "bucket": "61_90",
      "label": "61-90 days",
      "count": 1,
      "amount": "48200.00"
    },
    {
      "bucket": "over_90",
      "label": "Over 90 days",
      "count": 2,
      "amount": "35340.00"
    }
  ],
  "total_open": "415640.00",
  "gl_balance": "415640.00",
  "ties_to_gl": true,
  "documents": [
    {
      "invoice_id": "AR-2410",
      "name": "Field & Birch Manufacturing",
      "invoice_date": "2026-04-10",
      "due_date": "2026-05-10",
      "department": "SALES",
      "description": "April invoice still open",
      "open_amount": "15500.00",
      "days_past_due": 143,
      "days_until_due": 0,
      "bucket": "over_90"
    },
    {
      "invoice_id": "AR-2408",
      "name": "Saltmarsh Robotics",
      "invoice_date": "2026-05-02",
      "due_date": "2026-06-01",
      "department": "SALES",
      "description": "May invoice still open",
      "open_amount": "19840.00",
      "days_past_due": 121,
      "days_until_due": 0,
      "bucket": "over_90"
    },
    {
      "invoice_id": "AR-2401",
      "name": "Redcedar Assembly",
      "invoice_date": "2026-06-15",
      "due_date": "2026-07-15",
      "department": "SALES",
      "description": "June product invoice, past due",
      "open_amount": "48200.00",
      "days_past_due": 77,
      "days_until_due": 0,
      "bucket": "61_90"
    },
    {
      "invoice_id": "AR-2402",
      "name": "Saltmarsh Robotics",
      "invoice_date": "2026-07-20",
      "due_date": "2026-08-19",
      "department": "SALES",
      "description": "July parts invoice",
      "open_amount": "36750.00",
      "days_past_due": 42,
      "days_until_due": 0,
      "bucket": "31_60"
    },
    {
      "invoice_id": "AR-2403",
      "name": "Field & Birch Manufacturing",
      "invoice_date": "2026-08-05",
      "due_date": "2026-09-04",
      "department": "SALES",
      "description": "August shipment",
      "open_amount": "61400.00",
      "days_past_due": 26,
      "days_until_due": 0,
      "bucket": "1_30"
    },
    {
      "invoice_id": "AR-2404",
      "name": "Quarry Line Products",
      "invoice_date": "2026-08-28",
      "due_date": "2026-09-27",
      "department": "SALES",
      "description": "August shipment, just past due",
      "open_amount": "22150.00",
      "days_past_due": 3,
      "days_until_due": 0,
      "bucket": "1_30"
    },
    {
      "invoice_id": "AR-2405",
      "name": "Hearthstone Automation",
      "invoice_date": "2026-09-01",
      "due_date": "2026-10-01",
      "department": "SALES",
      "description": "September shipment",
      "open_amount": "88000.00",
      "days_past_due": 0,
      "days_until_due": 1,
      "bucket": "current"
    },
    {
      "invoice_id": "AR-2406",
      "name": "Littleford Mills",
      "invoice_date": "2026-09-12",
      "due_date": "2026-10-12",
      "department": "SALES",
      "description": "September parts order",
      "open_amount": "54600.00",
      "days_past_due": 0,
      "days_until_due": 12,
      "bucket": "current"
    },
    {
      "invoice_id": "AR-2407",
      "name": "Redcedar Assembly",
      "invoice_date": "2026-09-18",
      "due_date": "2026-10-18",
      "department": "SALES",
      "description": "September replenishment",
      "open_amount": "41900.00",
      "days_past_due": 0,
      "days_until_due": 18,
      "bucket": "current"
    },
    {
      "invoice_id": "AR-2409",
      "name": "Quarry Line Products",
      "invoice_date": "2026-09-25",
      "due_date": "2026-10-25",
      "department": "SALES",
      "description": "Late September shipment",
      "open_amount": "27300.00",
      "days_past_due": 0,
      "days_until_due": 25,
      "bucket": "current"
    }
  ],
  "documents_returned": 10,
  "documents_omitted": 0
}
```

## `draft_adjusting_entry`

Request:

```json
{
  "period": "2026-10",
  "memo": "Accrue September software support invoice PPS-7781, not yet recorded.",
  "support_recon_id": "REC-AP-01",
  "auto_reverse": true,
  "prepared_by": "demo-client",
  "lines": [
    {
      "account_code": "6300",
      "department": "ENG",
      "debit": "7800.00",
      "credit": "0.00",
      "memo": "Paper & Pixel September support"
    },
    {
      "account_code": "2100",
      "debit": "0.00",
      "credit": "7800.00",
      "memo": "Accrued expense"
    }
  ]
}
```

Response:

```json
{
  "ok": true,
  "synthetic": true,
  "company": "Halden & Quay Supply, Inc.",
  "currency": "USD",
  "data_notice": "All figures are invented. Halden & Quay Supply, Inc. is a fictional company. This is not a real ledger and not financial advice.",
  "posted": false,
  "status": "DRAFT - not posted. A person has to review this and post it in the ledger.",
  "draft_id": "DRAFT-5843C8515274",
  "prepared_by": "demo-client",
  "period": "2026-10",
  "memo": "Accrue September software support invoice PPS-7781, not yet recorded.",
  "auto_reverse": true,
  "warnings": [
    "Reversal date 2026-11-01 is outside the periods loaded in this dataset. It is part of the proposal only."
  ],
  "support": {
    "recon_id": "REC-AP-01",
    "account_code": "2100",
    "period": "2026-09",
    "item_type": "unrecorded_invoice",
    "description": "Paper & Pixel Software invoice PPS-7781 dated 2026-09-28 for September support, in hand but not recorded.",
    "amount": "7800.00",
    "status": "open",
    "owner_role": "AP reviewer"
  },
  "entry": {
    "period": "2026-10",
    "entry_date": "2026-10-01",
    "description": "Accrue September software support invoice PPS-7781, not yet recorded.",
    "balanced": true,
    "total_debits": "7800.00",
    "total_credits": "7800.00",
    "lines": [
      {
        "line_no": 1,
        "account_code": "6300",
        "account_name": "Software",
        "department": "ENG",
        "debit": "7800.00",
        "credit": "0.00",
        "memo": "Paper & Pixel September support"
      },
      {
        "line_no": 2,
        "account_code": "2100",
        "account_name": "Accrued Expenses",
        "department": null,
        "debit": "0.00",
        "credit": "7800.00",
        "memo": "Accrued expense"
      }
    ]
  },
  "reversal": {
    "period": "2026-11",
    "entry_date": "2026-11-01",
    "description": "Reversal of draft: Accrue September software support invoice PPS-7781, not yet recorded.",
    "balanced": true,
    "total_debits": "7800.00",
    "total_credits": "7800.00",
    "lines": [
      {
        "line_no": 1,
        "account_code": "6300",
        "account_name": "Software",
        "department": "ENG",
        "debit": "0.00",
        "credit": "7800.00",
        "memo": "Reversal: Paper & Pixel September support"
      },
      {
        "line_no": 2,
        "account_code": "2100",
        "account_name": "Accrued Expenses",
        "department": null,
        "debit": "7800.00",
        "credit": "0.00",
        "memo": "Reversal: Accrued expense"
      }
    ]
  }
}
```

## `draft_adjusting_entry`

Request:

```json
{
  "period": "2026-10",
  "memo": "Intentionally unbalanced preview.",
  "auto_reverse": false,
  "lines": [
    {
      "account_code": "6950",
      "department": "FIN",
      "debit": "85.00",
      "credit": "0.00",
      "memo": "Bank fee"
    },
    {
      "account_code": "1000",
      "debit": "0.00",
      "credit": "80.00",
      "memo": "Cash"
    }
  ]
}
```

Response:

```json
{
  "ok": false,
  "synthetic": true,
  "error": "Entry is out of balance by 5.00.",
  "debits": "85.00",
  "credits": "80.00",
  "posted": false,
  "status": "NOT POSTED"
}
```
