// The FastAPI backend is the source of truth for every shape here.

export type AnswerStatus = 'answered' | 'partial' | 'abstained' | 'error';

export type NodeStatus = 'ok' | 'skipped' | 'timeout' | 'error' | 'fallback';

export interface Usage {
  llm_calls: number;
  tokens: number;
}

export interface ConflictSide {
  entity: string;
  value: string;
  unit: string;
  label: string;
  chunk_id: string;
  doc_id: string;
  citation: string;
  quote: string;
}

export interface Conflict {
  entity: string;
  property: string;
  comparable: boolean;
  sides: ConflictSide[];
}

export type TrendLabel = 'decreasing' | 'increasing' | 'stable' | 'variable' | 'no_production' | 'insufficient_data';

export interface ProductionTrend {
  label: TrendLabel;
  months: number;
  first: number | null;
  last: number | null;
  mean: number | null;
  change_pct: number | null;
  slope_pct_month: number | null;
  scatter_pct: number | null;
}

export interface ProductionPoint {
  month: string;
  oil: number | null;
  gas: number | null;
}

// One field (or a contract grouping fields) from ANH fiscalized production.
export interface ProductionSeries {
  name: string;
  kind: 'field' | 'contract';
  fields: string[];
  departments: string[];
  municipalities: string[];
  operators: string[];
  units: { oil: 'BPDC'; gas: 'MPCPDC' };
  points: ProductionPoint[];
  trends: { oil: ProductionTrend; gas: ProductionTrend };
  source: string;
}

// One remembered turn, signed by the server; sent back unchanged (max 3).
export interface MemoryRecord {
  v: number;
  ts: number;
  kind: 'text' | 'image' | 'wellsim';
  language: 'es' | 'en';
  question: string;
  standalone: string;
  summary: string;
  entities: string[];
  facts: Record<string, string>;
  sig: string;
}

// What the user has open on screen; context for the agent, never evidence.
export interface UiContext {
  formation?: string;
  place?: string;
}

export interface ChatResponse {
  trace_id: string;
  status: AnswerStatus;
  answer: string;
  citations: string[];
  references: string[];
  caveats: string[];
  conflicts: Conflict[];
  overlay_webp_b64: string | null;
  usage: Usage | null;
  production: ProductionSeries[];
  simulation: WellSweepResponse | null;
  vision: VisionResult | null;
  memory: MemoryRecord | null;
}

export interface NodeEvent {
  node: string;
  status: NodeStatus;
  duration_ms: number;
  summary: Record<string, unknown>;
}

export interface ErrorResponse {
  error: string;
  request_id: string;
}

export interface MetaLimits {
  questions_per_minute: number;
  questions_per_day_per_ip: number;
  questions_per_day: number;
  tokens_per_day: number;
  concurrent_runs: number;
  question_max_chars: number;
  image_max_bytes: number;
  image_formats: string[];
}

export interface MetaResponse {
  app: string;
  version: string;
  models: Record<string, string>;
  limits: MetaLimits;
  usage_today: Record<string, number>;
  citation_labels: Record<string, string>;
}

export interface CheckResult {
  ok: boolean;
  detail: string;
}

export interface ReadyResponse {
  ready: boolean;
  checks: Record<string, CheckResult>;
}

export interface TraceResponse {
  trace_id: string;
  created_at: string;
  status: string;
  language: string | null;
  mode: string | null;
  attempts: number | null;
  llm_calls: number | null;
  tokens_in: number | null;
  tokens_out: number | null;
  latency_ms: number | null;
  verification: Record<string, unknown> | null;
  conflicts: Record<string, unknown>[] | null;
  trace: Record<string, unknown>[];
  chunks: Record<string, unknown>[];
  app_version: string | null;
}

export interface LocateResponse {
  kind: string;
  name: string;
  geojson: GeoJsonGeometry | null;
  source: string;
}

export interface GeoJsonGeometry {
  type: string;
  coordinates?: unknown;
  geometries?: GeoJsonGeometry[];
}

export type EntityKind =
  | 'formation' | 'member' | 'group' | 'field' | 'well' | 'organization'
  | 'municipality' | 'seismic_3d' | 'fault' | 'contract' | 'contract_area'
  | 'regulation' | 'document' | 'person' | 'institution' | 'topic' | 'basin';

export interface EntityRelation {
  direction: 'in' | 'out';
  rel: string;
  kind: string;
  total: number;
  names: string[];
}

export interface EntityDocument {
  doc_id: string;
  citation: string;
  title: string;
  collection: string;
  scope: string;
  chunks: number;
  described: boolean;
}

export interface EntityResponse {
  entity: { 
    kind: string; 
    name: string; 
    score: number;
    mentions: number;
    props: Record<string, unknown>
     };
  candidates: { kind: string;
     name: string; 
     score: number }[];
  relations: EntityRelation[];
  documents: EntityDocument[];
  source: string;
}

