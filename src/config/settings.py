from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]
CORPUS_METADATA = ROOT / "corpus_metadata.yaml"
CORPUS_VOLUMES = (
    (ROOT / "markdown", CORPUS_METADATA),
    (ROOT / "Mardown", ROOT / "Mardown" / "corpus_metadata.yaml"),
)

EMBED_MODEL = "text-embedding-3-large"
EMBED_DIMS = 1536
EMBED_BATCH = 64
EMBED_MAX_CHARS = 24000
FALLBACK_EMBED_MODEL = "gemini-embedding-001"

BM25_KEY = "bm25"
BM25_SOURCE_KEY = "lexical_text"
RRF_K = 60
CANDIDATES = 300
BM25_WEIGHTS = {
    "exact": 1.0,
    "conceptual": 1.0,
    "cross_language": 1.0,
}

CORE_COLLECTIONS = ("VMM_Basin",)
CHUNK_POLICY_TYPES = {
    "prose_tables": ("text", "table"),
    "rows": ("table_row",),
}
ROW_CARD_WEIGHT = 1.0

PIPELINE_VERSION = "chunk-v1"
APP_VERSION = "0.1.0"

VISION_MODEL = ROOT / "geocrack_cnn.onnx"
VISION_CONFIG = ROOT / "model_config_mobilenet_v2.json"
VISION_LABEL = "MobileNetV2-UNet"
VISION_THRESHOLD = 0.35
VISION_MAX_SIDE = 1024
VISION_THREADS = 2
VISION_BATCH = 8
VISION_MIN_COMPONENT_PX = 60

KG_LABEL = "Crocol-KG-2026"
KG_MAX_ENTITIES = 4
KG_EVIDENCE_CHUNKS = 12
KG_FACT_ROWS = 14
VISION_BORDER_PX = 3
VISION_MAX_BYTES = 10 * 1024 * 1024
VISION_MAX_PIXELS = 24_000_000
VISION_FORMATS = ("JPEG", "PNG", "WEBP")

UPLOAD_DIR = ROOT / "uploads" / "images"
UPLOAD_RETENTION_H = 72
PURGE_EVERY_S = 3600

API_PREFIX = "/api"
QUESTION_MIN_CHARS = 3
QUESTION_MAX_CHARS = 2000
RATE_PER_MINUTE = 1
RATE_PER_DAY = 12
OTHER_RATE_PER_MINUTE = 60
GLOBAL_QUESTIONS_PER_DAY = 30
GLOBAL_TOKENS_PER_DAY = 800_000
MAX_CONCURRENT_RUNS = 2
RUN_WAIT_S = 10.0
MAX_REQUEST_BYTES = 11 * 1024 * 1024

WELLSIM_LABEL = "Crocol-WellSim-2026"
WELLSIM_MAX_NR = 50
WELLSIM_MAX_NZ = 20
WELLSIM_MAX_NT = 365
WELLSIM_MAX_N_RATE = 12
WELLSIM_MAX_N_BHP = 10
WELLSIM_THETA = 1.0
WELLSIM_MAX_POINTS = 200
WELLSIM_CURVE_DIGITS = 4
WELLSIM_RUN_TIMEOUT_S = 10.0
WELLSIM_SWEEP_TIMEOUT_S = 30.0
WELLSIM_WAIT_S = 5.0
WELLSIM_RUNS_PER_MINUTE = 10
WELLSIM_SWEEPS_PER_DAY = 20

# Global Settings config file path
GLOBAL_SETTINGS_PATH = ROOT / "global_settings.yaml"

# Global Settings class
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    chroma_host: str = "api.trychroma.com"
    chroma_api_key: SecretStr
    chroma_tenant: str
    chroma_database: str
    collection_name: str = "vmm_vector_store"
    openai_api_key: SecretStr
    google_api_key: SecretStr | None = None
    anthropic_api_key: SecretStr | None = None
    cohere_api_key: SecretStr | None = None
    pg_dsn: SecretStr | None = None
    crocol_env: str = "development"
    crocol_cors_origins: str = "http://localhost:5173"
    crocol_trusted_proxy: str | None = None

    @property
    def cors_origins(self) -> list[str]:

        return [o.strip() for o in self.crocol_cors_origins.split(",")
                if o.strip()]

    @property
    def production(self) -> bool:

        return self.crocol_env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


def peripheral_in_core(path: Path) -> list[str]:
    
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    defaults = data.get("defaults", {})
    found = []
    
    for doc in data["documents"]:
        scope = doc.get("scope", defaults.get("scope"))
        collection = doc.get("collection", defaults.get("collection"))
        
        if scope == "peripheral" and collection in CORE_COLLECTIONS:
            found.append(doc["source_path"])
            
    return found


@lru_cache
def default_excluded_sources() -> tuple[str, ...]:
    """Peripheral documents inside a core collection, across all volumes."""
    excluded = []
    for _, metadata_path in CORPUS_VOLUMES: # AI Generate Documents
        excluded.extend(peripheral_in_core(metadata_path))
        
    return tuple(sorted(excluded))
