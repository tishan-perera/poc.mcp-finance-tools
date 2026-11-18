"""No tool, server, or viewer source writes the ledger."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (
    ROOT / "src" / "mcp_finance_tools" / "tools.py",
    ROOT / "src" / "mcp_finance_tools" / "server.py",
    ROOT / "src" / "mcp_finance_tools" / "viewer.py",
)
# English in a docstring ("does not insert") is fine. These are SQL write statements.
FORBIDDEN = ("INSERT INTO", "UPDATE ", "DELETE FROM", "DROP TABLE", "DROP INDEX", "ALTER TABLE")


def test_tooling_source_has_no_write_sql():
    for path in SOURCE:
        text = path.read_text(encoding="utf-8").upper()
        for word in FORBIDDEN:
            assert word not in text, f"{path.name} contains {word}"
