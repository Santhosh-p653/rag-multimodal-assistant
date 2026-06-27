"""
troubleshooting_agent.py — Agentic Reasoning Service.
Guides diagnostic logic, formulates questions, recommends corrective actions,
and decides workflow escalations based on manual context and conversation logs.
"""
import json
from typing import Dict, Any, List
from app.config import LLM_PROVIDER, GROQ_API_KEY, SAMBANOVA_API_KEY, LLM_MODEL


def fallback_reasoning(context_text: str, history: List[Dict[str, str]], last_message: str) -> Dict[str, Any]:
    """Deterministic rule-based agent reasoning for fallback/testing without API keys."""
    message = (last_message or "").lower()

    has_fan_context = (
        "e105" in message or
        "fan" in message or
        any("e105" in h.get("answer", "").lower() for h in history) or
        any("e105" in h.get("question", "").lower() for h in history) or
        any("fan" in h.get("question", "").lower() for h in history)
    )

    if has_fan_context:
        if not history:
            return {
                "decision": "QUESTION",
                "text": "Is the cooling fan spinning at all?",
                "reasoning": "Standard verification step for E105 Fan Error."
            }

        last_ans = history[-1].get("answer", "").lower()

        if "no" in last_ans:
            return {
                "decision": "ACTION",
                "text": "Power off the device. Remove the rear panel and inspect the fan connector. Ensure the cable is firmly clicked into the motherboard slot.",
                "reasoning": "User confirmed fan is idle. Re-seating connection is the first resolution instruction."
            }
        elif "yes" in last_ans:
            return {
                "decision": "QUESTION",
                "text": "Is there any noise or obstruction blocking the fan blades?",
                "reasoning": "Fan spins but error remains, checking for mechanical obstructions."
            }
        else:
            return {
                "decision": "ESCALATE",
                "text": "Unable to determine fan status from your answer. Please contact support at support@example.com.",
                "reasoning": "Ambiguous user feedback on diagnostic query."
            }

    if "power" in message or "turn on" in message or "dead" in message:
        if not history:
            return {
                "decision": "QUESTION",
                "text": "Is the power outlet working and is the power LED blinking?",
                "reasoning": "Verify source voltage availability."
            }

        last_ans = history[-1].get("answer", "").lower()

        if "yes" in last_ans:
            return {
                "decision": "ACTION",
                "text": "Hold the power button for 10 seconds to execute a hard reset, then unplug and reconnect the cable.",
                "reasoning": "Outlet works, performing system reset sequence."
            }
        else:
            return {
                "decision": "ESCALATE",
                "text": "The power supply appears faulty. Please contact customer support for warranty service.",
                "reasoning": "No voltage detected at source socket."
            }

    if not history:
        return {
            "decision": "QUESTION",
            "text": "Could you please describe any error codes or lights displaying on the device panel?",
            "reasoning": "Collect primary fault symptoms."
        }

    return {
        "decision": "ESCALATE",
        "text": "The troubleshooting steps in the manuals do not cover this specific symptom. Escalating to human technical support.",
        "reasoning": "Out of scope of local knowledge manuals."
    }


async def diagnose_and_propose(
    context_chunks: List[Dict[str, Any]],
    history: List[Dict[str, str]],
    last_message: str
) -> Dict[str, Any]:
    if LLM_PROVIDER == "none":
        return fallback_reasoning("", history, last_message)

    context_text = "\n\n".join(
        [f"[Source: {c['source']}]\n{c['content']}" for c in context_chunks]
    )

    dialogue_log = ""
    for i, turn in enumerate(history, 1):
        dialogue_log += f"Turn {i}:\nQuestion Asked: {turn.get('question', '')}\nUser Answered: {turn.get('answer', '')}\n\n"

    dialogue_log += f"Current User Message: {last_message}"

    prompt = f"""You are an expert technical troubleshooting agent.
Answer ONLY based on the supplied context manual below.

Goal:
1. Decide ACTION / QUESTION / ESCALATE
2. Return strict JSON output only

---
Troubleshooting Context:
{context_text}
---
Dialogue Logs:
{dialogue_log}
"""

    try:
        response_text = ""

        if LLM_PROVIDER == "groq":
            from groq import Groq
            client = Groq(api_key=GROQ_API_KEY)
            response = client.chat.completions.create(
                model=LLM_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=512,
            )
            response_text = response.choices[0].message.content.strip()

        elif LLM_PROVIDER == "sambanova":
            from openai import OpenAI
            client = OpenAI(
                api_key=SAMBANOVA_API_KEY,
                base_url="https://api.sambanova.ai/v1",
            )
            response_text = client.chat.completions.create(
                model=LLM_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=512,
            ).choices[0].message.content.strip()

        if response_text.startswith("```"):
            response_text = "\n".join(response_text.splitlines()[1:-1]).strip()

        parsed = json.loads(response_text)

        if "decision" in parsed and "text" in parsed:
            return parsed

        raise ValueError("Invalid JSON schema returned by LLM")

    except Exception as e:
        print(f"[TroubleshootingAgent] LLM failure: {e}")
        return fallback_reasoning(context_text, history, last_message)