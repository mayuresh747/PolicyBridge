"""Query-adaptive traversal profile dispatcher (S1).

Pure routing: given an (optional) classification, return the edge set,
depth, and per-edge-weight overrides the beam traversal should use.
Zero API / LLM / DB calls.

Per D-04 the fifth strategy-doc profile is intentionally dropped from
this module — that edge family is empty and out of Phase 8 scope.
Unknown / missing intents (including any future legacy label) fall
back to the default profile built from the existing ``GRAPH_TRAVERSAL_*``
/ ``GRAPH_EXPAND_WEIGHTS`` config.

See ``docs/graph/kg-traversal-improvement-strategy.md`` §S1 for the
intent → edge mapping this module implements.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.config import (
    GRAPH_EXPAND_WEIGHTS,
    GRAPH_TRAVERSAL_DEPTH,
    GRAPH_TRAVERSAL_EDGE_TYPES,
)

# Weight assigned to edge types that are not present in
# ``GRAPH_EXPAND_WEIGHTS`` (currently only ``NEXT_SECTION`` for the
# procedural profile). A neutral 1.0 keeps the beam scorer numerically
# well-behaved without privileging or penalising the edge.
_DEFAULT_MISSING_EDGE_WEIGHT: float = 1.0


@dataclass(frozen=True)
class TraversalProfile:
    """Immutable routing bundle consumed by the beam traversal (08-03).

    Attributes:
        name: Profile label (e.g. "definition", "default"). Used for
            debugging / telemetry only — not for dispatch.
        edge_types: Ordered list of Kuzu edge types the beam should
            consider, in priority order. Empty list is invalid.
        max_depth: Maximum hop count from seed chunks.
        edge_weights: ``{edge_type: weight}`` map used by the beam
            scorer. Keys are exactly ``edge_types``; values are rounded
            to 4 dp so tests can compare against expected floats.
    """

    name: str
    edge_types: list[str]
    max_depth: int
    edge_weights: dict[str, float] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Profile table — D-04: the strategy doc's fifth row is deliberately dropped
# because that edge family is empty and out of Phase 8 scope.
# ---------------------------------------------------------------------------
_PROFILES: dict[str, dict[str, Any]] = {
    "definition":      {"edge_types": ["DEFINED_BY", "CITES"],               "max_depth": 1, "overrides": {"DEFINED_BY": 1.2}},
    "authority_chain": {"edge_types": ["IMPLEMENTS", "SUBJECT_TO"],          "max_depth": 3, "overrides": {"IMPLEMENTS": 1.5}},
    "cross_agency":    {"edge_types": ["IMPLEMENTS", "CITES", "SUBJECT_TO"], "max_depth": 2, "overrides": {}},
    "procedural":      {"edge_types": ["NEXT_SECTION", "CITES"],             "max_depth": 2, "overrides": {}},
}


def _weights_for(
    edge_types: list[str],
    overrides: dict[str, float] | None = None,
) -> dict[str, float]:
    """Build ``{edge_type: weight}`` for a profile.

    Base weight comes from ``GRAPH_EXPAND_WEIGHTS``; edge types absent
    from that table (notably ``NEXT_SECTION``) fall back to
    ``_DEFAULT_MISSING_EDGE_WEIGHT`` so the beam scorer still has a
    numeric multiplier. Per-edge multiplicative overrides (e.g.
    ``DEFINED_BY×1.2``) are applied on top.
    """
    overrides = overrides or {}
    out: dict[str, float] = {}
    for et in edge_types:
        base = GRAPH_EXPAND_WEIGHTS.get(et, _DEFAULT_MISSING_EDGE_WEIGHT)
        mult = overrides.get(et, 1.0)
        out[et] = round(base * mult, 4)
    return out


def _default_profile() -> TraversalProfile:
    """Build the fallback profile from current config defaults.

    Used when ``classification`` is ``None`` or carries an unrecognised
    intent label.
    """
    edges = list(GRAPH_TRAVERSAL_EDGE_TYPES)
    return TraversalProfile(
        name="default",
        edge_types=edges,
        max_depth=GRAPH_TRAVERSAL_DEPTH,
        edge_weights=_weights_for(edges),
    )


def profile_for(query: str, classification: dict | None) -> TraversalProfile:
    """Route a classified query to a ``TraversalProfile``.

    Args:
        query: The user's query text. Currently unused — reserved for
            future lightweight heuristics (e.g. regex overrides). Kept
            in the signature so callers at the pipeline/hybrid layer
            do not need a churn when heuristics arrive.
        classification: Optional dict carrying an ``intent`` key
            (string label). May be ``None`` if upstream skipped
            classification.

    Returns:
        A ``TraversalProfile`` matching the intent, or the default
        profile for unknown / missing intents.

    Notes:
        Pure function: no I/O, no API calls, deterministic. Safe to
        call from synchronous hot paths.
    """
    del query  # reserved; currently only classification drives routing

    if not classification:
        return _default_profile()

    intent = classification.get("intent")
    if not isinstance(intent, str):
        return _default_profile()

    spec = _PROFILES.get(intent)
    if spec is None:
        return _default_profile()

    return TraversalProfile(
        name=intent,
        edge_types=list(spec["edge_types"]),
        max_depth=int(spec["max_depth"]),
        edge_weights=_weights_for(spec["edge_types"], spec.get("overrides")),
    )
