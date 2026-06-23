"""Post-processing confidence assignment from retrieval scores (D-07).

Confidence levels are determined by source-based rules, not LLM judgment:
  - strongly_supported: score > 0.8
  - reasonably_inferred: score >= 0.5
  - uncertain: score < 0.5

These thresholds are initial values; Phase 6 can tune against ground truth.

FALLBACK: This file may be created by parallel Plan 04-01 agent.
Defines locally for Plan 04-04 if not yet available.
"""

from src.config import CONFIDENCE_INFER_THRESHOLD, CONFIDENCE_STRONG_THRESHOLD


def assign_confidence(score: float, source_count: int) -> str:
    """Assign per-claim confidence level based on retrieval evidence.

    Args:
        score: RRF retrieval score for the source chunk.
        source_count: Number of sources supporting this claim.

    Returns:
        One of "strongly_supported", "reasonably_inferred", or "uncertain".
    """
    if score > CONFIDENCE_STRONG_THRESHOLD:
        return "strongly_supported"
    elif score >= CONFIDENCE_INFER_THRESHOLD:
        return "reasonably_inferred"
    else:
        return "uncertain"
