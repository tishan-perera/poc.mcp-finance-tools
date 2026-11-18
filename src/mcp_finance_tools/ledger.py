"""Load the synthetic CSV books into a read-only in-memory SQLite database.

The CSV files are the dataset. SQLite is only a query engine. After the load,
the connection is switched to ``PRAGMA query_only`` so a later statement cannot
insert, update, or delete. This module has no method that posts a journal entry.
"""

from __future__ import annotations

import csv
import sqlite3
from pathlib import Path

BUNDLED = Path(__file__).resolve().parent / "data"

FILES = (
    "meta",
    "departments",
    "accounts",
    "periods",
    "journal_entries",
    "journal_lines",
    "budgets",
    "reconciliations",
    "ap_invoices",
    "ar_invoices",
)

_SCHEMA = """
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);

CREATE TABLE departments (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL
);

CREATE TABLE accounts (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    account_type TEXT NOT NULL,
    normal_balance TEXT NOT NULL CHECK (normal_balance IN ('debit', 'credit')),
    statement TEXT NOT NULL CHECK (statement IN ('balance_sheet', 'income_statement')),
    active INTEGER NOT NULL CHECK (active IN (0, 1))
);

CREATE TABLE periods (
    period TEXT PRIMARY KEY,
    sort_key INTEGER NOT NULL UNIQUE,
    year INTEGER NOT NULL,
    month INTEGER NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('open', 'closed')),
    kind TEXT NOT NULL CHECK (kind IN ('opening', 'operating', 'future'))
);

CREATE TABLE journal_entries (
    entry_id TEXT PRIMARY KEY,
    period TEXT NOT NULL REFERENCES periods(period),
    entry_date TEXT NOT NULL,
    source TEXT NOT NULL,
    description TEXT NOT NULL
);

CREATE TABLE journal_lines (
    line_id INTEGER PRIMARY KEY,
    entry_id TEXT NOT NULL REFERENCES journal_entries(entry_id),
    line_no INTEGER NOT NULL,
    account_code TEXT NOT NULL REFERENCES accounts(code),
    department TEXT REFERENCES departments(code),
    debit_cents INTEGER NOT NULL CHECK (debit_cents >= 0),
    credit_cents INTEGER NOT NULL CHECK (credit_cents >= 0),
    memo TEXT NOT NULL,
    CHECK ((debit_cents = 0) != (credit_cents = 0))
);

CREATE TABLE budgets (
    period TEXT NOT NULL REFERENCES periods(period),
    department TEXT NOT NULL REFERENCES departments(code),
    account_code TEXT NOT NULL REFERENCES accounts(code),
    amount_cents INTEGER NOT NULL CHECK (amount_cents >= 0),
    PRIMARY KEY (period, department, account_code)
);

CREATE TABLE reconciliations (
    recon_id TEXT PRIMARY KEY,
    account_code TEXT NOT NULL REFERENCES accounts(code),
    period TEXT NOT NULL REFERENCES periods(period),
    item_type TEXT NOT NULL,
    description TEXT NOT NULL,
    amount_cents INTEGER NOT NULL CHECK (amount_cents > 0),
    status TEXT NOT NULL CHECK (status IN ('open', 'cleared')),
    owner_role TEXT NOT NULL
);

CREATE TABLE ap_invoices (
    invoice_id TEXT PRIMARY KEY,
    vendor TEXT NOT NULL,
    invoice_date TEXT NOT NULL,
    due_date TEXT NOT NULL,
    department TEXT NOT NULL REFERENCES departments(code),
    description TEXT NOT NULL,
    amount_cents INTEGER NOT NULL CHECK (amount_cents > 0),
    open_cents INTEGER NOT NULL CHECK (open_cents > 0)
);

CREATE TABLE ar_invoices (
    invoice_id TEXT PRIMARY KEY,
    customer TEXT NOT NULL,
    invoice_date TEXT NOT NULL,
    due_date TEXT NOT NULL,
    department TEXT NOT NULL REFERENCES departments(code),
    description TEXT NOT NULL,
    amount_cents INTEGER NOT NULL CHECK (amount_cents > 0),
    open_cents INTEGER NOT NULL CHECK (open_cents > 0)
);
"""


def bundled_data_dir() -> Path:
    return BUNDLED


