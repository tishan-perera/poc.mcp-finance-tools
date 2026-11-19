"""The local viewer renders the same read-only results."""

import threading
from http.server import ThreadingHTTPServer
from urllib.request import urlopen

from mcp_finance_tools.viewer import Handler


def _serve():
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def test_viewer_pages_show_synthetic_books():
    server = _serve()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        checks = {
            "/": ("balanced", "270,500.00", "Synthetic"),
            "/journals?text=heat+wave": ("August heat wave", "JE-"),
            "/recon?account=1000": ("ties", "REC-CASH-01"),
            "/variance?period=2026-06&department=SALES": ("unfavorable", "Travel"),
            "/aging?subledger=ar": ("Redcedar Assembly", "Ties to GL"),
            "/draft?example=software": ("DRAFT - not posted", "Posted: False"),
            "/draft?example=unbalanced": ("NOT POSTED", "out of balance"),
        }
        for path, snippets in checks.items():
            body = urlopen(base + path).read().decode()
            for snippet in snippets:
                assert snippet in body, path
        assert not hasattr(Handler, "do_POST")
    finally:
        server.shutdown()
