"""Tool behavior on the committed synthetic books."""

import hashlib
from pathlib import Path

from mcp_finance_tools import tools
from mcp_finance_tools.ledger import bundled_data_dir, open_ledger


def _hash_books() -> str:
    digest = hashlib.sha256()
    for path in sorted(Path(bundled_data_dir()).glob("*.csv")):
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def test_lookup_and_unknown_account():
    with open_ledger() as books:
        found = tools.lookup_gl_account(books, "cash")
        assert found["ok"] is True
        assert [row["account_code"] for row in found["matches"]] == ["1000"]
        assert found["matches"][0]["ending_balance"] == "1588720.00"
        missing = tools.lookup_gl_account(books, "zzz")
        assert missing["ok"] is False
        assert "1000" in {row["code"] for row in missing["known_accounts"]}


def test_trial_balance_balances_and_locks_the_story():
    with open_ledger() as books:
        report = tools.get_trial_balance(books, "2026-09")
        assert report["totals"]["balanced"] is True
        assert report["totals"]["debit"] == report["totals"]["credit"]
        assert report["net_income"]["ytd"] == "270500.00"
        product = next(row for row in report["rows"] if row["account_code"] == "4000")
        assert product["credit"] == "4520000.00"
        assert product["period_credits"] == "520000.00"
        assert all(row["account_code"] != "5200" for row in report["rows"])
        filtered = tools.get_trial_balance(books, "2026-09", "balance_sheet")
        assert filtered["totals"]["balanced"] is True
        assert all(row["statement"] == "balance_sheet" for row in filtered["rows"])
        assert tools.get_trial_balance(books, "2026-13")["ok"] is False


def test_journal_search():
    with open_ledger() as books:
        found = tools.search_journal_entries(books, text="heat wave")
        assert found["match_count"] == 1
        assert "August heat wave" in found["entries"][0]["description"]
        assert found["entries"][0]["balanced"] is True
        payroll = tools.search_journal_entries(books, source="payroll", limit=3)
        assert payroll["match_count"] == 9
        assert payroll["returned"] == 3
        escaped = tools.search_journal_entries(books, text="%")
        assert escaped["ok"] is True
        assert escaped["match_count"] == 0
        quoted = tools.search_journal_entries(books, text="wave' OR '1'='1")
        assert quoted["ok"] is True
        assert quoted["match_count"] == 0


def test_open_reconciliations_and_bank_proof():
    with open_ledger() as books:
        cash = tools.list_open_reconciliations(books, account_code="1000")
        ids = {item["recon_id"] for item in cash["items"]}
        assert "REC-CASH-01" in ids
        assert "REC-CASH-04" not in ids
        assert cash["cash_bank_reconciliation"]["ties"] is True
        cleared = tools.list_open_reconciliations(books, include_cleared=True)
        assert "REC-CASH-04" in {item["recon_id"] for item in cleared["items"]}


def test_budget_variance_signs():
    with open_ledger() as books:
        june = tools.get_budget_variance(books, "2026-06", department="SALES")
        travel = next(row for row in june["rows"] if row["account_code"] == "6400")
        assert travel["actual"] == "16000.00"
        assert travel["budget"] == "7000.00"
        assert travel["variance"] == "9000.00"
        assert travel["direction"] == "unfavorable"
        assert travel["material"] is True
        software = tools.get_budget_variance(books, "2026-09", department="ENG")
        subscriptions = next(row for row in software["rows"] if row["account_code"] == "6300")
        assert subscriptions["direction"] == "favorable"
        assert subscriptions["favorable_amount"] == "2000.00"
        assert subscriptions["material"] is True
        assert tools.get_budget_variance(books, "2026-10")["ok"] is False


def test_aging_ties_and_buckets():
    with open_ledger() as books:
        aging = tools.get_ap_ar_aging(books, "ar")
        assert aging["ties_to_gl"] is True
        assert aging["total_open"] == "415640.00"
        assert aging["gl_balance"] == "415640.00"
        by_id = {doc["invoice_id"]: doc["bucket"] for doc in aging["documents"]}
        assert by_id["AR-2405"] == "current"
        assert by_id["AR-2403"] == "1_30"
        assert by_id["AR-2402"] == "31_60"
        assert by_id["AR-2401"] == "61_90"
        assert by_id["AR-2408"] == "over_90"
        assert all(bucket["count"] > 0 for bucket in aging["buckets"])
        named = tools.get_ap_ar_aging(books, "ar", name="redcedar")
        assert named["ties_to_gl"] is False
        assert {doc["name"] for doc in named["documents"]} == {"Redcedar Assembly"}
        payables = tools.get_ap_ar_aging(books, "ap")
        assert payables["ties_to_gl"] is True
        assert payables["total_open"] == "163860.00"