class Ledger:
    """Read API over one synthetic ledger."""

    def __init__(self, data_dir: Path | None = None):
        self.data_dir = Path(data_dir) if data_dir else BUNDLED
        self._conn = _load(self.data_dir)
        _validate(self._conn)

    def __enter__(self) -> Ledger:
        return self

    def __exit__(self, *exc: object) -> bool:
        self.close()
        return False

    def close(self) -> None:
        self._conn.close()

    def meta(self) -> dict[str, str]:
        rows = self._conn.execute("SELECT key, value FROM meta ORDER BY key").fetchall()
        return {row["key"]: row["value"] for row in rows}

    def accounts(self) -> list[dict]:
        return [dict(row) for row in self._conn.execute("SELECT * FROM accounts ORDER BY code")]

    def account(self, code: str) -> dict | None:
        row = self._conn.execute("SELECT * FROM accounts WHERE code = ?", (code,)).fetchone()
        return dict(row) if row else None

    def departments(self) -> list[dict]:
        return [dict(row) for row in self._conn.execute("SELECT * FROM departments ORDER BY code")]

    def periods(self) -> list[dict]:
        return [dict(row) for row in self._conn.execute("SELECT * FROM periods ORDER BY sort_key")]

    def period(self, period: str) -> dict | None:
        row = self._conn.execute("SELECT * FROM periods WHERE period = ?", (period,)).fetchone()
        return dict(row) if row else None

    def activity(self, *, through_sort: int | None = None, period: str | None = None) -> dict[str, tuple[int, int]]:
        if (through_sort is None) == (period is None):
            raise ValueError("pass either through_sort or period")
        if period is None:
            sql = """
                SELECT l.account_code AS code,
                       SUM(l.debit_cents) AS debit_cents,
                       SUM(l.credit_cents) AS credit_cents
                FROM journal_lines l
                JOIN journal_entries e ON e.entry_id = l.entry_id
                JOIN periods p ON p.period = e.period
                WHERE p.sort_key <= ?
                GROUP BY l.account_code
            """
            params: tuple = (through_sort,)
        else:
            sql = """
                SELECT l.account_code AS code,
                       SUM(l.debit_cents) AS debit_cents,
                       SUM(l.credit_cents) AS credit_cents
                FROM journal_lines l
                JOIN journal_entries e ON e.entry_id = l.entry_id
                WHERE e.period = ?
                GROUP BY l.account_code
            """
            params = (period,)
        return {row["code"]: (row["debit_cents"], row["credit_cents"]) for row in self._conn.execute(sql, params)}

    def income_actuals(self, start_sort: int, end_sort: int, department: str | None) -> list[dict]:
        rows = self._conn.execute(
            """
            SELECT l.department AS department,
                   l.account_code AS account_code,
                   SUM(l.debit_cents) AS debit_cents,
                   SUM(l.credit_cents) AS credit_cents
            FROM journal_lines l
            JOIN journal_entries e ON e.entry_id = l.entry_id
            JOIN periods p ON p.period = e.period
            JOIN accounts a ON a.code = l.account_code
            WHERE p.sort_key BETWEEN ? AND ?
              AND a.statement = 'income_statement'
              AND (? IS NULL OR l.department = ?)
            GROUP BY l.department, l.account_code
            ORDER BY l.department, l.account_code
            """,
            (start_sort, end_sort, department, department),
        )
        return [dict(row) for row in rows]

    def budgets(self, start_sort: int, end_sort: int, department: str | None) -> list[dict]:
        rows = self._conn.execute(
            """
            SELECT b.department AS department,
                   b.account_code AS account_code,
                   SUM(b.amount_cents) AS amount_cents
            FROM budgets b
            JOIN periods p ON p.period = b.period
            WHERE p.sort_key BETWEEN ? AND ?
              AND (? IS NULL OR b.department = ?)
            GROUP BY b.department, b.account_code
            ORDER BY b.department, b.account_code
            """,
            (start_sort, end_sort, department, department),
        )
        return [dict(row) for row in rows]

    def search(
        self,
        *,
        text: str | None,
        account_code: str | None,
        department: str | None,
        period: str | None,
        source: str | None,
        min_cents: int | None,
        max_cents: int | None,
        limit: int,
    ) -> tuple[int, list[dict]]:
        clauses = ["1 = 1"]
        params: list = []
        if period:
            clauses.append("e.period = ?")
            params.append(period)
        if source:
            clauses.append("e.source = ?")
            params.append(source)
        if account_code:
            clauses.append("l.account_code = ?")
            params.append(account_code)
        if department:
            clauses.append("l.department = ?")
            params.append(department)
        if text:
            pattern = _like_contains(text)
            clauses.append("(e.description LIKE ? ESCAPE '\\' OR l.memo LIKE ? ESCAPE '\\')")
            params.extend([pattern, pattern])
        if min_cents is not None:
            clauses.append("(l.debit_cents >= ? OR l.credit_cents >= ?)")
            params.extend([min_cents, min_cents])
        if max_cents is not None:
            clauses.append(
                "((l.debit_cents > 0 AND l.debit_cents <= ?) OR (l.credit_cents > 0 AND l.credit_cents <= ?))"
            )
            params.extend([max_cents, max_cents])
        where = " AND ".join(clauses)
        count = self._conn.execute(
            f"""
            SELECT COUNT(DISTINCT e.entry_id) AS n
            FROM journal_entries e
            JOIN journal_lines l ON l.entry_id = e.entry_id
            WHERE {where}
            """,
            params,
        ).fetchone()["n"]
        id_rows = self._conn.execute(
            f"""
            SELECT e.entry_id AS entry_id
            FROM journal_entries e
            JOIN journal_lines l ON l.entry_id = e.entry_id
            WHERE {where}
            GROUP BY e.entry_id
            ORDER BY e.entry_date DESC, e.entry_id DESC
            LIMIT ?
            """,
            [*params, limit],
        ).fetchall()
        entries = []
        for id_row in id_rows:
            header = self._conn.execute(
                "SELECT * FROM journal_entries WHERE entry_id = ?",
                (id_row["entry_id"],),
            ).fetchone()
            lines = self._conn.execute(
                """
                SELECT l.line_no, l.account_code, a.name AS account_name, l.department,
                       l.debit_cents, l.credit_cents, l.memo
                FROM journal_lines l
                JOIN accounts a ON a.code = l.account_code
                WHERE l.entry_id = ?
                ORDER BY l.line_no
                """,
                (id_row["entry_id"],),
            ).fetchall()
            entries.append({**dict(header), "lines": [dict(line) for line in lines]})
        return count, entries

    def reconciliations(self, *, status: str | None, account_code: str | None, period: str | None) -> list[dict]:
        rows = self._conn.execute(
            """
            SELECT * FROM reconciliations
            WHERE (? IS NULL OR status = ?)
              AND (? IS NULL OR account_code = ?)
              AND (? IS NULL OR period = ?)
            ORDER BY account_code, recon_id
            """,
            (status, status, account_code, account_code, period, period),
        )
        return [dict(row) for row in rows]

    def reconciliation(self, recon_id: str) -> dict | None:
        row = self._conn.execute("SELECT * FROM reconciliations WHERE recon_id = ?", (recon_id,)).fetchone()
        return dict(row) if row else None

    def invoices(self, kind: str) -> list[dict]:
        if kind == "ap":
            sql = """
                SELECT invoice_id, vendor AS name, invoice_date, due_date, department,
                       description, amount_cents, open_cents
                FROM ap_invoices
                ORDER BY due_date, invoice_id
            """
        elif kind == "ar":
            sql = """
                SELECT invoice_id, customer AS name, invoice_date, due_date, department,
                       description, amount_cents, open_cents
                FROM ar_invoices
                ORDER BY due_date, invoice_id
            """
        else:
            raise ValueError("kind must be 'ap' or 'ar'")
        return [dict(row) for row in self._conn.execute(sql)]


