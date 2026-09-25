"""
backend/test_mcp_cli.py — Backward-compatible entrypoint forwarding to backend/scripts/test_mcp_cli.py.
"""
from scripts.test_mcp_cli import main

if __name__ == "__main__":
    main()
