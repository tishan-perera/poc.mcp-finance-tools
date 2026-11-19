"""Build the synthetic books for Halden & Quay Supply, Inc.

The company, people, vendors, customers, and every amount are invented.
Running this script again with no arguments rewrites the CSV bundle under
src/mcp_finance_tools/data. `--check` rewrites a temp copy and exits non-zero
if it differs from the committed CSV, so the bundle cannot drift from the
story in this file.

Nothing here calls a network or reads a real ledger.
"""

from __future__ import annotations

import argparse
import calendar
import csv
import difflib
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "src" / "mcp_finance_tools" / "data"

COMPANY = "Halden & Quay Supply, Inc."
AS_OF = "2026-09-30"
AS_OF_PERIOD = "2026-09"

DEPARTMENTS = [
    ("SALES", "Sales"),
    ("MKTG", "Marketing"),
    ("OPS", "Operations"),
    ("ENG", "Engineering"),
    ("FIN", "Finance"),
    ("PPL", "People"),
]

# code, name, account_type, normal_balance, statement
ACCOUNTS = [
    ("1000", "Cash", "asset", "debit", "balance_sheet"),
    ("1100", "Accounts Receivable", "asset", "debit", "balance_sheet"),
    ("1200", "Inventory", "asset", "debit", "balance_sheet"),
    ("1300", "Prepaid Expenses", "asset", "debit", "balance_sheet"),
    ("1500", "Property and Equipment", "asset", "debit", "balance_sheet"),
    ("1510", "Accumulated Depreciation", "contra_asset", "credit", "balance_sheet"),
    ("2000", "Accounts Payable", "liability", "credit", "balance_sheet"),
    ("2100", "Accrued Expenses", "liability", "credit", "balance_sheet"),
    ("2200", "Deferred Revenue", "liability", "credit", "balance_sheet"),
    ("2300", "Accrued Payroll", "liability", "credit", "balance_sheet"),
    ("3000", "Common Stock", "equity", "credit", "balance_sheet"),
    ("3100", "Retained Earnings", "equity", "credit", "balance_sheet"),
    ("4000", "Product Revenue", "revenue", "credit", "income_statement"),
    ("4100", "Service Revenue", "revenue", "credit", "income_statement"),
    ("5000", "Cost of Goods Sold", "expense", "debit", "income_statement"),
    ("5100", "Freight In", "expense", "debit", "income_statement"),
    ("5200", "Inventory Shrink", "expense", "debit", "income_statement"),
    ("6000", "Salaries and Wages", "expense", "debit", "income_statement"),
    ("6100", "Employee Benefits", "expense", "debit", "income_statement"),
    ("6200", "Rent", "expense", "debit", "income_statement"),
    ("6300", "Software", "expense", "debit", "income_statement"),
    ("6400", "Travel", "expense", "debit", "income_statement"),
    ("6500", "Marketing Programs", "expense", "debit", "income_statement"),
    ("6600", "Professional Services", "expense", "debit", "income_statement"),
    ("6700", "Depreciation Expense", "expense", "debit", "income_statement"),
    ("6800", "Utilities", "expense", "debit", "income_statement"),
    ("6900", "Insurance Expense", "expense", "debit", "income_statement"),
    ("6950", "Bank Fees", "expense", "debit", "income_statement"),
]

MONTHS = [
    "2026-01",
    "2026-02",
    "2026-03",
    "2026-04",
    "2026-05",
    "2026-06",
    "2026-07",
    "2026-08",
    "2026-09",
]
# Whole dollars, stored as cents. Chosen so 15%, 58%, and 2.5% land on cents.
PRODUCT = [
    48_000_000,
    46_500_000,
    51_000_000,
    49_500_000,
    53_000_000,
    50_500_000,
    47_000_000,
    54_500_000,
    52_000_000,
]
PRODUCT_BUDGET = [
    50_000_000,
    50_000_000,
    50_000_000,
    50_000_000,
    51_000_000,
    51_000_000,
    49_000_000,
    52_000_000,
    52_000_000,
]

