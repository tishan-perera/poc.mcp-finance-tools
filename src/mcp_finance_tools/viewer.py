"""A small read-only page for the same functions the MCP server exposes.

    uv run mcp-finance-viewer

Then open http://127.0.0.1:8765. Uses only the Python standard library.
The draft page previews a proposal. It does not post.
"""

from __future__ import annotations

import html
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from mcp_finance_tools import tools
from mcp_finance_tools.ledger import open_ledger

CSS = """
:root { --paper:#f3efe6; --card:#fffdf8; --ink:#1c2430; --muted:#5e6872; --line:#e2d9cc;
        --green:#0f6b4c; --greenbg:#e5f6ee; --red:#8f2d2d; --redbg:#fdecec; --amber:#8a5a12; --amberbg:#fff4df; }
* { box-sizing:border-box }
body { margin:0; font:15px/1.45 "Segoe UI", Helvetica, Arial, sans-serif; background:var(--paper); color:var(--ink) }
header { background:#16382c; color:#fff; padding:14px 22px; display:flex; gap:18px; align-items:center; flex-wrap:wrap }
header b { font-size:16px; letter-spacing:.01em }
header a { color:#c9e6da; text-decoration:none }
header a.on { color:#fff; font-weight:650 }
main { max-width:1120px; margin:20px auto 40px; padding:0 16px }
.banner { background:var(--amberbg); color:var(--amber); border:1px solid #efd7a8; border-radius:8px;
          padding:8px 12px; margin-bottom:14px; font-size:13px }
.card { background:var(--card); border:1px solid var(--line); border-radius:12px;
        padding:16px 18px; margin-bottom:16px }
h2 { margin:0 0 8px; font-size:18px }
.stats { display:flex; gap:18px; flex-wrap:wrap; margin:8px 0 12px }
.stat { min-width:140px }
.stat span { display:block; color:var(--muted); font-size:12px; text-transform:uppercase; letter-spacing:.04em }
table { width:100%; border-collapse:collapse; font-variant-numeric:tabular-nums }
th, td { text-align:left; padding:6px 8px; border-bottom:1px solid var(--line); vertical-align:top }
td:first-child { white-space:nowrap }
th { color:var(--muted); font-size:12px; text-transform:uppercase; letter-spacing:.03em }
.num { text-align:right; font-variant-numeric:tabular-nums }
.pill { display:inline-block; padding:1px 8px; border-radius:99px; font-size:12px }
.ok { background:var(--greenbg); color:var(--green) }
.bad { background:var(--redbg); color:var(--red) }
.warn { background:var(--amberbg); color:var(--amber) }
.muted { color:var(--muted) }
form { display:flex; gap:8px; flex-wrap:wrap; margin:8px 0 12px }
input, select { padding:6px 8px; border:1px solid var(--line); border-radius:6px; font:inherit; background:#fff }
button { background:#0f6b4c; color:#fff; border:0; border-radius:6px; padding:7px 12px; font:inherit }
"""

PAGES = [
    ("/", "Trial balance"),
    ("/journals", "Journals"),
    ("/recon", "Reconciliations"),
    ("/variance", "Variance"),
    ("/aging", "Aging"),
    ("/draft", "Draft entry"),
]

DRAFTS = {
    "software": {
        "period": "2026-10",
        "memo": "Accrue September software support invoice PPS-7781, not yet recorded.",
        "support_recon_id": "REC-AP-01",
        "lines": [
            {
                "account_code": "6300",
                "department": "ENG",
                "debit": "7800.00",
                "credit": "0",
                "memo": "Paper & Pixel September support",
            },
            {
                "account_code": "2100",
                "department": None,
                "debit": "0",
                "credit": "7800.00",
                "memo": "Accrued expense",
            },
        ],
    },
    "shrink": {
        "period": "2026-10",
        "memo": "Record the September cycle-count shortage. Count support is REC-INV-01.",
        "support_recon_id": "REC-INV-01",
        "lines": [
            {
                "account_code": "5200",
                "department": "OPS",
                "debit": "6150.00",
                "credit": "0",
                "memo": "Inventory shrink",
            },
            {
                "account_code": "1200",
                "department": None,
                "debit": "0",
                "credit": "6150.00",
                "memo": "Inventory",
            },
        ],
    },
    "unbalanced": {
        "period": "2026-10",
        "memo": "This preview is intentionally out of balance.",
        "support_recon_id": None,
        "lines": [
            {
                "account_code": "6950",
                "department": "FIN",
                "debit": "85.00",
                "credit": "0",
                "memo": "Bank fee",
            },
            {
                "account_code": "1000",
                "department": None,
                "debit": "0",
                "credit": "80.00",
                "memo": "Cash",
            },
        ],
    },
}


