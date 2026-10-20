from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from config.roles import MEMORY_TURNS
from config.settings import (
    MEMORY_FIELD_CHARS,
    WELLSIM_MAX_N_BHP,
    WELLSIM_MAX_N_RATE,
    WELLSIM_MAX_NR,
    WELLSIM_MAX_NT,
    WELLSIM_MAX_NZ,
)


ShortText = Annotated[str, Field(max_length=120)]
MemoryText = Annotated[str, Field(max_length=MEMORY_FIELD_CHARS)]


class MemoryRecord(BaseModel):
    """One remembered turn; signed by the server, kept by the browser."""

    model_config = ConfigDict(extra="forbid")

    v: int
    ts: int
    kind: Literal["text", "image", "wellsim"]
    language: Literal["es", "en"]
    question: MemoryText
    standalone: MemoryText
    summary: MemoryText
    entities: list[ShortText] = Field(default=[], max_length=8)
    facts: dict[str, ShortText] = Field(default={}, max_length=8)
    sig: str = Field(pattern=r"^[0-9a-f]{64}$")


class UiContext(BaseModel):
    """What the user has open on screen; context, never evidence."""

    model_config = ConfigDict(extra="forbid")

    formation: ShortText | None = None
    place: ShortText | None = None


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    well: "WellParams | None" = None
    history: list[MemoryRecord] = Field(default=[], max_length=MEMORY_TURNS)
    ui_context: UiContext | None = None


class Usage(BaseModel):
    llm_calls: int
    tokens: int


class CrackReportOut(BaseModel):
    model: str
    threshold: float
    width_px: int
    height_px: int
    tiles: int
    density_pct: float
    fractal_dimension: float
    fractal_r2: float
    crack_count: int
    total_length_px: float
    mean_width_px: float
    max_width_px: float
    severity: Literal["low", "moderate", "high", "critical"]
    mean_confidence: float
    ambiguous_pct: float
    elapsed_ms: int
    dominant_angles: list[tuple[float, float]] = []
    rose: list[float] = []


class VisionInterpretation(BaseModel):
    is_rock: bool
    rock_description: str
    diagnosis: str
    fluid_flow: str
    confidence: Literal["low", "medium", "high"]


class VisionResult(BaseModel):
    report: CrackReportOut
    mask_webp_b64: str | None = None
    interpretation: VisionInterpretation | None = None


class ChatResponse(BaseModel):
    trace_id: str
    status: str
    answer: str
    citations: list[str] = []
    references: list[str] = []
    caveats: list[str] = []
    conflicts: list[dict[str, Any]] = []
    overlay_webp_b64: str | None = None
    usage: Usage | None = None
    production: list[dict[str, Any]] = []
    simulation: dict[str, Any] | None = None
    vision: VisionResult | None = None
    memory: MemoryRecord | None = None


class ErrorResponse(BaseModel):
    error: str
    request_id: str


class TraceResponse(BaseModel):
    trace_id: str
    created_at: str
    status: str
    language: str | None = None
    mode: str | None = None
    attempts: int | None = None
    llm_calls: int | None = None
    tokens_in: int | None = None
    tokens_out: int | None = None
    latency_ms: int | None = None
    verification: dict[str, Any] | None = None
    conflicts: list[dict[str, Any]] | None = None
    trace: list[dict[str, Any]] = []
    chunks: list[dict[str, Any]] = []
    app_version: str | None = None


class CheckResult(BaseModel):
    ok: bool
    detail: str = ""


class ReadyResponse(BaseModel):
    ready: bool
    checks: dict[str, CheckResult]


class MetaResponse(BaseModel):
    app: str
    version: str
    models: dict[str, str]
    limits: dict[str, Any]
    usage_today: dict[str, int]
    citation_labels: dict[str, str]


class EntitySummary(BaseModel):
    kind: str
    name: str
    score: float
    mentions: int
    props: dict[str, Any] = {}


class EntityCandidate(BaseModel):
    kind: str
    name: str
    score: float


class EntityRelation(BaseModel):
    direction: Literal["in", "out"]
    rel: str
    kind: str
    total: int
    names: list[str]


class EntityDocument(BaseModel):
    doc_id: str
    citation: str
    title: str
    collection: str
    scope: str
    chunks: int
    described: bool


class EntityResponse(BaseModel):
    entity: EntitySummary
    candidates: list[EntityCandidate] = []
    relations: list[EntityRelation] = []
    documents: list[EntityDocument] = []
    source: str


class LocateResponse(BaseModel):
    kind: str
    name: str
    geojson: dict[str, Any] | None
    source: str