SALARIES = {
    "SALES": 3_200_000,
    "MKTG": 1_400_000,
    "OPS": 2_600_000,
    "ENG": 2_200_000,
    "FIN": 1_600_000,
    "PPL": 1_000_000,
}
SOFTWARE = (("ENG", 1_200_000), ("FIN", 400_000), ("SALES", 300_000))

# Invoice id, name, invoice date, due date, department, description, open cents.
# Open amounts are the September 30 snapshot. Their sum is the GL control balance.
AR_OPEN = [
    (
        "AR-2401",
        "Redcedar Assembly",
        "2026-06-15",
        "2026-07-15",
        "SALES",
        "June product invoice, past due",
        4_820_000,
    ),
    (
        "AR-2402",
        "Saltmarsh Robotics",
        "2026-07-20",
        "2026-08-19",
        "SALES",
        "July parts invoice",
        3_675_000,
    ),
    (
        "AR-2403",
        "Field & Birch Manufacturing",
        "2026-08-05",
        "2026-09-04",
        "SALES",
        "August shipment",
        6_140_000,
    ),
    (
        "AR-2404",
        "Quarry Line Products",
        "2026-08-28",
        "2026-09-27",
        "SALES",
        "August shipment, just past due",
        2_215_000,
    ),
    (
        "AR-2405",
        "Hearthstone Automation",
        "2026-09-01",
        "2026-10-01",
        "SALES",
        "September shipment",
        8_800_000,
    ),
    (
        "AR-2406",
        "Littleford Mills",
        "2026-09-12",
        "2026-10-12",
        "SALES",
        "September parts order",
        5_460_000,
    ),
    (
        "AR-2407",
        "Redcedar Assembly",
        "2026-09-18",
        "2026-10-18",
        "SALES",
        "September replenishment",
        4_190_000,
    ),
    (
        "AR-2408",
        "Saltmarsh Robotics",
        "2026-05-02",
        "2026-06-01",
        "SALES",
        "May invoice still open",
        1_984_000,
    ),
    (
        "AR-2409",
        "Quarry Line Products",
        "2026-09-25",
        "2026-10-25",
        "SALES",
        "Late September shipment",
        2_730_000,
    ),
    (
        "AR-2410",
        "Field & Birch Manufacturing",
        "2026-04-10",
        "2026-05-10",
        "SALES",
        "April invoice still open",
        1_550_000,
    ),
]
AP_OPEN = [
    (
        "AP-3301",
        "Brightbox Packaging",
        "2026-08-20",
        "2026-09-19",
        "OPS",
        "Packaging materials",
        2_840_000,
    ),
    (
        "AP-3302",
        "Kelso Metals Supply",
        "2026-09-08",
        "2026-10-08",
        "OPS",
        "September metal stock",
        5_385_000,
    ),
    (
        "AP-3303",
        "Pine Street Logistics",
        "2026-09-15",
        "2026-10-15",
        "OPS",
        "September inbound freight",
        1_786_000,
    ),
    (
        "AP-3304",
        "Cobalt & Clay Industrial",
        "2026-07-01",
        "2026-07-31",
        "OPS",
        "July component purchase",
        2_460_000,
    ),
    (
        "AP-3305",
        "Paper & Pixel Software",
        "2026-08-01",
        "2026-08-31",
        "ENG",
        "August implementation help",
        800_000,
    ),
    (
        "AP-3306",
        "Kelso Metals Supply",
        "2026-05-15",
        "2026-06-14",
        "OPS",
        "May metal stock still open",
        2_175_000,
    ),
    (
        "AP-3307",
        "Pine Street Logistics",
        "2026-08-01",
        "2026-08-15",
        "OPS",
        "August freight invoice",
        940_000,
    ),
]

