"""
scrape_allcarmanuals.py — Scraper and Ingestion Pipeline for allcarmanuals.com and Automotive Manuals.
Follows BeautifulSoup pattern to discover manual download links, download service manuals (PDF),
and pipe them into OCTO-AUTO's ingestion pipeline (MarkItDown, PyMuPDF, SigLIP 2, Qdrant, PostgreSQL).
"""
import sys
import os
import argparse
import asyncio
from pathlib import Path
from typing import List, Dict, Any

# Ensure backend root is on sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

import requests
from bs4 import BeautifulSoup

from app.config import settings
from app.services.parser import ParserService
from app.database.postgres import register_manual


# Example target makes & models available on workshop manuals directories
DIRECTORY_SOURCES = [
    {
        "make": "Toyota",
        "model": "Camry",
        "url": "https://allcarmanuals.com/factory-service-manual-Toyota-Camry.html"
    },
    {
        "make": "Nissan",
        "model": "350Z",
        "url": "https://allcarmanuals.com/factory-service-manual-Nissan-350Z.html"
    }
]


def extract_manual_links(page_url: str) -> List[Dict[str, str]]:
    """
    Scrapes an allcarmanuals directory page for manual links and download titles.
    """
    print(f"[Scraper] Fetching directory: {page_url}")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        response = requests.get(page_url, headers=headers, timeout=15)
        response.raise_for_status()
    except Exception as e:
        print(f"[Scraper WARN] Could not reach {page_url}: {e}")
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    manual_links = []

    # Factory structures typically group manuals via systematic lists or divs
    # Check both class 'manual-link-container' and generic download links
    for block in soup.find_all("div", class_="manual-link-container"):
        a_tag = block.find("a")
        h3_tag = block.find("h3") or block.find("h4")
        if a_tag and a_tag.get("href"):
            link = a_tag["href"]
            title = h3_tag.text.strip() if h3_tag else a_tag.text.strip()
            manual_links.append({"title": title, "download_url": link})

    # Fallback to general table/list anchor links if standard container isn't present
    if not manual_links:
        for a in soup.find_all("a", href=True):
            href = a["href"].lower()
            if any(term in href for term in [".pdf", "/download/", "workshop-manual", "service-manual"]):
                manual_links.append({"title": a.text.strip() or "Workshop Manual", "download_url": a["href"]})

    print(f"[Scraper] Found {len(manual_links)} potential manual links on page.")
    return manual_links


def download_manual_file(download_url: str, save_filename: str) -> Path:
    """
    Downloads a manual file to the backend input_documents directory.
    """
    input_dir = Path(settings.INPUT_DIR)
    input_dir.mkdir(parents=True, exist_ok=True)
    target_path = input_dir / save_filename

    print(f"[Downloader] Downloading {download_url} -> {target_path.name}...")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }

    response = requests.get(download_url, headers=headers, stream=True, timeout=60)
    response.raise_for_status()

    with open(target_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=1024 * 64):
            if chunk:
                f.write(chunk)

    print(f"[Downloader] Saved {target_path.name} ({target_path.stat().st_size} bytes).")
    return target_path


async def ingest_downloaded_manual(file_path: Path, make: str = "", model: str = ""):
    """
    Pipes downloaded manual file through ParserService, embeds into Qdrant, and registers in PostgreSQL.
    """
    print(f"\n[Ingest Pipeline] Ingesting {file_path.name} into OCTO-AUTO...")
    parser = ParserService()
    file_bytes = file_path.read_bytes()

    # Parse and chunk document (MarkItDown + PyMuPDF CAD figures + SentenceTransformers + SigLIP 2)
    result = parser.parse_file(file_path.name, file_bytes)

    # Register in PostgreSQL manual_registry
    ok, reg = await register_manual(
        filename=file_path.name,
        file_bytes=file_bytes,
        equipment_type="automobile",
        model=f"{make} {model}".strip() if (make or model) else None,
        chunks_count=result.get("chunks_ingested", 0)
    )

    print(f"[Ingest Pipeline] Completed: {result.get('chunks_ingested')} chunks indexed into Qdrant.")
    print(f"[Ingest Pipeline] PostgreSQL record registered: {ok}")


async def main():
    parser = argparse.ArgumentParser(description="Scrape and ingest workshop service manuals from allcarmanuals.com")
    parser.add_argument("--url", type=str, default="", help="Target allcarmanuals directory page URL")
    parser.add_argument("--make", type=str, default="Toyota", help="Vehicle manufacturer")
    parser.add_argument("--model", type=str, default="Camry", help="Vehicle model")
    args = parser.parse_args()

    target_url = args.url or DIRECTORY_SOURCES[0]["url"]
    print("=" * 60)
    print(f"OCTO-AUTO Scraper: {args.make} {args.model}")
    print(f"Target: {target_url}")
    print("=" * 60)

    links = extract_manual_links(target_url)
    if not links:
        print("[INFO] No direct public links scraped (target server might require session or proxy).")
        print("[INFO] Demonstrating automated ingestion pipeline with sample automotive service manual...")
        sample_path = Path(settings.INPUT_DIR) / "toyota_camry_sample_fsm.pdf"
        if not sample_path.exists():
            # Create a clean sample automotive workshop manual PDF if not present
            from reportlab.lib.pagesizes import letter
            from reportlab.pdfgen import canvas
            c = canvas.Canvas(str(sample_path), pagesize=letter)
            c.setFont("Helvetica-Bold", 16)
            c.drawString(50, 750, f"TOYOTA {args.model.upper()} FACTORY SERVICE MANUAL — IGNITION & ENGINE")
            c.setFont("Helvetica", 11)
            c.drawString(50, 710, "SECTION 1: Spark Plug & Ignition Coil Inspection (2.5L 4-Cyl Engine)")
            c.drawString(50, 690, "- Spark plug type: Denso Iridium FK20HR11. Gap: 0.043 in (1.1 mm).")
            c.drawString(50, 670, "- Tightening torque for spark plugs: 18 N*m (13 ft-lb).")
            c.drawString(50, 650, "- Coil-on-Plug (COP) bolt torque: 10 N*m (7.5 ft-lb).")
            c.drawString(50, 620, "SECTION 2: DTC P0301 Diagnostic Troubleshooting Procedure")
            c.drawString(50, 600, "1. Disconnect Cylinder 1 ignition coil 4-pin harness connector.")
            c.drawString(50, 580, "2. Measure supply voltage between Pin 1 (B+) and Pin 2 (Ground): >12.0 V.")
            c.drawString(50, 560, "3. Swap Cylinder 1 coil to Cylinder 2. Clear DTC and verify if misfire moves.")
            c.showPage()
            c.save()
            print(f"[Generated Sample FSM] Created {sample_path.name}")

        await ingest_downloaded_manual(sample_path, make=args.make, model=args.model)
    else:
        print(f"[Scraper] Found {len(links)} links. Downloading first manual...")
        first = links[0]
        # Clean filename
        fname = f"{args.make}_{args.model}_manual.pdf".replace(" ", "_")
        try:
            downloaded = download_manual_file(first["download_url"], fname)
            await ingest_downloaded_manual(downloaded, make=args.make, model=args.model)
        except Exception as err:
            print(f"[Scraper ERROR] Failed downloading: {err}")


if __name__ == "__main__":
    asyncio.run(main())
