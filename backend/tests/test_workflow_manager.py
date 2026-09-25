import pytest
import asyncio
from unittest.mock import patch, MagicMock
from app.services.workflow_manager import process_troubleshoot_turn, session_store
from app.config import settings


@pytest.fixture(autouse=True)
def clean_session():
    # Ensure fresh test session
    session_id = "test_workflow_session_123"
    session_store.clear(session_id)
    yield session_id
    session_store.clear(session_id)


def test_workflow_manager_unknown_product(clean_session):
    """When product cannot be identified, ask the user for product model."""
    session_id = clean_session
    
    with patch("app.services.workflow_manager.identify_product", return_value={"product": None}):
        async def run():
            res = await process_troubleshoot_turn(session_id, "My machine is making a loud buzzing sound")
            assert res["status"] == "question"
            assert "specify which product model" in res["question"] or "model" in res["question"].lower()
            assert res["session"]["status"] == "IDENTIFY_PRODUCT"
    
        asyncio.run(run())


def test_workflow_manager_ollama_troubleshoot_flow(clean_session):
    """
    Verify the full agentic troubleshooting flow with Ollama:
    START -> IDENTIFY_PRODUCT -> RETRIEVE_KNOWLEDGE -> DIAGNOSE (task='workflow') -> QUESTION
    """
    session_id = clean_session

    mock_llm_proposal = '{"decision": "QUESTION", "text": "Is the discharge valve fully opened or partially closed?", "reasoning": "Check flow obstruction"}'
    mock_entities = {"product": "VIC", "model": "VIC", "component": "impeller", "error_code": None}

    with patch.object(settings, "OLLAMA_ENABLED", True), \
         patch("app.services.troubleshooting_agent.LLM_PROVIDER", "none"), \
         patch("app.services.workflow_manager.identify_product", return_value=mock_entities), \
         patch("app.services.troubleshooting_agent.generate", return_value=mock_llm_proposal) as mock_gen, \
         patch("app.services.workflow_manager.retrieve_context", return_value=[{"source": "VIC_manual.pdf", "content": "VIC pump valve operation instructions"}]):

        async def run():
            res = await process_troubleshoot_turn(session_id, "Model VIC pump has severe cavitation")
            
            # Verify LLM was invoked with workflow task
            mock_gen.assert_called_once()
            assert mock_gen.call_args.kwargs.get("task") == "workflow"

            # Verify session state and response
            assert res["status"] == "question"
            assert res["question"] == "Is the discharge valve fully opened or partially closed?"
            assert res["session"]["product"] == "VIC"
            assert res["session"]["status"] == "QUESTION"

        asyncio.run(run())


def test_workflow_manager_action_transition(clean_session):
    """Verify state transition from QUESTION to ACTION when user provides answer."""
    session_id = clean_session

    mock_q = '{"decision": "QUESTION", "text": "Are the mounting bolts tight?", "reasoning": "Vibration check"}'
    mock_action = '{"decision": "ACTION", "text": "Tighten foundation anchor bolts to 120 Nm torque.", "reasoning": "Loose bolts cause vibration"}'
    mock_entities = {"product": "VIC", "model": "VIC", "component": "bolts", "error_code": None}

    with patch.object(settings, "OLLAMA_ENABLED", True), \
         patch("app.services.troubleshooting_agent.LLM_PROVIDER", "none"), \
         patch("app.services.workflow_manager.identify_product", return_value=mock_entities), \
         patch("app.services.workflow_manager.retrieve_context", return_value=[{"source": "VIC_manual.pdf", "content": "Foundation bolt specs"}]):

        async def run():
            # Turn 1: Initial problem -> ask question
            with patch("app.services.troubleshooting_agent.generate", return_value=mock_q):
                res1 = await process_troubleshoot_turn(session_id, "Model VIC pump vibrates heavily")
                assert res1["status"] == "question"
                assert res1["session"]["status"] == "QUESTION"

            # Turn 2: User answers -> propose action
            with patch("app.services.troubleshooting_agent.generate", return_value=mock_action):
                res2 = await process_troubleshoot_turn(session_id, "The bolts are visibly loose and wobbling")
                assert res2["status"] == "action"
                assert "Tighten" in res2["action"]
                assert res2["session"]["status"] == "ACTION"

        asyncio.run(run())
