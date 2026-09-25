"""
auto_mcp_server.py — Dedicated Automotive Model Context Protocol (MCP) Server for OCTO-AUTO.
Exposes vehicle diagnostic tools, OBD-II DTC resolution, ECT sensor ohm tables, OEM parts catalog,
multimodal visual schematics retrieval, and PostgreSQL-persisted vehicle manuals management.
Can be executed as a stdio server for Claude Desktop / IDEs or mounted via SSE in FastAPI (/auto_mcp/sse).
"""
import sys
import os
import math
import base64
from typing import Dict, Any, List, Optional
from mcp.server.mcpserver import MCPServer

# Ensure backend root is on sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

# Initialize FastMCP Server instance
mcp = MCPServer(
    name="Octo Automotive Diagnostic Server",
    description="Automotive diagnostics, OBD-II DTC troubleshooting, sensor multimeter testing, visual wiring schematics, and factory manual management."
)


def _run_async_safely(async_fn, *args, **kwargs):
    """
    Executes an async function safely from within a synchronous FastMCP tool thread.
    Creates a dedicated thread with a clean event loop to prevent 'NoneType' send crashes.
    """
    import concurrent.futures
    import asyncio

    def worker():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(async_fn(*args, **kwargs))
        finally:
            loop.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        fut = pool.submit(worker)
        return fut.result(timeout=60)


# ─── Tool 1: Vehicle Manual Knowledge Retrieval ──────────────────────────────
@mcp.tool()
def search_vehicle_manuals(query: str, make: str = "", model: str = "", source_file: str = "") -> str:
    """
    Search OCTO-AUTO vector database for factory service manuals, wiring schematics, torque specs, and repair steps.

    Args:
        query: Diagnostic question or component search query (e.g. 'alternator replacement torque specs', 'P0301 spark plug gap').
        make: Vehicle manufacturer (e.g. 'Toyota', 'Ford', 'Honda', 'Nissan').
        model: Vehicle model name (e.g. 'Camry', 'F-150', 'Civic').
        source_file: Optional filename filter (e.g. 'Toyota_Camry_2021_Manual.pdf').

    Returns:
        Formatted manual context string with source citations and retrieval confidence.
    """
    try:
        from app.services.retriever import retrieve_context
        query_entities = {}
        if make or model:
            query_entities = {"make": make, "model": model, "product": f"{make} {model}".strip()}

        chunks, confidence = retrieve_context(
            query,
            source_file=source_file if source_file else None,
            query_entities=query_entities if query_entities else None
        )
        if not chunks:
            return "No relevant vehicle manual context found in vector store. Check uploaded manuals or refine query."

        formatted_chunks = []
        for i, chunk in enumerate(chunks, 1):
            src = chunk.get("source", "unknown")
            pg = chunk.get("page_number") or chunk.get("page", "N/A")
            content = chunk.get("content", "").strip()
            formatted_chunks.append(f"--- Document Chunk {i} [Source: {src} | Page: {pg}] ---\n{content}")

        return f"Retrieval Confidence: {confidence}\n\n" + "\n\n".join(formatted_chunks)
    except Exception as e:
        return f"Error retrieving context from vehicle manuals: {str(e)}"


