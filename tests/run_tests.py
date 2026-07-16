import asyncio
import sys
import os

# Bypass slowapi limiter by mocking it before importing main
from unittest.mock import Mock
def mock_decorator(*args, **kwargs):
    def decorator(func):
        return func
    return decorator

m = Mock()
m.limit = mock_decorator
sys.modules['slowapi'] = Mock(Limiter=Mock(return_value=m))
sys.modules['slowapi.util'] = Mock()
sys.modules['slowapi.errors'] = Mock()

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "backend")))

from app.main import chat, ChatRequest, agent_run, AgentRequest
from app.config import RRF_HIGH_THRESHOLD, RRF_LOW_THRESHOLD
from fastapi import Request

async def test_checklist():
    print(f"Current Thresholds: HIGH={RRF_HIGH_THRESHOLD}, LOW={RRF_LOW_THRESHOLD}")
    
    req = Request({"type": "http", "client": ("127.0.0.1", 8000)})
    
    tests = [
        {"desc": "Clear query", "q": "What is error E105 on X100?"},
        {"desc": "Vague query (zero signal)", "q": "help"},
        {"desc": "Vague query (partial signal)", "q": "printer thing"},
        {"desc": "Misspelled", "q": "cnt prnt on pinter"},
        {"desc": "Incomplete", "q": "the red light"},
        {"desc": "Unrelated", "q": "how to cook pasta"},
        {"desc": "Ambiguous", "q": "fan is noisy"}
    ]
    
    for t in tests:
        print(f"\n=== Testing: {t['desc']} ===")
        print(f"Query: {t['q']}")
        try:
            res = await chat(ChatRequest(message=t['q']), req)
            print(f"Answer: {res.answer}")
            print(f"Needs Clarification: {res.needs_clarification}")
            print(f"Clarification Q: {res.clarification_question}")
            print(f"Sources: {res.sources}")
        except Exception as e:
            print(f"Error: {str(e)}")

    print("\n=== Testing: /agent/run regression ===")
    try:
        from app.services.agent_flow import agent_graph
        inputs = {
            "query": "How do I fix the blinking light on X100?",
            "source_input": None,
            "source_content": None,
            "product_id": None,
            "clarification_needed": False,
            "retrieved_chunks": [],
            "sources": [],
            "mode": "qa",
            "answer": "",
            "steps": [],
            "content_changed": False,
            "version_info": None,
            "clarification_options": []
        }
        res = agent_graph.invoke(inputs)
        print("Agent Run result keys:", res.keys())
        print("Agent Run sources:", res.get("sources"))
    except Exception as e:
        print("Agent Run error:", str(e))

if __name__ == "__main__":
    import dotenv
    dotenv.load_dotenv("backend/.env")
    asyncio.run(test_checklist())
