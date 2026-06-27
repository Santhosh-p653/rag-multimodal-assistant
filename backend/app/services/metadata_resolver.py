"""
metadata_resolver.py — Service to resolve extracted entity dictionary into Qdrant Filter objects.
Handles hierarchical search filter levels (Level 1: Exact Product, Level 2: Family, Level 3: Global).
"""
from typing import Dict, Any, Optional
from qdrant_client.models import Filter, FieldCondition, MatchValue


def resolve_metadata_filter(entities: Dict[str, Any], filter_level: int = 1) -> Optional[Filter]:
    """
    Convert extracted entities into a Qdrant Filter depending on the priority level.
    
    Level 1: Exact product/model match
    Level 2: Product family match
    Level 3: Global manuals (no filters)
    """
    if filter_level == 1:
        product = entities.get("product") or entities.get("model")
        if product:
            return Filter(
                must=[
                    FieldCondition(
                        key="product",
                        match=MatchValue(value=product),
                    )
                ]
            )
    elif filter_level == 2:
        family = entities.get("product_family")
        if family:
            return Filter(
                must=[
                    FieldCondition(
                        key="product_family",
                        match=MatchValue(value=family),
                    )
                ]
            )

    return None
