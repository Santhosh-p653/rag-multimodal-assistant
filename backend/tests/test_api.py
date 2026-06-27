import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

# Resolve namespace collision by renaming imports
from app.main import app as fastapi_app
import app.main as app_main

# Override parser service to avoid real init/file writes
app_main.parser_service = MagicMock()

client = TestClient(fastapi_app)


def test_api_health():
    with patch("app.services.vector_store.VectorStoreService") as mock_vs:
        mock_vs.return_value.count.return_value = 10
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        assert response.json()["vectors_stored"] == 10


@patch("app.main.retrieve_context")
@patch("app.main.call_llm")
def test_api_chat(mock_llm, mock_retrieve):
    mock_retrieve.return_value = [
        {"chunk_id": "c1", "content": "Manual instructions detail power checks.", "source": "manual.pdf"}
    ]
    mock_llm.return_value = "Please execute power checks on the device."

    response = client.post("/chat", json={"message": "How do I start the device?"})
    assert response.status_code == 200
    assert "power checks" in response.json()["answer"]
    assert "manual.pdf" in response.json()["sources"]
