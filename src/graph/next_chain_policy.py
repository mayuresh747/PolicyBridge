"""S7: per-document-type NEXT_SECTION cosine threshold.

Replaces a single static ``GRAPH_EXPAND_NEXT_THRESHOLD = 0.35`` floor with
a per-document-type table. Tight regulatory sections (WAC/SMC/RCW) hold
high cosine across adjacent sections and warrant a higher floor; long
narrative sections (WA Court Opinions) drift sooner and need a looser
floor; Seattle DIR / SPU / Governor Orders sit in the middle.

Design notes:
    - Pure data + one lookup function; zero runtime cost, no I/O.
    - No LLM / embedding / API calls. Binding per Phase 8 D-01, D-02.
    - Prefix-match lookup: ``threshold_for("wac_section")`` matches the
      ``"wac"`` entry so callers can pass LanceDB ``document_type`` fields
      directly (values like "wac", "wac_chapter", "court_opinion",
      "dir_rule" all resolve correctly).
    - Unknown types fall back to ``GRAPH_EXPAND_NEXT_THRESHOLD`` (the
      legacy default) so flipping the flag on never raises and always
      preserves the pre-Phase-8 floor for unmapped doctypes.

Consumers:
    - ``src/retrieval/graph_expander.py`` — reads the per-chunk
      ``document_type`` from LanceDB metadata and calls
      ``threshold_for(doc_type)`` when
      ``GRAPH_FEATURE_NEXT_ADAPTIVE`` is True.
    - Plan 08-07 will read ``NEXT_THRESHOLDS`` directly for the weight
      sweep; keep the dict keys stable.
"""

from __future__ import annotations

from src.config import GRAPH_EXPAND_NEXT_THRESHOLD

# Per-document-type cosine floor for NEXT_SECTION contiguity expansion.
# Keys are lowercase prefixes; ``threshold_for`` matches by prefix so callers
# can pass free-text document_type values (e.g. "wac_section") directly.
# Values derived from §S7 of docs/graph/kg-traversal-improvement-strategy.md
# and Phase-8 D-09:
#   - WAC / RCW / SMC       -> tight 0.50   (structured statutes)
#   - IBC-WA                -> 0.40         (structured but technical variance)
#   - Seattle DIR / SPU     -> 0.35         (policy, fine-grained)
#   - Governor Orders       -> 0.30         (executive orders, more variance)
#   - WA Court Opinions     -> 0.25         (long narrative; drift is normal)
NEXT_THRESHOLDS: dict[str, float] = {
    "wac":            0.50,
    "rcw":            0.50,
    "smc":            0.50,
    "ibc":            0.40,
    "dir":            0.35,
    "spu":            0.35,
    "governor":       0.30,
    "court_opinion":  0.25,
    "court":          0.25,  # alias for bare "court" document_type values
}


def threshold_for(document_type: str | None) -> float:
    """Return the NEXT_SECTION cosine floor for a given document type.

    Lookup rules (in order):
        1. If ``document_type`` is falsy (None, empty, whitespace-only),
           return :data:`GRAPH_EXPAND_NEXT_THRESHOLD` (the legacy default).
        2. Lowercase the value and test it against every key in
           :data:`NEXT_THRESHOLDS`. If the value *starts with* a key, return
           that key's threshold. Longer keys win ties (e.g.
           ``"court_opinion"`` beats ``"court"`` when both match).
        3. If no prefix matches, return :data:`GRAPH_EXPAND_NEXT_THRESHOLD`.

    This function is pure and side-effect-free.

    Args:
        document_type: The LanceDB ``document_type`` metadata value for a
            chunk. Free text; common values are ``"WAC"``, ``"wac_chapter"``,
            ``"court_opinion"``, ``"dir_rule"``, etc.

    Returns:
        A cosine threshold in ``[0.0, 1.0]``. NEXT_SECTION chain walking
        breaks when the next chunk's cosine similarity drops below this.

    Examples:
        >>> threshold_for("WAC")
        0.5
        >>> threshold_for("court_opinion")
        0.25
        >>> threshold_for(None) == GRAPH_EXPAND_NEXT_THRESHOLD
        True
    """
    if document_type is None:
        return GRAPH_EXPAND_NEXT_THRESHOLD

    normalised = document_type.strip().lower()
    if not normalised:
        return GRAPH_EXPAND_NEXT_THRESHOLD

    # Longest-prefix-match so "court_opinion" (len 13) beats "court" (len 5)
    # when both would otherwise match the same input.
    best_key: str | None = None
    for key in NEXT_THRESHOLDS:
        if normalised.startswith(key):
            if best_key is None or len(key) > len(best_key):
                best_key = key

    if best_key is None:
        return GRAPH_EXPAND_NEXT_THRESHOLD

    return NEXT_THRESHOLDS[best_key]
