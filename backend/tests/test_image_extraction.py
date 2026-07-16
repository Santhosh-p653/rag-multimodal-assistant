import pytest
from unittest.mock import patch, MagicMock
from app.services.image_extractor import extract_and_filter_images
import sys

mock_fitz = MagicMock()
sys.modules['fitz'] = mock_fitz

@patch("app.services.image_extractor.Image")
@patch("app.services.image_extractor.imagehash")
@patch("app.services.image_extractor.os.makedirs")
@patch("builtins.open")
def test_extract_images_filters_by_size(mock_open, mock_makedirs, mock_imagehash, mock_Image):
    # Mock PDF document with one page and two images (one small, one large)
    mock_doc = MagicMock()
    mock_page = MagicMock()
    mock_page.rect = MagicMock(width=1000, height=1000)
    mock_page.get_images.return_value = [[1], [2]]
    mock_doc.__len__.return_value = 1
    mock_doc.__getitem__.return_value = mock_page
    mock_fitz.open.return_value = mock_doc

    # Mock extract_image
    mock_doc.extract_image.side_effect = [
        {"image": b"small_img", "ext": "png"},
        {"image": b"large_img", "ext": "jpg"}
    ]

    # Mock get_image_rects to place them in the middle of the page
    rect1 = MagicMock(x0=500, y0=500, x1=510, y1=510, width=10, height=10)
    rect2 = MagicMock(x0=500, y0=500, x1=900, y1=900, width=400, height=400)
    mock_page.get_image_rects.side_effect = [[rect1], [rect2]]

    # Mock PIL Image for size (small < MIN_DIMENSIONS, large >= MIN_DIMENSIONS)
    mock_pil_small = MagicMock()
    mock_pil_small.size = (50, 50)
    mock_pil_large = MagicMock()
    mock_pil_large.size = (400, 400)
    mock_Image.open.side_effect = [mock_pil_small, mock_pil_large]

    # Mock hash
    mock_imagehash.phash.side_effect = ["hash1", "hash2"]

    # Mock nearby text
    mock_page.get_text.return_value = "Caption text here"

    extracted = extract_and_filter_images("dummy.pdf", "doc_123")
    
    assert len(extracted) == 1
    assert extracted[0]["document_id"] == "doc_123"
    assert extracted[0]["page_number"] == 1
    assert "Caption text here" in extracted[0]["nearby_text"]

@patch("app.services.image_extractor.Image")
@patch("app.services.image_extractor.imagehash")
@patch("app.services.image_extractor.os.makedirs")
@patch("builtins.open")
def test_extract_images_filters_repeated(mock_open, mock_makedirs, mock_imagehash, mock_Image):
    # Mock PDF document with one page and two identical images
    mock_doc = MagicMock()
    mock_page = MagicMock()
    mock_page.rect = MagicMock(width=1000, height=1000)
    mock_page.get_images.return_value = [[1], [2], [3], [4], [5]]
    mock_doc.__len__.return_value = 1
    mock_doc.__getitem__.return_value = mock_page
    mock_fitz.open.return_value = mock_doc

    mock_doc.extract_image.return_value = {"image": b"img", "ext": "png"}
    
    rect = MagicMock(x0=500, y0=500, x1=900, y1=900, width=400, height=400)
    mock_page.get_image_rects.return_value = [rect]

    mock_pil = MagicMock()
    mock_pil.size = (400, 400)
    mock_Image.open.return_value = mock_pil

    # Mock hash to return the same hash 5 times (limit is usually 3)
    mock_imagehash.phash.return_value = "same_hash"
    mock_page.get_text.return_value = "Text"

    extracted = extract_and_filter_images("dummy.pdf", "doc_123")
    
    # Should only keep up to MAX_REPEATED_PHASH_COUNT (which is 3)
    from app.services.image_filters import MAX_REPEATED_PHASH_COUNT
    assert len(extracted) == MAX_REPEATED_PHASH_COUNT
