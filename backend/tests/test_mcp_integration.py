"""
test_mcp_integration.py — Security & Integration tests for Octo RAG MCP Server.
"""
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.main import app as fastapi_app
import app.main as app_main

app_main.parser_service = MagicMock()
client = TestClient(fastapi_app)


def test_mcp_error_code_tool():
    from app.mcp.mcp_client import invoke_mcp_error_lookup

    result = invoke_mcp_error_lookup("GE", "Profile", "Er FF")
    assert result["status"] == "FOUND"
    assert result["component"] == "Evaporator Fan Motor"
    assert "12V DC" in result["test_procedure"]

    fallback_result = invoke_mcp_error_lookup("Whirlpool", "SideBySide", "UNKNOWN_999")
    assert fallback_result["status"] == "GENERIC_FALLBACK"


def test_mcp_thermistor_ohm_tool():
    from app.mcp.mcp_client import invoke_mcp_thermistor_table

    res_25c = invoke_mcp_thermistor_table(25.0)
    assert res_25c["status"] == "OK"
    assert res_25c["expected_resistance_kohm"] == 10.0

    res_0c = invoke_mcp_thermistor_table(0.0)
    assert res_0c["expected_resistance_kohm"] > 25.0


def test_mcp_part_lookup_tool():
    from app.mcp.mcp_client import invoke_mcp_part_lookup

    part_res = invoke_mcp_part_lookup("GE Profile", "defrost heater")
    assert part_res["status"] == "MATCH_FOUND"
    assert part_res["oem_part_number"] == "WR51X10055"


def test_mcp_manual_search_tool():
    from app.mcp.mcp_client import invoke_mcp_search

    with patch("app.services.retriever.retrieve_context") as mock_ret:
        mock_ret.return_value = (
            [{"chunk_id": "c1", "content": "Defrost heater replacement instructions", "source": "manual.pdf", "page_number": 4}],
            "HIGH"
        )
        res = invoke_mcp_search("defrost heater replacement")
        assert "Defrost heater replacement instructions" in res
        assert "Retrieval Confidence: HIGH" in res


def test_mcp_sse_endpoint_mounted():
    # Verify /mcp route exists on FastAPI app
    routes = [r.path for r in fastapi_app.routes]
    assert any(r.startswith("/mcp") for r in routes)
