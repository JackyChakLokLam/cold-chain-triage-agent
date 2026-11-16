import json
import pandas as pd
from openai import OpenAI

# 本地 RTX 4080 Super 引擎（零成本、本地隐私脱敏）
local_llm = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")

def scan_and_redact_shipments() -> str:
    """
    步骤1（本地 4080S 算力）：读取 Excel，过滤正常单据，并用本地 14B 模型对异常单据的司机姓名/电话做 PII 隐私脱敏。
    """
    df = pd.read_excel("shipments.xlsx")
    flagged = []

    for _, row in df.iterrows():
        # 规则初筛：只把延误或温度超标（>4.0C）的异常单提取出来，省掉云端 Token
        if "Delayed" in str(row["eta_status"]) or float(row["temp_c"]) > 4.0:
            prompt = (
                "Redact all personal names and phone numbers in the following logistics note "
                "using [REDACTED_DRIVER] and [REDACTED_PHONE], and summarize the issue in 1 concise sentence:\n"
                f"{row['raw_driver_note']}"
            )
            res = local_llm.chat.completions.create(
                model="qwen2.5:14b",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0
            )
            clean_summary = res.choices[0].message.content.strip()

            flagged.append({
                "shipment_id": row["shipment_id"],
                "carrier": row["carrier"],
                "carrier_email": row["carrier_email"],
                "route": f"{row['origin']} -> {row['destination']}",
                "eta_status": row["eta_status"],
                "temp_c": row["temp_c"],
                "required_temp_range": row["required_temp_range"],
                "sanitized_issue_summary": clean_summary
            })

    return json.dumps(flagged, ensure_ascii=False)

def log_escalation_and_draft_email(shipment_id: str, severity: str, action_type: str, draft_email: str) -> str:
    """
    步骤2（确定性落盘工具）：将 Agent 决策结果写入本地审计日志，并强制打上人工审核标签（Guardrail）。
    """
    record = {
        "shipment_id": shipment_id,
        "severity": severity,
        "action_type": action_type,
        "approval_status": "PENDING_HUMAN_APPROVAL",
        "draft_email": draft_email
    }
    with open("agent_audit_log.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return f"Logged {shipment_id} with status PENDING_HUMAN_APPROVAL."