RECONS = [
    (
        "REC-CASH-01",
        "1000",
        "2026-09",
        "deposit_in_transit",
        "Customer deposit recorded on 2026-09-29, not on the bank statement yet.",
        4_260_000,
        "open",
        "Cash accountant",
    ),
    (
        "REC-CASH-02",
        "1000",
        "2026-09",
        "outstanding_check",
        "Check 1042 to Brightbox Packaging, mailed 2026-09-18, still outstanding.",
        1_845_000,
        "open",
        "Cash accountant",
    ),
    (
        "REC-CASH-03",
        "1000",
        "2026-09",
        "unrecorded_bank_fee",
        "September bank service charge on the statement, not yet on the books.",
        8_500,
        "open",
        "Cash accountant",
    ),
    (
        "REC-CASH-04",
        "1000",
        "2026-08",
        "outstanding_check",
        "Check 1031 cleared in September.",
        2_200_000,
        "cleared",
        "Cash accountant",
    ),
    (
        "REC-AP-01",
        "2100",
        "2026-09",
        "unrecorded_invoice",
        "Paper & Pixel Software invoice PPS-7781 dated 2026-09-28 for September support, in hand but not recorded.",
        780_000,
        "open",
        "AP reviewer",
    ),
    (
        "REC-AP-02",
        "2000",
        "2026-09",
        "unapplied_debit",
        "Debit memo from Kelso Metals Supply, not yet matched to a bill. The AP control account still ties.",
        124_000,
        "open",
        "AP reviewer",
    ),
    (
        "REC-AR-01",
        "1100",
        "2026-09",
        "unapplied_receipt",
        "Redcedar receipt of 9600 on 2026-09-22 was applied to the wrong invoice. The AR control still ties.",
        960_000,
        "open",
        "AR reviewer",
    ),
    (
        "REC-AR-02",
        "1100",
        "2026-07",
        "unapplied_receipt",
        "Short-payment note resolved in August.",
        50_000,
        "cleared",
        "AR reviewer",
    ),
    (
        "REC-INV-01",
        "1200",
        "2026-09",
        "count_shortage",
        "September cycle count is 6150 below the books. Not posted.",
        615_000,
        "open",
        "Inventory control",
    ),
    (
        "REC-PRE-01",
        "1300",
        "2026-09",
        "schedule_difference",
        "Prepaid insurance support is 1200 below the book balance. Review the amortization schedule.",
        120_000,
        "open",
        "GL accountant",
    ),
]

EXPECTED_AR = 41_564_000
EXPECTED_AP = 16_386_000
DIT = 4_260_000
OUTSTANDING_CHECKS = 1_845_000
BANK_FEE = 8_500


def pct(cents: int, num: int, den: int) -> int:
    if cents * num % den != 0:
        raise SystemExit(f"{cents} * {num}/{den} is not an exact number of cents")
    return cents * num // den


def month_end(period: str) -> str:
    year, month = (int(part) for part in period.split("-"))
    day = calendar.monthrange(year, month)[1]
    return f"{year:04d}-{month:02d}-{day:02d}"


def account_map() -> dict[str, dict]:
    return {
        code: {
            "code": code,
            "name": name,
            "account_type": account_type,
            "normal_balance": normal,
            "statement": statement,
        }
        for code, name, account_type, normal, statement in ACCOUNTS
    }