# ─── Tool 2: OBD-II Diagnostic Trouble Code (DTC) Resolver ────────────────────
@mcp.tool()
def lookup_obd_error_code(code: str, make: str = "", model: str = "") -> dict:
    """
    Lookup OBD-II Diagnostic Trouble Code (DTC) details, freeze-frame inspection criteria,
    multimeter circuit test points, probable causes, and repair procedures.

    Args:
        code: OBD-II code (e.g. 'P0300', 'P0301', 'P0420', 'P0171', 'P0128', 'P0455', 'U0100').
        make: Vehicle make (e.g. 'Toyota', 'Ford', 'Chevrolet', 'Honda').
        model: Vehicle model (e.g. 'Camry', 'Silverado', 'Accord').

    Returns:
        Structured diagnostic dictionary with DTC definition, severity, test points, and repair steps.
    """
    code_upper = code.strip().upper()

    obd_database: Dict[str, Dict[str, Any]] = {
        "P0300": {
            "title": "Random / Multiple Cylinder Misfire Detected",
            "system": "Ignition & Fuel Delivery",
            "severity": "CRITICAL (Flashing Check Engine Light causes catalyst damage)",
            "probable_causes": [
                "Low fuel pressure / clogged fuel filter",
                "Mass Airflow Sensor (MAF) contamination",
                "Worn spark plugs or failing ignition coil pack rail",
                "Large vacuum leak at intake manifold gasket",
                "EGR valve stuck open"
            ],
            "multimeter_pinouts": "Measure fuel pump supply voltage (>12.0V) and resistance of fuel injector coils (11-14 ohms at 20°C).",
            "diagnostic_steps": [
                "1. Connect OBD-II scan tool and inspect live misfire counts per cylinder.",
                "2. If misfires are localized to one bank, inspect Bank 1 O2 sensor and fuel trims (STFT/LTFT).",
                "3. Perform smoke test on intake boot and PCV hose for unmetered air leaks.",
                "4. Check fuel rail pressure with mechanical gauge against OEM specification (typically 40-55 psi)."
            ]
        },
        "P0301": {
            "title": "Cylinder 1 Misfire Detected",
            "system": "Cylinder 1 Ignition / Injection / Compression",
            "severity": "HIGH",
            "probable_causes": [
                "Fouled or worn Cylinder 1 spark plug",
                "Defective Cylinder 1 Coil-on-Plug (COP) boot or coil pack",
                "Clogged or leaking Cylinder 1 fuel injector",
                "Low compression on Cylinder 1 (worn piston rings or burnt valve)"
            ],
            "multimeter_pinouts": "COP Connector Pin 1 (12V B+), Pin 2 (Chassis Ground <0.5 ohms), Pin 3 (ECU Trigger 5V pulse).",
            "diagnostic_steps": [
                "1. Swap Cylinder 1 ignition coil with Cylinder 2.",
                "2. Clear DTCs and road test vehicle. If code moves to P0302, replace ignition coil.",
                "3. If misfire remains on Cylinder 1, remove spark plug and inspect for oil/fuel fouling.",
                "4. Swap fuel injector 1 with injector 3 or perform compression test (target: >150 psi, within 10% across cylinders)."
            ]
        },
        "P0420": {
            "title": "Catalytic Converter System Efficiency Below Threshold (Bank 1)",
            "system": "Exhaust & Emissions Control",
            "severity": "MODERATE (Emissions failure)",
            "probable_causes": [
                "Degraded three-way catalytic converter substrate",
                "Exhaust leak upstream or near downstream O2 sensor",
                "Faulty downstream heated oxygen sensor (Sensor 2)",
                "Engine oil or coolant burning poisoning catalyst washcoat"
            ],
            "multimeter_pinouts": "Downstream O2 Sensor heater element circuit: 5-15 ohms across heater pins at 20°C.",
            "diagnostic_steps": [
                "1. Inspect live data: Bank 1 Sensor 2 should hold steady between 0.6V and 0.8V during cruise.",
                "2. If Sensor 2 mirrors upstream Sensor 1 oscillating rapidly between 0.1V and 0.9V, catalyst efficiency is depleted.",
                "3. Inspect exhaust flex pipe and manifold gaskets for carbon tracks/leaks before replacing converter.",
                "4. Verify engine does not exhibit head gasket leak (white exhaust smoke) or oil consumption."
            ]
        },
        "P0171": {
            "title": "Fuel System Too Lean (Bank 1)",
            "system": "Air-Fuel Ratio & Intake Metering",
            "severity": "HIGH (Causes engine hesitation and potential valve overheating)",
            "probable_causes": [
                "Dirty Mass Airflow (MAF) sensor hot wire",
                "Unmetered air vacuum leak (cracked PCV hose, torn intake accordion boot)",
                "Low fuel delivery pressure (weak fuel pump or clogged fuel filter)",
                "Clogged fuel injectors on Bank 1"
            ],
            "multimeter_pinouts": "MAF Sensor: Pin 1 (12V Supply), Pin 2 (Signal Ground), Pin 3 (MAF Frequency/Voltage 0.5V-4.5V).",
            "diagnostic_steps": [
                "1. Check Long Term Fuel Trim (LTFT) on scan tool — values above +15% confirm lean condition.",
                "2. Clean MAF sensor element using dedicated MAF electronic cleaner spray.",
                "3. Spray brake cleaner or unlit propane around intake manifold runners while monitoring short-term fuel trim.",
                "4. Test fuel pressure under load with fuel pressure gauge connected to Schrader valve."
            ]
        },
        "P0128": {
            "title": "Coolant Thermostat (Coolant Temp Below Thermostat Regulating Temp)",
            "system": "Engine Cooling & Thermal Management",
            "severity": "LOW to MODERATE (Prolongs cold enrichment, reduces fuel economy)",
            "probable_causes": [
                "Thermostat stuck open or opening prematurely",
                "Defective Engine Coolant Temperature (ECT) sensor",
                "Low engine coolant level with air pocket at ECT sensor housing",
                "Radiator cooling fan running continuously"
            ],
            "multimeter_pinouts": "ECT Sensor: 2-pin NTC thermistor. Resistance should decrease smoothly from ~2.5kΩ at 20°C to ~300Ω at 80°C.",
            "diagnostic_steps": [
                "1. Check coolant expansion tank level when engine is cold.",
                "2. Monitor live ECT reading with scan tool from cold start. If upper radiator hose warms up immediately, thermostat is stuck open.",
                "3. Measure ECT sensor resistance with multimeter against OEM temperature-resistance chart.",
                "4. Replace thermostat and bleed cooling system of trapped air."
            ]
        },
        "U0100": {
            "title": "Lost Communication With ECM / PCM 'A'",
            "system": "Controller Area Network (CAN) High-Speed Bus",
            "severity": "CRITICAL (No-start or transmission limp mode)",
            "probable_causes": [
                "Blown ECM main power fuse or faulty ECM main relay",
                "Loose, corroded, or damaged ECM chassis ground eyelet",
                "CAN Bus wiring short to ground or 12V (CAN-H / CAN-L)",
                "Corroded pins at ECM harness 96-pin / 128-pin header connector"
            ],
            "multimeter_pinouts": "DLC Port Pin 6 (CAN High) to Pin 14 (CAN Low) resistance with battery disconnected: MUST measure ~60 ohms (two 120Ω terminating resistors in parallel).",
            "diagnostic_steps": [
                "1. Disconnect negative battery terminal. Measure resistance between OBD-II DLC Pin 6 and Pin 14. If 120Ω, one terminating resistor circuit is open. If 0Ω, CAN bus is shorted.",
                "2. Inspect ECM power supply pins with ignition key ON for full battery voltage (>12.0V).",
                "3. Check voltage drop across ECM ground wires (<0.1V while cranking).",
                "4. Inspect engine harness near firewall and battery tray for rodent chewing or harness rub-through."
            ]
        }
    }

    if code_upper in obd_database:
        entry = obd_database[code_upper]
        return {
            "code": code_upper,
            "vehicle": f"{make} {model}".strip() or "Standard OBD-II Specification",
            "title": entry["title"],
            "system": entry["system"],
            "severity": entry["severity"],
            "probable_causes": entry["probable_causes"],
            "multimeter_pinouts": entry["multimeter_pinouts"],
            "diagnostic_steps": entry["diagnostic_steps"],
            "status": "EXACT_DTC_MATCH"
        }

    # Generic OBD-II prefix resolution
    system_map = {
        "P0": "Powertrain — Standard Generic DTC",
        "P1": "Powertrain — Manufacturer Specific DTC",
        "P2": "Powertrain — Standard Generic DTC",
        "P3": "Powertrain — Generic & Manufacturer DTC",
        "B0": "Body — Standard Generic DTC",
        "C0": "Chassis (ABS / Steering) — Generic DTC",
        "U0": "Network Communication (CAN Bus) — Generic DTC",
        "U1": "Network Communication — Manufacturer Specific DTC"
    }
    prefix = code_upper[:2]
    cat_desc = system_map.get(prefix, "Automotive Diagnostic Trouble Code")

    return {
        "code": code_upper,
        "vehicle": f"{make} {model}".strip() or "General Automotive",
        "title": f"Diagnostic Trouble Code {code_upper}",
        "system": cat_desc,
        "severity": "Requires Diagnostic Verification",
        "probable_causes": [
            f"Sensor circuit out-of-range or defective component for {code_upper}",
            "Wiring harness chafing, loose pin tension, or connector corrosion",
            "Ground reference offset or low system voltage"
        ],
        "multimeter_pinouts": "Measure sensor reference voltage (5.0V VREF), sensor signal wire, and sensor signal ground (<0.05V).",
        "diagnostic_steps": [
            f"1. Query vehicle factory service manual for exact manufacturer pinout for {code_upper}.",
            "2. Inspect wiring harness and connector lock tab for physical damage.",
            "3. Verify battery state of charge (12.6V resting, >10.0V cranking).",
            "4. Monitor live sensor PID on scan tool while wiggling the wire harness."
        ],
        "status": "GENERIC_DTC_FALLBACK"
    }


