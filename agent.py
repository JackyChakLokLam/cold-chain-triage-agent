import os
import json
from dotenv import load_dotenv
from openai import OpenAI
from tools import scan_and_redact_shipments, log_escalation_and_draft_email

load_dotenv()

# 云端 DeepSeek 引擎（负责高可靠性多步推理与严格 JSON 工具调用）
cloud_llm = OpenAI(
    base_url="https://api.deepseek.com",
    api_key=os.getenv("DEEPSEEK_API_KEY")
)

TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "scan_and_redact_shipments",
            "description": "Scan shipments.xlsx locally using the on-premise GPU model to filter delayed or temperature-excursion loads and redact PII.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "log_escalation_and_draft_email",
            "description": "Log an exception triage decision and queue a carrier follow-up email for human approval.",
            "parameters": {
                "type": "object",
                "properties": {
                    "shipment_id": {"type": "string"},
                    "severity": {"type": "string", "enum": ["HIGH_CRITICAL", "MEDIUM_DELAY"]},
                    "action_type": {"type": "string", "enum": ["DRAFT_CARRIER_EMAIL", "ESCALATE_MISSING_CONTACT"]},
                    "draft_email": {"type": "string"}
                },
                "required": ["shipment_id", "severity", "action_type", "draft_email"]
            }
        }
    }
]

AVAILABLE_FUNCTIONS = {
    "scan_and_redact_shipments": scan_and_redact_shipments,
    "log_escalation_and_draft_email": log_escalation_and_draft_email
}

def run_dispatch_agent():
    messages = [
        {
            "role": "system",
            "content": (
                "You are a Cold-Chain Logistics Triage Agent. "
                "1. Call scan_and_redact_shipments first to inspect flagged loads. "
                "2. For each flagged load: if temp_c exceeds required_temp_range, mark severity as HIGH_CRITICAL; otherwise MEDIUM_DELAY. "
                "3. If carrier_email is 'MISSING', set action_type to ESCALATE_MISSING_CONTACT and write an internal supervisor alert; "
                "otherwise set action_type to DRAFT_CARRIER_EMAIL and draft a concise, professional check-call email to the carrier. "
                "4. Call log_escalation_and_draft_email for EVERY flagged shipment before giving your final summary."
            )
        },
        {"role": "user", "content": "Run today's morning cold-chain shipment triage."}
    ]

    while True:
        response = cloud_llm.chat.completions.create(
            model="deepseek-chat",
            max_tokens=4096,
            messages=messages,
            tools=TOOLS_SCHEMA
        )
        msg = response.choices[0].message
        messages.append(msg)

        if not msg.tool_calls:
            print("\n=== AGENT FINAL SUMMARY ===")
            print(msg.content)
            break

        for tool_call in msg.tool_calls:
            fn_name = tool_call.function.name
            fn_args = json.loads(tool_call.function.arguments) if tool_call.function.arguments else {}
            print(f"[Agent Calling Tool] {fn_name}({fn_args})")
            result = AVAILABLE_FUNCTIONS[fn_name](**fn_args)
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result
            })

if __name__ == "__main__":
    run_dispatch_agent()