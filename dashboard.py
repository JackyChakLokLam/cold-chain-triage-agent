import html
import json
import os
import smtplib
import subprocess
import sys
from datetime import datetime
from email.message import EmailMessage
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs
from dotenv import load_dotenv

load_dotenv()

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
    --blue: #3b82f6; --blue-bg: rgba(59, 130, 246, 0.15);
  }
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: var(--bg); color: var(--text); margin: 0; padding: 24px; }
  .container { max-width: 1100px; margin: 0 auto; }
  header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border); padding-bottom: 16px; margin-bottom: 24px; gap: 16px; }
  h1 { font-size: 1.4rem; margin: 0; }
  .subtitle { color: var(--muted); font-size: 0.85rem; margin-top: 4px; }
  .header-actions { display: flex; align-items: center; gap: 12px; }
  .stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 24px; }
  .stat-card { background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 16px; }
  .stat-label { color: var(--muted); font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; }
  .stat-val { font-size: 1.8rem; font-weight: 700; margin-top: 6px; }
  .card { background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 20px; margin-bottom: 16px; }
  .card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
  .badge { padding: 4px 10px; border-radius: 999px; font-size: 0.75rem; font-weight: 600; }
  .sev-HIGH_CRITICAL { background: var(--red-bg); color: var(--red); border: 1px solid var(--red); }
  .sev-MEDIUM_DELAY { background: var(--amber-bg); color: var(--amber); border: 1px solid var(--amber); }
  .edited-tag { background: var(--blue-bg); color: #93c5fd; border: 1px solid var(--blue); margin-left: 6px; }
  .status-PENDING_HUMAN_APPROVAL { background: var(--amber-bg); color: var(--amber); }
  .status-APPROVED_AND_DISPATCHED { background: var(--green-bg); color: var(--green); }
  .status-DISPATCH_FAILED, .status-REJECTED { background: var(--red-bg); color: var(--red); }
  .meta { color: var(--muted); font-size: 0.85rem; margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center; }
  .draft-box { background: #0b1120; border: 1px solid var(--border); border-radius: 6px; padding: 16px; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 0.88rem; white-space: pre-wrap; line-height: 1.6; color: #e2e8f0; }
  textarea.draft-editor { width: 100%; box-sizing: border-box; min-height: 230px; background: #0b1120; border: 1px solid #475569; border-radius: 6px; padding: 16px; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 0.88rem; line-height: 1.6; color: #f8fafc; resize: vertical; outline: none; }
  textarea.draft-editor:focus { border-color: var(--blue); box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.25); }
  .actions { display: flex; gap: 10px; margin-top: 16px; justify-content: flex-end; }
  button { cursor: pointer; border: none; border-radius: 6px; padding: 9px 16px; font-weight: 600; font-size: 0.85rem; transition: opacity 0.15s; }
  button:hover:not(:disabled) { opacity: 0.9; }
  button:disabled { opacity: 0.6; cursor: wait; }
  .btn-run { background: var(--blue); color: #ffffff; }
  .btn-approve { background: var(--green); color: #052e16; }
  .btn-reject { background: transparent; border: 1px solid var(--border); color: var(--muted); }
  .banner { background: var(--blue-bg); border: 1px solid var(--blue); color: #93c5fd; padding: 12px 16px; border-radius: 8px; margin-bottom: 20px; font-size: 0.88rem; }
  .dispatch-note { font-size: 0.82rem; color: var(--green); margin-top: 10px; text-align: right; }
  .dispatch-err { font-size: 0.82rem; color: var(--red); margin-top: 10px; text-align: right; }
  .empty { text-align: center; padding: 48px; color: var(--muted); background: var(--card); border-radius: 10px; border: 1px dashed var(--border); }
</style>
</head>
<body>
<div class="container">
  <header>
    <div>
      <h1>Cold-Chain Exception Triage & Approval Console</h1>
      <div class="subtitle">Hybrid Edge-Cloud Pipeline (Local GPU PII Redaction + DeepSeek Tool Calling + Human Edit & SMTP)</div>
    </div>
    <div class="header-actions">
      <form method="POST" action="/run-agent" onsubmit="const btn=this.querySelector('button'); btn.disabled=true; btn.innerText='Running Local GPU + DeepSeek...';">
        <button type="submit" class="btn-run">Run Agent Scan</button>
      </form>
    </div>
  </header>

  {{BANNER}}

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

LAST_RUN_NOTICE = ""


def get_record_status(record: dict) -> str:
    return record.get("status") or record.get("approval_status") or "PENDING_HUMAN_APPROVAL"


def load_records() -> list[dict]:
    if not os.path.exists(LOG_FILE):
        return []
    records = []
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def save_records(records: list[dict]) -> None:
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def dispatch_real_email(record: dict) -> tuple[bool, str]:
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "465"))
    smtp_user = os.getenv("SMTP_USER", "").strip()
    smtp_pass = os.getenv("SMTP_PASS", "").strip()

    if not smtp_user or not smtp_pass:
        return False, "Missing SMTP_USER or SMTP_PASS in .env"

    override_email = os.getenv("TEST_OVERRIDE_EMAIL", "").strip()
    carrier_email = str(record.get("carrier_email", "")).strip()
    recipient = override_email if override_email else carrier_email

    if not recipient or recipient.upper() == "MISSING":
        return False, "No valid recipient email address (carrier contact missing)."

    draft_text = record.get("draft_email") or record.get("draft_content") or ""
    lines = draft_text.strip().splitlines()
    subject = f"Cold-Chain Dispatch Alert: {record.get('shipment_id', 'Shipment')}"
    body = draft_text

    if lines and lines[0].lower().startswith("subject:"):
        subject = lines[0].split(":", 1)[1].strip()
        body = "\n".join(lines[1:]).strip()

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = smtp_user
    msg["To"] = recipient
    msg.set_content(body)

    try:
        with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=15) as server:
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        mode_tag = " (Sandbox Override)" if override_email else ""
        return True, f"Dispatched via SMTP to {recipient}{mode_tag}"
    except Exception as e:
        return False, f"SMTP Error: {str(e)}"


def render_page() -> str:
    global LAST_RUN_NOTICE
    records = load_records()
    total = len(records)
    critical = sum(1 for r in records if r.get("severity") == "HIGH_CRITICAL")
    pending = sum(1 for r in records if get_record_status(r) == "PENDING_HUMAN_APPROVAL")

    banner_html = f'<div class="banner">{html.escape(LAST_RUN_NOTICE)}</div>' if LAST_RUN_NOTICE else ""
    LAST_RUN_NOTICE = ""

    if not records:
        cards_html = '<div class="empty">No audit records found. Click <strong>Run Agent Scan</strong> above to evaluate shipments.</div>'
    else:
        blocks = []
        for idx, r in enumerate(records):
            sev = html.escape(str(r.get("severity", "UNKNOWN")))
            status = html.escape(get_record_status(r))
            action_type = html.escape(str(r.get("action_type", "N/A")))
            shipment_id = html.escape(str(r.get("shipment_id", f"LOAD-{idx}")))
            raw_draft = r.get("draft_email") or r.get("draft_content") or r.get("message") or json.dumps(r, indent=2, ensure_ascii=False)
            draft = html.escape(str(raw_draft))
            reviewed_at = html.escape(str(r.get("reviewed_at", "")))
            dispatch_result = html.escape(str(r.get("dispatch_result", "")))
            edited_badge = '<span class="badge edited-tag">HUMAN EDITED</span>' if r.get("human_edited") else ""

            if status == "PENDING_HUMAN_APPROVAL":
                blocks.append(f"""
                <div class="card">
                  <form method="POST" action="/decision">
                    <input type="hidden" name="index" value="{idx}">
                    <div class="card-header">
                      <div>
                        <strong style="font-size:1.1rem;">{shipment_id}</strong>
                        <span class="badge sev-{sev}" style="margin-left:8px;">{sev}</span>
                      </div>
                      <span class="badge status-{status}">{status}</span>
                    </div>
                    <div class="meta">
                      <span>Action: <strong>{action_type}</strong></span>
                      <span style="color:#93c5fd; font-size:0.8rem;">Editable before dispatch</span>
                    </div>
                    <textarea name="edited_draft" class="draft-editor">{draft}</textarea>
                    <div class="actions">
                      <button type="submit" name="decision" value="REJECTED" class="btn-reject">Hold / Reject</button>
                      <button type="submit" name="decision" value="APPROVED_AND_DISPATCHED" class="btn-approve">Approve & Dispatch Email</button>
                    </div>
                  </form>
                </div>""")
            else:
                result_class = "dispatch-err" if status in ("DISPATCH_FAILED", "REJECTED") else "dispatch-note"
                result_line = f'<div class="{result_class}">{dispatch_result}</div>' if dispatch_result else ""
                blocks.append(f"""
                <div class="card">
                  <div class="card-header">
                    <div>
                      <strong style="font-size:1.1rem;">{shipment_id}</strong>
                      <span class="badge sev-{sev}" style="margin-left:8px;">{sev}</span>
                      {edited_badge}
                    </div>
                    <span class="badge status-{status}">{status}</span>
                  </div>
                  <div class="meta"><span>Action: <strong>{action_type}</strong></span></div>
                  <div class="draft-box">{draft}</div>
                  {result_line}
                  <div style="color:var(--muted); font-size:0.82rem; margin-top:6px; text-align:right;">Reviewed: {reviewed_at}</div>
                </div>""")
        cards_html = "\n".join(blocks)

    return (
        HTML_TEMPLATE.replace("{{BANNER}}", banner_html)
        .replace("{{TOTAL}}", str(total))
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
        body = render_page().encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        global LAST_RUN_NOTICE
        if self.path == "/run-agent":
            if os.path.exists(LOG_FILE):
                os.remove(LOG_FILE)
            result = subprocess.run([sys.executable, "agent.py"], capture_output=True, text=True)
            if result.returncode == 0:
                LAST_RUN_NOTICE = f"Agent scan completed at {datetime.now().strftime('%H:%M:%S')} — audit log refreshed."
            else:
                LAST_RUN_NOTICE = f"Agent scan failed: {result.stderr.strip() or 'Unknown error'}"
            self.send_response(303)
            self.send_header("Location", "/")
            self.end_headers()
            return

        if self.path == "/decision":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode("utf-8")
            params = parse_qs(body)
            idx = int(params.get("index", ["-1"])[0])
            decision = params.get("decision", [""])[0]
            edited_draft = params.get("edited_draft", [None])[0]

            records = load_records()
            if 0 <= idx < len(records) and decision in ("APPROVED_AND_DISPATCHED", "REJECTED"):
                if edited_draft is not None:
                    normalized_edited = edited_draft.replace("\r\n", "\n").strip()
                    original_draft = str(records[idx].get("draft_email") or records[idx].get("draft_content") or "").replace("\r\n", "\n").strip()
                    if normalized_edited != original_draft:
                        records[idx]["human_edited"] = True
                    records[idx]["draft_email"] = normalized_edited

                if decision == "APPROVED_AND_DISPATCHED":
                    ok, info = dispatch_real_email(records[idx])
                    new_status = "APPROVED_AND_DISPATCHED" if ok else "DISPATCH_FAILED"
                    records[idx]["dispatch_result"] = info
                else:
                    new_status = "REJECTED"
                    records[idx]["dispatch_result"] = "Held by coordinator — external dispatch blocked."

                records[idx]["status"] = new_status
                records[idx]["approval_status"] = new_status
                records[idx]["reviewed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                save_records(records)

            self.send_response(303)
            self.send_header("Location", "/")
            self.end_headers()
            return

        self.send_response(404)
        self.end_headers()

    def log_message(self, format, *args):
        pass


if __name__ == "__main__":
    server = HTTPServer(("127.0.0.1", PORT), DashboardHandler)
    print(f"Human-in-the-Loop Dashboard running at http://127.0.0.1:{PORT}")
    print("Press Ctrl+C to stop.")
    server.serve_forever()