# ─── Tool 3: Engine Coolant Temperature (ECT) Multimeter Ohm Table ───────────
@mcp.tool()
def get_ect_sensor_ohm_table(temp_celsius: float = 20.0) -> dict:
    """
    Lookup automotive NTC Engine Coolant Temperature (ECT) and Intake Air Temperature (IAT)
    sensor resistance values for multimeter testing.
    Standard Steinhart-Hart curve: 20°C corresponds to ~2,400 - 2,600 ohms.

    Args:
        temp_celsius: Ambient or coolant temperature in Celsius (-40 to 120°C).

    Returns:
        Structured dictionary with expected resistance in Ohms and reference benchmark table.
    """
    t_c = float(temp_celsius)
    t_k = t_c + 273.15

    # Automotive NTC thermistor parameters: R0 = 2450 ohms at T0 = 293.15K (20C), Beta = 3850K
    r0 = 2450.0
    t0 = 293.15
    beta = 3850.0

    exp_arg = beta * ((1.0 / t_k) - (1.0 / t0))
    # Safety clamp to prevent math overflow
    exp_arg = max(-10.0, min(exp_arg, 10.0))
    expected_ohms = round(r0 * math.exp(exp_arg), 1)

    table_points = [-20, 0, 20, 40, 60, 80, 100]
    reference_table = []
    for pt in table_points:
        pt_k = pt + 273.15
        val = round(r0 * math.exp(beta * ((1.0 / pt_k) - (1.0 / t0))), 1)
        reference_table.append({
            "temp_c": pt,
            "temp_f": round((pt * 9 / 5) + 32, 1),
            "expected_resistance_ohms": val,
            "tolerance_range": f"{round(val * 0.90, 1)} - {round(val * 1.10, 1)} Ω"
        })

    return {
        "queried_temp_celsius": t_c,
        "queried_temp_fahrenheit": round((t_c * 9 / 5) + 32, 1),
        "expected_resistance_ohms": expected_ohms,
        "acceptable_multimeter_range": f"{round(expected_ohms * 0.90, 1)} - {round(expected_ohms * 1.10, 1)} Ω",
        "multimeter_lead_placement": "Disconnect ECT 2-pin connector. Connect multimeter leads across the two pins of the sensor directly with meter set to 20kΩ resistance scale.",
        "pass_fail_rule": "If meter reads 0.00 Ω (shorted) or O.L / 1 (infinite open circuit), sensor is defective and must be replaced.",
        "reference_benchmark_table": reference_table
    }


