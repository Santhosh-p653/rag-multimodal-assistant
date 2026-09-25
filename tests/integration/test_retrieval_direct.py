"""
tests/integration/test_retrieval_direct.py — Direct vector retrieval & LLM generation verification.
Preserved from scratch/test_retrieval_direct.py.
"""
import sys
import os

# Ensure backend root is on sys.path regardless of execution working directory
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "backend"))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from app.services.retriever import retrieve_context
from app.services.vector_store import VectorStoreService
from app.services.llm_provider import call_llm

def run_direct_retrieval_test(query: str = "What is the operating pressure of the Industrial Pump Model IP-500?"):
    vs = VectorStoreService()
    chunks_all = vs.get_all_chunks()
    print(f"Total chunks in vector store: {len(chunks_all)}")
    for c in chunks_all[:5]:
        print(f"Chunk from {c.get('source_file')}: {c.get('content')[:100]}...")

    chunks, conf = retrieve_context(query)
    print(f"Retrieved {len(chunks)} chunks with confidence {conf}:")
    for c in chunks:
        print(f"  - Source: {c.get('source')}, Score: {c.get('rrf_score')}, Content: {c.get('content')[:80]}")

    if not chunks:
        print("No chunks retrieved. Skipping prompt synthesis.")
        return

    context_str = "\n\n".join([f"--- Source: {c['source']} ---\n{c['content']}" for c in chunks])
    prompt = f"""You are a technical support assistant. Answer the user's question using only the provided context. If the answer cannot be found in the context, say "I could not find that information in the uploaded manuals."
Context:
{context_str}

User Question: {query}
Answer:"""

    print("\n--- Sending Prompt to call_llm(task='chat') ---")
    print(prompt)
    print("\n--- LLM Response ---")
    ans = call_llm(prompt, task="chat")
    print("Answer:", repr(ans))

if __name__ == "__main__":
    run_direct_retrieval_test()
