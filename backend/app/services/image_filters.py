"""
image_filters.py — Configuration constants for image extraction and filtering.
"""

# Dimensions and Area filters
MIN_IMAGE_DIMENSIONS = (100, 100)  # px (width, height)
MIN_IMAGE_AREA_RATIO = 0.02        # 2% of page area

# Header/Footer filters (to discard decorative borders/logos)
HEADER_FOOTER_MARGIN = 0.08        # Top/bottom 8% of the page
LOGO_MAX_AREA_RATIO = 0.05         # 5% of page area

# Aspect ratio limits (to catch divider lines)
ASPECT_RATIO_MIN = 0.1             # 1:10
ASPECT_RATIO_MAX = 10.0            # 10:1

# Duplication filter (repeated logos across pages)
MAX_REPEATED_PHASH_COUNT = 2       # If seen >= 3 times (so > 2), it's decorative

# Text-to-Image Semantic Association Thresholds
ASSOCIATION_MIN_SIMILARITY = 0.40  # Minimum cosine similarity at ingestion

# Distance heuristic
NEARBY_TEXT_MAX_DISTANCE = 150     # words

# Retrieval-time Confidence Filters
MEDIUM_CAPTION_MIN_SIMILARITY = 0.70
MEDIUM_NEARBY_MIN_SIMILARITY = 0.65

# Image Limits
MAX_RETRIEVED_IMAGES_HIGH = 3
MAX_RETRIEVED_IMAGES_MEDIUM = 1
