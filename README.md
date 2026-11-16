# Hybrid Edge-Cloud Cold-Chain Triage Agent

An automated exception-triage AI agent designed for cold-chain logistics operations. It combines **local GPU inference (RTX 4080 Super + Ollama)** for zero-cost PII redaction and rule filtering with **cloud LLM tool-calling (DeepSeek API)** for multi-step exception escalation.

## Architecture & Workflow
1. **Deterministic Pre-Filtering (`tools.py`)**: Scans daily shipment logs (`shipments.xlsx`) and filters out on-time, in-range loads locally (`0` cloud tokens spent on healthy shipments).
2. **On-Premise PII Redaction (Local GPU)**: Uses `qwen2.5:14b` via Ollama to strip driver names and phone numbers (`[REDACTED_DRIVER]`, `[REDACTED_PHONE]`) before any data leaves the local machine.
3. **Autonomous Triage & Escalation (`agent.py`)**: DeepSeek evaluates temperature excursions (`> 4.0°C`) vs. transit delays, drafting carrier check-call emails or triggering internal supervisor alerts when carrier contact info is missing.
4. **Human-in-the-Loop Guardrail**: Logs all decisions and email drafts to `agent_audit_log.jsonl` with `PENDING_HUMAN_APPROVAL` status—preventing unverified external communications.

## Quick Start
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
# Add DEEPSEEK_API_KEY=your_key to .env
python setup_data.py
python agent.py