# ─── Tool 4: Automotive OEM Parts Catalog ─────────────────────────────────────
@mcp.tool()
def lookup_oem_part_number(make: str, model: str, component_name: str) -> dict:
    """
    Lookup OEM part numbers, torque specifications, socket sizes, and difficulty for vehicle components.

    Args:
        make: Vehicle make (e.g. 'Toyota', 'Ford', 'Honda', 'Chevrolet').
        model: Vehicle model (e.g. 'Camry', 'F-150', 'Civic', 'Silverado').
        component_name: Component (e.g. 'spark plug', 'ignition coil', 'oxygen sensor', 'brake pads', 'alternator').

    Returns:
        Structured dictionary with OEM part number, torque specs, tool sizes, and procedure.
    """
    m_clean = make.strip().title()
    mo_clean = model.strip().title()
    comp_clean = component_name.strip().lower()

    catalog = {
        ("toyota", "spark plug"): {
            "oem_part": "Denso 3426 / FK20HR11 (Iridium Long Life)",
            "specs": "Thread M14x1.25, Hex 16mm (5/8\"), Preset Gap 0.043\" (1.1mm)",
            "torque_spec": "18 N·m (13 lb-ft) — DO NOT over-torque aluminum cylinder head",
            "tools_needed": "5/8\" magnetic spark plug socket, 3/8\" torque wrench, extension bar",
            "difficulty": "Easy (25 mins)"
        },
        ("toyota", "ignition coil"): {
            "oem_part": "Denso 673-1301 / Toyota 90919-02244",
            "specs": "12V B+, 4-pin connector, Integrated Igniter",
            "torque_spec": "Retaining bolt 10 N·m (7.5 lb-ft, 10mm bolt)",
            "tools_needed": "10mm socket, 1/4\" ratchet",
            "difficulty": "Easy (15 mins)"
        },
        ("toyota", "oxygen sensor"): {
            "oem_part": "Denso 234-9049 (Upstream Air/Fuel Ratio Sensor)",
            "specs": "4-wire heated planar sensor, M18x1.5 thread",
            "torque_spec": "44 N·m (32 lb-ft) — apply anti-seize paste to threads only",
            "tools_needed": "22mm (7/8\") slotted O2 sensor socket, penetrating oil",
            "difficulty": "Moderate (45 mins)"
        },
        ("ford", "spark plug"): {
            "oem_part": "Motorcraft SP-550 / CYFS-12F-P (Iridium)",
            "specs": "Thread M14, Hex 5/8\", Pre-gapped 0.030\" (0.75mm)",
            "torque_spec": "15 N·m (133 lb-in) — install dry",
            "tools_needed": "5/8\" spark plug socket with rubber grommet, torque wrench",
            "difficulty": "Moderate (40 mins)"
        },
        ("ford", "ignition coil"): {
            "oem_part": "Motorcraft DG-511 / 3L3Z-12029-BA",
            "specs": "Coil-on-Plug, 2-pin connector, high-voltage boot spring",
            "torque_spec": "7 N·m (62 lb-in, 7mm bolt)",
            "tools_needed": "7mm socket, 6\" extension bar",
            "difficulty": "Easy to Moderate"
        },
        ("honda", "spark plug"): {
            "oem_part": "NGK Laser Iridium ILZKR7B11 / 7751",
            "specs": "Thread M12x1.25, Hex 14mm, Gap 0.044\" (1.1mm)",
            "torque_spec": "18 N·m (13 lb-ft)",
            "tools_needed": "14mm thin-wall spark plug socket, torque wrench",
            "difficulty": "Easy (30 mins)"
        },
        ("honda", "brake pads"): {
            "oem_part": "Honda Genuine 45022-T2F-A01 (Front Ceramic Brake Pad Set)",
            "specs": "Low-dust ceramic compound with stainless hardware shims",
            "torque_spec": "Caliper slide pin bolts: 34 N·m (25 lb-ft); Caliper bracket: 108 N·m (80 lb-ft)",
            "tools_needed": "14mm socket, 17mm wrench, brake caliper piston retractor, silicone grease",
            "difficulty": "Moderate (60 mins)"
        }
    }

    # Match make + component keyword
    found_key = None
    for (cat_make, cat_comp) in catalog:
        if cat_make in m_clean.lower() and cat_comp in comp_clean:
            found_key = (cat_make, cat_comp)
            break

    if found_key:
        match = catalog[found_key]
        return {
            "vehicle": f"{m_clean} {mo_clean}".strip(),
            "component": component_name,
            "oem_part_number": match["oem_part"],
            "technical_specs": match["specs"],
            "torque_specification": match["torque_spec"],
            "tools_required": match["tools_needed"],
            "difficulty": match["difficulty"],
            "status": "EXACT_PART_FOUND"
        }

    return {
        "vehicle": f"{m_clean} {mo_clean}".strip(),
        "component": component_name,
        "oem_part_number": f"OEM Standard Replacement for {m_clean} {mo_clean}",
        "technical_specs": f"Verify OEM service parts microfiche for {m_clean} VIN specific build date",
        "torque_specification": "Standard M6: 10 N·m (7 lb-ft) | M8: 25 N·m (18 lb-ft) | M10: 50 N·m (37 lb-ft) | M12: 85 N·m (63 lb-ft)",
        "tools_required": "Metric socket set (8mm-19mm), calibrated torque wrench",
        "difficulty": "Moderate",
        "status": "GENERIC_SPEC_ESTIMATED"
    }


