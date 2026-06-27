"""
prompt_guard.py — Service to detect prompt injection attacks.
Uses strict pattern-matching matching to reject override or developer prompt leak attempts.
"""
import re

# Regex patterns matching common prompt injection techniques
INJECTION_PATTERNS = [
    r"(?i)ignore\s+(?:previous|above|the)?\s*instructions",
    r"(?i)system\s+prompt",
    r"(?i)developer\s+message",
    r"(?i)reveal\s+(?:hidden|system)?\s*prompt",
    r"(?i)show\s+secrets",
    r"(?i)override\s+(?:instructions|rules)",
    r"(?i)forget\s+(?:previous\s+)?rules",
    r"(?i)you\s+must\s+ignore",
    r"(?i)new\s+instructions",
    r"(?i)bypass\s+restrictions",
]


def is_prompt_injection(query: str) -> bool:
    """Returns True if the query resembles a prompt injection attack, else False."""
    if not query:
        return False

    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, query):
            print(f"[PromptGuard] Blocked query due to injection pattern: '{pattern}'")
            return True

    return False
