"""MCP server: read-only finance tools over the synthetic Halden & Quay books.

The process speaks MCP on stdin/stdout. It does not open a port, and it does
not take an API key. Drafts are returned to the caller. They are not posted.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from mcp_finance_tools import __version__, tools
from mcp_finance_tools.ledger import open_ledger

try:  # MCP Python SDK 2.x
    from mcp.server import MCPServer as _Server
except ImportError:  # SDK 1.x
    from mcp.server.fastmcp import FastMCP as _Server

from mcp.types import ToolAnnotations

# Hints for clients. The guarantee is the code: there is no write method.
READ_ONLY = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)

mcp = _Server(
    "finance-tools",
    instructions=(
        "Read-only tools over the synthetic books of the fictional company "
        "Halden & Quay Supply, Inc. Every figure is invented. You cannot post, "
        "edit, or delete ledger records. draft_adjusting_entry returns a proposal "
        "for a person to review. It does not post."
    ),
    version=__version__,
)


class DraftLine(BaseModel):
    """One side of a proposed adjusting entry. Amounts are US dollars, not cents."""

    model_config = ConfigDict(extra="forbid")

    account_code: Annotated[
        str,
        Field(pattern=r"^\d{4}$", description="GL account code, for example 6300."),
    ]
    department: Annotated[
        str | None,
        Field(
            pattern=r"^[A-Z]{2,8}$",
            description=(
                "Department code such as SALES, MKTG, OPS, ENG, FIN, or PPL. "
                "Required on income-statement accounts. Omit on balance-sheet accounts."
            ),
        ),
    ] = None
    debit: Annotated[
        str | float | int,
        Field(description="Debit in USD. Use 0 on a credit line. At most 2 decimal places."),
    ]
    credit: Annotated[
        str | float | int,
        Field(description="Credit in USD. Use 0 on a debit line. At most 2 decimal places."),
    ]
    memo: Annotated[str, Field(min_length=1, max_length=200, description="What this line is for.")]


@mcp.tool(title="Look up a GL account", annotations=READ_ONLY)
def lookup_gl_account(
    query: Annotated[
        str,
        Field(description="Account code or part of an account name. Example: 1000 or cash."),
    ],
    period: Annotated[
        str | None,
        Field(
            pattern=r"^\d{4}-\d{2}$",
            description="Balances through this period (YYYY-MM). Defaults to the dataset close, 2026-09.",
        ),
    ] = None,
) -> dict:
    """Look up GL accounts in the synthetic ledger and return master data plus balances.

    Read-only. Matches an exact account code, or otherwise a case-insensitive
    part of the code or name. Balances are pre-close: income-statement accounts
    are activity, not closed to retained earnings.
    """
    with open_ledger() as books:
        return tools.lookup_gl_account(books, query, period)


@mcp.tool(title="Trial balance", annotations=READ_ONLY)
def get_trial_balance(
    period: Annotated[str, Field(pattern=r"^\d{4}-\d{2}$", description="Accounting period, YYYY-MM.")],
    statement: Annotated[
        Literal["all", "balance_sheet", "income_statement"],
        Field(description="Limit the rows to one statement, or return all. Totals always cover the whole book."),
    ] = "all",
) -> dict:
    """Return the pre-close trial balance for one period of the synthetic ledger.

    Read-only. Debit and credit columns are ending balances. The book is in
    balance when those two totals match. Net income in the response is a memo,
    not a posted closing entry.
    """
    with open_ledger() as books:
        return tools.get_trial_balance(books, period, statement)


@mcp.tool(title="Search journal entries", annotations=READ_ONLY)
def search_journal_entries(
    text: Annotated[
        str | None,
        Field(description="Case-sensitive substring matched against the entry description and line memos."),
    ] = None,
    account_code: Annotated[str | None, Field(description="GL account code, for example 6800.")] = None,
    department: Annotated[str | None, Field(description="Department code, for example OPS.")] = None,
    period: Annotated[str | None, Field(pattern=r"^\d{4}-\d{2}$", description="Limit to one YYYY-MM period.")] = None,
    source: Annotated[
        str | None,
        Field(
            description=(
                "Posting source: opening, billing, collection, cogs, purchase, freight, "
                "professional_services, ap_payment, payroll, rent, software, travel, "
                "marketing, utilities, depreciation, or insurance."
            )
        ),
    ] = None,
    min_amount: Annotated[
        str | float | int | None,
        Field(description="Keep lines whose debit or credit is at least this many USD."),
    ] = None,
    max_amount: Annotated[
        str | float | int | None,
        Field(description="Keep lines whose debit or credit is at most this many USD, and not zero."),
    ] = None,
    limit: Annotated[int, Field(ge=1, le=50, description="Maximum entries to return. Default 20.")] = 20,
) -> dict:
    """Search posted journal entries in the synthetic ledger.

    Read-only. With no filters, returns the latest entries up to limit.
    Every returned entry includes its lines and whether the entry balances.
    """
    with open_ledger() as books:
        return tools.search_journal_entries(
            books,
            text=text,
            account_code=account_code,
            department=department,
            period=period,
            source=source,
            min_amount=min_amount,
            max_amount=max_amount,
            limit=limit,
        )


@mcp.tool(title="Open reconciliation items", annotations=READ_ONLY)
def list_open_reconciliations(
    account_code: Annotated[
        str | None, Field(description="Limit to one GL account, for example 1000 for cash.")
    ] = None,
    period: Annotated[
        str | None,
        Field(pattern=r"^\d{4}-\d{2}$", description="Limit to items tagged to this period."),
    ] = None,
    include_cleared: Annotated[bool, Field(description="Also return items already marked cleared.")] = False,
) -> dict:
    """List reconciliation items on the synthetic ledger.

    Read-only. Cleared items are omitted unless include_cleared is true.
    A cash request also returns the bank reconciliation and whether adjusted
    book equals adjusted bank. Off-book items are support for a person. They
    are not posted by this tool.
    """
    with open_ledger() as books:
        return tools.list_open_reconciliations(books, account_code, period, include_cleared)


@mcp.tool(title="Budget versus actual", annotations=READ_ONLY)
def get_budget_variance(
    period: Annotated[
        str,
        Field(pattern=r"^\d{4}-\d{2}$", description="Operating period, 2026-01 through 2026-09."),
    ],
    department: Annotated[
        str | None,
        Field(description="Department code. Omit for every department."),
    ] = None,
    ytd: Annotated[bool, Field(description="Sum January through the period instead of the single month.")] = False,
    materiality_pct: Annotated[
        float,
        Field(
            ge=0,
            le=100,
            description="Flag a row when the absolute variance is at least this percent of budget.",
        ),
    ] = 10.0,
    materiality_amount: Annotated[
        float,
        Field(
            ge=0,
            description="Flag a row when the absolute variance is at least this many USD. Default 5000.",
        ),
    ] = 5000.0,
) -> dict:
    """Compare budget to actual for income-statement accounts in the synthetic ledger.

    Read-only. variance is actual minus budget in the account's natural sign.
    favorable_amount is positive when the variance helps earnings (more revenue,
    or less expense). A row is material when it clears either threshold.
    Cost of goods is tagged to Sales in this dataset. It is not allocated further.
    """
    with open_ledger() as books:
        return tools.get_budget_variance(
            books,
            period,
            department=department,
            ytd=ytd,
            materiality_pct=materiality_pct,
            materiality_amount=materiality_amount,
        )


@mcp.tool(title="AP and AR aging", annotations=READ_ONLY)
def get_ap_ar_aging(
    subledger: Annotated[
        Literal["ap", "ar"],
        Field(description="ap for open vendor bills, ar for open customer invoices."),
    ],
    as_of: Annotated[
        str | None,
        Field(
            description=(
                "Bucket the snapshot items as of this YYYY-MM-DD date. "
                "Defaults to 2026-09-30. Does not reconstruct historical open items."
            )
        ),
    ] = None,
    name: Annotated[
        str | None,
        Field(description="Case-insensitive substring of the vendor or customer name."),
    ] = None,
    limit: Annotated[
        int,
        Field(ge=1, le=100, description="Maximum documents to return. Totals still cover every match."),
    ] = 50,
) -> dict:
    """Age open payables or receivables on the synthetic September close.

    Read-only. On the snapshot date, with no name filter, total_open ties to
    the control account (2000 for AP, 1100 for AR). The population is that
    snapshot. A different as_of only moves items between buckets.
    """
    with open_ledger() as books:
        return tools.get_ap_ar_aging(books, subledger, as_of=as_of, name=name, limit=limit)


@mcp.tool(title="Draft an adjusting entry", annotations=READ_ONLY)
def draft_adjusting_entry(
    period: Annotated[str, Field(pattern=r"^\d{4}-\d{2}$", description="Period the proposal is for, YYYY-MM.")],
    memo: Annotated[str, Field(min_length=1, max_length=300, description="Why this entry is being proposed.")],
    lines: Annotated[
        list[DraftLine],
        Field(description="At least two lines. Debits must equal credits. Amounts are USD."),
    ],
    auto_reverse: Annotated[
        bool,
        Field(description="Also return the reversing proposal for the first day of the next month."),
    ] = True,
    support_recon_id: Annotated[
        str | None,
        Field(description="Optional open reconciliation id this draft is meant to clear, for example REC-AP-01."),
    ] = None,
    prepared_by: Annotated[
        str,
        Field(description="Label stored on the draft. This is not an approval."),
    ] = "agent",
) -> dict:
    """Draft an adjusting entry for a person to review. This does not post.

    Read-only. The response is a proposal with posted set to false. It is not
    written to the ledger, not given a journal-entry id, and not reversed in
    the books. A closed period is called out and left closed. The caller, or
    another system a person operates, would have to post it.
    """
    with open_ledger() as books:
        return tools.draft_adjusting_entry(
            books,
            period=period,
            memo=memo,
            lines=lines,
            auto_reverse=auto_reverse,
            support_recon_id=support_recon_id,
            prepared_by=prepared_by,
        )


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
