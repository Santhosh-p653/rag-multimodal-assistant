"""
query_understanding.py — Pre-retrieval query understanding and normalization layer.
Extracts intent, entities, ambiguities, and classifies input confidence for routing.
"""
import json
from typing import Dict, Any

def understand_query(raw_query: str) -> Dict[str, Any]:
    """
    Analyzes the raw user query and returns a structured understanding payload.
    Returns:
      original_query: str
      normalized_query: str
      intent: str
      entities: dict
      technical_terms: list[str]
      product_hint: str | None
      issue_hint: str | None
      ambiguities: list[str]
      input_confidence: Literal["HIGH", "MEDIUM", "LOW"]
    """
    from app.main import call_llm

    # Defensive fallback defaults
    fallback = {
        "original_query": raw_query,
        "normalized_query": raw_query,
        "intent": "unknown",
        "entities": {},
        "technical_terms": [],
        "product_hint": None,
        "issue_hint": None,
        "ambiguities": [],
        "input_confidence": "LOW"
    }
    
    prompt = f"""You are a query understanding module for a technical support assistant.
Analyze the user query below. Handle vague queries, incomplete sentences, spelling/grammar mistakes, colloquial language, and noisy speech-to-text artifacts gracefully.

Output ONLY valid JSON matching this schema:
{{
  "original_query": string,
  "normalized_query": string,
  "intent": "question" | "troubleshoot" | "greeting" | "unknown",
  "entities": {{}},
  "technical_terms": [],
  "product_hint": string or null,
  "issue_hint": string or null,
  "ambiguities": [],
  "input_confidence": "HIGH" | "MEDIUM" | "LOW"
}}

Rules:
- "normalized_query" MUST be the actual rewritten user query in standard English. NEVER output instructions, placeholder descriptions, or empty string. If the query is already clear, repeat the user query verbatim.
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
            "ambiguities": ambiguities,
            "input_confidence": confidence
        }
        
    except Exception as e:
        print(f"[QueryUnderstanding] Failed to parse LLM response: {str(e)}")
        return fallback
