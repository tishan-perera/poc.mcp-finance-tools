"""The MCP server advertises read-only tools and answers a real client."""

import json

import anyio
import pytest

pytest.importorskip("mcp")
from mcp import Client  # noqa: E402

from mcp_finance_tools.server import mcp  # noqa: E402

EXPECTED = {
    "lookup_gl_account",
    "get_trial_balance",
    "search_journal_entries",
    "list_open_reconciliations",
    "get_budget_variance",
    "get_ap_ar_aging",
    "draft_adjusting_entry",
}


def _payload(result) -> dict:
    structured = getattr(result, "structured_content", None)
    if isinstance(structured, dict) and "ok" in structured:
        return structured
    text = next(block.text for block in result.content if hasattr(block, "text"))
    parsed = json.loads(text)
    if isinstance(parsed, dict) and "ok" in parsed:
        return parsed
    return parsed["result"]


async def _session():
    async with Client(mcp) as client:
        listing = await client.list_tools()
        trial = await client.call_tool("get_trial_balance", {"period": "2026-09"})
        draft = await client.call_tool(
            "draft_adjusting_entry",
            {
                "period": "2026-10",
                "memo": "Accrue invoice PPS-7781.",
                "support_recon_id": "REC-AP-01",
                "lines": [
                    {
                        "account_code": "6300",
                        "department": "ENG",
                        "debit": "7800.00",
                        "credit": "0",
                        "memo": "Support",
                    },
                    {
                        "account_code": "2100",
                        "debit": "0",
                        "credit": "7800.00",
                        "memo": "Accrual",
                    },
                ],
            },
        )
        return listing, trial, draft


def test_server_lists_read_only_tools_and_does_not_post():
    listing, trial, draft = anyio.run(_session)
    tools = listing.tools
    assert {tool.name for tool in tools} == EXPECTED
    for tool in tools:
        assert tool.annotations is not None
        assert tool.annotations.read_only_hint is True
        assert tool.annotations.destructive_hint is False
        assert tool.annotations.open_world_hint is False
        assert tool.description
        assert tool.input_schema["type"] == "object"
        assert tool.input_schema["properties"]
    described = next(tool for tool in tools if tool.name == "draft_adjusting_entry")
    assert "does not post" in described.description
    assert "lines" in described.input_schema["properties"]
    trial_body = _payload(trial)
    assert trial_body["totals"]["balanced"] is True
    draft_body = _payload(draft)
    assert draft_body["posted"] is False
    assert draft_body["draft_id"].startswith("DRAFT-")