# ─── Tool 5: Multimodal Visual Schematics & Wiring Diagrams Retrieval ─────────
@mcp.tool()
def search_vehicle_visual_schematics(query_text: str = "", query_image_base64: str = "") -> dict:
    """
    Retrieve vehicle wiring diagrams, ECU pinouts, fuse box layouts, and exploded CAD figures.
    Uses SigLIP 2 cross-modal embeddings to match text queries OR an uploaded schematic/photo.

    Args:
        query_text: Text description (e.g. 'ignition coil harness wiring diagram', 'fuse box diagram').
        query_image_base64: Optional base64-encoded image string to perform visual nearest-neighbor search.

    Returns:
        Structured dictionary containing matching schematic diagrams, bounding boxes, and document pages.
    """
    try:
        from app.services.vision_search import search_similar_images

        hits = search_similar_images(
            query=query_text if query_text else None,
            query_image_base64=query_image_base64 if query_image_base64 else None,
            top_k=4
        )

        return {
            "status": "success",
            "query_text": query_text,
            "has_query_image": bool(query_image_base64),
            "schematics_count": len(hits),
            "schematics": hits
        }
    except Exception as e:
        return {"status": "error", "error": str(e), "schematics": []}


# ─── Tool 6: Autonomous Automotive Agent Execution ────────────────────────────
@mcp.tool()
def run_auto_agent(
    query: str,
    image_base64: str = "",
    source_input: str = "",
    session_id: str = ""
) -> dict:
    """
    Execute autonomous LangGraph troubleshooting workflow for automotive maintenance.
    Performs multimodal query understanding, hybrid RRF retrieval, and step-by-step repair synthesis.

    Args:
        query: Automotive technical question or issue description.
        image_base64: Optional base64 image of the damaged part, error screen, or wiring connector.
        source_input: Optional vehicle manual filename filter.
        session_id: Optional tracking session ID.

    Returns:
        Structured AgentResponse with answer text, repair steps, sources, and matching schematic images.
    """
    try:
        import uuid
        from app.services.agent_flow import agent_graph

        sess_id = session_id or str(uuid.uuid4())
        inputs = {
            "query": query,
            "raw_query": query,
            "query_image": image_base64 if image_base64 else None,
            "language": "auto",
            "source_input": source_input if source_input else None,
            "source_content": None,
            "product_id": None,
            "clarification_needed": False,
            "retrieved_chunks": [],
            "sources": [],
            "mode": "troubleshoot",
            "answer": "",
            "steps": [],
            "content_changed": False,
            "version_info": None,
            "clarification_options": [],
            "session_id": sess_id,
            "input_confidence": "HIGH",
            "retrieval_confidence": "HIGH",
            "clarification_question": None,
            "clarification_attempts": 0,
            "resolved_query": None,
            "retrieval_retries": 0,
            "understood_data": {}
        }

        # Run thread-safe agent graph
        result = _run_async_safely(agent_graph.ainvoke, inputs) if hasattr(agent_graph, "ainvoke") else agent_graph.invoke(inputs)

        # Log turn in PostgreSQL
        try:
            from app.database.postgres import record_session_turn
            _run_async_safely(
                record_session_turn,
                session_id=sess_id,
                sender="user",
                message_text=query,
                equipment_type="automobile"
            )
            _run_async_safely(
                record_session_turn,
                session_id=sess_id,
                sender="assistant",
                message_text=result.get("answer", ""),
                question=result.get("clarification_question"),
                equipment_type="automobile"
            )
        except Exception:
            pass

        return {
            "status": "success",
            "session_id": sess_id,
            "answer": result.get("answer", ""),
            "steps": result.get("steps", []),
            "sources": result.get("sources", []),
            "images": result.get("images", []),
            "clarification_needed": result.get("clarification_needed", False)
        }
    except Exception as e:
        return {"status": "error", "error": str(e), "session_id": session_id}


