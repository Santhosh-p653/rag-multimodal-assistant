"""
tests/e2e/test_generation_e2e.py — End-to-end integration test for manual upload and agent query.
Preserved from scratch/debug_generation.py.
"""
import urllib.request
import json
import os
import sys

boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"

def upload_file(filename: str, text_content: str, base_url: str = "http://127.0.0.1:8000"):
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: text/plain\r\n\r\n"
        f"{text_content}\r\n"
        f"--{boundary}--\r\n"
    ).encode("utf-8")

    req = urllib.request.Request(
        f"{base_url}/upload",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST"
    )
    res = urllib.request.urlopen(req, timeout=60)
    return json.loads(res.read())

def ask_question(query: str, source_input: str = None, base_url: str = "http://127.0.0.1:8000"):
    payload = json.dumps({"query": query, "source_input": source_input}).encode("utf-8")
    req = urllib.request.Request(
        f"{base_url}/agent/run",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    res = urllib.request.urlopen(req, timeout=60)
    return json.loads(res.read())

def run_test():
    m1 = """# Industrial Pump Model IP-500 Operating Manual
## Specifications
- Operating Pressure: 75 PSI
- Maximum Flow Rate: 120 Gallons Per Minute (GPM)
- Recommended Lubricant: ISO VG 46 Synthetic Oil
## Troubleshooting
- If pump vibrates excessively, check impeller alignment and anchor bolts.
- Error Code P01 indicates low fluid pressure in the intake chamber."""

    print("Uploading manual...")
    up_res = upload_file("Industrial_Pump_Operating_Manual.txt", m1)
    print("Upload response:", up_res)

    print("Querying agent...")
    ans = ask_question("What is the operating pressure of the Industrial Pump Model IP-500?")
    print("Agent response:", json.dumps(ans, indent=2))

if __name__ == "__main__":
    run_test()