// Well simulator (Crocol-WellSim-2026), mirrored from app/schemas.py.
export type WellMode = 'rate' | 'bhp';
export type WellControl = 'rate' | 'bhp';

export interface WellParams {
  rw: number;
  re: number;
  h: number;
  Nr: number;
  Nz: number;
  kh: number;
  kv_kh: number;
  phi: number;
  cf: number;
  pi: number;
  pb: number;
  mu: number;
  Bo: number;
  co: number;
  rho: number;
  kro: number;
  skin: number;
  perf_top: number;
  perf_bot: number | null;
  well_mode: WellMode;
  q: number | null;
  pwf: number | null;
  pwf_min: number | null;
  max_drawdown: number | null;
  q_max: number | null;
  q_abandon: number | null;
  enforce_pb: boolean;
  T: number;
  Nt: number;
  dt_mode: 'uniform' | 'geometric';
  dt0: number;
}

export interface WellSweepOptions {
  controls: WellControl[];
  n_rate: number;
  n_bhp: number;
  rate_min: number | null;
  rate_max: number | null;
  tolerance: number;
  refine_rounds: number;
  discount_rate: number;
}

export interface WellLimits {
  max_nr: number;
  max_nz: number;
  max_nt: number;
  max_n_rate: number;
  max_n_bhp: number;
  runs_per_minute: number;
  sweeps_per_day: number;
}

export interface WellDefaultsResponse {
  well: WellParams;
  options: WellSweepOptions;
  limits: WellLimits;
  source: string;
}

export type WellStepMode = 'target' | 'pwf_floor' | 'q_cap';

export interface WellRunSummary {
  np_stb: number;
  recovery_factor: number;
  ooip_stb: number;
  q_avg_stb_d: number;
  q_final_stb_d: number;
  pwf_final_psi: number;
  p_avg_final_psi: number;
  p_min_cell_psi: number;
  t_end_days: number;
  ended_by: 'horizon' | 'abandonment';
  pwf_floor_psi: number;
  floor_source: string;
  plateau_days: number | null;
  valid: boolean;
}

export interface WellRunResponse {
  summary: WellRunSummary;
  events: { t_days: number; mode: WellStepMode }[];
  warnings: string[];
  assumptions: string[];
  inputs: Record<string, unknown>;
  series: {
    t_days: number[];
    pwf_psi: number[];
    q_stb_d: number[];
    np_stb: number[];
    p_avg_psi: number[];
    mode: WellStepMode[];
  };
  fields: {
    r_cell_ft: number[];
    z_cell_ft: number[];
    pressure_drop_final_psi: number[][];
  };
  source: string;
}

export interface WellCase {
  control: WellControl;
  target: number;
  np_stb: number;
  rf: number;
  pct_of_limit: number;
  plateau_days: number | null;
  t_end_days: number;
  ended_by: string;
  q_final_stb_d: number;
  pwf_final_psi: number;
  drawdown_max_psi: number;
  discounted_np_stb: number;
  t90_days: number | null;
  limit: string;
  valid: boolean;
}

export interface WellCurve {
  control: WellControl;
  target: number;
  t_days: number[];
  np_stb: number[];
}

export interface WellSweepResponse {
  objective: string;
  inputs: Record<string, number | string | null>;
  bounds: Record<string, unknown>;
  columns: string[];
  rows: (string | number | boolean | null)[][];
  best_overall: WellCase;
  best_rate: WellCase | null;
  best_bhp: WellCase | null;
  recommended_rate: WellCase | null;
  best_discounted_rate: WellCase | null;
  recommendation_rule: string;
  notes: string[];
  assumptions: string[];
  table_markdown: string;
  curves: WellCurve[];
  well: Record<string, unknown>;
  source: string;
}

// Crack segmentation (MobileNetV2-UNet) results, mirrored from app/schemas.py.
export type CrackSeverity = 'low' | 'moderate' | 'high' | 'critical';

export interface CrackReport {
  model: string;
  threshold: number;
  width_px: number;
  height_px: number;
  tiles: number;
  density_pct: number;
  fractal_dimension: number;
  fractal_r2: number;
  crack_count: number;
  total_length_px: number;
  mean_width_px: number;
  max_width_px: number;
  severity: CrackSeverity;
  mean_confidence: number;
  ambiguous_pct: number;
  elapsed_ms: number;
  dominant_angles: [number, number][];
  rose: number[];
}

export interface VisionInterpretation {
  is_rock: boolean;
  rock_description: string;
  diagnosis: string;
  fluid_flow: string;
  confidence: 'low' | 'medium' | 'high';
}

export interface VisionResult {
  report: CrackReport;
  mask_webp_b64: string | null;
  interpretation: VisionInterpretation | null;
}
