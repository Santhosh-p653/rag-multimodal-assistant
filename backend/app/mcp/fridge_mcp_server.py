"""
fridge_mcp_server.py — MCPServer for Octo RAG Refrigerator Assistant.
Exposes refrigerator diagnostic tools and manual vector database access.
Can be executed as stdio server or mounted via SSE in FastAPI.
"""
import sys
import os
import math
from mcp.server.mcpserver import MCPServer

# Ensure backend root is on sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

# Initialize MCPServer instance
mcp = MCPServer(
    name="Octo RAG Refrigerator Diagnostic Server",
    description="Diagnostics, error code resolution, multimeter testing, and manual retrieval for refrigerators."
)


# --- Knowledge Base Retrieval Tool ---
@mcp.tool()
def search_fridge_manuals(query: str, source_file: str = "") -> str:
    """
    Search Octo RAG vector database for technical refrigerator manuals, installation steps, and troubleshooting.

    Args:
        query: The search query or question about refrigerator manuals.
        source_file: Optional filename filter (e.g. 'GE_Profile_Fridge.pdf').

    Returns:
        Formatted manual context string with source citations.
    """
    try:
        from app.services.retriever import retrieve_context
        chunks, confidence = retrieve_context(query, source_file=source_file if source_file else None)
        if not chunks:
            return "No relevant technical manual context found in vector store."

        formatted_chunks = []
        for i, chunk in enumerate(chunks, 1):
            src = chunk.get("source", "unknown")
            pg = chunk.get("page_number", "N/A")
            content = chunk.get("content", "").strip()
            formatted_chunks.append(f"--- Chunk {i} [Source: {src} | Page: {pg}] ---\n{content}")

        return f"Retrieval Confidence: {confidence}\n\n" + "\n\n".join(formatted_chunks)
    except Exception as e:
        return f"Error retrieving context from manuals: {str(e)}"


# --- Refrigerator Error Code Diagnostic Tool ---
@mcp.tool()
def lookup_error_code(brand: str, model: str, code: str) -> dict:
    """
    Lookup diagnostic error code details, component test instructions, multimeter pins, and repair steps.

    Args:
        brand: Appliance brand (e.g. GE, Whirlpool, LG, Samsung, Frigidaire).
        model: Model number or series (e.g. Profile, French Door, Side-by-Side).
        code: Error code displayed on control panel (e.g. 'Er FF', 'SY EF', '22 E', 'E5', '88 88').

    Returns:
        Dictionary containing fault description, component to test, multimeter test procedure, and resolution.
    """
    normalized_code = code.strip().upper()

    ERROR_DATABASE = {
        "ER FF": {
            "component": "Evaporator Fan Motor",
            "description": "Freezer Evaporator Fan Motor failure or ice blockage detected.",
            "test_procedure": "Measure voltage between Fan Signal Pin & GND on PCB (Expected: 12V DC). Check fan blade rotation for ice buildup.",
            "recommended_action": "Thaw ice blockage, test fan motor resistance (approx 1.5 - 3.0 kOhm across coil), replace motor if open loop."
        },
        "SY EF": {
            "component": "Evaporator Fan Circuit",
            "description": "System Evaporator Fan communication error or harness failure.",
            "test_procedure": "Disconnect J4 connector on main board. Check continuity from J4 pin 3 to fan motor connector.",
            "recommended_action": "Inspect wire harness for corrosion or pin displacement. Replace main control board if harness passes continuity."
        },
        "22 E": {
            "component": "Freezer Fan Motor",
            "description": "Freezer fan locked rotor or feedback pulse missing.",
            "test_procedure": "Check for 12V DC supply at fan motor harness. Rotate fan manually to test bearing drag.",
            "recommended_action": "Clear frost from fan housing. Replace fan motor if 12V present but motor fails to spin."
        },
        "E5": {
            "component": "Defrost Sensor / Thermistor",
            "description": "Defrost temperature sensor open circuit or shorted.",
            "test_procedure": "Measure thermistor resistance at room temp (25°C / 77°F). Expected: ~10 kOhm. At 0°C (32°F): ~32.6 kOhm.",
            "recommended_action": "Replace defrost sensor thermistor if resistance reads 0 Ohm (shorted) or infinite open-loop."
        },
        "88 88": {
            "component": "Main Control Board Power Reset",
            "description": "Power glitch or control panel communication lockup.",
            "test_procedure": "Unplug refrigerator from wall outlet for 5 minutes. Re-plug and observe display boot sequence.",
            "recommended_action": "If '88 88' persists after power cycle, inspect main PCB for burnt capacitors or replace main board."
        }
    }

    if normalized_code in ERROR_DATABASE:
        result = ERROR_DATABASE[normalized_code].copy()
        result.update({"brand": brand, "model": model, "code": normalized_code, "status": "FOUND"})
        return result

    return {
        "brand": brand,
        "model": model,
        "code": normalized_code,
        "status": "GENERIC_FALLBACK",
        "component": "Control Board / Sensor Loop",
        "description": f"Diagnostic code '{normalized_code}' logged on {brand} {model} control display.",
        "test_procedure": "Disconnect main power for 5 minutes to reset main microcomputer. Perform diagnostic mode self-test via keypad code.",
        "recommended_action": "Query Octo RAG technical manuals for exact wiring diagram schematic for model series."
    }