def open_ledger(data_dir: Path | None = None) -> Ledger:
    return Ledger(data_dir)


def natural_balance(normal: str, debit_cents: int, credit_cents: int) -> int:
    if normal == "debit":
        return debit_cents - credit_cents
    return credit_cents - debit_cents


def presentation_columns(normal: str, natural_cents: int) -> tuple[int, int]:
    """Classic trial-balance columns. A normal balance sits on its own side."""
    if natural_cents >= 0:
        if normal == "debit":
            return natural_cents, 0
        return 0, natural_cents
    if normal == "debit":
        return 0, -natural_cents
    return -natural_cents, 0


def cash_bank_proof(book_cash_cents: int, statement_cents: int, items: list[dict]) -> dict:
    """Bank reconciliation using open cash items only.

    Adjusted bank = statement + deposits in transit - outstanding checks.
    Adjusted book = book cash - unrecorded bank fees.
    """
    open_items = [item for item in items if item["status"] == "open"]

    def total(item_type: str) -> int:
        return sum(item["amount_cents"] for item in open_items if item["item_type"] == item_type)

    deposits = total("deposit_in_transit")
    checks = total("outstanding_check")
    fees = total("unrecorded_bank_fee")
    adjusted_bank = statement_cents + deposits - checks
    adjusted_book = book_cash_cents - fees
    return {
        "book_cash_cents": book_cash_cents,
        "statement_cents": statement_cents,
        "deposits_in_transit_cents": deposits,
        "outstanding_checks_cents": checks,
        "unrecorded_bank_fees_cents": fees,
        "adjusted_bank_cents": adjusted_bank,
        "adjusted_book_cents": adjusted_book,
        "ties": adjusted_bank == adjusted_book,
    }