class WellParams(BaseModel):
    """Web form well: defaults are the CLI's; theta and boundaries are fixed."""

    model_config = ConfigDict(extra="forbid")

    rw: float = Field(0.354, gt=0, description="Well radius (ft)")
    re: float = Field(1000.0, gt=0, description="Drainage radius (ft)")
    h: float = Field(50.0, gt=0, description="Producing thickness (ft)")
    Nr: int = Field(40, ge=3, le=WELLSIM_MAX_NR, description="Radial cells")
    Nz: int = Field(10, ge=1, le=WELLSIM_MAX_NZ,
                    description="Vertical cells")
    kh: float = Field(100.0, gt=0,
                      description="Horizontal permeability (md)")
    kv_kh: float = Field(0.1, gt=0, le=1.0, description="Anisotropy kv/kh")
    phi: float = Field(0.2, gt=0, lt=1, description="Porosity (fraction)")
    cf: float = Field(4e-6, ge=0,
                      description="Rock compressibility (1/psi)")
    pi: float = Field(4000.0, gt=0,
                      description="Initial reservoir pressure (psi)")
    pb: float = Field(2000.0, gt=0,
                      description="Bubble point pressure (psi)")
    mu: float = Field(1.5, gt=0, description="Oil viscosity (cP)")
    Bo: float = Field(1.2, gt=0,
                      description="Oil formation volume factor (rb/STB)")
    co: float = Field(1e-5, ge=0, description="Oil compressibility (1/psi)")
    rho: float = Field(50.0, gt=0, description="Oil density (lb/ft3)")
    kro: float = Field(1.0, gt=0, le=1.0,
                       description="Oil relative permeability")
    skin: float = Field(0.0, ge=-6.0, le=100.0, description="Skin factor")
    perf_top: float = Field(0.0, ge=0,
                            description="Perforation top (ft below top)")
    perf_bot: float | None = Field(None, gt=0,
                                   description="Perforation bottom (ft)")
    well_mode: Literal["rate", "bhp"] = "rate"
    q: float | None = Field(1000.0, gt=0, description="Target rate (STB/d)")
    pwf: float | None = Field(None, gt=0,
                              description="Target flowing BHP (psi)")
    pwf_min: float | None = Field(None, gt=0,
                                  description="Operating minimum BHP (psi)")
    max_drawdown: float | None = Field(None, gt=0,
                                       description="Maximum drawdown (psi)")
    q_max: float | None = Field(None, gt=0,
                                description="Facility rate limit (STB/d)")
    q_abandon: float | None = Field(None, gt=0,
                                    description="Economic limit (STB/d)")
    enforce_pb: bool = True
    T: float = Field(365.0, gt=0, le=36500.0,
                     description="Simulated horizon (days)")
    Nt: int = Field(100, ge=1, le=WELLSIM_MAX_NT,
                    description="Number of time steps")
    dt_mode: Literal["uniform", "geometric"] = "geometric"
    dt0: float = Field(1e-3, gt=0, description="First time step (days)")


class WellSweepOptions(BaseModel):

    model_config = ConfigDict(extra="forbid")

    controls: list[Literal["rate", "bhp"]] = Field(
        default=["rate", "bhp"],
         min_length=1, max_length=2)
    n_rate: int = Field(10, ge=3, le=WELLSIM_MAX_N_RATE)
    n_bhp: int = Field(8, ge=3, le=WELLSIM_MAX_N_BHP)
    rate_min: float | None = Field(None, gt=0)
    rate_max: float | None = Field(None, gt=0)
    tolerance: float = Field(0.01, gt=0, le=0.1)
    refine_rounds: int = Field(2, ge=0, le=3)
    discount_rate: float = Field(0.10, ge=0, le=1.0)


class WellSweepRequest(BaseModel):

    model_config = ConfigDict(extra="forbid")

    well: WellParams = Field(default_factory=WellParams)
    options: WellSweepOptions = Field(default_factory=WellSweepOptions)


class WellSeries(BaseModel):
    t_days: list[float]
    pwf_psi: list[float]
    q_stb_d: list[float]
    np_stb: list[float]
    p_avg_psi: list[float]
    mode: list[str]


class WellFields(BaseModel):
    r_cell_ft: list[float]
    z_cell_ft: list[float]
    pressure_drop_final_psi: list[list[float]]


class WellRunResponse(BaseModel):
    summary: dict[str, Any]
    events: list[dict[str, Any]]
    warnings: list[str]
    assumptions: list[str]
    inputs: dict[str, Any]
    series: WellSeries
    fields: WellFields
    source: str


class WellCurve(BaseModel):
    control: Literal["rate", "bhp"]
    target: float
    t_days: list[float]
    np_stb: list[float]


class WellSweepResponse(BaseModel):
    objective: str
    inputs: dict[str, Any]
    bounds: dict[str, Any]
    columns: list[str]
    rows: list[list[Any]]
    best_overall: dict[str, Any]
    best_rate: dict[str, Any] | None
    best_bhp: dict[str, Any] | None
    recommended_rate: dict[str, Any] | None
    best_discounted_rate: dict[str, Any] | None
    recommendation_rule: str
    notes: list[str]
    assumptions: list[str]
    table_markdown: str
    curves: list[WellCurve]
    well: dict[str, Any]
    source: str


class WellDefaultsResponse(BaseModel):
    well: WellParams
    options: WellSweepOptions
    limits: dict[str, int]
    source: str


ChatRequest.model_rebuild()
