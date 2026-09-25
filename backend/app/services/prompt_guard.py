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

# Domain boundary patterns for refrigerator & cooling appliance support AND automotive domain
IN_DOMAIN_PATTERNS = [
    # Refrigerator & cooling appliance patterns
    r"(?i)\b(?:refrigerator|refrigerators|fridge|fridges|freezer|freezers|cooler|coolers|chiller|chillers|ice\s*maker|defrost|compressor|evaporator|condenser|thermostat|door\s*seal|temperature|cooling|refrigerant|cold)\b",
    # Automotive / Vehicle patterns
    r"(?i)\b(?:car|cars|vehicle|vehicles|automobile|automobiles|automotive|truck|trucks|engine|transmission|gearbox|clutch|brake|brakes|braking|abs|suspension|steering|chassis|ecu|pcm|ecm|obd|obd2|obd-ii|dtc|alternator|starter|spark\s*plug|spark\s*plugs|fuel\s*pump|fuel\s*injector|fuel\s*injectors|radiator|coolant|exhaust|catalytic|misfire|cylinder|piston|timing\s*belt|timing\s*chain|battery|powertrain|drivetrain|tire|tires|wheel|wheels|oil\s*change|oil\s*filter|air\s*filter|o2\s*sensor|oxygen\s*sensor|rpm|speedometer|headlight|fuse|manifold|throttle)\b",
    # Automotive OBD-II DTC patterns (e.g. P0300, P0171, B1000, C0035, U0100)
    r"(?i)\b[PBCU]\d{4}\b",
    # Common vehicle makes
    r"(?i)\b(?:toyota|honda|ford|chevrolet|chevy|nissan|bmw|mercedes|benz|audi|volkswagen|vw|hyundai|kia|subaru|mazda|tesla|dodge|jeep|chrysler|lexus|acura|volvo)\b",
]

OUT_OF_DOMAIN_PATTERNS = [
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
    Returns True if the query is explicitly out of supported domains (refrigerators & automobiles).
    Blocks non-supported queries before reaching the LLM.
    """
    if not query:
        return False

    # If query explicitly contains domain terms, consider it in-domain
    for in_pattern in IN_DOMAIN_PATTERNS:
        if re.search(in_pattern, query):
            return False

    # If query matches an out-of-domain topic pattern, return True (block)
    for pattern in OUT_OF_DOMAIN_PATTERNS:
        if re.search(pattern, query):
            print(f"[PromptGuard] Blocked out-of-domain query matching pattern: '{pattern}'")
            return True

    return False
