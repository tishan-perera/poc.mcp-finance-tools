"""Call every finance tool the way an MCP client would, and print a transcript.

uv run python scripts/demo_client.py > docs/transcript.md
"""

from __future__ import annotations

import json
import os
import sys

import anyio
from mcp import Client
from mcp.client.stdio import StdioServerParameters

SOFTWARE_DRAFT = {
    "period": "2026-10",
    "memo": "Accrue September software support invoice PPS-7781, not yet recorded.",
    "support_recon_id": "REC-AP-01",
    "auto_reverse": True,
    "prepared_by": "demo-client",
    "lines": [
        {
            "account_code": "6300",
            "department": "ENG",
            "debit": "7800.00",
            "credit": "0.00",
            "memo": "Paper & Pixel September support",
        },
        {
            "account_code": "2100",
            "debit": "0.00",
            "credit": "7800.00",
            "memo": "Accrued expense",
        },
    ],
}

UNBALANCED_DRAFT = {
    "period": "2026-10",
    "memo": "Intentionally unbalanced preview.",
    "auto_reverse": False,
    "lines": [
        {
            "account_code": "6950",
            "department": "FIN",
            "debit": "85.00",
            "credit": "0.00",
            "memo": "Bank fee",
        },
        {
            "account_code": "1000",
            "debit": "0.00",
            "credit": "80.00",
            "memo": "Cash",
        },
    ],
}

CALLS = [
    ("lookup_gl_account", {"query": "cash"}),
    ("get_trial_balance", {"period": "2026-09", "statement": "balance_sheet"}),
    ("search_journal_entries", {"text": "heat wave"}),
    ("list_open_reconciliations", {"account_code": "1000"}),
    ("get_budget_variance", {"period": "2026-06", "department": "SALES", "ytd": False}),
    ("get_ap_ar_aging", {"subledger": "ar"}),
    ("draft_adjusting_entry", SOFTWARE_DRAFT),
    ("draft_adjusting_entry", UNBALANCED_DRAFT),
]


def _child_env() -> dict[str, str]:
    keep = ("PATH", "HOME", "LANG", "LC_ALL", "VIRTUAL_ENV", "UV_PROJECT_ENVIRONMENT")
    env = {key: os.environ[key] for key in keep if key in os.environ}
    env["PYTHONPATH"] = os.pathsep.join(sys.path)
    return env


def _payload(result) -> str:
    structured = getattr(result, "structured_content", None)
    if isinstance(structured, dict):
        return json.dumps(structured, indent=2)
    text = "\n".join(block.text for block in result.content if hasattr(block, "text"))
    try:
        return json.dumps(json.loads(text), indent=2)
    except ValueError:
        return text


async def main() -> None:
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "mcp_finance_tools"],
        env=_child_env(),
    )
    async with Client(params) as client:
        listing = await client.list_tools()
        print("# MCP transcript (synthetic books)\n")
        print(
            "Halden & Quay Supply, Inc. is fictional. The client below is a real "
            "MCP session over stdio. No API key is set. The draft calls do not post.\n"
        )
        print("Tools the server advertises:\n")
        for tool in listing.tools:
            annotations = tool.annotations
            read_only = getattr(annotations, "read_only_hint", None)
            description = " ".join((tool.description or "").split())
            print(f"- `{tool.name}` (read-only: {read_only}) - {description}")
        for name, arguments in CALLS:
            result = await client.call_tool(name, arguments)
            print(f"\n## `{name}`\n")
            print("Request:\n")
            print("```json")
            print(json.dumps(arguments, indent=2))
            print("```\n")
            print("Response:\n")
            print("```json")
            print(_payload(result))
            print("```")


if __name__ == "__main__":
    anyio.run(main)