# ─── Tool 7: Multi-Turn OBD-II Troubleshooting Machine ────────────────────────
@mcp.tool()
def troubleshoot_vehicle_turn(session_id: str, message: str, dtc_code: str = "") -> dict:
    """
    Execute an interactive step-by-step OBD-II diagnostic turn.
    Maintains bounded state machine (START -> QUESTION -> ACTION -> VERIFY -> RESOLVED/ESCALATE)
    and persists diagnostic history in PostgreSQL.

    Args:
        session_id: Multi-turn session identifier.
        message: Mechanic's answer or symptom observation.
        dtc_code: Optional OBD-II DTC (e.g. 'P0301').

    Returns:
        Structured state machine response with current step, diagnostic question, next action, and status.
    """
    try:
        from app.services.workflow_manager import process_troubleshoot_turn
        from app.database.postgres import record_session_turn

        combined_msg = f"{message} (DTC: {dtc_code})".strip() if dtc_code else message

        # 1. Record user turn in PostgreSQL
        _run_async_safely(
            record_session_turn,
            session_id=session_id,
            sender="user",
            message_text=combined_msg,
            equipment_type="automobile"
        )

        # 2. Process turn through workflow engine
        result = _run_async_safely(process_troubleshoot_turn, session_id, combined_msg)

        # 3. Record assistant response in PostgreSQL
        resp_text = result.get("question") or result.get("next_action") or result.get("answer", "")
        _run_async_safely(
            record_session_turn,
            session_id=session_id,
            sender="assistant",
            message_text=resp_text,
            question=result.get("question"),
            action=result.get("next_action"),
            equipment_type="automobile"
        )

        return result
    except Exception as e:
        return {"status": "error", "error": str(e), "session_id": session_id}


