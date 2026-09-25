"""
query_understanding.py — Pre-retrieval query understanding and normalization layer.
Extracts intent, entities, ambiguities, and classifies input confidence for routing.
"""
import json
from typing import Dict, Any

def detect_query_script(text: str) -> str:
    """Detect whether query text contains native Indic script (Tamil, Hindi, etc.)."""
    if any("\u0b80" <= ch <= "\u0bff" for ch in text):
        return "ta"
    if any("\u0900" <= ch <= "\u097f" for ch in text):
        return "hi"
    if any("\u0c00" <= ch <= "\u0c7f" for ch in text):
        return "te"
    if any("\u0c80" <= ch <= "\u0cff" for ch in text):
        return "kn"
    if any("\u0d00" <= ch <= "\u0d7f" for ch in text):
        return "ml"
    if any("\u0980" <= ch <= "\u09ff" for ch in text):
        return "bn"
    return "en"


def understand_query(raw_query: str, hint_language: str = "auto") -> Dict[str, Any]:
    """
    Analyzes the raw user query and returns a structured understanding payload.
    Translates non-English queries to standardized English in 'normalized_query' for search,
    while tracking the original language for localized answer generation.
    """
    from app.main import call_llm

    detected_script = detect_query_script(raw_query)
    effective_lang = detected_script if detected_script != "en" else (hint_language if hint_language != "auto" else "en")

    # Defensive fallback defaults
    fallback = {
        "original_query": raw_query,
        "normalized_query": raw_query,
        "language": effective_lang,
        "intent": "unknown",
        "entities": {},
        "technical_terms": [],
        "product_hint": None,
        "issue_hint": None,
        "ambiguities": [],
        "input_confidence": "LOW"
    }
    
    prompt = f"""You are a query understanding module for a technical support assistant.
Analyze the user query below. Handle multilingual input (Tamil, Hindi, English), colloquial language, and noisy speech-to-text artifacts gracefully.

Output ONLY valid JSON matching this schema:
{{
  "original_query": string,
  "normalized_query": string,
  "language": "{effective_lang}",
  "intent": "question" | "troubleshoot" | "greeting" | "unknown",
  "entities": {{}},
  "technical_terms": [],
  "product_hint": string or null,
  "issue_hint": string or null,
  "ambiguities": [],
  "input_confidence": "HIGH" | "MEDIUM" | "LOW"
}}

Rules:
- "normalized_query" MUST be rewritten in standard English for technical document search. If the query is in Tamil, Hindi, or another language, translate its core technical meaning into clear English.
- "input_confidence": use "HIGH" if clear and actionable, "MEDIUM" if partially unclear, "LOW" if vague or off-topic.
- "ambiguities": list specific questions to clarify any genuine ambiguity, or empty list [] if none.

User Query: "{raw_query}"
"""

    try:
        response_text = call_llm(prompt, task="classification")
        cleaned_text = response_text.replace("```json", "").replace("```", "").strip()
        data = json.loads(cleaned_text)
        
        # Ensure confidence is one of the allowed values
        confidence = data.get("input_confidence", "LOW")
        if confidence not in ["HIGH", "MEDIUM", "LOW"]:
            confidence = "LOW"

        # Sanitize normalized_query to discard template echoes or empty results
        normalized_query = str(data.get("normalized_query", "")).strip()
        placeholder_indicators = [
            "corrected, clear",
            "standardized version",
            "the corrected",
            "the core user intent",
            "the specific product",
            "string or null",
        ]
        if not normalized_query or any(p in normalized_query.lower() for p in placeholder_indicators):
            normalized_query = raw_query

        # Sanitize ambiguities to filter out prompt template echoes
        raw_ambiguities = data.get("ambiguities", [])
        ambiguities = []
        if isinstance(raw_ambiguities, list):
            for a in raw_ambiguities:
                if isinstance(a, str):
                    a_clean = a.strip()
                    if (
                        a_clean
                        and "clarification question" not in a_clean.lower()
                        and "fan is running" not in a_clean.lower()
                        and "either/or" not in a_clean.lower()
                        and len(a_clean) > 5
                    ):
                        ambiguities.append(a_clean)
            
        return {
            "original_query": data.get("original_query", raw_query),
            "normalized_query": normalized_query,
            "intent": data.get("intent", "unknown"),
            "entities": data.get("entities", {}) if isinstance(data.get("entities"), dict) else {},
            "technical_terms": data.get("technical_terms", []) if isinstance(data.get("technical_terms"), list) else [],
            "product_hint": data.get("product_hint"),
            "issue_hint": data.get("issue_hint"),
            "language": data.get("language", effective_lang),
            "ambiguities": ambiguities,
            "input_confidence": confidence
        }
        
    except Exception as e:
        print(f"[QueryUnderstanding] Failed to parse LLM response: {str(e)}")
        return fallback
