import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "backend")))
from app.services.query_understanding import understand_query
from app.main import chat, ChatRequest
import asyncio

def test_124():
    print("--- 1.2.4 Testing understand_query fallback ---")
    from unittest.mock import patch
    with patch("app.services.query_understanding.call_llm", return_value="malformed json"):
        res = understand_query("printer issue")
        assert res["input_confidence"] == "LOW"
        assert res["normalized_query"] == "printer issue"
        print("Passed 1.2.4: Fallback defaults triggered correctly.")

def test_123():
    print("--- 1.2.3 Testing agent_flow retrieve tuple unpack ---")
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
    try:
        res = agent_graph.invoke(inputs)
        print("Passed 1.2.3: agent_graph executed successfully.")
    except Exception as e:
        print(f"Failed 1.2.3: {str(e)}")

if __name__ == "__main__":
    import dotenv
    dotenv.load_dotenv("backend/.env")
    test_124()
    test_123()
