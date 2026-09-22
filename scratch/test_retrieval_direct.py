import sys
import os
sys.path.insert(0, os.path.abspath("backend"))

from app.services.retriever import retrieve_context
from app.services.vector_store import VectorStoreService
from app.services.llm_provider import call_llm

query = "What is the operating pressure of the Industrial Pump Model IP-500?"
vs = VectorStoreService()
chunks_all = vs.get_all_chunks()
print(f"Total chunks in vector store: {len(chunks_all)}")
for c in chunks_all:
    print(f"Chunk from {c.get('source_file')}: {c.get('content')[:100]}...")

chunks, conf = retrieve_context(query)
print(f"Retrieved {len(chunks)} chunks with confidence {conf}:")
for c in chunks:
    print(f"  - Source: {c.get('source')}, Score: {c.get('rrf_score')}, Content: {c.get('content')[:80]}")

context_str = "\n\n".join([f"--- Source: {c['source']} ---\n{c['content']}" for c in chunks])
prompt = f"""You are a technical support assistant. Answer the user's question using only the provided context. If the answer cannot be found in the context, say "I could not find that information in the uploaded manuals."
Context:
{context_str}

User Question: {query}\nAnswer:"""

print("\n--- Sending Prompt to call_llm(task='chat') ---")
print(prompt)
print("\n--- LLM Response ---")
ans = call_llm(prompt, task="chat")
print("Answer:", repr(ans))
