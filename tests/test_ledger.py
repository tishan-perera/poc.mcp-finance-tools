"""The synthetic books load, tie, and stay read-only."""

import sqlite3

import pytest

from mcp_finance_tools.ledger import Ledger, open_ledger

READ_METHODS = {
    "account",
    "accounts",
    "activity",
    "budgets",
    "close",
    "departments",
    "income_actuals",
    "invoices",
    "meta",
    "period",
    "periods",
    "reconciliation",
    "reconciliations",
    "search",
}


def test_public_surface_has_no_write_method():
    public = {name for name in dir(Ledger) if not name.startswith("_")}
    assert public <= READ_METHODS


def test_connection_rejects_writes():
    with open_ledger() as books:
        with pytest.raises(sqlite3.OperationalError):
            books._conn.execute("INSERT INTO meta (key, value) VALUES ('x', 'y')")
        with pytest.raises(sqlite3.OperationalError):
            books._conn.execute("UPDATE meta SET value = 'nope' WHERE key = 'currency'")


def test_control_accounts_match_the_snapshot():
    with open_ledger() as books:
        meta = books.meta()
        assert meta["company_name"] == "Halden & Quay Supply, Inc."
        assert meta["currency"] == "USD"
        assert meta["as_of_date"] == "2026-09-30"
        assert "fictional" in meta["synthetic_notice"]
        assert meta["ending_ar_cents"] == "41564000"
        assert meta["ending_ap_cents"] == "16386000"
        assert meta["ytd_net_income_cents"] == "27050000"
        assert sum(row["open_cents"] for row in books.invoices("ar")) == 41_564_000
        assert sum(row["open_cents"] for row in books.invoices("ap")) == 16_386_000
