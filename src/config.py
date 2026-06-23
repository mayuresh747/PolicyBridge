"""Non-secret configuration for the Seattle Regulatory RAG ingestion pipeline."""

import os
import secrets
from pathlib import Path

# Paths
DOCUMENTS_ROOT = Path(os.getenv("DOCUMENTS_ROOT", "/app/All Documents"))
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
LANCEDB_PATH = DATA_DIR / "lancedb"
KUZU_PATH = DATA_DIR / "kuzu_graph"
MANIFEST_PATH = DATA_DIR / "ingestion_manifest.json"
LLM_CACHE_PATH = DATA_DIR / "graph_llm_cache.jsonl"
VALIDATION_DIR = DATA_DIR / "validation"
FAILURES_PATH = DATA_DIR / "failures.json"

# --- Phase 7: Persistence ---
DB_PATH = DATA_DIR / "rag.db"
TRACE_DIR = DATA_DIR / "traces"
TRACE_RETENTION_DAYS = int(os.getenv("TRACE_RETENTION_DAYS", "90"))
MAX_CONVERSATIONS_PER_USER = int(os.getenv("MAX_CONVERSATIONS_PER_USER", "500"))
JWT_SECRET = os.getenv("JWT_SECRET") or secrets.token_hex(32)
JWT_EXPIRY_DAYS = int(os.getenv("JWT_EXPIRY_DAYS", "7"))

# Agency folder mapping (agency name -> folder name under DOCUMENTS_ROOT)
AGENCY_FOLDERS = {
    "WAC": "WAC_Chapters",
    "RCW": "RCW_Chapters",
    "SMC": "SMC_Chapters",
    "Seattle DIR": "Seattle_Active_DIR_Rules",
    "IBC-WA": "IBC WA Docs",
    "SPU": "SPU Design Standards",
    "WA Court Opinions": "washington_court_opinions",
    "Governor Orders": "WA_Governor_Active_Orders",
}

# Chunk size limits per agency (max tokens per chunk)
CHUNK_SIZE_LIMITS = {
    "WAC": 2000,
    "RCW": 2000,
    "SMC": 2000,
    "Seattle DIR": 2000,
    "IBC-WA": 2000,
    "SPU": 2000,
    "WA Court Opinions": 3000,
    "Governor Orders": 2000,
}

# Embedding config
EMBEDDING_MODEL = "text-embedding-3-large"
EMBEDDING_DIMENSIONS = 3072
EMBED_BATCH_SIZE = 100
MAX_CONCURRENT_EMBEDS = 10

# LLM relationship extraction config
LLM_EXTRACT_MODEL = "gpt-4.1-mini"
LLM_EXTRACT_MAX_CONCURRENT = 10
LLM_EXTRACT_MAX_CHUNK_CHARS = 3000

# Processing config
MULTIPROCESSING_WORKERS = 4
VALIDATION_DOCS_PER_AGENCY = 3

# Authority levels per agency
AUTHORITY_LEVELS = {
    "WAC": "state_admin_rule",
    "RCW": "state_statute",
    "SMC": "local_statute",
    "Seattle DIR": "local_admin_rule",
    "IBC-WA": "state_admin_rule",
    "SPU": "guidance",
    "WA Court Opinions": "court_opinion",
    "Governor Orders": "state_executive_order",
}

# LanceDB config
LANCEDB_TABLE_NAME = "chunks"
VECTOR_INDEX_NUM_PARTITIONS = 256
VECTOR_INDEX_NUM_SUB_VECTORS = 96

