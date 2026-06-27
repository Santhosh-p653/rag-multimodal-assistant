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


def test_rate_limits_chat():
    with patch("app.main.retrieve_context") as mock_ret, patch("app.main.call_llm") as mock_llm:
        mock_ret.return_value = [
            {
                "chunk_id": "c1",
                "content": "Manual instructions.",
                "source": "manual.pdf",
            }
        ]

        mock_llm.return_value = "Mocked LLM answer."

        # The limit on /chat is 20/minute
        for _ in range(20):
            response = client.post(
                "/chat",
                json={"message": "healthy rate limit test query"},
            )
            assert response.status_code == 200

        # The 21st query within the minute window must yield 429 Too Many Requests
        blocked_response = client.post(
            "/chat",
            json={"message": "healthy rate limit test query"},
        )

        assert blocked_response.status_code == 429