def test_draft_is_not_posted_and_does_not_touch_the_books():
    before = _hash_books()
    with open_ledger() as books:
        draft = tools.draft_adjusting_entry(
            books,
            period="2026-10",
            memo="Accrue September software support invoice PPS-7781.",
            support_recon_id="REC-AP-01",
            lines=[
                {
                    "account_code": "6300",
                    "department": "ENG",
                    "debit": "7800.00",
                    "credit": "0",
                    "memo": "Paper & Pixel September support",
                },
                {
                    "account_code": "2100",
                    "debit": "0",
                    "credit": "7800.00",
                    "memo": "Accrued expense",
                },
            ],
        )
        assert draft["posted"] is False
        assert draft["status"].startswith("DRAFT")
        assert draft["draft_id"].startswith("DRAFT-")
        assert draft["entry"]["balanced"] is True
        assert draft["entry"]["total_debits"] == "7800.00"
        assert draft["reversal"]["lines"][0]["credit"] == "7800.00"
        assert draft["reversal"]["entry_date"] == "2026-11-01"
        assert any("outside the periods" in note for note in draft["warnings"])
        unbalanced = tools.draft_adjusting_entry(
            books,
            period="2026-10",
            memo="Out of balance on purpose.",
            lines=[
                {
                    "account_code": "6950",
                    "department": "FIN",
                    "debit": "85.00",
                    "credit": "0",
                    "memo": "Fee",
                },
                {"account_code": "1000", "debit": "0", "credit": "80.00", "memo": "Cash"},
            ],
        )
        assert unbalanced["posted"] is False
        assert unbalanced["status"] == "NOT POSTED"
        assert "out of balance" in unbalanced["error"]
        closed = tools.draft_adjusting_entry(
            books,
            period="2026-09",
            memo="Proposed after the close.",
            auto_reverse=False,
            lines=[
                {
                    "account_code": "6950",
                    "department": "FIN",
                    "debit": "85.00",
                    "credit": "0",
                    "memo": "Fee",
                },
                {"account_code": "1000", "debit": "0", "credit": "85.00", "memo": "Cash"},
            ],
        )
        assert closed["posted"] is False
        assert any("closed" in note for note in closed["warnings"])
        rejected = tools.draft_adjusting_entry(
            books,
            period="2026-10",
            memo="Department on a balance-sheet line.",
            lines=[
                {
                    "account_code": "1000",
                    "department": "FIN",
                    "debit": "10.00",
                    "credit": "0",
                    "memo": "Cash",
                },
                {"account_code": "2100", "debit": "0", "credit": "10.00", "memo": "Accrual"},
            ],
        )
        assert rejected["posted"] is False
        missing_dept = tools.draft_adjusting_entry(
            books,
            period="2026-10",
            memo="Expense with no department.",
            lines=[
                {"account_code": "6950", "debit": "10.00", "credit": "0", "memo": "Fee"},
                {"account_code": "1000", "debit": "0", "credit": "10.00", "memo": "Cash"},
            ],
        )
        assert missing_dept["posted"] is False
        assert "department" in missing_dept["error"]
        precise = tools.draft_adjusting_entry(
            books,
            period="2026-10",
            memo="Too many decimals.",
            lines=[
                {
                    "account_code": "6950",
                    "department": "FIN",
                    "debit": "1.001",
                    "credit": "0",
                    "memo": "Fee",
                },
                {"account_code": "1000", "debit": "0", "credit": "1.001", "memo": "Cash"},
            ],
        )
        assert precise["posted"] is False
        unknown = tools.draft_adjusting_entry(
            books,
            period="2026-10",
            memo="Missing support.",
            support_recon_id="REC-NOPE",
            lines=[
                {
                    "account_code": "6950",
                    "department": "FIN",
                    "debit": "10",
                    "credit": "0",
                    "memo": "Fee",
                },
                {"account_code": "1000", "debit": "0", "credit": "10", "memo": "Cash"},
            ],
        )
        assert unknown["posted"] is False
    assert _hash_books() == before


def test_same_draft_has_a_stable_id():
    lines = [
        {
            "account_code": "5200",
            "department": "OPS",
            "debit": "6150.00",
            "credit": "0",
            "memo": "Shrink",
        },
        {"account_code": "1200", "debit": "0", "credit": "6150.00", "memo": "Inventory"},
    ]
    with open_ledger() as books:
        first = tools.draft_adjusting_entry(
            books, "2026-10", "Book the cycle count.", lines, support_recon_id="REC-INV-01"
        )
        second = tools.draft_adjusting_entry(
            books, "2026-10", "Book the cycle count.", lines, support_recon_id="REC-INV-01"
        )
        assert first["draft_id"] == second["draft_id"]
        assert first["posted"] is False