# Retrieval config (Phase 3)
VECTOR_TOP_K = 30   # enlarged pool fed into linear fusion (was 20)
BM25_TOP_K = 30     # enlarged pool fed into linear fusion (was 20)
RETRIEVAL_TOP_K = 15
# Per-level synthesis context budget (chunks sent to GPT-5.1).
# L3+ uses answer-embedding reranking; L1/L2 uses RRF score ranking.
# RETRIEVAL_TOP_K remains the per-leaf retrieval cap (unchanged).
SYNTHESIS_TOP_K: dict[str, int] = {
    "L1": 8,
    "L2": 12,
    "L3": 20,
    "L4": 30,
    "L5": 35,
    "L6": 20,
}
# Post-reranking graph expansion (PPR-style authority chain injection)
# HippoRAG (NeurIPS 2024), GAAMA (2025), ToG-2 (ICLR 2024)
GRAPH_EXPAND_WEIGHTS: dict[str, float] = {
    "IMPLEMENTS": 0.75,   # formal authority declaration — highest trust
    "SUBJECT_TO": 0.70,   # compliance chain — high trust
    "DEFINED_BY":  0.65,   # definition — useful but phrasing diverges
    "AMENDED_BY":  0.60,   # specific amendment
    "CITES":       0.35,   # generic cross-reference — noisiest
}
GRAPH_EXPAND_NEXT_THRESHOLD: float = 0.35  # cosine stop threshold for NEXT_SECTION
GRAPH_EXPAND_MAX_HOPS:       int   = 5     # max NEXT_SECTION hops per direction
GRAPH_EXPAND_MAX_NEIGHBORS:  int   = 3     # hub dampening: max per seed per edge type
GRAPH_EXPAND_MAX_ADDITIONS:  int   = 10    # total graph-expanded chunks injected
GRAPH_EXPAND_SEEDS:          int   = 5     # top-N cosine chunks used as seeds
GRAPH_EXPAND_MAX_ADDITIONS_L12: int = 5   # L1/L2 graph expansion budget (vs 10 for L3+)
# DEPRECATED: used only by legacy rrf_fuse path (kept for rollback reference)
RRF_K = 60
RETRIEVAL_WEIGHTS = {"vector": 0.5, "bm25": 0.25, "graph": 0.25}
# Active fusion weights for linear_fuse (vector + bm25 only; graph is post-retrieval)
FUSION_WEIGHTS = {"vector": 0.55, "bm25": 0.45}
GRAPH_TRAVERSAL_DEPTH = 2
GRAPH_TRAVERSAL_EDGE_TYPES = ["CITES", "IMPLEMENTS", "SUBJECT_TO"]
GRAPH_TRAVERSAL_MAX_RESULTS = 50

# --- Phase 8 KG traversal feature flags (D-17: each strategy independently toggled) ---
# Defaults updated per 08-07 A/B sweep decision table:
#   promoted (default "1"): PROFILES, BEAM_TRAVERSAL, SEED_FUSION, COMPOSER, NEXT_ADAPTIVE
#   rejected (default "0"): DIVERSITY  (NDCG@5 regressed -0.033, beyond -0.02 tolerance)
#   forced off (default "0"): ONDEMAND_RESOLVER  (no-lift under current ingestion; chunks
#       don't populate unresolved_citations. Module wired; activates once ingestion extends.)
# See benchmarks/reports/runs/08-ab-sweep/summary.json for per-flag deltas.
GRAPH_FEATURE_PROFILES:            bool = os.getenv("GRAPH_FEATURE_PROFILES",          "1") == "1"  # S1  promoted
GRAPH_FEATURE_BEAM_TRAVERSAL:      bool = os.getenv("GRAPH_FEATURE_BEAM_TRAVERSAL",    "1") == "1"  # S2  promoted
GRAPH_FEATURE_SEED_FUSION:         bool = os.getenv("GRAPH_FEATURE_SEED_FUSION",       "1") == "1"  # S3  promoted
GRAPH_FEATURE_DIVERSITY:           bool = os.getenv("GRAPH_FEATURE_DIVERSITY",         "0") == "1"  # S5  rejected
GRAPH_FEATURE_COMPOSER:            bool = os.getenv("GRAPH_FEATURE_COMPOSER",          "1") == "1"  # S6  promoted (extractive)
GRAPH_FEATURE_NEXT_ADAPTIVE:       bool = os.getenv("GRAPH_FEATURE_NEXT_ADAPTIVE",     "1") == "1"  # S7  promoted
GRAPH_FEATURE_ONDEMAND_RESOLVER:   bool = os.getenv("GRAPH_FEATURE_ONDEMAND_RESOLVER", "0") == "1"  # S10 no-lift

# --- Phase 8 beam-traversal tunables (consumed by src/graph/beam_traversal.py in 08-03) ---
GRAPH_BEAM_WIDTH:                  int = int(os.getenv("GRAPH_BEAM_WIDTH", "10"))
GRAPH_BEAM_MAX_DEPTH:              int = int(os.getenv("GRAPH_BEAM_MAX_DEPTH", "3"))
GRAPH_BEAM_DEPTH_DECAY:            list[float] = [1.0, 0.7, 0.45]
GRAPH_BEAM_HUB_PENALTY_ALPHA:      float = float(os.getenv("GRAPH_BEAM_HUB_PENALTY_ALPHA", "1.0"))  # hub_penalty = 1 / (1 + alpha*log(1+in_degree))

