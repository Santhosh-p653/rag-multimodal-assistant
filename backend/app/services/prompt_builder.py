"""
prompt_builder.py — Builds a grounded RAG prompt from retrieved context chunks.
"""


SYSTEM_PROMPT = """You are a technical support assistant.
Answer ONLY using the supplied context below.
If the answer is not present in the context, respond with exactly:
"I could not find that information in the uploaded manuals."
Do not make up information. Do not reference external knowledge."""


def build_prompt(chunks: list[dict], query: str) -> str:
    """
    Assemble the full prompt string from context chunks and the user query.

    Args:
        chunks: List of context dicts from retriever (must have 'content' key).
        query:  The user's question.

    Returns:
        A formatted prompt string ready to send to the LLM.
    """
    # Combine chunk contents with source labels
    context_parts = []
    for i, chunk in enumerate(chunks, 1):
        source = chunk.get("source", "unknown")
        content = chunk.get("content", "").strip()
        context_parts.append(f"[Source: {source}]\n{content}")

    context_text = "\n\n---\n\n".join(context_parts)

    prompt = f"""{SYSTEM_PROMPT}

Context:
{context_text}

Question:
{query}

Answer:"""

    return prompt
