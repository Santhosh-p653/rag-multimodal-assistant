"""
image_extractor.py — Extracts, filters, and saves images from PDFs.
"""
import os
import uuid
from PIL import Image
import io
import imagehash
from app.config import settings
from app.services.image_filters import (
    MIN_IMAGE_DIMENSIONS,
    MIN_IMAGE_AREA_RATIO,
    HEADER_FOOTER_MARGIN,
    LOGO_MAX_AREA_RATIO,
    ASPECT_RATIO_MIN,
    ASPECT_RATIO_MAX,
    MAX_REPEATED_PHASH_COUNT
)

def get_vector_drawing_regions(page, distance_threshold=20):
    drawings = page.get_drawings()
    if not drawings:
        return []
    
    rects = [d['rect'] for d in drawings if d['rect'].width > 0 or d['rect'].height > 0]
    clusters = []
    for r in rects: 
        clusters.append(r)
    
    changed = True
    while changed:
        changed = False
        new_clusters = []
        while clusters:
            curr = clusters.pop(0)
            curr_expanded = curr + (-distance_threshold, -distance_threshold, distance_threshold, distance_threshold)
            merged = False
            for i, other in enumerate(clusters):
                if curr_expanded.intersects(other):
                    clusters[i] = curr | other
                    merged = True
                    changed = True
                    break
            if not merged:
                new_clusters.append(curr)
        clusters = new_clusters
        
    # Only return regions that are reasonably sized (e.g. at least 50x50)
    return [c for c in clusters if c.width > 50 and c.height > 50]

def extract_and_filter_images(pdf_path: str, document_id: str) -> list:
    """
    Extracts images from a PDF, applies decorative filters, and saves them to disk.
    Returns a list of image metadata dicts.
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        print("[ImageExtractor] PyMuPDF (fitz) not installed. Skipping image extraction.")
        return []

    images_dir = os.path.join(str(settings.OUTPUT_DIR), "images", document_id)
    os.makedirs(images_dir, exist_ok=True)

    extracted_images = []
    phash_counts = {}

    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        print(f"[ImageExtractor] Failed to open {pdf_path}: {e}")
        return []

    for page_num in range(len(doc)):
        page = doc[page_num]
        page_rect = page.rect
        page_area = page_rect.width * page_rect.height

        # Get all images on the page
        try:
            image_list = page.get_images(full=True)
        except Exception as e:
            print(f"[ImageExtractor] Failed to get images on page {page_num}: {e}")
            continue

        for img_index, img_info in enumerate(image_list):
            xref = img_info[0]
            try:
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]
                img_ext = base_image["ext"]
                image_type = "raster"
                
                # Convert bytes to PIL Image for dimension & hash checks
                pil_img = Image.open(io.BytesIO(image_bytes))
                width, height = pil_img.size
                
                # Filter 1: Dimensions
                if width < MIN_IMAGE_DIMENSIONS[0] or height < MIN_IMAGE_DIMENSIONS[1]:
                    img_area = width * height
                    if (img_area / page_area) < MIN_IMAGE_AREA_RATIO:
                        continue # Too small
                        
                # Filter 2: Aspect Ratio
                aspect_ratio = width / max(height, 1)
                if aspect_ratio < ASPECT_RATIO_MIN or aspect_ratio > ASPECT_RATIO_MAX:
                    continue # Likely a divider line

                # Filter 3: Header/Footer
                # PyMuPDF doesn't give direct bbox for get_images easily without page.get_image_bbox
                # For Phase 3, we use get_image_rects to find where it is on the page
                rects = page.get_image_rects(xref)
                if rects:
                    rect = rects[0]
                    img_area = rect.width * rect.height
                    
                    is_top = rect.y0 < (page_rect.height * HEADER_FOOTER_MARGIN)
                    is_bottom = rect.y1 > (page_rect.height * (1.0 - HEADER_FOOTER_MARGIN))
                    is_small = (img_area / page_area) < LOGO_MAX_AREA_RATIO
                    
                    if (is_top or is_bottom) and is_small:
                        continue # Header/Footer logo
                
                # Filter 4: pHash (Repeated logos)
                p_hash = str(imagehash.phash(pil_img))
                phash_counts[p_hash] = phash_counts.get(p_hash, 0) + 1
                if phash_counts[p_hash] > MAX_REPEATED_PHASH_COUNT:
                    continue # Repeated decorative image

                # Save Image
                image_id = f"{document_id}_p{page_num+1}_{uuid.uuid4().hex[:6]}"
                img_filename = f"{image_id}.{img_ext}"
                img_path = os.path.join(images_dir, img_filename)
                
                with open(img_path, "wb") as f:
                    f.write(image_bytes)
                
                # Find nearby text (caption heuristic)
                nearby_text = ""
                if rects:
                    rect = rects[0]
                    # Expand rect slightly to grab nearby text
                    expanded_rect = fitz.Rect(rect.x0 - 50, rect.y0 - 50, rect.x1 + 50, rect.y1 + 50)
                    nearby_text = page.get_text("text", clip=expanded_rect).strip()
                    # Truncate nearby text
                    nearby_text = " ".join(nearby_text.split()[:50])

                extracted_images.append({
                    "image_id": image_id,
                    "document_id": document_id,
                    "page_number": page_num + 1,
                    "image_path": img_path,
                    "nearby_text": nearby_text,
                    "caption": nearby_text, # Fallback caption
                    "image_type": image_type
                })

            except Exception as e:
                print(f"[ImageExtractor] Failed to extract/decode image xref {xref} on page {page_num}: {e}")
                continue

        # Extract Vector Drawing Regions
        try:
            vector_regions = get_vector_drawing_regions(page)
            for v_idx, v_rect in enumerate(vector_regions):
                pix = page.get_pixmap(clip=v_rect, dpi=150)
                image_bytes = pix.tobytes("png")
                img_ext = "png"
                image_type = "page_region"
                
                pil_img = Image.open(io.BytesIO(image_bytes))
                width, height = pil_img.size
                
                # Check aspect ratio
                aspect_ratio = width / max(height, 1)
                if aspect_ratio < ASPECT_RATIO_MIN or aspect_ratio > ASPECT_RATIO_MAX:
                    continue
                    
                # Deduplication via pHash
                p_hash = str(imagehash.phash(pil_img))
                phash_counts[p_hash] = phash_counts.get(p_hash, 0) + 1
                if phash_counts[p_hash] > MAX_REPEATED_PHASH_COUNT:
                    continue
                    
                image_id = f"{document_id}_p{page_num+1}_vec_{uuid.uuid4().hex[:6]}"
                img_filename = f"{image_id}.{img_ext}"
                img_path = os.path.join(images_dir, img_filename)
                
                with open(img_path, "wb") as f:
                    f.write(image_bytes)
                
                # Nearby text
                expanded_rect = fitz.Rect(v_rect.x0 - 50, v_rect.y0 - 50, v_rect.x1 + 50, v_rect.y1 + 50)
                nearby_text = page.get_text("text", clip=expanded_rect).strip()
                nearby_text = " ".join(nearby_text.split()[:50])
                
                extracted_images.append({
                    "image_id": image_id,
                    "document_id": document_id,
                    "page_number": page_num + 1,
                    "image_path": img_path,
                    "nearby_text": nearby_text,
                    "caption": nearby_text,
                    "image_type": image_type
                })
        except Exception as e:
            print(f"[ImageExtractor] Failed to extract vector regions on page {page_num}: {e}")

    doc.close()

    # Save metadata
    if extracted_images:
        import json
        metadata_path = os.path.join(images_dir, "metadata.json")
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(extracted_images, f)

    return extracted_images
