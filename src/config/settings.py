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
    "conceptual": 0.3,
    "cross_language": 0.3,
}

CORE_COLLECTIONS = ("VMM_Basin",)
CHUNK_POLICY_TYPES = {
    "prose_tables": ("text", "table"),
    "rows": ("table_row",),
}
ROW_CARD_WEIGHT = 1.0


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
    pg_dsn: SecretStr | None = None


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
    for _, metadata_path in CORPUS_VOLUMES:
        excluded.extend(peripheral_in_core(metadata_path))
    return tuple(sorted(excluded))