def _load(data_dir: Path) -> sqlite3.Connection:
    missing = [name for name in FILES if not (data_dir / f"{name}.csv").is_file()]
    if missing:
        raise FileNotFoundError(f"Synthetic books are missing {missing} in {data_dir}")
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(_SCHEMA)
    for name in FILES:
        _import_csv(conn, name, data_dir / f"{name}.csv")
    conn.execute("PRAGMA query_only = ON")
    return conn


def _import_csv(conn: sqlite3.Connection, table: str, path: Path) -> None:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        if reader.fieldnames is None:
            raise ValueError(f"{path} has no header")
        columns = list(reader.fieldnames)
    if not rows:
        return
    placeholders = ", ".join("?" for _ in columns)
    sql = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})"
    payload = [tuple(_coerce(table, column, row[column]) for column in columns) for row in rows]
    conn.executemany(sql, payload)


def _coerce(table: str, column: str, value: str) -> object:
    if value == "" and column == "department":
        return None
    if column.endswith("_cents") or column in {
        "sort_key",
        "year",
        "month",
        "line_id",
        "line_no",
        "active",
    }:
        return int(value)
    return value


def _validate(conn: sqlite3.Connection) -> None:
    unbalanced = conn.execute(
        """
        SELECT e.entry_id
        FROM journal_entries e
        JOIN journal_lines l ON l.entry_id = e.entry_id
        GROUP BY e.entry_id
        HAVING SUM(l.debit_cents) != SUM(l.credit_cents)
        """
    ).fetchall()
    if unbalanced:
        ids = ", ".join(row["entry_id"] for row in unbalanced)
        raise ValueError(f"Unbalanced journal entries in the synthetic books: {ids}")

    bad_department = conn.execute(
        """
        SELECT l.entry_id, l.line_no
        FROM journal_lines l
        JOIN accounts a ON a.code = l.account_code
        WHERE (a.statement = 'income_statement' AND l.department IS NULL)
           OR (a.statement = 'balance_sheet' AND l.department IS NOT NULL)
        """
    ).fetchall()
    if bad_department:
        raise ValueError("A synthetic journal line has the wrong department treatment")

    outside = conn.execute(
        """
        SELECT e.entry_id
        FROM journal_entries e
        JOIN periods p ON p.period = e.period
        WHERE e.entry_date < p.start_date OR e.entry_date > p.end_date
        """
    ).fetchall()
    if outside:
        raise ValueError("A synthetic journal date falls outside its period")

    meta = {row["key"]: row["value"] for row in conn.execute("SELECT key, value FROM meta")}
    as_of = meta["as_of_period"]
    sort_key = conn.execute("SELECT sort_key FROM periods WHERE period = ?", (as_of,)).fetchone()["sort_key"]

    def balance(code: str) -> int:
        normal = conn.execute("SELECT normal_balance FROM accounts WHERE code = ?", (code,)).fetchone()[
            "normal_balance"
        ]
        row = conn.execute(
            """
            SELECT COALESCE(SUM(l.debit_cents), 0) AS debit_cents,
                   COALESCE(SUM(l.credit_cents), 0) AS credit_cents
            FROM journal_lines l
            JOIN journal_entries e ON e.entry_id = l.entry_id
            JOIN periods p ON p.period = e.period
            WHERE l.account_code = ? AND p.sort_key <= ?
            """,
            (code, sort_key),
        ).fetchone()
        return natural_balance(normal, row["debit_cents"], row["credit_cents"])

    ar_open = conn.execute("SELECT COALESCE(SUM(open_cents), 0) AS n FROM ar_invoices").fetchone()["n"]
    ap_open = conn.execute("SELECT COALESCE(SUM(open_cents), 0) AS n FROM ap_invoices").fetchone()["n"]
    if balance("1100") != ar_open or int(meta["ending_ar_cents"]) != ar_open:
        raise ValueError("AR open items do not tie to the receivable control account")
    if balance("2000") != ap_open or int(meta["ending_ap_cents"]) != ap_open:
        raise ValueError("AP open items do not tie to the payable control account")

    cash_items = [dict(row) for row in conn.execute("SELECT * FROM reconciliations WHERE account_code = '1000'")]
    proof = cash_bank_proof(balance("1000"), int(meta["bank_statement_cents"]), cash_items)
    if not proof["ties"]:
        raise ValueError("Cash does not tie to the synthetic bank statement")


def _like_contains(text: str) -> str:
    escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"
