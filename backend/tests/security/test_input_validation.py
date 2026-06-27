import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

# Resolve namespace collision by renaming imports
from app.main import app as fastapi_app
import app.main as app_main

# Override parser service
app_main.parser_service = MagicMock()

client = TestClient(fastapi_app)


def test_empty_query():
    # Chat request with empty message should fail Pydantic constraints
    response = client.post("/chat", json={"message": ""})
    assert response.status_code == 422


def test_oversized_query():
    # Chat request exceeding 4000 characters should fail Pydantic constraints
    huge_message = "A" * 4001
    response = client.post("/chat", json={"message": huge_message})
    assert response.status_code == 422


def test_troubleshoot_constraints():
    # Oversized message in troubleshoot should be rejected
    response = client.post(
        "/troubleshoot",
        json={"session_id": "ok_sess", "message": "A" * 4001}
    )
    assert response.status_code == 422

    # Oversized session_id (limit 100) should be rejected
    response2 = client.post(
        "/troubleshoot",
        json={"session_id": "X" * 101, "message": "Help"}
    )
    assert response2.status_code == 422