class Books:
    def __init__(self) -> None:
        self.accounts = account_map()
        self.entries: list[list] = []
        self.lines: list[list] = []
        self._seq: dict[str, int] = {}
        self._line_id = 1
        self.natural = {code: 0 for code in self.accounts}
        self.actuals: dict[tuple[str, str, str], int] = {}

    def add(self, period: str, date: str, source: str, description: str, lines: list[tuple]) -> None:
        debits = sum(line[2] for line in lines)
        credits = sum(line[3] for line in lines)
        if debits != credits or debits <= 0:
            raise SystemExit(f"{description} does not balance ({debits} vs {credits})")
        number = self._seq.get(period, 0) + 1
        self._seq[period] = number
        entry_id = f"JE-{period}-{number:02d}"
        self.entries.append([entry_id, period, date, source, description])
        for line_no, (account, department, debit, credit, memo) in enumerate(lines, start=1):
            meta = self.accounts[account]
            if debit < 0 or credit < 0 or (debit == 0) == (credit == 0):
                raise SystemExit(f"{entry_id} line {line_no} needs one positive side")
            if meta["statement"] == "income_statement" and not department:
                raise SystemExit(f"{entry_id} income-statement line {account} needs a department")
            if meta["statement"] == "balance_sheet" and department:
                raise SystemExit(f"{entry_id} balance-sheet line {account} cannot take a department")
            self.lines.append([self._line_id, entry_id, line_no, account, department or "", debit, credit, memo])
            self._line_id += 1
            delta = debit - credit if meta["normal_balance"] == "debit" else credit - debit
            self.natural[account] += delta
            if meta["statement"] == "income_statement":
                key = (period, department, account)
                self.actuals[key] = self.actuals.get(key, 0) + delta
        for code, floor in (
            ("1000", 10_000_000),
            ("1100", 1),
            ("1200", 1),
            ("1300", 1),
            ("2000", 1),
        ):
            if self.natural[code] < floor:
                raise SystemExit(f"account {code} fell to {self.natural[code]} after {entry_id}")


def opening_lines() -> list[tuple]:
    # Debits 3,925,000. Credits, with retained earnings as the plug, match.
    return [
        ("1000", "", 125_000_000, 0, "Opening cash"),
        ("1100", "", 64_000_000, 0, "Opening receivables"),
        ("1200", "", 89_000_000, 0, "Opening inventory"),
        ("1300", "", 4_500_000, 0, "Opening prepaid expenses"),
        ("1500", "", 110_000_000, 0, "Opening property and equipment"),
        ("1510", "", 0, 32_000_000, "Opening accumulated depreciation"),
        ("2000", "", 0, 41_000_000, "Opening accounts payable"),
        ("2100", "", 0, 7_500_000, "Opening accrued expenses"),
        ("2200", "", 0, 9_000_000, "Opening deferred revenue"),
        ("2300", "", 0, 6_000_000, "Opening accrued payroll"),
        ("3000", "", 0, 50_000_000, "Opening common stock"),
        ("3100", "", 0, 247_000_000, "Opening retained earnings"),
    ]


