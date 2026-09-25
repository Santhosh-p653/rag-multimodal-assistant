"""
troubleshooting_agent.py — Agentic Reasoning Service.
Guides diagnostic logic, formulates questions, recommends corrective actions,
and decides workflow escalations based on manual context and conversation logs.
"""
import json
from typing import Dict, Any, List
from app.config import LLM_PROVIDER, GROQ_API_KEY, SAMBANOVA_API_KEY, LLM_MODEL, settings
from app.services.llm_provider import generate


def fallback_reasoning(context_text: str, history: List[Dict[str, str]], last_message: str) -> Dict[str, Any]:
    """Deterministic rule-based automotive diagnostic reasoning for fallback/testing without API keys."""
    message = (last_message or "").lower()

    # Misfire / Ignition diagnostic branch (e.g. P0300, P0301, misfire)
    has_misfire_context = (
        "p030" in message or
        "misfire" in message or
        any("p030" in h.get("answer", "").lower() for h in history) or
        any("p030" in h.get("question", "").lower() for h in history) or
        any("misfire" in h.get("question", "").lower() for h in history)
    )

    if has_misfire_context:
        if not history:
            return {
                "decision": "QUESTION",
                "text": "Are you experiencing the misfire under heavy acceleration or only during cold idle?",
                "reasoning": "Standard automotive diagnostic tree step to differentiate ignition coil breakdown from vacuum leaks or fuel delivery issues."
            }

        last_ans = history[-1].get("answer", "").lower()

        if "acceleration" in last_ans or "heavy" in last_ans or "load" in last_ans:
            return {
                "decision": "ACTION",
                "text": "Inspect the ignition coil packs and spark plugs on the affected cylinder. Check spark plug electrode gap (typically 0.040-0.044 in) and verify no oil contamination in the spark plug well.",
                "reasoning": "Under-load misfires are predominantly caused by secondary ignition breakdown or high cylinder pressure quenching weak sparks."
            }
        elif "idle" in last_ans or "cold" in last_ans:
            return {
                "decision": "QUESTION",
                "text": "Have you inspected the intake manifold and vacuum hoses for unmetered air leaks using smoke or carburetor cleaner?",
                "reasoning": "Idle misfires are commonly triggered by lean conditions resulting from intake manifold gasket or vacuum hose degradation."
            }
        else:
            return {
                "decision": "ACTION",
                "text": "Swap the ignition coil from the misfiring cylinder to an adjacent cylinder, clear DTCs, and road-test to see if the misfire code follows the coil.",
                "reasoning": "Definitive diagnostic isolation technique for identifying intermittent ignition coil failure without replacing parts blindly."
            }

    # No-crank / Battery / Starter diagnostic branch
    if any(k in message for k in ["no crank", "won't start", "clicking", "dead battery", "starter", "alternator"]):
        if not history:
            return {
                "decision": "QUESTION",
                "text": "When you turn the ignition key to START, do you hear a single loud click, rapid clicking, or complete silence?",
                "reasoning": "Differentiate between starter solenoid engagement, low battery state-of-charge, or ignition switch open circuit."
            }

        last_ans = history[-1].get("answer", "").lower()

        if "rapid" in last_ans or "clicking" in last_ans:
            return {
                "decision": "ACTION",
                "text": "Test the 12V battery open-circuit voltage with a multimeter. If below 12.4V (approx. 75% charge), recharge or jump-start the battery and inspect the battery terminals for corrosion.",
                "reasoning": "Rapid clicking indicates the starter solenoid pulls in but source voltage collapses under inrush current load."
            }
        elif "single" in last_ans or "click" in last_ans:
            return {
                "decision": "ACTION",
                "text": "Perform a starter motor voltage drop test on the B+ cable terminal while cranking. If battery voltage reaches the starter terminal but the motor does not turn, replace the starter motor.",
                "reasoning": "Single click confirms solenoid pull-in coil energizes, but motor contacts or brushes are open/worn."
            }
        else:
            return {
                "decision": "QUESTION",
                "text": "Is the vehicle in Park or Neutral, and is the brake/clutch interlock safety switch fully depressed?",
                "reasoning": "Neutral safety switch or clutch interlock switch prevents starter relay energization."
            }

    if not history:
        return {
            "decision": "QUESTION",
            "text": "Could you provide the vehicle Year, Make, Model, engine displacement, and any active OBD-II Diagnostic Trouble Codes (e.g. P0171, P0300)?",
            "reasoning": "Collect primary vehicle specification baseline and DTCs to open the appropriate service manual diagnostic chart."
        }

    return {
        "decision": "ESCALATE",
        "text": "The troubleshooting steps in the uploaded service manuals do not cover this specific vehicle symptom. Escalating to master automotive technical support.",
        "reasoning": "Symptom out of scope of currently ingested vehicle service documentation."
    }


async def diagnose_and_propose(
    context_chunks: List[Dict[str, Any]],
    history: List[Dict[str, str]],
    last_message: str
) -> Dict[str, Any]:
    if LLM_PROVIDER == "none" and not getattr(settings, "OLLAMA_ENABLED", False):
        return fallback_reasoning("", history, last_message)

    context_text = "\n\n".join(
        [f"[Source: {c['source']}]\n{c['content']}" for c in context_chunks]
    )

    dialogue_log = ""
    for i, turn in enumerate(history, 1):
        dialogue_log += f"Turn {i}:\nQuestion Asked: {turn.get('question', '')}\nUser Answered: {turn.get('answer', '')}\n\n"

    dialogue_log += f"Current User Message: {last_message}"

    prompt = f"""You are Octo RAG AutoTech, an expert Master Automotive Diagnostic Technician.
Guide the mechanic or vehicle owner through a systematic diagnostic tree using ONLY the supplied vehicle manual context below.

Your primary objective is to evaluate the fault symptoms, diagnostic trouble codes (DTCs), and user test results to decide the next step:
- "QUESTION": Ask a focused diagnostic verification question (e.g. check sensor resistance with a DMM, observe freeze frame data, check fuel pressure).
- "ACTION": Recommend an explicit corrective procedure or repair instruction grounded strictly in the manual (including safety precautions, tool requirements, and torque specs).
- "ESCALATE": Escalate if the symptom exceeds shop-floor procedures or requires specialized OEM factory scan tool programming.

Return strict JSON output only with keys "decision" (QUESTION | ACTION | ESCALATE), "text", and "reasoning".

---
Automotive Service Manual Context:
{context_text}
---
Diagnostic Dialogue Logs:
{dialogue_log}
"""

    if LLM_PROVIDER == "none" and not getattr(settings, "OLLAMA_ENABLED", False):
        return fallback_reasoning(context_text, history, last_message)

    try:
        response_text = generate(
            prompt,
            task="workflow",
            temperature=0.1,
            max_tokens=512,
        )

        if response_text.startswith("```"):
            response_text = "\n".join(response_text.splitlines()[1:-1]).strip()

        parsed = json.loads(response_text)

        if "decision" in parsed and "text" in parsed:
            return parsed

        raise ValueError("Invalid JSON schema returned by LLM")

    except Exception as e:
        print(f"[TroubleshootingAgent] LLM failure: {e}")
        return fallback_reasoning(context_text, history, last_message)