def esc(value: object) -> str:
    return html.escape(str(value))


def pretty(value: object) -> str:
    text = str(value)
    negative = text.startswith("-")
    whole, frac = text.lstrip("-").split(".")
    body = f"{int(whole):,}.{frac}"
    return f"-${body}" if negative else f"${body}"


def page(path: str, body: str) -> str:
    nav = "".join(f'<a href="{href}" class="{"on" if href == path else ""}">{label}</a>' for href, label in PAGES)
    return (
        "<!doctype html><html><head><meta charset=utf-8>"
        "<meta name=viewport content='width=device-width,initial-scale=1'>"
        "<title>Halden &amp; Quay books</title>"
        f"<style>{CSS}</style></head><body>"
        f"<header><b>Halden &amp; Quay books</b>{nav}</header><main>"
        "<div class=banner>Synthetic data for a fictional company. "
        "Read-only. A draft on this page is a preview and is not posted.</div>"
        f"{body}</main></body></html>"
    )


def pill(direction: str) -> str:
    kind = {"favorable": "ok", "unfavorable": "bad", "flat": "warn"}.get(direction, "warn")
    return f"<span class='pill {kind}'>{esc(direction)}</span>"


def trial_view(books, query: dict) -> str:
    period = query.get("period", ["2026-09"])[0]
    statement = query.get("statement", ["all"])[0]
    result = tools.get_trial_balance(books, period, statement)
    if not result["ok"]:
        return f"<div class=card><h2>Trial balance</h2><p class=bad>{esc(result['error'])}</p></div>"
    totals = result["totals"]
    state = "ok" if totals["balanced"] else "bad"
    rows = "".join(
        "<tr>"
        f"<td>{esc(row['account_code'])}</td><td>{esc(row['account_name'])}</td>"
        f"<td>{esc(row['statement'].replace('_', ' '))}</td>"
        f"<td class=num>{pretty(row['debit'])}</td><td class=num>{pretty(row['credit'])}</td>"
        "</tr>"
        for row in result["rows"]
    )
    return (
        "<div class=card><h2>Trial balance</h2>"
        f"<form><input name=period value='{esc(period)}' style='width:110px'>"
        "<select name=statement>"
        + "".join(
            f"<option {'selected' if statement == value else ''}>{value}</option>"
            for value in ("all", "balance_sheet", "income_statement")
        )
        + "</select><button>Show</button></form>"
        "<div class=stats>"
        f"<div class=stat><span>Through</span>{esc(result['through_date'])}</div>"
        f"<div class=stat><span>Debits</span>{pretty(totals['debit'])}</div>"
        f"<div class=stat><span>Credits</span>{pretty(totals['credit'])}</div>"
        f"<div class=stat><span>Status</span><span class='pill {state}'>"
        f"{'balanced' if totals['balanced'] else 'out of balance'}</span></div>"
        f"<div class=stat><span>YTD net income (memo)</span>{pretty(result['net_income']['ytd'])}</div>"
        "</div>"
        "<table><tr><th>Account</th><th>Name</th><th>Statement</th>"
        "<th class=num>Debit</th><th class=num>Credit</th></tr>"
        f"{rows}</table>"
        f"<p class=muted>{esc(result['basis'])}</p></div>"
    )


def journals_view(books, query: dict) -> str:
    text = query.get("text", ["heat wave"])[0]
    result = tools.search_journal_entries(books, text=text or None, limit=10)
    if not result["ok"]:
        body = f"<p>{esc(result['error'])}</p>"
    else:
        blocks = []
        for entry in result["entries"]:
            lines = "".join(
                "<tr>"
                f"<td>{esc(line['account_code'])} {esc(line['account_name'])}</td>"
                f"<td>{esc(line['department'] or '')}</td>"
                f"<td class=num>{pretty(line['debit'])}</td>"
                f"<td class=num>{pretty(line['credit'])}</td>"
                f"<td>{esc(line['memo'])}</td></tr>"
                for line in entry["lines"]
            )
            blocks.append(
                f"<h2>{esc(entry['entry_id'])} · {esc(entry['entry_date'])}</h2>"
                f"<p>{esc(entry['description'])} "
                f"<span class='pill ok'>{esc(entry['source'])}</span></p>"
                "<table><tr><th>Account</th><th>Dept</th><th class=num>Debit</th>"
                f"<th class=num>Credit</th><th>Memo</th></tr>{lines}</table>"
            )
        body = "".join(blocks) or "<p>No entries.</p>"
        body = f"<p class=muted>{result['returned']} of {result['match_count']} entries.</p>" + body
    return (
        "<div class=card><h2>Journal search</h2>"
        f"<form action=/journals><input name=text value='{esc(text)}'>"
        f"<button>Search</button></form>{body}</div>"
    )


