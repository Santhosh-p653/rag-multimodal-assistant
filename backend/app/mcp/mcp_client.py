"""
mcp_client.py — Diagnostic MCP Tool Client helper for Octo RAG services.
Invokes local FastMCP tools directly or asynchronously for context enrichment.
"""
from typing import Dict, Any, Optional
from app.mcp.fridge_mcp_server import (
    lookup_error_code,
    get_thermistor_ohm_table,
    lookup_part_number,
    search_fridge_manuals
)


def invoke_mcp_error_lookup(brand: str, model: str, code: str) -> Dict[str, Any]:
    """Invoke MCP error code diagnostic tool."""
    return lookup_error_code(brand=brand, model=model, code=code)


def invoke_mcp_thermistor_table(temp_celsius: float) -> Dict[str, Any]:
    """Invoke MCP thermistor ohm table tool."""
    return get_thermistor_ohm_table(temp_celsius=temp_celsius)


def invoke_mcp_part_lookup(model: str, component_name: str) -> Dict[str, Any]:
    """Invoke MCP OEM part lookup tool."""
    return lookup_part_number(model=model, component_name=component_name)


def invoke_mcp_search(query: str, source_file: Optional[str] = None) -> str:
    """Invoke MCP manual search tool."""
    return search_fridge_manuals(query=query, source_file=source_file)
