"""Finance tools as plain functions over a read-only ledger.

Nothing in this module writes a journal entry, updates a balance, or posts a
draft. ``draft_adjusting_entry`` returns a proposal and sets ``posted`` to false.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import date
from functools import wraps
from typing import Any

from mcp_finance_tools.ledger import (
    Ledger,
    cash_bank_proof,
    natural_balance,
    presentation_columns,
)
from mcp_finance_tools.money import MAX_LINE_CENTS, cents_to_decimal, decimal_to_cents

BUCKETS = (
    ("current", "Current"),
    ("1_30", "1-30 days"),
    ("31_60", "31-60 days"),
    ("61_90", "61-90 days"),
    ("over_90", "Over 90 days"),
)


class ToolProblem(Exception):
    def __init__(self, message: str, **extra: Any):
        super().__init__(message)
        self.message = message
        self.extra = extra


def _catches(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except ToolProblem as exc:
            body = {"ok": False, "synthetic": True, "error": exc.message, **exc.extra}
            if fn.__name__ == "draft_adjusting_entry":
                body["posted"] = False
                body["status"] = "NOT POSTED"
            return body

    return wrapper


def _ok(books: Ledger, **payload: Any) -> dict:
    meta = books.meta()
    return {
        "ok": True,
        "synthetic": True,
        "company": meta["company_name"],
        "currency": meta["currency"],
        "data_notice": meta["synthetic_notice"],
        **payload,
    }


def _require_period(books: Ledger, period: str) -> dict:
    row = books.period(period)
    if row is None:
        known = [item["period"] for item in books.periods()]
        raise ToolProblem(f"Unknown period '{period}'.", known_periods=known)
    return row


def _require_department(books: Ledger, department: str | None) -> None:
    if department is None:
        return
    known = [item["code"] for item in books.departments()]
    if department not in known:
        raise ToolProblem(f"Unknown department '{department}'.", known_departments=known)


def _money_map(activity: dict[str, tuple[int, int]], code: str) -> tuple[int, int]:
    return activity.get(code, (0, 0))


def _account_amounts(account: dict, ending: tuple[int, int], period_move: tuple[int, int]) -> dict:
    natural = natural_balance(account["normal_balance"], ending[0], ending[1])
    debit_col, credit_col = presentation_columns(account["normal_balance"], natural)
    return {
        "account_code": account["code"],
        "account_name": account["name"],
        "account_type": account["account_type"],
        "statement": account["statement"],
        "normal_balance": account["normal_balance"],
        "active": bool(account["active"]),
        "period_debits": cents_to_decimal(period_move[0]),
        "period_credits": cents_to_decimal(period_move[1]),
        "ending_debits": cents_to_decimal(ending[0]),
        "ending_credits": cents_to_decimal(ending[1]),
        "ending_balance": cents_to_decimal(natural),
        "debit": cents_to_decimal(debit_col),
        "credit": cents_to_decimal(credit_col),
    }


def _net_income(accounts: list[dict], activity: dict[str, tuple[int, int]]) -> int:
    total = 0
    for account in accounts:
        debit_cents, credit_cents = _money_map(activity, account["code"])
        natural = natural_balance(account["normal_balance"], debit_cents, credit_cents)
        if account["account_type"] == "revenue":
            total += natural
        elif account["account_type"] == "expense":
            total -= natural
    return total


@_catches
def lookup_gl_account(books: Ledger, query: str, period: str | None = None) -> dict:
    """Account master plus balances. Read-only."""
    text = query.strip()
    if not text:
        raise ToolProblem("Query is required.")
    meta = books.meta()
    period_row = _require_period(books, period or meta["as_of_period"])
    accounts = books.accounts()
    exact = [account for account in accounts if account["code"] == text]
    if exact:
        matches = exact
    else:
        needle = text.casefold()
        matches = [
            account
            for account in accounts
            if needle in account["code"].casefold() or needle in account["name"].casefold()
        ]
    if not matches:
        raise ToolProblem(
            f"No account matches '{query}'.",
            known_accounts=[{"code": account["code"], "name": account["name"]} for account in accounts],
        )
    ending = books.activity(through_sort=period_row["sort_key"])
    movement = books.activity(period=period_row["period"])
    return _ok(
        books,
        query=query,
        period=period_row["period"],
        through_date=period_row["end_date"],
        count=len(matches),
        matches=[
            _account_amounts(account, _money_map(ending, account["code"]), _money_map(movement, account["code"]))
            for account in matches
        ],
    )


@_catches
def get_trial_balance(books: Ledger, period: str, statement: str = "all") -> dict:
    """Pre-close trial balance. Read-only."""
    if statement not in {"all", "balance_sheet", "income_statement"}:
        raise ToolProblem("statement must be all, balance_sheet, or income_statement.")
    period_row = _require_period(books, period)
    accounts = books.accounts()
    ending = books.activity(through_sort=period_row["sort_key"])
    movement = books.activity(period=period_row["period"])
    rows = []
    debit_total = 0
    credit_total = 0
    for account in accounts:
        end_amounts = _money_map(ending, account["code"])
        period_amounts = _money_map(movement, account["code"])
        shaped = _account_amounts(account, end_amounts, period_amounts)
        natural = natural_balance(account["normal_balance"], end_amounts[0], end_amounts[1])
        debit_col, credit_col = presentation_columns(account["normal_balance"], natural)
        debit_total += debit_col
        credit_total += credit_col
        has_activity = any(end_amounts) or any(period_amounts)
        if has_activity and (statement == "all" or account["statement"] == statement):
            rows.append(shaped)
    return _ok(
        books,
        period=period_row["period"],
        period_status=period_row["status"],
        through_date=period_row["end_date"],
        basis=books.meta()["books_basis"],
        row_filter=statement,
        rows=rows,
        totals={
            "debit": cents_to_decimal(debit_total),
            "credit": cents_to_decimal(credit_total),
            "balanced": debit_total == credit_total,
            "note": "Totals are the whole pre-close trial balance, including rows hidden by a statement filter.",
        },
        net_income={
            "period": cents_to_decimal(_net_income(accounts, movement)),
            "ytd": cents_to_decimal(_net_income(accounts, ending)),
            "note": "Memo only. Not a posted closing entry.",
        },
    )


@_catches
def search_journal_entries(
    books: Ledger,
    text: str | None = None,
    account_code: str | None = None,
    department: str | None = None,
    period: str | None = None,
    source: str | None = None,
    min_amount: object = None,
    max_amount: object = None,
    limit: int = 20,
) -> dict:
    """Search posted journal entries. Read-only."""
    if period:
        _require_period(books, period)
    _require_department(books, department)
    if account_code and books.account(account_code) is None:
        raise ToolProblem(f"Unknown account '{account_code}'.")
    if limit < 1 or limit > 50:
        raise ToolProblem("limit must be from 1 to 50.")
    try:
        min_cents = None if min_amount is None else decimal_to_cents(min_amount)
        max_cents = None if max_amount is None else decimal_to_cents(max_amount)
    except ValueError as exc:
        raise ToolProblem(str(exc)) from exc
    count, entries = books.search(
        text=text or None,
        account_code=account_code,
        department=department,
        period=period,
        source=source,
        min_cents=min_cents,
        max_cents=max_cents,
        limit=limit,
    )
    shaped = []
    for entry in entries:
        debits = sum(line["debit_cents"] for line in entry["lines"])
        credits = sum(line["credit_cents"] for line in entry["lines"])
        shaped.append(
            {
                "entry_id": entry["entry_id"],
                "period": entry["period"],
                "entry_date": entry["entry_date"],
                "source": entry["source"],
                "description": entry["description"],
                "balanced": debits == credits,
                "total_debits": cents_to_decimal(debits),
                "total_credits": cents_to_decimal(credits),
                "lines": [
                    {
                        "line_no": line["line_no"],
                        "account_code": line["account_code"],
                        "account_name": line["account_name"],
                        "department": line["department"],
                        "debit": cents_to_decimal(line["debit_cents"]),
                        "credit": cents_to_decimal(line["credit_cents"]),
                        "memo": line["memo"],
                    }
                    for line in entry["lines"]
                ],
            }
        )
    return _ok(
        books,
        match_count=count,
        returned=len(shaped),
        limit=limit,
        entries=shaped,
    )


@_catches
def list_open_reconciliations(
    books: Ledger,
    account_code: str | None = None,
    period: str | None = None,
    include_cleared: bool = False,
) -> dict:
    """Open reconciliation items, plus the cash-to-bank proof. Read-only."""
    if account_code and books.account(account_code) is None:
        raise ToolProblem(f"Unknown account '{account_code}'.")
    if period:
        _require_period(books, period)
    status = None if include_cleared else "open"
    items = books.reconciliations(status=status, account_code=account_code, period=period)
    payload: dict[str, Any] = {
        "count": len(items),
        "include_cleared": include_cleared,
        "items": [_recon_item(item) for item in items],
    }
    if account_code in (None, "1000"):
        payload["cash_bank_reconciliation"] = _cash_proof(books)
    return _ok(books, **payload)


def _recon_item(item: dict) -> dict:
    return {
        "recon_id": item["recon_id"],
        "account_code": item["account_code"],
        "period": item["period"],
        "item_type": item["item_type"],
        "description": item["description"],
        "amount": cents_to_decimal(item["amount_cents"]),
        "status": item["status"],
        "owner_role": item["owner_role"],
    }


def _cash_proof(books: Ledger) -> dict:
    meta = books.meta()
    as_of = books.period(meta["as_of_period"])
    ending = books.activity(through_sort=as_of["sort_key"])
    cash_account = books.account("1000")
    assert cash_account is not None
    book = natural_balance(cash_account["normal_balance"], *_money_map(ending, "1000"))
    items = books.reconciliations(status=None, account_code="1000", period=None)
    proof = cash_bank_proof(book, int(meta["bank_statement_cents"]), items)
    return {
        "as_of": meta["as_of_date"],
        "book_cash": cents_to_decimal(proof["book_cash_cents"]),
        "bank_statement": cents_to_decimal(proof["statement_cents"]),
        "deposits_in_transit": cents_to_decimal(proof["deposits_in_transit_cents"]),
        "outstanding_checks": cents_to_decimal(proof["outstanding_checks_cents"]),
        "unrecorded_bank_fees": cents_to_decimal(proof["unrecorded_bank_fees_cents"]),
        "adjusted_book": cents_to_decimal(proof["adjusted_book_cents"]),
        "adjusted_bank": cents_to_decimal(proof["adjusted_bank_cents"]),
        "ties": proof["ties"],
        "note": "Adjusted book equals adjusted bank when ties is true. Synthetic statement.",
    }


@_catches
def get_budget_variance(
    books: Ledger,
    period: str,
    department: str | None = None,
    ytd: bool = False,
    materiality_pct: float = 10.0,
    materiality_amount: float = 5000.0,
) -> dict:
    """Budget versus actual for income-statement accounts. Read-only.

    ``variance`` is actual minus budget, in the natural sign of the account
    (revenue credit, expense debit). ``favorable_amount`` is positive when the
    variance helps earnings: higher revenue, or lower expense.
    """
    period_row = _require_period(books, period)
    if period_row["kind"] != "operating":
        raise ToolProblem(
            f"No operating budget is loaded for {period}. The synthetic budget covers 2026-01 through 2026-09."
        )
    _require_department(books, department)
    if materiality_pct < 0 or materiality_pct > 100:
        raise ToolProblem("materiality_pct must be from 0 to 100.")
    try:
        material_cents = decimal_to_cents(materiality_amount)
    except ValueError as exc:
        raise ToolProblem(str(exc)) from exc
    if material_cents < 0:
        raise ToolProblem("materiality_amount cannot be negative.")
    if ytd:
        start = books.period("2026-01")
        if start is None:
            raise ToolProblem("2026-01 is missing from the synthetic books.")
        start_sort = start["sort_key"]
    else:
        start_sort = period_row["sort_key"]
    accounts = {account["code"]: account for account in books.accounts()}
    actual_rows = books.income_actuals(start_sort, period_row["sort_key"], department)
    budget_rows = books.budgets(start_sort, period_row["sort_key"], department)
    keys = {(row["department"], row["account_code"]) for row in actual_rows}
    keys.update((row["department"], row["account_code"]) for row in budget_rows)
    actual_map = {
        (row["department"], row["account_code"]): natural_balance(
            accounts[row["account_code"]]["normal_balance"], row["debit_cents"], row["credit_cents"]
        )
        for row in actual_rows
    }
    budget_map = {(row["department"], row["account_code"]): row["amount_cents"] for row in budget_rows}
    lines = []
    for key in sorted(keys):
        dept, code = key
        account = accounts[code]
        actual = actual_map.get(key, 0)
        budget = budget_map.get(key, 0)
        if actual == 0 and budget == 0:
            continue
        variance = actual - budget
        favorable_amount = variance if account["account_type"] == "revenue" else -variance
        if variance == 0:
            direction = "flat"
        elif favorable_amount > 0:
            direction = "favorable"
        else:
            direction = "unfavorable"
        lines.append(
            {
                "department": dept,
                "account_code": code,
                "account_name": account["name"],
                "account_type": account["account_type"],
                "actual": cents_to_decimal(actual),
                "budget": cents_to_decimal(budget),
                "variance": cents_to_decimal(variance),
                "favorable_amount": cents_to_decimal(favorable_amount),
                "direction": direction,
                "material": _is_material(variance, budget, materiality_pct, material_cents),
            }
        )
    return _ok(
        books,
        period=period_row["period"],
        ytd=ytd,
        department=department,
        materiality_pct=materiality_pct,
        materiality_amount=cents_to_decimal(material_cents),
        rows=lines,
        totals=_variance_totals(lines),
        material_rows=[row for row in lines if row["material"] and row["direction"] != "flat"],
    )


def _is_material(variance: int, budget: int, pct: float, amount_cents: int) -> bool:
    if variance == 0:
        return False
    if abs(variance) >= amount_cents:
        return True
    if budget == 0:
        return True
    return abs(variance) * 100 >= abs(budget) * pct


def _variance_totals(lines: list[dict]) -> dict:
    def cents(field: str) -> int:
        total = 0
        for line in lines:
            text = line[field]
            sign = -1 if text.startswith("-") else 1
            whole, frac = text.lstrip("-").split(".")
            total += sign * (int(whole) * 100 + int(frac))
        return total

    favorable = cents("favorable_amount")
    return {
        "actual": cents_to_decimal(cents("actual")),
        "budget": cents_to_decimal(cents("budget")),
        "favorable_amount": cents_to_decimal(favorable),
        "direction": "flat" if favorable == 0 else "favorable" if favorable > 0 else "unfavorable",
        "note": (
            "favorable_amount is positive when the mix of revenue and expense variances helps earnings. "
            "Actual and budget here add natural amounts across accounts, so that pair is not a profit total."
        ),
    }


@_catches
def get_ap_ar_aging(
    books: Ledger,
    subledger: str,
    as_of: str | None = None,
    name: str | None = None,
    limit: int = 50,
) -> dict:
    """Open AP or AR items in aging buckets. Read-only.

    The open-item population is the snapshot at the dataset as-of date. Passing
    another ``as_of`` only rebuckets those same items. It does not reconstruct
    history. The total ties to the control account on the snapshot date, with
    no name filter.
    """
    if subledger not in {"ap", "ar"}:
        raise ToolProblem("subledger must be 'ap' or 'ar'.")
    if limit < 1 or limit > 100:
        raise ToolProblem("limit must be from 1 to 100.")
    meta = books.meta()
    snapshot = date.fromisoformat(meta["as_of_date"])
    try:
        as_of_date = snapshot if as_of is None else date.fromisoformat(as_of)
    except ValueError as exc:
        raise ToolProblem("as_of must be a date in YYYY-MM-DD form.") from exc
    needle = name.casefold().strip() if name else None
    documents = []
    for invoice in books.invoices(subledger):
        if needle and needle not in invoice["name"].casefold():
            continue
        due = date.fromisoformat(invoice["due_date"])
        age = (as_of_date - due).days
        documents.append(
            {
                "invoice_id": invoice["invoice_id"],
                "name": invoice["name"],
                "invoice_date": invoice["invoice_date"],
                "due_date": invoice["due_date"],
                "department": invoice["department"],
                "description": invoice["description"],
                "open_amount": cents_to_decimal(invoice["open_cents"]),
                "open_cents": invoice["open_cents"],
                "days_past_due": max(age, 0),
                "days_until_due": max(-age, 0),
                "bucket": _bucket(age),
            }
        )
    bucket_rows = []
    for key, label in BUCKETS:
        members = [doc for doc in documents if doc["bucket"] == key]
        bucket_rows.append(
            {
                "bucket": key,
                "label": label,
                "count": len(members),
                "amount": cents_to_decimal(sum(doc["open_cents"] for doc in members)),
            }
        )
    total = sum(doc["open_cents"] for doc in documents)
    control = "2000" if subledger == "ap" else "1100"
    gl_cents = _control_balance(books, control)
    on_snapshot = as_of_date == snapshot and needle is None
    shown = documents[:limit]
    for doc in shown:
        doc.pop("open_cents")
    return _ok(
        books,
        subledger=subledger,
        as_of=as_of_date.isoformat(),
        snapshot_as_of=snapshot.isoformat(),
        snapshot_note=(
            "Open items are the books at the snapshot date. "
            "A different as_of only changes which bucket those items fall into."
        ),
        control_account=control,
        buckets=bucket_rows,
        total_open=cents_to_decimal(total),
        gl_balance=cents_to_decimal(gl_cents),
        ties_to_gl=on_snapshot and total == gl_cents,
        documents=shown,
        documents_returned=len(shown),
        documents_omitted=max(len(documents) - len(shown), 0),
    )


def _bucket(age_days: int) -> str:
    if age_days <= 0:
        return "current"
    if age_days <= 30:
        return "1_30"
    if age_days <= 60:
        return "31_60"
    if age_days <= 90:
        return "61_90"
    return "over_90"


def _control_balance(books: Ledger, code: str) -> int:
    meta = books.meta()
    period = books.period(meta["as_of_period"])
    assert period is not None
    account = books.account(code)
    assert account is not None
    ending = books.activity(through_sort=period["sort_key"])
    return natural_balance(account["normal_balance"], *_money_map(ending, code))


@_catches
def draft_adjusting_entry(
    books: Ledger,
    period: str,
    memo: str,
    lines: list,
    auto_reverse: bool = True,
    support_recon_id: str | None = None,
    prepared_by: str = "agent",
) -> dict:
    """Validate a proposed adjusting entry and return it as a draft.

    This function does not insert a journal entry. ``posted`` is always false.
    """
    text = memo.strip()
    if not text:
        raise ToolProblem("Memo is required.")
    if len(text) > 300:
        raise ToolProblem("Memo must be 300 characters or fewer.")
    author = prepared_by.strip() or "agent"
    if len(author) > 80:
        raise ToolProblem("prepared_by must be 80 characters or fewer.")
    period_row = _require_period(books, period)
    if not isinstance(lines, list) or len(lines) < 2:
        raise ToolProblem("An adjusting entry needs at least two lines.")
    if len(lines) > 12:
        raise ToolProblem("An adjusting entry can have at most 12 lines.")
    parsed = [_parse_line(books, line, index) for index, line in enumerate(lines, start=1)]
    debits = sum(line["debit_cents"] for line in parsed)
    credits = sum(line["credit_cents"] for line in parsed)
    if debits != credits:
        raise ToolProblem(
            f"Entry is out of balance by {cents_to_decimal(abs(debits - credits))}.",
            debits=cents_to_decimal(debits),
            credits=cents_to_decimal(credits),
        )
    if debits == 0:
        raise ToolProblem("Entry total must be greater than zero.")

    warnings: list[str] = []
    if period_row["status"] != "open":
        warnings.append(f"Period {period} is {period_row['status']}. This draft does not reopen it or post to it.")
    support = None
    if support_recon_id:
        found = books.reconciliation(support_recon_id)
        if found is None:
            raise ToolProblem(f"Unknown reconciliation item '{support_recon_id}'.")
        support = _recon_item(found)
        if found["status"] != "open":
            warnings.append(f"{support_recon_id} is not an open item.")
        if found["amount_cents"] != debits:
            warnings.append(
                f"Draft total {cents_to_decimal(debits)} does not match "
                f"{support_recon_id} amount {cents_to_decimal(found['amount_cents'])}."
            )

    entry_date = period_row["start_date"] if period_row["kind"] == "future" else period_row["end_date"]
    entry = _public_entry(period, entry_date, text, parsed)
    reversal = None
    reversal_date = _first_of_next_month(period)
    if auto_reverse:
        flipped = [_flip(line) for line in parsed]
        reversal = _public_entry(
            reversal_date[:7],
            reversal_date,
            f"Reversal of draft: {text}",
            flipped,
        )
        if books.period(reversal_date[:7]) is None:
            warnings.append(
                f"Reversal date {reversal_date} is outside the periods loaded in this dataset. "
                "It is part of the proposal only."
            )

    identity = {
        "period": period,
        "memo": text,
        "lines": [
            {
                "account_code": line["account_code"],
                "department": line["department"],
                "debit_cents": line["debit_cents"],
                "credit_cents": line["credit_cents"],
                "memo": line["memo"],
            }
            for line in parsed
        ],
        "auto_reverse": auto_reverse,
        "support_recon_id": support_recon_id,
    }
    digest = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()[:12].upper()
    return _ok(
        books,
        posted=False,
        status="DRAFT - not posted. A person has to review this and post it in the ledger.",
        draft_id=f"DRAFT-{digest}",
        prepared_by=author,
        period=period,
        memo=text,
        auto_reverse=auto_reverse,
        warnings=warnings,
        support=support,
        entry=entry,
        reversal=reversal,
    )


def _parse_line(books: Ledger, raw: object, index: int) -> dict:
    if hasattr(raw, "model_dump"):
        data = raw.model_dump()
    elif isinstance(raw, Mapping):
        data = dict(raw)
    else:
        raise ToolProblem(f"Line {index} must be an object.")
    try:
        account_code = str(data["account_code"]).strip()
        memo = str(data["memo"]).strip()
        department = data.get("department")
        debit = decimal_to_cents(data["debit"])
        credit = decimal_to_cents(data["credit"])
    except KeyError as exc:
        raise ToolProblem(f"Line {index} is missing {exc.args[0]}.") from exc
    except ValueError as exc:
        raise ToolProblem(f"Line {index}: {exc}") from exc
    if department == "":
        department = None
    if department is not None:
        department = str(department).strip()
    if not memo:
        raise ToolProblem(f"Line {index} needs a memo.")
    if debit < 0 or credit < 0:
        raise ToolProblem(f"Line {index} cannot use a negative amount.")
    if debit > MAX_LINE_CENTS or credit > MAX_LINE_CENTS:
        raise ToolProblem(f"Line {index} exceeds the $10000000.00 line cap.")
    if (debit == 0) == (credit == 0):
        raise ToolProblem(f"Line {index} needs one positive side and a zero on the other.")
    account = books.account(account_code)
    if account is None or not account["active"]:
        raise ToolProblem(f"Line {index} uses unknown account '{account_code}'.")
    if account["statement"] == "income_statement":
        if not department:
            raise ToolProblem(f"Line {index} is income statement account {account_code} and needs a department.")
        _require_department(books, department)
    elif department:
        raise ToolProblem(f"Line {index} is balance sheet account {account_code}. Leave department empty.")
    return {
        "account_code": account_code,
        "account_name": account["name"],
        "department": department,
        "debit_cents": debit,
        "credit_cents": credit,
        "memo": memo,
    }


def _flip(line: dict) -> dict:
    return {
        **line,
        "debit_cents": line["credit_cents"],
        "credit_cents": line["debit_cents"],
        "memo": f"Reversal: {line['memo']}",
    }


def _public_entry(period: str, entry_date: str, description: str, lines: list[dict]) -> dict:
    debits = sum(line["debit_cents"] for line in lines)
    credits = sum(line["credit_cents"] for line in lines)
    return {
        "period": period,
        "entry_date": entry_date,
        "description": description,
        "balanced": debits == credits,
        "total_debits": cents_to_decimal(debits),
        "total_credits": cents_to_decimal(credits),
        "lines": [
            {
                "line_no": index,
                "account_code": line["account_code"],
                "account_name": line["account_name"],
                "department": line["department"],
                "debit": cents_to_decimal(line["debit_cents"]),
                "credit": cents_to_decimal(line["credit_cents"]),
                "memo": line["memo"],
            }
            for index, line in enumerate(lines, start=1)
        ],
    }


def _first_of_next_month(period: str) -> str:
    year, month = (int(part) for part in period.split("-"))
    month += 1
    if month == 13:
        year += 1
        month = 1
    return f"{year:04d}-{month:02d}-01"
