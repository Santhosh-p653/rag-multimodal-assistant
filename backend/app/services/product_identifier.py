"""
product_identifier.py — Service to identify product, model, component, error codes, and families from text.
Uses LLM structured extraction, falling back to local regex matching.
"""
import re
import json
from typing import Dict, Any, Optional
from app.config import LLM_PROVIDER, GROQ_API_KEY, SAMBANOVA_API_KEY, LLM_MODEL


def identify_product_fallback(text: str) -> Dict[str, Any]:
    """Fallback regex extractor for basic product names, categories, error codes, components."""
    text_lower = text.lower()

    # 1. Product detection
    product = None
    if "x100" in text_lower:
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

    # 2. Error code detection
    error_code = None
    err_match = re.search(r"\b(e\d{3})\b", text_lower)
    if err_match:
        error_code = err_match.group(1).upper()

    # 3. Category detection
    category = None
    if "printer" in text_lower:
        category = "Printer"
    elif "router" in text_lower:
        category = "Router"
    elif "camera" in text_lower:
        category = "Camera"

    # 4. Component detection
    component = None
    components = [
        "cooling fan",
        "power supply",
        "ink cartridge",
        "fan",
        "cable",
        "tray",
        "ink",
        "toner",
        "cartridge",
        "drum",
    ]
    for c in components:
        if c in text_lower:
            component = c.title()
            break

    # 5. Product family
    product_family = None
    if product:
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
    if LLM_PROVIDER == "none":
        return None

    prompt = f"""You are a technical support metadata extractor.
Analyze the following text and extract the following entity fields:
- product (e.g. "X100", "A200", null if not found)
- model (e.g. "X100", "A200", null if not found)
- category (e.g. "Printer", "Router", null if not found)
- error_code (e.g. "E105", "E202", null if not found)
- component (e.g. "Cooling Fan", "Power Supply", null if not found)
- product_family (e.g. "X-Series", "A-Series", null if not found)
- version (e.g. "v2.1", null if not found)
- section (e.g. "Troubleshooting", "Installation", null if not found)
- page (integer if mentioned, otherwise null)

Return the result strictly as a valid JSON object. Do not include any other markdown, text, backticks, or explanation.
Format:
{{
  "product": "X100" or null,
  "model": "X100" or null,
  "category": "Printer" or null,
  "error_code": "E105" or null,
  "component": "Cooling Fan" or null,
  "product_family": "X-Series" or null,
  "version": "v2.1" or null,
  "section": "Troubleshooting" or null,
  "page": 25 or null
}}

Text to analyze:
"{text}"
"""

    try:
        response_text = ""
        if LLM_PROVIDER == "groq":
            from groq import Groq

            client = Groq(api_key=GROQ_API_KEY)
            response = client.chat.completions.create(
                model=LLM_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=256,
            )
            response_text = response.choices[0].message.content.strip()

        elif LLM_PROVIDER == "sambanova":
            from openai import OpenAI

            client = OpenAI(
                api_key=SAMBANOVA_API_KEY,
                base_url="https://api.sambanova.ai/v1",
            )
            response = client.chat.completions.create(
                model=LLM_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=256,
            )
            response_text = response.choices[0].message.content.strip()

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
