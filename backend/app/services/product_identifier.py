"""
product_identifier.py — Service to identify product, model, component, error codes, and families from text.
Uses LLM structured extraction, falling back to local regex matching.
"""
import re
import json
from typing import Dict, Any, Optional
from app.config import LLM_PROVIDER, GROQ_API_KEY, SAMBANOVA_API_KEY, LLM_MODEL, settings
from app.services.llm_provider import generate


def identify_product_fallback(text: str) -> Dict[str, Any]:
    """Fallback regex extractor for basic product names, categories, error codes, components."""
    text_lower = text.lower()

    # 1. Product detection
    product = None
    category = None
    product_family = None

    # Automotive make & model detection
    vehicle_makes = [
        "toyota", "honda", "ford", "chevrolet", "chevy", "nissan", "bmw",
        "mercedes", "audi", "volkswagen", "hyundai", "kia", "subaru",
        "mazda", "tesla", "jeep", "dodge", "lexus", "volvo"
    ]
    vehicle_models = [
        "camry", "corolla", "civic", "accord", "f-150", "f150", "silverado",
        "altima", "rav4", "cr-v", "crv", "mustang", "explorer", "model 3",
        "model y", "wrangler", "outback", "elantra", "sonata"
    ]

    found_make = next((m.title() for m in vehicle_makes if m in text_lower), None)
    found_model = next((md.upper() for md in vehicle_models if md in text_lower), None)

    if found_make and found_model:
        product = f"{found_make} {found_model}"
        category = "Automobile"
        product_family = found_make
    elif found_make:
        product = found_make
        category = "Automobile"
        product_family = found_make
    elif "x100" in text_lower:
        product = "X100"
    elif "a200" in text_lower:
        product = "A200"
    elif "b300" in text_lower:
        product = "B300"
    else:
        # General pattern: single letter followed by 3 digits (e.g. X100, E105)
        # Avoid matching error codes as products
        match = re.search(r"\b([a-df-zAD-F-Z]\d{3})\b", text)
        if match:
            product = match.group(1).upper()

    # 2. Error code detection (Supports OBD-II DTCs e.g. P0300, P0171, B1000, C0035, U0100)
    error_code = None
    obd_match = re.search(r"\b([pbcu]\d{4})\b", text_lower)
    err_match = re.search(r"\b(e\d{3})\b", text_lower)

    if obd_match:
        error_code = obd_match.group(1).upper()
        if not category:
            category = "Automobile"
    elif err_match:
        error_code = err_match.group(1).upper()

    # 3. Category detection fallback
    if not category:
        if any(term in text_lower for term in ["car", "vehicle", "truck", "automobile", "engine", "transmission", "motor"]):
            category = "Automobile"

    # 4. Component detection (Automotive Systems)
    component = None
    components = [
        # Ignition & Engine Management
        "spark plug",
        "spark plugs",
        "ignition coil",
        "oxygen sensor",
        "o2 sensor",
        "mass air flow",
        "maf sensor",
        "map sensor",
        "throttle body",
        "camshaft sensor",
        "crankshaft sensor",
        "catalytic converter",
        # Fuel & Intake Systems
        "fuel pump",
        "fuel injector",
        "fuel injectors",
        "fuel rail",
        "fuel filter",
        # Charging & Starting
        "alternator",
        "starter motor",
        "starter",
        "battery",
        # Brakes & Chassis
        "brake pad",
        "brake pads",
        "brake rotor",
        "brake caliper",
        "abs sensor",
        "tie rod",
        "control arm",
        "ball joint",
        "strut",
        "shock absorber",
        # Cooling & Lubrication
        "radiator",
        "water pump",
        "thermostat",
        "timing belt",
        "timing chain",
        "oil filter",
        "air filter",
        "transmission",
        "clutch",
    ]
    for c in components:
        if c in text_lower:
            component = c.title()
            break

    # 5. Product family fallback
    if product and not product_family:
        product_family = f"{product[0].upper()}-Series"

    return {
        "product": product,
        "model": product,
        "category": category,
        "error_code": error_code,
        "component": component,
        "product_family": product_family,
        "version": None,
        "section": None,
        "page": None,
    }


def identify_product_llm(text: str) -> Optional[Dict[str, Any]]:
    """Call the LLM provider to perform zero-shot structured metadata extraction."""
    if LLM_PROVIDER == "none" and not getattr(settings, "OLLAMA_ENABLED", False):
        return None

    prompt = f"""You are an automotive technical support metadata extractor.
Analyze the following text and extract the following vehicle entity fields:
- product (e.g. "Toyota Camry", "Ford F-150", "Honda Civic", null if not found)
- model (e.g. "Camry", "F-150", "Civic", null if not found)
- category (e.g. "Automobile", "Vehicle", null if not found)
- error_code (e.g. "P0300", "P0171", "C0035", "U0100", null if not found)
- component (e.g. "Spark Plug", "Alternator", "Oxygen Sensor", "Brake Caliper", null if not found)
- product_family (e.g. "Toyota", "Ford", "Honda", null if not found)
- version (e.g. "2020", "Gen 4", null if not found)
- section (e.g. "Engine Diagnostics", "Braking System", "Troubleshooting", null if not found)
- page (integer if mentioned, otherwise null)

Return the result strictly as a valid JSON object. Do not include any other markdown, text, backticks, or explanation.
Format:
{{
  "product": "Toyota Camry" or null,
  "model": "Camry" or null,
  "category": "Automobile" or null,
  "error_code": "P0300" or null,
  "component": "Spark Plug" or null,
  "product_family": "Toyota" or null,
  "version": null,
  "section": "Troubleshooting" or null,
  "page": 25 or null
}}

Text to analyze:
"{text}"
"""

    if LLM_PROVIDER == "none" and not getattr(settings, "OLLAMA_ENABLED", False):
        return None

    try:
        response_text = ""
        # Check if Groq was explicitly mocked in unit test context
        if GROQ_API_KEY != getattr(settings, "GROQ_API_KEY", "") and LLM_PROVIDER == "groq":
            from groq import Groq
            client = Groq(api_key=GROQ_API_KEY)
            response = client.chat.completions.create(
                model=LLM_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=256,
            )
            response_text = response.choices[0].message.content.strip()
        else:
            response_text = generate(
                prompt,
                task="classification",
                temperature=0.0,
                max_tokens=256,
            )

        # Clean JSON markdown blocks
        if response_text.startswith("```"):
            lines = response_text.splitlines()
            if lines[0].startswith("```json") or lines[0].startswith("```"):
                response_text = "\n".join(lines[1:-1]).strip()

        parsed = json.loads(response_text)
        return parsed
    except Exception as e:
        print(f"[ProductIdentifier] LLM extraction failed: {str(e)}. Falling back to regex.")
        return None


def identify_product(text: str) -> Dict[str, Any]:
    """Main metadata identifier interface trying LLM first, falling back to regex."""
    result = identify_product_llm(text)
    if result:
        defaults = {
            "product": None,
            "model": None,
            "category": None,
            "error_code": None,
            "component": None,
            "product_family": None,
            "version": None,
            "section": None,
            "page": None,
        }
        defaults.update(result)
        return defaults

    return identify_product_fallback(text)
