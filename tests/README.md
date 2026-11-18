# tests/

No network, no API key, and no write against the CSV.

| File | What it checks |
|---|---|
| [test_ledger.py](test_ledger.py) | The public ledger API is read-only, SQLite rejects writes after load, and the snapshot totals match the story. |
| [test_tools.py](test_tools.py) | Trial balance foots, journal search, bank tie-out, variance signs, aging buckets, and drafts that stay unposted. The CSV hash is unchanged after a draft. |
| [test_generate.py](test_generate.py) | Regenerating the books matches the committed CSV. |
| [test_server.py](test_server.py) | A real MCP client lists the tools, sees `readOnlyHint`, and a draft call returns `posted: false`. |
| [test_viewer.py](test_viewer.py) | The local pages render the same results, including the unbalanced draft refusal. |
| [test_readonly.py](test_readonly.py) | The tool, server, and viewer source contain no SQL write statements. |
