import asyncio
import sys
import os
from unittest.mock import Mock, patch

# Bypass slowapi limiter
def mock_decorator(*args, **kwargs):
    def decorator(func):
        return func
    return decorator

m = Mock()
m.limit = mock_decorator
sys.modules['slowapi'] = Mock(Limiter=Mock(return_value=m))
sys.modules['slowapi.util'] = Mock()
sys.modules['slowapi.errors'] = Mock()

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

# Now we can import safely without ML models downloading/loading
from app.main import agent_run, AgentRequest
from app.services.agent_flow import agent_graph
from fastapi import Request

async def run_test(name, query, mock_retrieve_conf, expected_status, expected_retries=0, mock_qu_val=None):
    print(f"\n=== Test: {name} ===")
    req = Request({"type": "http", "client": ("127.0.0.1", 8000)})
    session_id = f"test-sess-{name.replace(' ', '')}"
    
    with patch("app.services.agent_flow.understand_query") as mock_qu, \
         patch("app.services.agent_flow.retrieve_context_service") as mock_retrieve, \
         patch("app.services.agent_flow.call_llm") as mock_main_llm:
        
        # 1. User says something
        if mock_qu_val is None:
            mock_qu_val = {"input_confidence": "HIGH", "product_hint": "printer", "normalized_query": "Fix printer"}
        mock_qu.return_value = mock_qu_val
        
        call_count = 0
        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= expected_retries:
                return ([], "LOW")
            return ([{"source": "manual.pdf", "content": "Fake content."}], mock_retrieve_conf)
            
        mock_retrieve.side_effect = side_effect
        mock_main_llm.return_value = '{"answer": "Diag answer", "steps": []}'
        
        res = await agent_run(AgentRequest(query=query, session_id=session_id), req)
        
        print("Assistant Answer:", res.get("answer"))
        print("Status:", res.get("status"))
        print("Needs Clarification:", res.get("clarification_needed"))
        print("Retrievals Called:", call_count)
        
        assert res.get("status") == expected_status, f"Expected {expected_status}, got {res.get('status')}"
        print("-> PASS")

async def test_high_confidence():
    await run_test("HIGH Confidence", "Fix printer", "HIGH", "answered", expected_retries=0)

async def test_medium_confidence():
    await run_test("MEDIUM Confidence", "Fix printer", "MEDIUM", "answered", expected_retries=0)

async def test_low_confidence_fallback():
    # Will retry once and then fail -> fallback
    mock_val = {"input_confidence": "HIGH", "normalized_query": "how to cook"}
    await run_test("LOW Confidence (Fallback)", "how to cook", "LOW", "fallback", expected_retries=1, mock_qu_val=mock_val)

if __name__ == "__main__":
    import dotenv
    dotenv.load_dotenv(os.path.join(os.path.dirname(__file__), "..", "backend", ".env"))
    asyncio.run(test_high_confidence())
    asyncio.run(test_medium_confidence())
    asyncio.run(test_low_confidence_fallback())
