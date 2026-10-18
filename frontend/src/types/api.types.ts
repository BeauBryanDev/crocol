// Mirrors src/crocol/app/schemas.py and docs/design/stage5_api.md §11.
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