# --- Phase 8 Plan 07 weight-tuning overrides ---
# Env-var-overrideable wrappers around the dict constants so
# benchmarks/sweeps/weight_tuning.py can grid-search without code changes.
# All wrappers are no-ops when the OVERRIDE env var is unset, preserving
# baseline behaviour for every non-sweep execution path.
def _parse_weights_env(var: str, default: dict[str, float]) -> dict[str, float]:
    raw = os.getenv(var, "")
    if not raw:
        return default
    out = dict(default)
    for pair in raw.split(","):
        if ":" in pair:
            k, v = pair.split(":", 1)
            try:
                out[k.strip()] = float(v.strip())
            except ValueError:
                pass
    return out


GRAPH_EXPAND_WEIGHTS = _parse_weights_env("GRAPH_EXPAND_WEIGHTS_OVERRIDE", GRAPH_EXPAND_WEIGHTS)
FUSION_WEIGHTS       = _parse_weights_env("FUSION_WEIGHTS_OVERRIDE",       FUSION_WEIGHTS)
GRAPH_EXPAND_SEEDS         = int(os.getenv("GRAPH_EXPAND_SEEDS_OVERRIDE",         GRAPH_EXPAND_SEEDS))
GRAPH_EXPAND_MAX_NEIGHBORS = int(os.getenv("GRAPH_EXPAND_MAX_NEIGHBORS_OVERRIDE", GRAPH_EXPAND_MAX_NEIGHBORS))
GRAPH_EXPAND_MAX_ADDITIONS = int(os.getenv("GRAPH_EXPAND_MAX_ADDITIONS_OVERRIDE", GRAPH_EXPAND_MAX_ADDITIONS))

VALID_AGENCIES = list(AGENCY_FOLDERS.keys())

# Query pipeline config (Phase 4)
QUERY_LLM_MODEL = "gpt-4.1-mini"         # Classifier, decomposer, premise detector, query rewriter
SYNTHESIS_LLM_MODEL = os.getenv("SYNTHESIS_LLM_MODEL", "gpt-5.1")  # Answer synthesis (env-overridable for A/B)
SYNTHESIS_TEMPERATURE = float(os.getenv("SYNTHESIS_TEMPERATURE", "0.1"))  # env-overridable (gpt-5.5 requires 1)
SYNTHESIS_MAX_TOKENS = 8192               # Max output tokens for synthesis
SESSION_TTL_MINUTES = 60                  # Session inactivity timeout (D-19)
MAX_SESSION_TURNS = 5                     # Conversation history depth (D-17)
MAX_CONCURRENT_LLM_CALLS = 10             # Semaphore limit for async LLM calls
MAX_RETRIEVAL_CALLS = 12                  # Safety limit for RT-RAG leaf retrievals (depth-4 trees can have 8 leaves)
LEVEL_MAX_DEPTH = {"L3": 3, "L4": 4, "L5": 4, "L6": 3}  # Max decomposition tree height per complexity level
CONFIDENCE_STRONG_THRESHOLD = 0.8         # Score > this = strongly_supported
CONFIDENCE_INFER_THRESHOLD = 0.5          # Score >= this = reasonably_inferred
AUTHORITY_HIERARCHY = {                   # Legal precedence (D-08), lower = higher authority
    "federal": 0,
    "state_statute": 1,       # RCW
    "state_admin_rule": 2,    # WAC
    "state_executive_order": 3, # Governor Orders
    "court_opinion": 4,       # WA Court Opinions
    "local_statute": 5,       # SMC
    "local_admin_rule": 6,    # Seattle DIR
    "guidance": 7,            # SPU
}

# Conflict expansion config (Approach 1: shared-authority graph + Approach 2: cross-agency vector)
CONFLICT_EXPAND_ENABLED = True
CONFLICT_EXPAND_MAX = 5                     # max conflict chunks to inject per query
CONFLICT_CROSS_AGENCY_THRESHOLD = 0.55      # min cosine similarity for cross-agency match
CONFLICT_CROSS_AGENCY_SEEDS = 3             # top chunks used as seeds for cross-agency search
CONFLICT_CROSS_AGENCY_PER_SEED = 3          # cross-agency results fetched per seed
CONFLICT_BUDGET_RESERVE: int = 5            # max conflict_expand chunks exempt from token budget (L3+ only)

# Token budget for synthesis context (hard cap on input to GPT-5.1)
SYNTHESIS_CONTEXT_MAX_TOKENS = 40_000       # max tokens of chunk text sent to synthesis
SYNTHESIS_OVERHEAD_TOKENS = 3_000           # reserve for system prompt + history + query
