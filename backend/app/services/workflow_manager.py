"""
workflow_manager.py — Workflow State Machine Transition coordinator.
Maintains states, evaluates user dialog inputs, transitions states, and updates sessions.
"""
from typing import Dict, Any
from app.services.session_store import SessionStore
from app.services.product_identifier import identify_product
from app.services.retriever import retrieve_context
from app.services.troubleshooting_agent import diagnose_and_propose

session_store = SessionStore()


async def process_troubleshoot_turn(session_id: str, message: str) -> Dict[str, Any]:
    """
    Main state machine entrypoint.
    Transitions states based on:
      START -> IDENTIFY_PRODUCT -> RETRIEVE_KNOWLEDGE -> DIAGNOSE -> QUESTION -> ACTION -> VERIFY -> RESOLVED/ESCALATE
    """
    session = session_store.get(session_id)
    current_status = session.get("status", "START")
    message_clean = message.strip()

    # --- STATE: START ---
    if current_status == "START":
        entities = identify_product(message_clean)
        product = entities.get("product")
        
        if product:
            session["product"] = product
            session["issue"] = entities.get("error_code") or entities.get("component") or "unknown"
            session["status"] = "RETRIEVE_KNOWLEDGE"
            # Proceed directly to knowledge retrieval in this same turn
            current_status = "RETRIEVE_KNOWLEDGE"
        else:
            session["status"] = "IDENTIFY_PRODUCT"
            session_store.save(session_id, session)
            return {
                "status": "question",
                "question": "Could you please specify which product model you are troubleshooting (e.g. X100, A200)?",
                "session": session
            }

    # --- STATE: IDENTIFY_PRODUCT ---
    if current_status == "IDENTIFY_PRODUCT":
        entities = identify_product(message_clean)
        product = entities.get("product")
        
        if product:
            session["product"] = product
            session["issue"] = entities.get("error_code") or entities.get("component") or "unknown"
            session["status"] = "RETRIEVE_KNOWLEDGE"
            current_status = "RETRIEVE_KNOWLEDGE"
        else:
            session_store.save(session_id, session)
            return {
                "status": "question",
                "question": "I couldn't detect the product model. Please enter the model number (e.g. X100, A200, B300) to retrieve the correct manual.",
                "session": session
            }

    # --- STATE: RETRIEVE_KNOWLEDGE ---
    if current_status == "RETRIEVE_KNOWLEDGE":
        product = session["product"]
        issue = session["issue"]
        
        # Retrieve context manuals matching product and issue
        print(f"[Workflow] Retrieving context for product '{product}' and issue '{issue}'...")
        context_chunks = retrieve_context(
            query=f"{product} {issue} troubleshooting",
            query_entities={"product": product, "model": product}
        )
        
        session["context"] = context_chunks
        session["status"] = "DIAGNOSE"
        current_status = "DIAGNOSE"

    # --- STATE: DIAGNOSE ---
    if current_status == "DIAGNOSE":
        context_chunks = session.get("context", [])
        
        # Run agentic reasoning
        proposal = await diagnose_and_propose(context_chunks, session["history"], message_clean)
        decision = proposal.get("decision", "QUESTION")
        text = proposal.get("text", "")
        
        session["step"] += 1
        
        if decision == "QUESTION":
            session["status"] = "QUESTION"
            # Store the current question we are asking so we can map the answer later
            session["last_question"] = text
            session_store.save(session_id, session)
            return {
                "status": "question",
                "question": text,
                "session": session
            }
        elif decision == "ACTION":
            session["status"] = "ACTION"
            session["last_action"] = text
            session_store.save(session_id, session)
            return {
                "status": "action",
                "action": text,
                "session": session
            }
        else: # ESCALATE
            session["status"] = "ESCALATE"
            session_store.save(session_id, session)
            return {
                "status": "escalate",
                "message": text,
                "session": session
            }

    # --- STATE: QUESTION ---
    if current_status == "QUESTION":
        last_question = session.get("last_question", "Question")
        
        # Append answer to dialog history
        session["history"].append({
            "question": last_question,
            "answer": message_clean
        })
        
        # Diagnose again with new dialog history
        context_chunks = session.get("context", [])
        proposal = await diagnose_and_propose(context_chunks, session["history"], message_clean)
        decision = proposal.get("decision", "QUESTION")
        text = proposal.get("text", "")
        
        session["step"] += 1

        if decision == "QUESTION":
            session["last_question"] = text
            session_store.save(session_id, session)
            return {
                "status": "question",
                "question": text,
                "session": session
            }
        elif decision == "ACTION":
            session["status"] = "ACTION"
            session["last_action"] = text
            session_store.save(session_id, session)
            return {
                "status": "action",
                "action": text,
                "session": session
            }
        else: # ESCALATE
            session["status"] = "ESCALATE"
            session_store.save(session_id, session)
            return {
                "status": "escalate",
                "message": text,
                "session": session
            }

    # --- STATE: ACTION ---
    if current_status == "ACTION":
        # After suggesting an action, prompt verification
        session["status"] = "VERIFY"
        session_store.save(session_id, session)
        return {
            "status": "verify",
            "question": "Did this action resolve the issue? Please reply Yes or No.",
            "session": session
        }

    # --- STATE: VERIFY ---
    if current_status == "VERIFY":
        ans_lower = message_clean.lower()
        last_action = session.get("last_action", "previous action")
        
        if "yes" in ans_lower:
            session["status"] = "RESOLVED"
            session_store.save(session_id, session)
            return {
                "status": "resolved",
                "message": "Great! Glad to hear the issue is resolved and everything is functioning correctly.",
                "session": session
            }
        else:
            # Action did not work, update history and diagnostic path
            session["history"].append({
                "question": f"Did action '{last_action}' work?",
                "answer": f"No, user replied: {message_clean}"
            })
            
            # Re-evaluate next diagnosis / next proposal
            context_chunks = session.get("context", [])
            proposal = await diagnose_and_propose(context_chunks, session["history"], message_clean)
            decision = proposal.get("decision", "ESCALATE")
            text = proposal.get("text", "")
            
            session["step"] += 1

            if decision == "QUESTION":
                session["status"] = "QUESTION"
                session["last_question"] = text
                session_store.save(session_id, session)
                return {
                    "status": "question",
                    "question": text,
                    "session": session
                }
            elif decision == "ACTION":
                session["status"] = "ACTION"
                session["last_action"] = text
                session_store.save(session_id, session)
                return {
                    "status": "action",
                    "action": text,
                    "session": session
                }
            else: # ESCALATE
                session["status"] = "ESCALATE"
                session_store.save(session_id, session)
                return {
                    "status": "escalate",
                    "message": text,
                    "session": session
                }

    # Fallback/Safety Return
    return {
        "status": "escalate",
        "message": "Session has ended. If you need help with a new issue, please restart the session.",
        "session": session
    }
