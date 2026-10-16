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
}
FALLBACKS = {
    "grade": HAIKU,
    "verify": HAIKU,
    "conflict": HAIKU,
}
MAX_OUTPUT_TOKENS = {
    "analyze": 800,
    "plan": 800,
    "rewrite": 600,
    "synthesize": 2500,
    "revise": 2500,
    "grade": 1200,
    "verify": 2500,
    "conflict": 2500,
}

MAX_ATTEMPTS = 2
MAX_VARIANTS = 3
RETRIEVE_LIMIT = 10
FUSE_TOP = 12
PER_DOC_CAP = 3
SYNTH_MAX_CHUNKS = 8
MAX_SUBQUESTIONS = 4
RESEARCH_MAX_CHUNKS = 16

LLM_CALL_BUDGET = {
    "quick": 4,
    "research": 8,
}
NODE_TIMEOUT_S = 30.0
TOTAL_TIMEOUT_S = {
    "quick": 60.0,
    "research": 180.0,
}
RECURSION_LIMIT = 40

RERANK_ENABLED = False
ALLOW_GENERAL_KNOWLEDGE = False