# --- Multimeter Thermistor Resistance Conversion Tool ---
@mcp.tool()
def get_thermistor_ohm_table(temp_celsius: float) -> dict:
    """
    Get expected resistance (kΩ) for refrigerator NTC thermistor temperature sensors for multimeter diagnostic testing.

    Args:
        temp_celsius: Temperature in °C (e.g. -20.0 for freezer, 0.0 for ice bath test, 25.0 for room temp).

    Returns:
        Dictionary with expected Resistance in kΩ, Voltage drop, and multimeter diagnostic guidance.
    """
    T0 = 298.15
    R0 = 10.0  # kΩ
    Beta = 3950.0

    T_kelvin = temp_celsius + 273.15
    if T_kelvin <= 0:
        return {"error": "Invalid temperature below absolute zero."}

    expected_kohm = R0 * math.exp(Beta * ((1.0 / T_kelvin) - (1.0 / T0)))
    expected_kohm_rounded = round(expected_kohm, 2)
    temp_fahrenheit = round((temp_celsius * 9/5) + 32, 1)

    return {
        "temperature_celsius": temp_celsius,
        "temperature_fahrenheit": temp_fahrenheit,
        "expected_resistance_kohm": expected_kohm_rounded,
        "multimeter_setting": "200kOhm Resistance (Ohms)",
        "testing_instruction": f"Place multimeter probes on thermistor leads. At {temp_celsius}°C ({temp_fahrenheit}°F), meter should read approx {expected_kohm_rounded} kOhm. Reading 0 Ohm indicates short circuit; infinite reading indicates open wire.",
        "status": "OK"
    }


# --- OEM Replacement Part Lookup Tool ---
@mcp.tool()
def lookup_part_number(model: str, component_name: str) -> dict:
    """
    Lookup OEM replacement part numbers and technical specifications for refrigerator components.

    Args:
        model: Refrigerator model or series (e.g. 'GE Profile', 'Whirlpool WRF535', 'LG LFXS28566S').
        component_name: Component description (e.g. 'defrost heater', 'start relay', 'water valve', 'ice maker', 'door seal').

    Returns:
        Dictionary with OEM part number, component specs, and replacement difficulty level.
    """
    comp_lower = component_name.strip().lower()

    PARTS_CATALOG = [
        {"key": "heater", "oem_part": "WR51X10055", "name": "Glass Tube Defrost Heater Assembly", "voltage": "120V AC, 525W", "difficulty": "Moderate"},
        {"key": "relay", "oem_part": "WR07X10055", "name": "Compressor PTC Start Relay & Overload", "voltage": "120V AC, 12-15 Ohm", "difficulty": "Easy"},
        {"key": "valve", "oem_part": "WR57X10032", "name": "Dual Water Inlet Valve Assembly", "voltage": "120V AC, Dual Solenoid", "difficulty": "Moderate"},
        {"key": "fan", "oem_part": "WR60X10185", "name": "Evaporator Fan Motor (DC Brushless)", "voltage": "12V DC, 3.2W", "difficulty": "Moderate"},
        {"key": "board", "oem_part": "WR55X10942", "name": "Main Electronic Control Board", "voltage": "120V AC Input / 12V DC Logic", "difficulty": "Easy"},
        {"key": "seal", "oem_part": "WR14X10065", "name": "Magnetic Fresh Food Door Gasket", "voltage": "N/A", "difficulty": "Easy"},
        {"key": "ice", "oem_part": "WR30X10093", "name": "Automatic Ice Maker Kit", "voltage": "120V AC, 8-Cube Cycle", "difficulty": "Easy"}
    ]

    for part in PARTS_CATALOG:
        if part["key"] in comp_lower:
            return {
                "searched_model": model,
                "searched_component": component_name,
                "oem_part_number": part["oem_part"],
                "official_name": part["name"],
                "electrical_specs": part["voltage"],
                "repair_difficulty": part["difficulty"],
                "status": "MATCH_FOUND"
            }

    return {
        "searched_model": model,
        "searched_component": component_name,
        "oem_part_number": "GENERIC_OEM_SPECIFIED",
        "official_name": f"Replacement {component_name.title()} for {model}",
        "electrical_specs": "Refer to unit rating plate",
        "repair_difficulty": "Consult service manual",
        "status": "GENERIC_LOOKUP"
    }


if __name__ == "__main__":
    print("[Octo RAG MCP] Starting Refrigerator Diagnostic MCPServer...", file=sys.stderr)
    mcp.run()
