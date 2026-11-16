import json
import os
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs

LOG_FILE = "agent_audit_log.jsonl"
PORT = 8080

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Cold-Chain Triage & Human Approval Dashboard</title>
<style>
  :root {
    --bg: #0f172a; --card: #1e293b; --border: #334155;
    --text: #f8fafc; --muted: #94a3b8;
    --red: #ef4444; --red-bg: rgba(239, 68, 68, 0.15);
    --amber: #f59e0b; --amber-bg: rgba(245, 158, 11, 0.15);
    --green: #10b981; --green-bg: rgba(16, 185, 129, 0.15);
    --blue: #3b82f6;
  }
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: var(--bg); color: var(--text); margin: 0; padding: 24px; }
  .container { max-width: 1100px; margin: 0 auto; }
  header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border); padding-bottom: 16px; margin-bottom: 24px; }
  h1 { font-size: 1.4rem; margin: 0; }
  .subtitle { color: var(--muted); font-size: 0.85rem; margin-top: 4px; }
  .stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 24px; }
  .stat-card { background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 16px; }
  .stat-label { color: var(--muted); font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; }
  .stat-val { font-size: 1.8rem; font-weight: 700; margin-top: 6px; }
  .card { background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 20px; margin-bottom: 16px; }
  .card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
  .badge { padding: 4px 10px; border-radius: 999px; font-size: 0.75rem; font-weight: 600; }
  .sev-HIGH_CRITICAL { background: var(--red-bg); color: var(--red); border: 1px solid var(--red); }
  .sev-MEDIUM_DELAY { background: var(--amber-bg); color: var(--amber); border: 1px solid var(--amber); }
  .status-PENDING_HUMAN_APPROVAL { background: var(--amber-bg); color: var(--amber); }
  .status-APPROVED_AND_DISPATCHED { background: var(--green-bg); color: var(--green); }
  .status-REJECTED { background: var(--red-bg); color: var(--red); }
  .meta { color: var(--muted); font-size: 0.85rem; margin-bottom: 14px; }
  .draft-box { background: #0b1120; border: 1px solid var(--border); border-radius: 6px; padding: 14px; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 0.85rem; white-space: pre-wrap; line-height: 1.5; color: #e2e8f0; }
  .actions { display: flex; gap: 10px; margin-top: 16px; justify-content: flex-end; }
  button { cursor: pointer; border: none; border-radius: 6px; padding: 8px 16px; font-weight: 600; font-size: 0.85rem; transition: opacity 0.15s; }
  button:hover { opacity: 0.9; }
  .btn-approve { background: var(--green); color: #052e16; }
  .btn-reject { background: transparent; border: 1px solid var(--border); color: var(--muted); }
  .empty { text-align: center; padding: 48px; color: var(--muted); background: var(--card); border-radius: 10px; border: 1px dashed var(--border); }
</style>
</head>
<body>
<div class="container">
  <header>
    <div>
      <h1>Cold-Chain Exception Triage & Approval Console</h1>
      <div class="subtitle">Hybrid Edge-Cloud Pipeline (Local GPU PII Redaction + DeepSeek Tool Calling)</div>
    </div>
    <div style="font-size: 0.8rem; color: var(--muted);">Source: <code>agent_audit_log.jsonl</code></div>
  </header>

  <div class="stats">
    <div class="stat-card"><div class="stat-label">Total Flagged Loads</div><div class="stat-val">{{TOTAL}}</div></div>
    <div class="stat-card"><div class="stat-label">High Critical (Temp Excursion)</div><div class="stat-val" style="color: var(--red);">{{CRITICAL}}</div></div>
    <div class="stat-card"><div class="stat-label">Pending Human Sign-off</div><div class="stat-val" style="color: var(--amber);">{{PENDING}}</div></div>
  </div>

  {{CARDS}}
</div>
</body>
</html>
"""

def load_records():
    if not os.path.exists(LOG_FILE):
        return []
    records = []
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records

def save_records(records):
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

def render_page():
    records = load_records()
    total = len(records)
    critical = sum(1 for r in records if r.get("severity") == "HIGH_CRITICAL")
    pending = sum(1 for r in records if r.get("status") == "PENDING_HUMAN_APPROVAL")

    if not records:
        cards_html = '<div class="empty">No audit records found. Run <code>python agent.py</code> first to generate triage logs.</div>'
    else:
        blocks = []
        for idx, r in enumerate(records):
            sev = r.get("severity", "UNKNOWN")
            status = r.get("status", "PENDING_HUMAN_APPROVAL")
            action_type = r.get("action_type", "N/A")
            shipment_id = r.get("shipment_id", f"LOAD-{idx}")
            draft = r.get("draft_content") or r.get("email_draft") or r.get("message") or json.dumps(r, indent=2, ensure_ascii=False)
            ts = r.get("timestamp", "")
            approved_at = r.get("reviewed_at", "")

            action_buttons = ""
            if status == "PENDING_HUMAN_APPROVAL":
                action_buttons = f"""
                <form method="POST" action="/decision" class="actions">
                  <input type="hidden" name="index" value="{idx}">
                  <button type="submit" name="decision" value="REJECTED" class="btn-reject">Hold / Reject</button>
                  <button type="submit" name="decision" value="APPROVED_AND_DISPATCHED" class="btn-approve">Approve & Dispatch</button>
                </form>"""
            else:
                action_buttons = f'<div class="meta" style="margin-top:12px; margin-bottom:0; text-align:right;">Reviewed: {approved_at}</div>'

            blocks.append(f"""
            <div class="card">
              <div class="card-header">
                <div>
                  <strong style="font-size:1.1rem;">{shipment_id}</strong>
                  <span class="badge sev-{sev}" style="margin-left:8px;">{sev}</span>
                </div>
                <span class="badge status-{status}">{status}</span>
              </div>
              <div class="meta">Action: <strong>{action_type}</strong> &nbsp;|&nbsp; Logged: {ts}</div>
              <div class="draft-box">{draft}</div>
              {action_buttons}
            </div>""")
        cards_html = "\n".join(blocks)

    return (
        HTML_TEMPLATE.replace("{{TOTAL}}", str(total))
        .replace("{{CRITICAL}}", str(critical))
        .replace("{{PENDING}}", str(pending))
        .replace("{{CARDS}}", cards_html)
    )

class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/":
            self.send_response(404)
            self.end_headers()
            return
        html = render_page().encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(html)))
        self.end_headers()
        self.wfile.write(html)

    def do_POST(self):
        if self.path != "/decision":
            self.send_response(404)
            self.end_headers()
            return
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8")
        params = parse_qs(body)
        idx = int(params.get("index", ["-1"])[0])
        decision = params.get("decision", [""])[0]

        records = load_records()
        if 0 <= idx < len(records) and decision in ("APPROVED_AND_DISPATCHED", "REJECTED"):
            records[idx]["status"] = decision
            records[idx]["reviewed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            save_records(records)

        self.send_response(303)
        self.send_header("Location", "/")
        self.end_headers()

    def log_message(self, format, *args):
        pass

if __name__ == "__main__":
    server = HTTPServer(("127.0.0.1", PORT), DashboardHandler)
    print(f"Human-in-the-Loop Dashboard running at http://127.0.0.1:{PORT}")
    print("Press Ctrl+C to stop.")
    server.serve_forever()