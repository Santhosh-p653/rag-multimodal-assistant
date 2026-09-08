"""
prompt_guard.py — Service to detect prompt injection attacks and out-of-domain queries.
Uses strict pattern-matching matching to reject override attempts or non-refrigerator queries.
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

# Domain boundary patterns for refrigerator & cooling appliance support
IN_DOMAIN_PATTERNS = [
    r"(?i)\b(?:refrigerator|refrigerators|fridge|fridges|freezer|freezers|cooler|coolers|chiller|chillers|ice\s*maker|defrost|compressor|evaporator|condenser|thermostat|door\s*seal|temperature|cooling|refrigerant|cold)\b"
]

OUT_OF_DOMAIN_PATTERNS = [
    r"(?i)\b(?:car|cars|engine|transmission|brake|brakes|tire|tires|oil\s+change|vehicle|automotive|honda|toyota|ford)\b",
    r"(?i)\b(?:recipe|recipes|bake|baking|cook|cooking|ingredient|ingredients|dish|soup|pasta|cake|pizza)\b",
    r"(?i)\b(?:washing\s+machine|washer|microwave|dishwasher|vacuum|oven|television|tv|dryer|lawn\s+mower)\b",
    r"(?i)\b(?:weather|forecast|stock|stocks|crypto|bitcoin|election|president|politics|capital\s+of)\b",
    r"(?i)\b(?:write\s+a\s+poem|tell\s+me\s+a\s+story|python\s+script|joke|jokes|movie|movies)\b",
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


def is_out_of_domain(query: str) -> bool:
    """
    Returns True if the query is explicitly out of the refrigerator/cooling appliance domain.
    Blocks non-refrigerator queries before reaching the LLM.
    """
    if not query:
        return False

    # If query explicitly contains refrigerator domain terms, consider it in-domain
    for in_pattern in IN_DOMAIN_PATTERNS:
        if re.search(in_pattern, query):
            return False

    # If query matches an out-of-domain topic pattern, return True (block)
    for pattern in OUT_OF_DOMAIN_PATTERNS:
        if re.search(pattern, query):
            print(f"[PromptGuard] Blocked out-of-domain query matching pattern: '{pattern}'")
            return True

    return False
