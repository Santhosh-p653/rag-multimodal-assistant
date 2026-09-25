"""
backend/scripts/test_mcp_cli.py — Offline interactive CLI test tool for Octo RAG MCP Server.
Organized under backend/scripts/ for clean separation of concerns (SRP).
"""
import sys
import os

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.mcp.mcp_client import (
    invoke_mcp_error_lookup,
    invoke_mcp_thermistor_table,
    invoke_mcp_part_lookup,
    invoke_mcp_search,
    invoke_mcp_agent,
    invoke_mcp_troubleshoot
)

def safe_print(label: str, obj):
    """Safely print objects without throwing CP1252 encoding errors on Windows console."""
    out_str = str(obj).encode("ascii", "replace").decode("ascii")
    print(f"\n{label}:\n{out_str}")

def main():
    print("=" * 60)
    print(" Octo RAG - Offline MCP Diagnostic Tester")
    print("=" * 60)
    print("1. Lookup Refrigerator Error Code (e.g. Er FF)")
    print("2. Multimeter Thermistor Ohm Table (e.g. 25 C)")
    print("3. OEM Spare Part Lookup (e.g. defrost heater)")
    print("4. Search Fridge Vector Manuals")
    print("5. Run Full LangGraph Agent Flow")
    print("6. Run Stateful Troubleshooting Turn")
    print("7. Exit")
    print("=" * 60)

    while True:
        try:
            choice = input("\nSelect a tool to test (1-7): ").strip()
            if choice == "1":
                code = input("Enter error code (default: Er FF): ").strip() or "Er FF"
                res = invoke_mcp_error_lookup("GE", "Profile", code)
                safe_print("[MCP Result]", res)
            elif choice == "2":
                temp = input("Enter temperature in C (default: 25.0): ").strip() or "25.0"
                res = invoke_mcp_thermistor_table(float(temp))
                safe_print("[MCP Result]", res)
            elif choice == "3":
                comp = input("Enter component (default: defrost heater): ").strip() or "defrost heater"
                res = invoke_mcp_part_lookup("GE Profile", comp)
                safe_print("[MCP Result]", res)
            elif choice == "4":
                query = input("Enter manual search query: ").strip()
                if query:
                    res = invoke_mcp_search(query)
                    safe_print("[MCP Result]", res)
            elif choice == "5":
                query = input("Enter query for LangGraph agent: ").strip()
                if query:
                    res = invoke_mcp_agent(query)
                    safe_print("[MCP Result]", res)
            elif choice == "6":
                msg = input("Enter symptom or message: ").strip()
                if msg:
                    res = invoke_mcp_troubleshoot("cli_sess", msg)
                    safe_print("[MCP Result]", res)
            elif choice == "7" or choice.lower() == "exit":
                print("\nExiting MCP CLI Tester. Goodbye!")
                break
        except KeyboardInterrupt:
            print("\nExiting.")
            break
        except Exception as e:
            print(f"\n[Error]: {e}")

if __name__ == "__main__":
    main()
