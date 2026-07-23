"""Flag a shelf region for re-shoot when too many of its detections came back
"unknown" to trust the scan — Path 2 of
docs/superpowers/specs/2026-07-20-shelfsense-mvp-design.md section 7
(Acceptance Criteria).

Takes the region's detections (each already LLM-verified by classify_crop),
not raw cosine scores: a high average embedding score no longer implies a
trustworthy region, since a shelf full of confidently-not-in-catalog products
can score high on similarity yet still correctly come back "unknown" from
the LLM. The unknown ratio is the signal that actually reflects "how much of
this region could we not identify," which is what re-shoot should react to.
"""
from typing import Dict, List


def is_low_confidence(detections: List[Dict], threshold: float = 0.5) -> bool:
    if not detections:
        return True
    unknown_count = sum(1 for d in detections if d["sku_id"] is None)
    return (unknown_count / len(detections)) > threshold