# ─── Tool 8: List Registered Vehicle Manuals (Files MCP) ───────────────────────
@mcp.tool()
def list_vehicle_manuals() -> dict:
    """
    List all registered automotive and vehicle workshop service manuals from PostgreSQL and Qdrant.
    Filters records tagged with equipment_type='automobile'.

    Returns:
        JSON list of indexed vehicle manuals with MD5 checksums, chunk counts, and model info.
    """
    try:
        from app.database.postgres import list_registered_manuals
        from app.services.vector_store import VectorStoreService

        all_manuals = _run_async_safely(list_registered_manuals)
        auto_manuals = [m for m in all_manuals if m.get("equipment_type") == "automobile"]
        if not auto_manuals:
            # Return all manuals if no specific automobile tag exists yet
            auto_manuals = all_manuals

        vs = VectorStoreService()
        vector_sources = vs.get_unique_sources()

        return {
            "status": "success",
            "count": len(auto_manuals),
            "manuals": auto_manuals,
            "vector_sources": vector_sources
        }
    except Exception as e:
        return {"status": "error", "error": str(e), "manuals": [], "count": 0}


# ─── Tool 9: Upload & Index Vehicle Manual (Files MCP) ────────────────────────
@mcp.tool()
def upload_vehicle_manual(
    filename: str,
    content_base64: str,
    make: str = "",
    model: str = ""
) -> dict:
    """
    Upload and index a vehicle workshop manual (PDF/DOCX) via FastMCP.
    Computes MD5 hash in PostgreSQL, parses text via MarkItDown, renders CAD wiring diagrams,
    and indexes vectors into Qdrant.

    Args:
        filename: Name of the file (e.g. 'Toyota_Camry_2021_FSM.pdf').
        content_base64: Base64-encoded raw file content.
        make: Vehicle make.
        model: Vehicle model.

    Returns:
        Structured dictionary confirming ingestion, chunk count, and registry ID.
    """
    try:
        from app.services.parser import ParserService
        from app.database.postgres import check_manual_duplicate_by_hash, register_manual

        file_bytes = base64.b64decode(content_base64)
        if not file_bytes:
            return {"status": "error", "error": "Decoded binary content is empty"}

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

        # Parse and chunk
        parser = ParserService()
        parse_result = parser.parse_file(filename, file_bytes)

        # Register in PostgreSQL with equipment_type='automobile'
        reg_result = _run_async_safely(
            register_manual,
            filename=filename,
            file_bytes=file_bytes,
            equipment_type="automobile",
            model=f"{make} {model}".strip() if (make or model) else None,
            chunks_count=parse_result["chunks_ingested"]
        )

        return {
            "status": "processed",
            "filename": filename,
            "markdown_file": parse_result["markdown_file"],
            "chunks_ingested": parse_result["chunks_ingested"],
            "equipment_type": "automobile",
            "registered_record": reg_result[1] if isinstance(reg_result, tuple) else reg_result
        }
    except Exception as e:
        return {"status": "error", "error": str(e), "filename": filename}


# ─── Tool 10: Delete Vehicle Manual (Files MCP) ───────────────────────────────
@mcp.tool()
def delete_vehicle_manual(filename: str) -> dict:
    """
    Atomically purge an automotive manual from disk, Qdrant vectors, and PostgreSQL registry.

    Args:
        filename: Name of the vehicle manual to purge.

    Returns:
        Structured dictionary confirming purge.
    """
    try:
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

        # 3. Remove extracted schematic images directory
        images_dir = Path(settings.OUTPUT_DIR) / "images" / base_name
        if images_dir.exists():
            shutil.rmtree(images_dir, ignore_errors=True)

        # 4. Purge vectors from Qdrant
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


if __name__ == "__main__":
    print("[Octo Auto MCP] Starting Automotive Diagnostic MCPServer...", file=sys.stderr)
    mcp.run()
