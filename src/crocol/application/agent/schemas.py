import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from crocol.domains.models.chunks import Chunk
from crocol.domains.services.citations import page_span

PROMPTS = Path(__file__).resolve().parent / "prompts"
FRONT_MATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.S)

Scope = Literal["core", "all"]
Policy = Literal["prose_tables", "numeric"]
QueryType = Literal["exact", "conceptual", "cross_language"]


class PlaceMention(BaseModel):
    name: str
    kind: Literal["municipality", "field", "well", "fault", "unknown"]


class Analysis(BaseModel):
    language: Literal["es", "en"]
    mode: Literal["quick", "research"]
    intents: list[str]
    corpus_scope: Scope
    chunk_policy: Policy
    query_type: QueryType
    variants: list[str]
    bm25_query: str | None = None
    places: list[PlaceMention] = []


class VisualDiagnosis(BaseModel):
    is_rock: bool
    rock_description: str
    diagnosis: str
    fluid_flow: str
    confidence: Literal["low", "medium", "high"]


class Grade(BaseModel):
    relevant: list[str]
    sufficient: bool
    missing: str
    reason: str


class RewritePlan(BaseModel):
    variants: list[str]
    corpus_scope: Scope
    chunk_policy: Policy
    query_type: QueryType
    bm25_query: str | None = None
    reason: str


class DraftAnswer(BaseModel):
    text: str
    cited: list[str]
    insufficient: bool = False


class ClaimCheck(BaseModel):
    claim: str
    labels: list[str]
    verdict: Literal["supported", "unsupported", "contradicted"]
    numeric: bool = False


class Verification(BaseModel):
    claims: list[ClaimCheck]


class SubQuestion(BaseModel):
    question: str
    corpus_scope: Scope
    chunk_policy: Policy
    query_type: QueryType


class ResearchPlan(BaseModel):
    sub_questions: list[SubQuestion]


class ConflictRecord(BaseModel):
    entity: str
    property: str
    value: str
    unit: str
    label: str
    quote: str


class ConflictRecords(BaseModel):
    records: list[ConflictRecord]


@dataclass(frozen=True)
class Prompt:
    name: str
    version: str
    text: str


@lru_cache
def load_prompt(name: str) -> Prompt:
    """Prompt file with a version front-matter line."""
    raw = (PROMPTS / f"{name}.md").read_text(encoding="utf-8")
    version = "0"
    match = FRONT_MATTER_RE.match(raw)
    
    if match:
        for line in match.group(1).splitlines():
            
            key, _, value = line.partition(":")
            
            if key.strip() == "version":
                version = value.strip()
                
        raw = raw[match.end():]
        
    return Prompt(name=name, 
                  version=version,
                  text=raw.strip()
                  )


def chunk_header(chunk: Chunk) -> str:
    
    pages = page_span(chunk.page_start, chunk.page_end)
    origin = f"{chunk.citation}, {pages}" if pages else chunk.citation
    
    if chunk.doc_type == "ai_research_report":
        
        origin = f"{origin}, UNVERIFIED AI-GENERATED SOURCE"
        
    heading = f" | {chunk.heading_path}" if chunk.heading_path else ""
    
    return f"[{chunk.label}] ({origin}){heading}"


def render_evidence(chunks: list[Chunk]) -> str:
    """Labelled evidence block shared by grade, synthesize and verify."""
    blocks = []
    for chunk in chunks:
        blocks.append(f"{chunk_header(chunk)}\n{chunk.text}")
        
    return "\n\n".join(blocks)
