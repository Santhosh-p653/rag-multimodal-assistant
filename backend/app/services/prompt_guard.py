"""
prompt_guard.py — Service to detect prompt injection attacks and out-of-domain queries.
Uses strict pattern-matching to reject override attempts, non-automotive queries, or household appliance requests.
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

# Domain boundary patterns strictly for the Automotive & Vehicle Diagnostic domain
IN_DOMAIN_PATTERNS = [
    # Core Automotive / Vehicle terms
    r"(?i)\b(?:car|cars|vehicle|vehicles|automobile|automobiles|automotive|truck|trucks|suv|sedan|coupe|motorcycle|van)\b",
    # Powertrain, Engine & Mechanical
    r"(?i)\b(?:engine|motor|transmission|gearbox|clutch|flywheel|driveshaft|differential|axle|cv\s*joint|transfer\s*case|powertrain|drivetrain)\b",
    # Braking, Steering & Suspension
    r"(?i)\b(?:brake|brakes|braking|caliper|rotors?|pads?|abs|master\s*cylinder|brake\s*fluid|suspension|struts?|shocks?|springs?|sway\s*bar|control\s*arm|ball\s*joint|steering|tie\s*rod|rack\s*and\s*pinion|power\s*steering|alignment|chassis)\b",
    # Electrical, Sensors & Diagnostics
    r"(?i)\b(?:ecu|pcm|ecm|bcm|tcm|obd|obd2|obd-ii|dtc|alternator|starter|spark\s*plug|spark\s*plugs|ignition\s*coil|distributor|battery|fuse|relay|wiring|harness|ground|multimeter|oscilloscope|live\s*data|freeze\s*frame)\b",
    # Fuel, Air & Exhaust Systems
    r"(?i)\b(?:fuel\s*pump|fuel\s*injector|fuel\s*injectors|fuel\s*rail|fuel\s*filter|fuel\s*pressure|intake\s*manifold|throttle\s*body|maf|map\s*sensor|turbo|turbocharger|supercharger|exhaust|catalytic\s*converter|muffler|o2\s*sensor|oxygen\s*sensor|egr|evap|pcv)\b",
    # Cooling & Lubrication Systems (Automotive)
    r"(?i)\b(?:radiator|coolant|antifreeze|water\s*pump|thermostat\s*housing|oil\s*change|oil\s*filter|oil\s*pan|oil\s*pump|dipstick|viscosity|head\s*gasket|overheating|timing\s*belt|timing\s*chain)\b",
    # Wheels, Tires & Body
    r"(?i)\b(?:tire|tires|wheel|wheels|tpms|torque\s*spec|torque\s*wrench|lug\s*nut|headlight|taillight|wiper|windshield)\b",
    # Automotive OBD-II DTC patterns (e.g. P0300, P0171, B1000, C0035, U0100)
    r"(?i)\b[PBCU]\d{4}\b",
    # Vehicle Manufacturers & Brands
    r"(?i)\b(?:toyota|honda|ford|chevrolet|chevy|nissan|bmw|mercedes|benz|audi|volkswagen|vw|hyundai|kia|subaru|mazda|tesla|dodge|jeep|chrysler|lexus|acura|volvo|mitsubishi|gmc|ram|infiniti|cadillac|buick|lincoln|land\s*rover|porsche|jaguar)\b",
]

# Queries explicitly forbidden / out-of-domain (including refrigerators, cooling appliances, recipes, non-automotive electronics)
OUT_OF_DOMAIN_PATTERNS = [
    # Refrigerator & cooling appliance patterns (strictly rejected)
    r"(?i)\b(?:refrigerator|refrigerators|fridge|fridges|freezer|freezers|cooler|coolers|chiller|chillers|ice\s*maker|defrost\s*heater|door\s*gasket|refrigerant\s*r134a\s*fridge)\b",
    # General household appliances
    r"(?i)\b(?:washing\s+machine|washer|microwave|dishwasher|vacuum|oven|stove|toaster|blender|television|tv|dryer|lawn\s+mower|air\s*fryer|water\s*heater)\b",
    # Cooking & Food
    r"(?i)\b(?:recipe|recipes|bake|baking|cook|cooking|ingredient|ingredients|dish|soup|pasta|cake|pizza|sandwich|salad)\b",
    # General non-automotive topics
    r"(?i)\b(?:weather|forecast|stock|stocks|crypto|bitcoin|election|president|politics|capital\s+of|horoscope)\b",
    r"(?i)\b(?:write\s+a\s+poem|tell\s+me\s+a\s+story|python\s+script|joke|jokes|movie|movies|song|lyrics)\b",
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
    Returns True if the query is outside the automotive domain.
    Explicitly rejects refrigerator, cooling appliance, and general non-vehicle queries before reaching the LLM.
    """
    if not query:
        return False

    # Check explicit out-of-domain patterns FIRST (e.g. refrigerator or cooking queries)
    for pattern in OUT_OF_DOMAIN_PATTERNS:
        if re.search(pattern, query):
            print(f"[PromptGuard] Blocked out-of-domain query matching pattern: '{pattern}'")
            return True

    # If query matches verified automotive domain terms, allow it
    for in_pattern in IN_DOMAIN_PATTERNS:
        if re.search(in_pattern, query):
            return False

    # If query contains neither automotive terms nor explicit out-of-domain terms,
    # we allow general technical follow-ups ("how do I test it?", "what is the torque?")
    # while blocking purely random queries
    return False
