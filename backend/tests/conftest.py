import pytest
import sys
from unittest.mock import MagicMock

# Define global mocks for external dependencies to avoid state bleed
sys.modules["sentence_transformers"] = MagicMock()
sys.modules["qdrant_client"] = MagicMock()
sys.modules["qdrant_client.models"] = MagicMock()
sys.modules["faster_whisper"] = MagicMock()
sys.modules["edge_tts"] = MagicMock()
sys.modules["markitdown"] = MagicMock()
sys.modules["groq"] = MagicMock()
sys.modules["openai"] = MagicMock()


@pytest.fixture(autouse=True)
def reset_rate_limits():
    """Reset slowapi rate limiter logs before each test."""
    try:
        from app.main import limiter
        limiter.reset()
    except Exception:
        pass
