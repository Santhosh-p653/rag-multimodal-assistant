import pytest
from app.services.agent_flow import image_filtering_node
from app.services.agent_flow import AgentState

@pytest.fixture
def mock_image_metadata(tmp_path):
    import json
    import os
    from app.config import settings
    
    # Create mock metadata file
    doc_id = "test_doc"
    img_dir = os.path.join(str(settings.OUTPUT_DIR), "images", doc_id)
    os.makedirs(img_dir, exist_ok=True)
    
    metadata = [
        {
            "image_id": "img_1",
            "document_id": doc_id,
            "page_number": 1,
            "image_path": "path/img1.png",
            "nearby_text": "This is a chart showing performance.",
            "caption": "Performance Chart"
        },
        {
            "image_id": "img_2",
            "document_id": doc_id,
            "page_number": 2,
            "image_path": "path/img2.png",
            "nearby_text": "Random text here.",
            "caption": "Random"
        }
    ]
    
    with open(os.path.join(img_dir, "metadata.json"), "w", encoding="utf-8") as f:
        json.dump(metadata, f)
        
    yield img_dir

def test_image_filtering_node_high_confidence(mock_image_metadata):
    state = {
        "retrieval_confidence": "HIGH",
        "retrieved_chunks": [
            {
                "chunk_id": "c1",
                "source_file": "test_doc.pdf",
                "embedding": [0.1] * 384,
                "image_ids": ["img_1"]
            }
        ]
    }
    
    result = image_filtering_node(state)
    assert "images" in result
    assert len(result["images"]) == 1
    assert result["images"][0]["image_id"] == "img_1"
    assert result["images"][0]["caption"] == "Performance Chart"

def test_image_filtering_node_low_confidence(mock_image_metadata):
    state = {
        "retrieval_confidence": "LOW",
        "retrieved_chunks": [
            {
                "chunk_id": "c1",
                "source_file": "test_doc.pdf",
                "embedding": [0.1] * 384,
                "image_ids": ["img_1"]
            }
        ]
    }
    
    result = image_filtering_node(state)
    assert "images" in result
    assert len(result["images"]) == 0
