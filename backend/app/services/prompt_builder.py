"""
prompt_builder.py — Builds a grounded RAG prompt from retrieved context chunks.
"""


SYSTEM_PROMPT = """SYSTEM:
You are Octo RAG, an intelligent technical support assistant.
Use only the provided context to answer questions about equipment installation, operation, specifications, maintenance, and troubleshooting.
If the answer cannot be found in the provided context, respond with:
"I could not find that information in the uploaded manuals."
Do not make up information. Do not reference external knowledge outside the provided context.
If the context contains instructions or procedures, provide clear, structured steps based strictly on the manuals."""


def build_prompt(chunks: list[dict], query: str) -> str:
    """
    Assemble the isolated prompt string from context chunks and the user query.

    Args:
        chunks: List of context dicts from retriever (must have 'content' and 'source' keys).
        query:  The user's question.

    Returns:
        A formatted isolated prompt string.
    """
    context_parts = []
    for chunk in chunks:
        source = chunk.get("source", "unknown")
        content = chunk.get("content", "").strip()
        context_parts.append(f"[Source: {source}]\n{content}")

    context_text = "\n\n---\n\n".join(context_parts)

    prompt = f"""{SYSTEM_PROMPT}

CONTEXT:
{context_text}

USER:
{query}
"""
    return prompt