def build() -> dict[str, list[list]]:
    if sum(amount for *_, amount in AR_OPEN) != EXPECTED_AR:
        raise SystemExit("AR open-item list does not sum to the expected control total")
    if sum(amount for *_, amount in AP_OPEN) != EXPECTED_AP:
        raise SystemExit("AP open-item list does not sum to the expected control total")

    books = Books()
    books.add("2025-12", "2025-12-31", "opening", "Opening balances, synthetic books.", opening_lines())

    for index, period in enumerate(MONTHS):
        product = PRODUCT[index]
        service = pct(product, 15, 100)
        cogs = pct(product, 58, 100)
        freight = pct(product, 25, 1000)
        billing = product + service
        extra_collection = 2_500_000 if period != "2026-09" else 2_436_000
        collection = billing + extra_collection
        purchases = cogs + 800_000
        professional = 800_000 if period in {"2026-03", "2026-06", "2026-09"} else 0
        extra_payment = 2_700_000 if period != "2026-09" else 3_014_000
        payment = purchases + freight + professional + extra_payment
        travel = 1_600_000 if period == "2026-06" else 700_000
        marketing = 3_600_000 if period == "2026-03" else 1_800_000
        utilities = 950_000 if period == "2026-08" else 600_000
        end = month_end(period)

        books.add(
            period,
            f"{period}-15",
            "billing",
            f"Product and service billings for {period}.",
            [
                ("1100", "", billing, 0, "Customer billings"),
                ("4000", "SALES", 0, product, "Product revenue"),
                ("4100", "SALES", 0, service, "Service revenue"),
            ],
        )
        books.add(
            period,
            f"{period}-20",
            "collection",
            f"Customer collections for {period}.",
            [
                ("1000", "", collection, 0, "Cash receipts"),
                ("1100", "", 0, collection, "Applied to receivables"),
            ],
        )
        books.add(
            period,
            end,
            "cogs",
            f"Cost of goods sold for {period}.",
            [
                ("5000", "SALES", cogs, 0, "Cost of goods sold"),
                ("1200", "", 0, cogs, "Inventory relieved"),
            ],
        )
        books.add(
            period,
            end,
            "purchase",
            f"Inventory purchases for {period}.",
            [
                ("1200", "", purchases, 0, "Inventory received"),
                ("2000", "", 0, purchases, "Vendor bills"),
            ],
        )
        books.add(
            period,
            end,
            "freight",
            f"Inbound freight for {period}.",
            [
                ("5100", "SALES", freight, 0, "Freight in"),
                ("2000", "", 0, freight, "Freight bills"),
            ],
        )
        if professional:
            books.add(
                period,
                end,
                "professional_services",
                f"Quarterly close support from Hart & Quill Advisors, {period}.",
                [
                    ("6600", "FIN", professional, 0, "Close support"),
                    ("2000", "", 0, professional, "Advisor bill"),
                ],
            )
        books.add(
            period,
            end,
            "ap_payment",
            f"Vendor payments for {period}.",
            [
                ("2000", "", payment, 0, "Payments to vendors"),
                ("1000", "", 0, payment, "Cash paid"),
            ],
        )
        payroll = [("6000", dept, amount, 0, f"Salaries, {dept}") for dept, amount in SALARIES.items()]
        payroll += [("6100", dept, pct(amount, 18, 100), 0, f"Benefits, {dept}") for dept, amount in SALARIES.items()]
        payroll_cash = sum(line[2] for line in payroll)
        payroll.append(("1000", "", 0, payroll_cash, "Payroll disbursement"))
        books.add(period, end, "payroll", f"Payroll for {period}.", payroll)
        books.add(
            period,
            end,
            "rent",
            f"Warehouse and office rent for {period}.",
            [("6200", "OPS", 2_800_000, 0, "Rent"), ("1000", "", 0, 2_800_000, "Rent paid")],
        )
        software_lines = [("6300", dept, amount, 0, f"Software, {dept}") for dept, amount in SOFTWARE]
        software_total = sum(line[2] for line in software_lines)
        software_lines.append(("1000", "", 0, software_total, "Software paid"))
        books.add(period, end, "software", f"Software subscriptions for {period}.", software_lines)
        travel_memo = "Travel for the June distributor expo" if period == "2026-06" else "Sales travel"
        books.add(
            period,
            end,
            "travel",
            travel_memo if period == "2026-06" else f"Sales travel for {period}.",
            [("6400", "SALES", travel, 0, travel_memo), ("1000", "", 0, travel, "Travel paid")],
        )
        marketing_memo = "Spring catalog campaign" if period == "2026-03" else "Marketing programs"
        books.add(
            period,
            end,
            "marketing",
            marketing_memo if period == "2026-03" else f"Marketing programs for {period}.",
            [
                ("6500", "MKTG", marketing, 0, marketing_memo),
                ("1000", "", 0, marketing, "Marketing paid"),
            ],
        )
        utility_memo = "Utility true-up for the August heat wave" if period == "2026-08" else "Utilities"
        books.add(
            period,
            end,
            "utilities",
            utility_memo if period == "2026-08" else f"Utilities for {period}.",
            [
                ("6800", "OPS", utilities, 0, utility_memo),
                ("1000", "", 0, utilities, "Utilities paid"),
            ],
        )
        books.add(
            period,
            end,
            "depreciation",
            f"Monthly depreciation for {period}.",
            [
                ("6700", "FIN", 1_400_000, 0, "Depreciation"),
                ("1510", "", 0, 1_400_000, "Accumulated depreciation"),
            ],
        )
        books.add(
            period,
            end,
            "insurance",
            f"Prepaid insurance amortization for {period}.",
            [
                ("6900", "FIN", 400_000, 0, "Insurance"),
                ("1300", "", 0, 400_000, "Prepaid insurance"),
            ],
        )

    if books.natural["1100"] != EXPECTED_AR:
        raise SystemExit(f"AR control {books.natural['1100']} != open items {EXPECTED_AR}")
    if books.natural["2000"] != EXPECTED_AP:
        raise SystemExit(f"AP control {books.natural['2000']} != open items {EXPECTED_AP}")
    if books.natural["1200"] != 89_000_000 + 9 * 800_000:
        raise SystemExit(f"unexpected inventory {books.natural['1200']}")
    if books.natural["1300"] != 4_500_000 - 9 * 400_000:
        raise SystemExit(f"unexpected prepaid {books.natural['1300']}")
    if books.natural["1510"] != 32_000_000 + 9 * 1_400_000:
        raise SystemExit(f"unexpected accumulated depreciation {books.natural['1510']}")

    budgets = budget_rows(books.actuals)
    _assert_story(books.actuals, budgets)

    bank_statement = books.natural["1000"] - BANK_FEE - DIT + OUTSTANDING_CHECKS
    net_income = _net_income(books.natural)

    meta = [
        ["company_name", COMPANY],
        ["entity_id", "SYNTHETIC-HALDEN-QUAY-001"],
        ["currency", "USD"],
        ["country", "United States"],
        ["fiscal_year_start", "January"],
        ["as_of_date", AS_OF],
        ["as_of_period", AS_OF_PERIOD],
        [
            "books_basis",
            "Pre-close. Income-statement accounts are not closed to retained earnings.",
        ],
        [
            "synthetic_notice",
            "All figures are invented. Halden & Quay Supply, Inc. is a fictional company. "
            "This is not a real ledger and not financial advice.",
        ],
        ["bank_statement_cents", str(bank_statement)],
        ["ytd_net_income_cents", str(net_income)],
        ["ending_cash_cents", str(books.natural["1000"])],
        ["ending_ar_cents", str(books.natural["1100"])],
        ["ending_ap_cents", str(books.natural["2000"])],
    ]

    periods = [
        ["2025-12", "202512", "2025", "12", "2025-12-01", "2025-12-31", "closed", "opening"],
    ]
    for period in MONTHS:
        year, month = period.split("-")
        periods.append(
            [
                period,
                f"{year}{month}",
                year,
                month,
                f"{period}-01",
                month_end(period),
                "closed",
                "operating",
            ]
        )
    periods.append(["2026-10", "202610", "2026", "10", "2026-10-01", "2026-10-31", "open", "future"])

    return {
        "meta": meta,
        "departments": [list(row) for row in DEPARTMENTS],
        "accounts": [[*row, 1] for row in ACCOUNTS],
        "periods": periods,
        "journal_entries": books.entries,
        "journal_lines": books.lines,
        "budgets": budgets,
        "reconciliations": [list(row) for row in RECONS],
        "ap_invoices": [[*row[:6], row[6], row[6]] for row in AP_OPEN],
        "ar_invoices": [[*row[:6], row[6], row[6]] for row in AR_OPEN],
    }


