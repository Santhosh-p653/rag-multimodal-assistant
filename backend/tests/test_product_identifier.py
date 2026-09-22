# ruff: noqa: E402

from unittest.mock import patch, MagicMock
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

# Retrieve globally mocked modules
mock_groq = sys.modules["groq"]

from app.services.product_identifier import identify_product


def test_product_identifier_fallback():
    # Explicitly test regex fallback code path when both Ollama and cloud are disabled
    from app.config import settings
    with patch.object(settings, "OLLAMA_ENABLED", False), \
         patch("app.services.product_identifier.LLM_PROVIDER", "none"):
        result = identify_product(
            "My printer X100 displays Error E105 because the cooling fan failed"
        )

        assert result["product"] == "X100"
        assert result["model"] == "X100"
        assert result["category"] == "Printer"
        assert result["error_code"] == "E105"
        assert result["component"] == "Cooling Fan"
        assert result["product_family"] == "X-Series"


@patch("app.services.product_identifier.LLM_PROVIDER", "groq")
@patch("app.services.product_identifier.GROQ_API_KEY", "fakekey")
def test_product_identifier_llm():
    # Mock LLM API response returning structured JSON
    mock_client = MagicMock()
    mock_groq.Groq.return_value = mock_client

    mock_response = MagicMock()
    mock_response.choices[0].message.content = """
    {
      "product": "A200",
      "model": "A200",
      "category": "Router",
      "error_code": "E202",
      "component": "Power Supply",
      "product_family": "A-Series",
      "version": "v1.2",
      "section": "Diagnostics",
      "page": 12
    }
    """

    mock_client.chat.completions.create.return_value = mock_response

    result = identify_product(
        "Router model A200 showing E202 error on page 12"
    )

    assert result["product"] == "A200"
    assert result["error_code"] == "E202"
    assert result["category"] == "Router"
    assert result["page"] == 12


def test_product_identifier_ollama():
    """Verify that identify_product succeeds via Ollama with task='classification'."""
    from app.config import settings

    mock_json = """
    {
      "product": "VIC",
      "model": "VIC-100",
      "category": "Pump",
      "error_code": "None",
      "component": "Impeller",
      "product_family": "VIC-Series",
      "version": "v1.0",
      "section": "Installation",
      "page": 11
    }
    """
    with patch.object(settings, "OLLAMA_ENABLED", True), \
         patch("app.services.product_identifier.LLM_PROVIDER", "none"), \
         patch("app.services.product_identifier.generate", return_value=mock_json) as mock_gen:

        result = identify_product("Model VIC Vertical Industrial Turbine Can Pumps")

        mock_gen.assert_called_once()
        assert mock_gen.call_args.kwargs.get("task") == "classification"
        assert result["product"] == "VIC"
        assert result["model"] == "VIC-100"
        assert result["category"] == "Pump"
        assert result["page"] == 11