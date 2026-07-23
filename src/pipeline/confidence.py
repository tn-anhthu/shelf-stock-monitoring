"""Flag a shelf region for re-shoot when its average classification confidence is
too low to trust — Path 2 of docs/superpowers/specs/2026-07-20-shelfsense-mvp-design.md
section 7 (Acceptance Criteria).
"""
from typing import List


def is_low_confidence(scores: List[float], threshold: float = 0.5) -> bool:
    if not scores:
        return True
    return (sum(scores) / len(scores)) < threshold