def _net_income(natural: dict[str, int]) -> int:
    total = 0
    for code, _, account_type, _, _ in ACCOUNTS:
        if account_type == "revenue":
            total += natural[code]
        elif account_type == "expense":
            total -= natural[code]
    return total


def budget_rows(actuals: dict[tuple[str, str, str], int]) -> list[list]:
    overrides: dict[tuple[str, str, str], int] = {}
    for index, period in enumerate(MONTHS):
        product_budget = PRODUCT_BUDGET[index]
        overrides[(period, "SALES", "4000")] = product_budget
        overrides[(period, "SALES", "4100")] = pct(product_budget, 15, 100)
        overrides[(period, "SALES", "5000")] = pct(product_budget, 58, 100)
        overrides[(period, "SALES", "5100")] = pct(product_budget, 25, 1000)
        overrides[(period, "ENG", "6300")] = 1_400_000
        overrides[(period, "SALES", "6400")] = 700_000
        overrides[(period, "MKTG", "6500")] = 1_800_000
        overrides[(period, "OPS", "6800")] = 600_000
    rows = []
    for key in sorted(actuals):
        amount = overrides.get(key, actuals[key])
        period, department, account = key
        rows.append([period, department, account, amount])
    return rows


def _assert_story(actuals: dict[tuple[str, str, str], int], budgets: list[list]) -> None:
    budget_map = {(row[0], row[1], row[2]): row[3] for row in budgets}
    expected = {
        ("2026-06", "SALES", "6400"): 900_000,
        ("2026-03", "MKTG", "6500"): 1_800_000,
        ("2026-08", "OPS", "6800"): 350_000,
        ("2026-02", "SALES", "4000"): -3_500_000,
        ("2026-09", "ENG", "6300"): -200_000,
    }
    for key, variance in expected.items():
        got = actuals[key] - budget_map[key]
        if got != variance:
            raise SystemExit(f"story variance {key} is {got}, expected {variance}")


