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
    name="Octo RAG Diagnostic Server",
    description="Diagnostics, error code resolution, multimeter testing, and manual retrieval for appliances and automobiles."
)


# --- Knowledge Base Retrieval Tool ---
@mcp.tool()
def search_fridge_manuals(query: str, source_file: str = "") -> str:
    """
    Search Octo RAG vector database for technical appliance and automotive manuals, installation steps, and troubleshooting.

    Args:
        query: The search query or question about appliance or vehicle manuals.
        source_file: Optional filename filter (e.g. 'GE_Profile_Fridge.pdf' or 'Toyota_Camry_Manual.pdf').

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


# --- Diagnostic Error Code Tool (Appliance & OBD-II Automotive) ---
@mcp.tool()
def lookup_error_code(brand: str, model: str, code: str) -> dict:
    """
    Lookup diagnostic error code details, component test instructions, multimeter pins, and repair steps.
    Supports both appliance control codes and automotive OBD-II DTCs.

    Args:
        brand: Brand / Make (e.g. GE, Whirlpool, LG, Toyota, Ford, Honda).
        model: Model number, series, or vehicle model (e.g. Profile, WRF535, Camry, F-150).
        code: Error code displayed on control panel or logged via OBD-II (e.g. 'Er FF', 'SY EF', 'P0300', 'P0171', 'P0420').

    Returns:
        Dictionary containing fault description, component to test, multimeter test procedure, and resolution.
    """
    normalized_code = code.strip().upper()

    ERROR_DATABASE = {
        # Refrigerator & Appliance Codes
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
        },
        # Automotive OBD-II Diagnostic Trouble Codes (DTCs)
        "P0300": {
            "component": "Ignition / Fuel System (Random Misfire)",
            "description": "Random / Multiple Cylinder Misfire Detected.",
            "test_procedure": "Inspect spark plugs, ignition coils, and fuel injectors across all cylinders. Test fuel pressure with fuel pressure gauge.",
            "recommended_action": "Check for vacuum leaks. Replace worn spark plugs or faulty ignition coil packs. Clean fouled fuel injectors."
        },
        "P0171": {
            "component": "Mass Airflow (MAF) / Fuel Trim System",
            "description": "System Too Lean (Bank 1) — ECM detected air-fuel mixture is excessively lean.",
            "test_procedure": "Inspect intake boots for cracks or vacuum leaks. Spray MAF cleaner on Mass Airflow Sensor wires. Check fuel rail pressure.",
            "recommended_action": "Smoke test intake manifold for vacuum leaks. Replace faulty MAF sensor or upstream O2 sensor. Replace clogged fuel filter."
        },
        "P0420": {
            "component": "Catalytic Converter System",
            "description": "Catalyst System Efficiency Below Threshold (Bank 1).",
            "test_procedure": "Monitor upstream and downstream O2 sensor waveforms with scan tool. Upstream should oscillate (0.1V - 0.9V); downstream should remain stable (~0.45V).",
            "recommended_action": "Verify exhaust manifold has no pre-cat exhaust leaks. If downstream O2 mirrors upstream, replace catalytic converter assembly."
        },
        "P0455": {
            "component": "EVAP Emission Control System",
            "description": "Evaporative Emission System Leak Detected (Gross Leak / No Flow).",
            "test_procedure": "Inspect fuel filler cap seal for cracks or loose fit. Command EVAP purge solenoid with bidirectional scan tool.",
            "recommended_action": "Tighten or replace fuel cap. Smoke-test EVAP vapor lines, EVAP canister, and purge/vent solenoids."
        },
        "U0100": {
            "component": "CAN Bus Communication Network",
            "description": "Lost Communication With Engine Control Module (ECM / PCM).",
            "test_procedure": "Measure CAN-High to CAN-Low terminating resistance at OBD-II port pins 6 and 14 (Expected: ~60 Ohms with battery disconnected).",
            "recommended_action": "Inspect ECM wiring harness and ground lugs for corrosion. Check ECM power supply fuses and relays."
        },
        "B1000": {
            "component": "Electronic Control Unit (ECU)",
            "description": "ECU / Body Control Module Internal Hardware Fault.",
            "test_procedure": "Verify vehicle battery voltage is above 12.4V. Check ECU ground references and power lines.",
            "recommended_action": "Clear code and perform battery hard reset. If fault returns immediately, reprogram or replace module."
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
        "description": f"Diagnostic code '{normalized_code}' logged on {brand} {model}.",
        "test_procedure": "Perform system reset sequence. Query onboard diagnostic mode self-test.",
        "recommended_action": "Query Octo RAG technical manuals for exact wiring diagram schematic for model series."
    }


# --- Multimeter Thermistor Resistance Conversion Tool ---
@mcp.tool()
def get_thermistor_ohm_table(temp_celsius: float) -> dict:
    """
    Get expected resistance (kΩ) for NTC thermistor temperature sensors for multimeter diagnostic testing.
    Supports both appliance thermistors (defrost/evaporator) and automotive thermistors (ECT Engine Coolant & IAT Intake Air sensors).

    Args:
        temp_celsius: Temperature in °C (e.g. -20.0 for freezer, 0.0 for ice bath test, 25.0 for room temp, 90.0 for engine operating temp).

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
    Lookup OEM replacement part numbers and technical specifications for appliance and automotive components.

    Args:
        model: Model or series (e.g. 'GE Profile', 'Whirlpool WRF535', 'Toyota Camry', 'Ford F-150').
        component_name: Component description (e.g. 'spark plug', 'alternator', 'brake pad', 'fuel pump', 'defrost heater', 'start relay', 'ice maker').

    Returns:
        Dictionary with OEM part number, component specs, and replacement difficulty level.
    """
    comp_lower = component_name.strip().lower()

    PARTS_CATALOG = [
        # Appliance OEM Parts
        {"key": "heater", "oem_part": "WR51X10055", "name": "Glass Tube Defrost Heater Assembly", "voltage": "120V AC, 525W", "difficulty": "Moderate"},
        {"key": "relay", "oem_part": "WR07X10055", "name": "Compressor PTC Start Relay & Overload", "voltage": "120V AC, 12-15 Ohm", "difficulty": "Easy"},
        {"key": "valve", "oem_part": "WR57X10032", "name": "Dual Water Inlet Valve Assembly", "voltage": "120V AC, Dual Solenoid", "difficulty": "Moderate"},
        {"key": "fan", "oem_part": "WR60X10185", "name": "Evaporator Fan Motor (DC Brushless)", "voltage": "12V DC, 3.2W", "difficulty": "Moderate"},
        {"key": "board", "oem_part": "WR55X10942", "name": "Main Electronic Control Board", "voltage": "120V AC Input / 12V DC Logic", "difficulty": "Easy"},
        {"key": "seal", "oem_part": "WR14X10065", "name": "Magnetic Fresh Food Door Gasket", "voltage": "N/A", "difficulty": "Easy"},
        {"key": "ice", "oem_part": "WR30X10093", "name": "Automatic Ice Maker Kit", "voltage": "120V AC, 8-Cube Cycle", "difficulty": "Easy"},
        # Automotive OEM / Aftermarket Parts
        {"key": "spark plug", "oem_part": "NGK-6619-ILFR6A", "name": "Laser Iridium Spark Plug", "voltage": "Ignition 25kV-45kV", "difficulty": "Easy"},
        {"key": "plug", "oem_part": "NGK-6619-ILFR6A", "name": "Laser Iridium Spark Plug", "voltage": "Ignition 25kV-45kV", "difficulty": "Easy"},
        {"key": "alternator", "oem_part": "DENSO-210-0658", "name": "OEM Remanufactured Alternator (130A)", "voltage": "13.8V - 14.4V DC, 130A", "difficulty": "Moderate"},
        {"key": "brake pad", "oem_part": "BOSCH-BC905", "name": "QuietCast Ceramic Brake Pad Set", "voltage": "N/A (Friction)", "difficulty": "Moderate"},
        {"key": "brake", "oem_part": "BOSCH-BC905", "name": "QuietCast Ceramic Brake Pad Set", "voltage": "N/A (Friction)", "difficulty": "Moderate"},
        {"key": "fuel pump", "oem_part": "WALBRO-GSS342", "name": "High Pressure In-Tank Electric Fuel Pump", "voltage": "12V DC, 255 LPH", "difficulty": "Hard"},
        {"key": "oxygen sensor", "oem_part": "BOSCH-15717", "name": "Direct-Fit Heated Oxygen Sensor (O2)", "voltage": "0.1V - 0.9V Signal, 12V Heater", "difficulty": "Easy"},
        {"key": "o2", "oem_part": "BOSCH-15717", "name": "Direct-Fit Heated Oxygen Sensor (O2)", "voltage": "0.1V - 0.9V Signal, 12V Heater", "difficulty": "Easy"},
        {"key": "oil filter", "oem_part": "MOBIL-M1-110A", "name": "Extended Performance Engine Oil Filter", "voltage": "N/A (Filtration)", "difficulty": "Easy"},
        {"key": "battery", "oem_part": "OPT-34R-800", "name": "12V AGM Starting Battery (800 CCA)", "voltage": "12.6V DC nominal", "difficulty": "Easy"},
        {"key": "radiator", "oem_part": "DENSO-221-3142", "name": "Direct-Fit Aluminum Radiator Core", "voltage": "N/A (Thermal)", "difficulty": "Moderate"}
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
        "electrical_specs": "Refer to unit rating plate / manufacturer specs",
        "repair_difficulty": "Consult service manual",
        "status": "GENERIC_LOOKUP"
    }


# --- LangGraph Unified Agentic Execution Tool ---
@mcp.tool()
def run_octo_agent(query: str, source_input: str = "", session_id: str = "") -> dict:
    """
    Execute the full Octo RAG LangGraph agentic graph (agent_flow.py).
    Scrapes web pages or ingests files if provided, performs version checking, fuzzy product matching,
    waterfall hybrid retrieval, and returns grounded answers with diagnostic steps and images.

    Args:
        query: User question or technical query.
        source_input: Optional URL to scrape or local filename.
        session_id: Optional session identifier.

    Returns:
        Dictionary containing answer, steps, sources, product_id, images, and status.
    """
    try:
        import uuid
        from app.services.agent_flow import agent_graph

        sid = session_id.strip() if session_id else str(uuid.uuid4())
        inputs = {
            "query": query,
            "source_input": source_input.strip() if source_input else None,
            "source_content": None,
            "product_id": None,
            "clarification_needed": False,
            "retrieved_chunks": [],
            "sources": [],
            "mode": "qa",
            "answer": "",
            "steps": [],
            "content_changed": False,
            "version_info": None,
            "clarification_options": [],
            "session_id": sid,
            "input_confidence": "LOW",
            "retrieval_confidence": "LOW",
            "clarification_question": None,
            "clarification_attempts": 0,
            "resolved_query": None,
            "retrieval_retries": 0,
            "understood_data": {}
        }
        result = agent_graph.invoke(inputs)
        return result
    except Exception as e:
        return {"answer": f"Agent workflow execution failed: {str(e)}", "status": "error"}


def _run_async_safely(async_fn, *args, **kwargs):
    """Safely run async coroutine from synchronous MCP tool regardless of event loop state."""
    import asyncio
    import concurrent.futures
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            return executor.submit(lambda: asyncio.run(async_fn(*args, **kwargs))).result()
    else:
        return asyncio.run(async_fn(*args, **kwargs))


# --- Stateful Troubleshooting Turn Tool ---
@mcp.tool()
def troubleshoot_appliance_turn(session_id: str, message: str) -> dict:
    """
    Execute a turn in the stateful multi-turn troubleshooting engine (workflow_manager.py).
    Guides technicians step-by-step through diagnostic paths (QUESTION -> ACTION -> VERIFY -> RESOLVED/ESCALATE).

    Args:
        session_id: Active troubleshooting session ID.
        message: Technician's response or diagnostic answer.

    Returns:
        Dictionary containing current state, next diagnostic question/action, options, and status.
    """
    try:
        from app.services.workflow_manager import process_troubleshoot_turn
        return _run_async_safely(process_troubleshoot_turn, session_id, message)
    except Exception as e:
        return {"answer": f"Troubleshooting turn failed: {str(e)}", "status": "error"}


# --- Files MCP Tools (Relational PostgreSQL + Qdrant Vector Engine) ---

@mcp.tool()
def list_manuals() -> dict:
    """
    List all technical manuals currently registered in PostgreSQL manual_registry
    and available in the Qdrant hybrid vector store.

    Returns:
        Structured JSON dictionary containing registered manuals, chunk counts, hashes, and total count.
    """
    try:
        from app.database.postgres import list_registered_manuals
        from app.services.vector_store import VectorStoreService

        pg_manuals = _run_async_safely(list_registered_manuals)
        vs = VectorStoreService()
        vector_sources = vs.get_unique_sources()

        return {
            "status": "success",
            "count": len(pg_manuals) if pg_manuals else len(vector_sources),
            "manuals": pg_manuals,
            "vector_sources": vector_sources
        }
    except Exception as e:
        return {"status": "error", "error": str(e), "manuals": [], "count": 0}


@mcp.tool()
def upload_manual(
    filename: str,
    content_base64: str,
    equipment_type: str = "industrial",
    model: str = ""
) -> dict:
    """
    Upload and index a technical equipment or vehicle manual via MCP.
    Performs MD5 duplicate check in PostgreSQL, converts/chunks document, embeds vectors into Qdrant,
    and registers in PostgreSQL manual_registry.

    Args:
        filename: Name of the manual file (e.g. 'Haas_CNC_VF2.pdf' or 'Toyota_Camry_2022.pdf').
        content_base64: Base64-encoded raw binary contents of the manual document.
        equipment_type: Equipment domain category ('industrial', 'automobile', 'appliance').
        model: Optional specific model identifier.

    Returns:
        Structured JSON dictionary with ingestion status, chunks count, markdown path, and registry details.
    """
    try:
        import base64
        from app.services.parser import ParserService
        from app.database.postgres import check_manual_duplicate_by_hash, register_manual

        file_bytes = base64.b64decode(content_base64)
        if not file_bytes:
            return {"status": "error", "error": "Decoded file content is empty"}

        # Check duplicate
        dup = _run_async_safely(check_manual_duplicate_by_hash, file_bytes)
        if dup:
            return {
                "status": "skipped_duplicate",
                "filename": filename,
                "message": f"Identical file hash already indexed for {dup.get('filename')}",
                "chunks_ingested": dup.get("chunks_count", 0),
                "file_hash": dup.get("file_hash")
            }

        # Parse, chunk, and vectorize
        parser = ParserService()
        parse_result = parser.parse_file(filename, file_bytes)

        # Register in PostgreSQL
        reg_result = _run_async_safely(
            register_manual,
            filename=filename,
            file_bytes=file_bytes,
            equipment_type=equipment_type,
            model=model if model else None,
            chunks_count=parse_result["chunks_ingested"]
        )

        return {
            "status": "processed",
            "filename": filename,
            "markdown_file": parse_result["markdown_file"],
            "chunks_ingested": parse_result["chunks_ingested"],
            "equipment_type": equipment_type,
            "registered_record": reg_result[1] if isinstance(reg_result, tuple) else reg_result
        }
    except Exception as e:
        return {"status": "error", "error": str(e), "filename": filename}


@mcp.tool()
def delete_manual(filename: str) -> dict:
    """
    Delete a manual completely from the knowledge base:
    1. Removes raw document from input storage
    2. Removes parsed markdown and extracted figure images
    3. Purges text & image vectors from Qdrant collections
    4. Removes record from PostgreSQL manual_registry

    Args:
        filename: Name of the manual to delete.

    Returns:
        Structured JSON dictionary confirming deletion.
    """
    try:
        import os
        import shutil
        from pathlib import Path
        from app.config import settings
        from app.services.vector_store import VectorStoreService
        from app.database.postgres import delete_registered_manual
        from app.services.retriever import clear_retrieval_cache

        safe_filename = os.path.basename(filename)
        base_name, _ = os.path.splitext(safe_filename)

        # 1. Remove raw file
        raw_path = Path(settings.INPUT_DIR) / safe_filename
        if raw_path.exists():
            try:
                raw_path.unlink()
            except Exception:
                pass

        # 2. Remove markdown file
        md_path = Path(settings.OUTPUT_DIR) / f"{base_name}.md"
        if md_path.exists():
            try:
                md_path.unlink()
            except Exception:
                pass

        # 3. Remove extracted images folder
        images_dir = Path(settings.OUTPUT_DIR) / "images" / base_name
        if images_dir.exists():
            shutil.rmtree(images_dir, ignore_errors=True)

        # 4. Remove vectors from Qdrant
        vs = VectorStoreService()
        vs.delete_by_filename(safe_filename)
        vs.delete_images_by_filename(safe_filename)

        # 5. Remove from PostgreSQL
        pg_deleted = _run_async_safely(delete_registered_manual, safe_filename)

        # Clear retrieval cache
        try:
            clear_retrieval_cache()
        except Exception:
            pass

        return {
            "status": "deleted",
            "filename": safe_filename,
            "postgres_record_removed": pg_deleted
        }
    except Exception as e:
        return {"status": "error", "error": str(e), "filename": filename}


@mcp.tool()
def get_manual_metadata(filename: str) -> dict:
    """
    Retrieve comprehensive metadata and indexing telemetry for a specific manual.
    Queries PostgreSQL manual_registry and Qdrant vector index.

    Args:
        filename: Name of the manual to inspect.

    Returns:
        Structured JSON dictionary containing file hash, chunk counts, equipment category, and timestamps.
    """
    try:
        import os
        from app.database.postgres import get_manual_by_filename
        from app.services.vector_store import VectorStoreService

        safe_filename = os.path.basename(filename)
        record = _run_async_safely(get_manual_by_filename, safe_filename)
        vs = VectorStoreService()
        all_sources = vs.get_unique_sources()
        is_in_vectors = safe_filename in all_sources

        if not record and not is_in_vectors:
            return {
                "status": "not_found",
                "filename": safe_filename,
                "found": False,
                "message": "Manual not found in PostgreSQL registry or vector store"
            }

        return {
            "status": "success",
            "filename": safe_filename,
            "found": True,
            "in_vector_store": is_in_vectors,
            "metadata": record or {"filename": safe_filename, "equipment_type": "industrial"}
        }
    except Exception as e:
        return {"status": "error", "error": str(e), "filename": filename}


if __name__ == "__main__":
    print("[Octo RAG MCP] Starting Refrigerator Diagnostic MCPServer...", file=sys.stderr)
    mcp.run()

