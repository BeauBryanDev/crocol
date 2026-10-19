## LLm Config Roles

HAIKU = "claude-haiku-5-5"
SONNET = "claude-sonnet-5-5"
GEMINI_FLASH = "gemini-3.5-flash"

MODELS = {
    "analyze": HAIKU,
    "plan": HAIKU,
    "rewrite": HAIKU,
    "synthesize": SONNET,
    "revise": SONNET,
    "grade": GEMINI_FLASH,
    "verify": GEMINI_FLASH,
    "conflict": GEMINI_FLASH,
    "vision": GEMINI_FLASH,
}
FALLBACKS = {
    "grade": HAIKU,
    "verify": HAIKU,
    "conflict": HAIKU,
    "vision": HAIKU,
}
MAX_OUTPUT_TOKENS = {
    "analyze": 800,
    "plan": 800,
    "rewrite": 600,
    "synthesize": 8000,
    "revise": 8000,
    "grade": 1200,
    "verify": 6000,
    "conflict": 2500,
    "vision": 1400,
}

MAX_ATTEMPTS = 2
MAX_VARIANTS = 3
RETRIEVE_LIMIT = 25
FUSE_TOP = 16
PER_DOC_CAP = 3
RERANK_CANDIDATES = 40
CANDIDATE_PER_DOC_CAP = 6
SYNTH_MAX_CHUNKS = 12
MAX_SUBQUESTIONS = 4
RESEARCH_MAX_CHUNKS = 16

LLM_CALL_BUDGET = {
    "quick": 4,
    "research": 8,
}
NODE_TIMEOUT_S = 30.0
WRITER_TIMEOUT_S = 90.0
CHECKER_TIMEOUT_S = 60.0
NODE_TIMEOUTS = {
    "synthesize": WRITER_TIMEOUT_S,
    "revise": WRITER_TIMEOUT_S,
    "verify": CHECKER_TIMEOUT_S,
    "conflict_check": CHECKER_TIMEOUT_S,
    "investigate": 45.0,
}
INVESTIGATE_GRADE_TIMEOUT_S = 25.0
UNGRADED_EVIDENCE = 6
LLM_HTTP_TIMEOUT_S = WRITER_TIMEOUT_S
TOTAL_TIMEOUT_S = {
    "quick": 120.0,
    "research": 180.0,
}
RECURSION_LIMIT = 40
VISION_LLM_CALLS = 1

RERANK_ENABLED = True
RERANK_MODEL = "rerank-v4.0-fast"
RERANK_TIMEOUT_S = 6.0
RERANK_MAX_CHARS = 4000
OPTIONAL_NODES = ("rerank", "conflict_check", "verify")
ALLOW_GENERAL_KNOWLEDGE = True
RESEARCH_MODE_ENABLED = True
RESEARCH_RESERVED_CALLS = 3
CONFLICT_PROPERTIES = ("toc", "tmax", "ro", "thickness", "porosity")
