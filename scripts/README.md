# scripts/

| File | What it does |
|---|---|
| [generate_synthetic_books.py](generate_synthetic_books.py) | Writes the fictional Halden & Quay CSV ledger. `--check` fails if the committed CSV has drifted from this story. Standard library only. |
| [demo_client.py](demo_client.py) | Starts the MCP server over stdio, calls every tool, and prints a Markdown transcript. |

```bash
uv run python scripts/generate_synthetic_books.py --check
uv run python scripts/demo_client.py > docs/transcript.md
```