def recon_view(books, query: dict) -> str:
    account = query.get("account", ["1000"])[0]
    result = tools.list_open_reconciliations(books, account_code=account or None)
    if not result["ok"]:
        return f"<div class=card><h2>Reconciliations</h2><p>{esc(result['error'])}</p></div>"
    proof = result.get("cash_bank_reconciliation")
    proof_html = ""
    if proof:
        state = "ok" if proof["ties"] else "bad"
        proof_html = (
            "<div class=stats>"
            f"<div class=stat><span>Book cash</span>{pretty(proof['book_cash'])}</div>"
            f"<div class=stat><span>Bank statement</span>{pretty(proof['bank_statement'])}</div>"
            f"<div class=stat><span>Deposits in transit</span>{pretty(proof['deposits_in_transit'])}</div>"
            f"<div class=stat><span>Outstanding checks</span>{pretty(proof['outstanding_checks'])}</div>"
            f"<div class=stat><span>Tie-out</span><span class='pill {state}'>"
            f"{'ties' if proof['ties'] else 'does not tie'}</span></div></div>"
        )
    rows = "".join(
        "<tr>"
        f"<td>{esc(item['recon_id'])}</td><td>{esc(item['account_code'])}</td>"
        f"<td>{esc(item['item_type'])}</td><td class=num>{pretty(item['amount'])}</td>"
        f"<td>{esc(item['description'])}</td><td>{esc(item['owner_role'])}</td></tr>"
        for item in result["items"]
    )
    return (
        "<div class=card><h2>Open reconciliation items</h2>"
        f"<form action=/recon><input name=account value='{esc(account)}' style='width:110px'>"
        f"<button>Filter</button></form>{proof_html}"
        "<table><tr><th>Item</th><th>Account</th><th>Type</th><th class=num>Amount</th>"
        f"<th>Description</th><th>Owner</th></tr>{rows}</table></div>"
    )


def variance_view(books, query: dict) -> str:
    period = query.get("period", ["2026-06"])[0]
    department = query.get("department", ["SALES"])[0]
    result = tools.get_budget_variance(books, period, department=department or None, ytd=False)
    if not result["ok"]:
        return f"<div class=card><h2>Budget versus actual</h2><p>{esc(result['error'])}</p></div>"
    rows = "".join(
        "<tr>"
        f"<td>{esc(row['account_code'])} {esc(row['account_name'])}</td>"
        f"<td class=num>{pretty(row['actual'])}</td><td class=num>{pretty(row['budget'])}</td>"
        f"<td class=num>{pretty(row['variance'])}</td><td>{pill(row['direction'])}</td>"
        f"<td>{'material' if row['material'] else ''}</td></tr>"
        for row in result["rows"]
    )
    totals = result["totals"]
    return (
        "<div class=card><h2>Budget versus actual</h2>"
        f"<form action=/variance><input name=period value='{esc(period)}' style='width:110px'>"
        f"<input name=department value='{esc(department)}' style='width:110px'>"
        "<button>Show</button></form>"
        f"<div class=stats><div class=stat><span>{esc(department)} {esc(period)}</span>"
        f"{pill(totals['direction'])}</div>"
        f"<div class=stat><span>Earnings impact</span>{pretty(totals['favorable_amount'])}</div></div>"
        "<table><tr><th>Account</th><th class=num>Actual</th><th class=num>Budget</th>"
        f"<th class=num>Variance</th><th>Direction</th><th></th></tr>{rows}</table>"
        "<p class=muted>Variance is actual minus budget. A positive favorable amount helps earnings.</p></div>"
    )