HEADERS = {
    "meta": ["key", "value"],
    "departments": ["code", "name"],
    "accounts": ["code", "name", "account_type", "normal_balance", "statement", "active"],
    "periods": ["period", "sort_key", "year", "month", "start_date", "end_date", "status", "kind"],
    "journal_entries": ["entry_id", "period", "entry_date", "source", "description"],
    "journal_lines": [
        "line_id",
        "entry_id",
        "line_no",
        "account_code",
        "department",
        "debit_cents",
        "credit_cents",
        "memo",
    ],
    "budgets": ["period", "department", "account_code", "amount_cents"],
    "reconciliations": [
        "recon_id",
        "account_code",
        "period",
        "item_type",
        "description",
        "amount_cents",
        "status",
        "owner_role",
    ],
    "ap_invoices": [
        "invoice_id",
        "vendor",
        "invoice_date",
        "due_date",
        "department",
        "description",
        "amount_cents",
        "open_cents",
    ],
    "ar_invoices": [
        "invoice_id",
        "customer",
        "invoice_date",
        "due_date",
        "department",
        "description",
        "amount_cents",
        "open_cents",
    ],
}


def write_books(directory: Path, tables: dict[str, list[list]]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for name, rows in tables.items():
        path = directory / f"{name}.csv"
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle, lineterminator="\n")
            writer.writerow(HEADERS[name])
            writer.writerows(rows)


def read_csvs(directory: Path) -> dict[str, str]:
    return {path.name: path.read_text(encoding="utf-8") for path in sorted(directory.glob("*.csv"))}


def check_against(committed: Path, tables: dict[str, list[list]]) -> list[str]:
    with tempfile.TemporaryDirectory() as tmp:
        generated = Path(tmp)
        write_books(generated, tables)
        left = read_csvs(generated)
    right = read_csvs(committed)
    problems = []
    for name in sorted(set(left) | set(right)):
        if left.get(name) == right.get(name):
            continue
        diff = "".join(
            difflib.unified_diff(
                (right.get(name) or "").splitlines(keepends=True),
                (left.get(name) or "").splitlines(keepends=True),
                fromfile=f"committed/{name}",
                tofile=f"generated/{name}",
            )
        )
        problems.append(diff or f"{name} differs")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate the synthetic Halden & Quay books.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="Directory for the CSV bundle.")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero if the committed CSV bundle differs from a fresh generate.",
    )
    args = parser.parse_args(argv)
    tables = build()
    if args.check:
        problems = check_against(DEFAULT_OUT, tables)
        if problems:
            sys.stderr.write("\n".join(problems))
            sys.stderr.write("\nCommitted CSV does not match scripts/generate_synthetic_books.py.\n")
            return 1
        return 0
    write_books(args.out, tables)
    meta = dict(tables["meta"])
    print(f"Wrote synthetic books for {meta['company_name']} to {args.out}")
    print(f"As of {meta['as_of_date']}. YTD net income (cents): {meta['ytd_net_income_cents']}")
    print(f"Cash (cents): {meta['ending_cash_cents']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
