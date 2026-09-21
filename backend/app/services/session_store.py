"""
session_store.py — In-memory session store for tracking troubleshooting diagnostic histories and user chat sessions.
"""
import time
from typing import Dict, Any, List, Optional


class SessionStore:
    """In-memory session registry for agentic state retention across turns and user conversation history."""

    _instance = None

    def __new__(cls):
        # Singleton: share sessions database across API endpoints
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.sessions = {}
            print("[SessionStore] Diagnostic session database initialized.")
        return cls._instance

    def get(self, session_id: str) -> Dict[str, Any]:
        """Fetch an active session state by session_id, initializing it if empty."""
        now = time.time()
        if session_id not in self.sessions:
            self.sessions[session_id] = {
                "session_id": session_id,
                "user_id": "default_user",
                "title": "New Conversation",
                "created_at": now,
                "updated_at": now,
                "product": None,
                "issue": None,
                "step": 0,
                "status": "START",
                "history": [],
                "messages": [],
                "context": [],
                # Phase 2 Additions
                "last_valid_user_query": None,
                "last_normalized_query": None,
                "pending_clarification": False,
                "clarification_question": None,
                "clarification_context": None,
                "clarification_attempts": 0,
                "last_valid_response": None,
                "input_confidence": None,
                "retrieval_confidence": None,
            }
        return self.sessions[session_id].copy()

    def save(self, session_id: str, data: Dict[str, Any]):
        """Save/overwrite a session state."""
        payload = data.copy()
        payload["updated_at"] = time.time()
        if "created_at" not in payload:
            payload["created_at"] = payload["updated_at"]
        self.sessions[session_id] = payload

    def append_message(self, session_id: str, message: Dict[str, Any], user_id: Optional[str] = None):
        """Append a message to the session and update title if first message."""
        session = self.get(session_id)
        if user_id:
            session["user_id"] = user_id
        if "messages" not in session:
            session["messages"] = []
        session["messages"].append(message)

        # Set title from first user query if still generic
        if session.get("title") in ("New Conversation", None) and message.get("sender") == "user":
            text = message.get("text", "").strip()
            session["title"] = (text[:40] + "...") if len(text) > 40 else (text or "Conversation")

        self.save(session_id, session)

    def list_by_user(self, user_id: str) -> List[Dict[str, Any]]:
        """List summary of all sessions for a specific user, newest first."""
        user_sessions = [
            {
                "session_id": sid,
                "user_id": s.get("user_id", "default_user"),
                "title": s.get("title", "Conversation"),
                "created_at": s.get("created_at", 0),
                "updated_at": s.get("updated_at", 0),
                "message_count": len(s.get("messages", [])),
                "last_message": (s.get("messages", [])[-1].get("text", "")[:60] if s.get("messages") else ""),
                "product": s.get("product"),
                "status": s.get("status"),
            }
            for sid, s in self.sessions.items()
            if s.get("user_id") == user_id or user_id == "all"
        ]
        user_sessions.sort(key=lambda x: x.get("updated_at", 0), reverse=True)
        return user_sessions

    def clear(self, session_id: str):
        """Delete a session's history."""
        if session_id in self.sessions:
            del self.sessions[session_id]