def aging_view(books, query: dict) -> str:
    kind = query.get("subledger", ["ar"])[0]
    result = tools.get_ap_ar_aging(books, kind)
    if not result["ok"]:
        return f"<div class=card><h2>Aging</h2><p>{esc(result['error'])}</p></div>"
    buckets = "".join(
        f"<div class=stat><span>{esc(bucket['label'])}</span>{pretty(bucket['amount'])}"
        f"<span class=muted>{bucket['count']} items</span></div>"
        for bucket in result["buckets"]
    )
    tie = "ok" if result["ties_to_gl"] else "bad"
    rows = "".join(
        "<tr>"
        f"<td>{esc(doc['invoice_id'])}</td><td>{esc(doc['name'])}</td>"
        f"<td>{esc(doc['due_date'])}</td><td class=num>{doc['days_past_due']}</td>"
        f"<td>{esc(doc['bucket'])}</td><td class=num>{pretty(doc['open_amount'])}</td></tr>"
        for doc in result["documents"]
    )
    return (
        "<div class=card><h2>AP / AR aging</h2>"
        "<form action=/aging><select name=subledger>"
        + "".join(
            f"<option value={value} {'selected' if kind == value else ''}>{label}</option>"
            for value, label in (("ar", "Receivables"), ("ap", "Payables"))
        )
        + "</select><button>Show</button></form>"
        f"<div class=stats>{buckets}"
        f"<div class=stat><span>Ties to GL {esc(result['control_account'])}</span>"
        f"<span class='pill {tie}'>{'yes' if result['ties_to_gl'] else 'no'}</span></div></div>"
        "<table><tr><th>Invoice</th><th>Name</th><th>Due</th><th class=num>Days</th>"
        f"<th>Bucket</th><th class=num>Open</th></tr>{rows}</table>"
        f"<p class=muted>Snapshot {esc(result['snapshot_as_of'])}. {esc(result['snapshot_note'])}</p></div>"
    )


def draft_view(books, query: dict) -> str:
    example = query.get("example", ["software"])[0]
    spec = DRAFTS.get(example, DRAFTS["software"])
    result = tools.draft_adjusting_entry(
        books,
        period=spec["period"],
        memo=spec["memo"],
        lines=spec["lines"],
        support_recon_id=spec["support_recon_id"],
        prepared_by="viewer-preview",
    )
    links = " ".join(f"<a href='/draft?example={name}'>{name}</a>" for name in DRAFTS)
    if not result["ok"]:
        detail = (
            f"<p><span class='pill bad'>{esc(result['status'])}</span></p>"
            f"<p>{esc(result['error'])}</p>"
            f"<p>Debits {pretty(result['debits']) if 'debits' in result else ''} "
            f"Credits {pretty(result['credits']) if 'credits' in result else ''}</p>"
        )
    else:
        entry = result["entry"]
        lines = "".join(
            "<tr>"
            f"<td>{esc(line['account_code'])} {esc(line['account_name'])}</td>"
            f"<td>{esc(line['department'] or '')}</td>"
            f"<td class=num>{pretty(line['debit'])}</td>"
            f"<td class=num>{pretty(line['credit'])}</td></tr>"
            for line in entry["lines"]
        )
        warnings = "".join(f"<li>{esc(item)}</li>" for item in result["warnings"])
        detail = (
            f"<p><span class='pill bad'>{esc(result['status'])}</span></p>"
            f"<p>Draft id {esc(result['draft_id'])}. Posted: {esc(result['posted'])}.</p>"
            f"<p>{esc(entry['description'])}</p>"
            "<table><tr><th>Account</th><th>Dept</th><th class=num>Debit</th>"
            f"<th class=num>Credit</th></tr>{lines}</table>"
            f"<p>Total {pretty(entry['total_debits'])}. Balanced: {esc(entry['balanced'])}.</p>"
            + (f"<ul>{warnings}</ul>" if warnings else "")
        )
    return (
        "<div class=card><h2>Adjusting-entry preview</h2>"
        f"<p class=muted>Examples: {links}. The preview calls the draft function and does not write.</p>"
        f"{detail}</div>"
    )


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        url = urlparse(self.path)
        query = parse_qs(url.query)
        with open_ledger() as books:
            views = {
                "/": trial_view,
                "/journals": journals_view,
                "/recon": recon_view,
                "/variance": variance_view,
                "/aging": aging_view,
                "/draft": draft_view,
            }
            view = views.get(url.path)
            if view is None:
                self._send("Not found", "text/plain", 404)
                return
            body = view(books, query)
        self._send(page(url.path, body), "text/html; charset=utf-8")

    def _send(self, text: str, content_type: str, status: int = 200) -> None:
        data = text.encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt: str, *args) -> None:
        return


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    print(f"Finance viewer on http://127.0.0.1:{port}  (Ctrl+C to stop)")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
