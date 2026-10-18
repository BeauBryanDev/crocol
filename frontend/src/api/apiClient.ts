import { ErrorResponse, MetaResponse, ReadyResponse, TraceResponse } from '../types/api.types';

// Empty in development: Vite proxies /api to FastAPI (vite.config.ts).
export const API_BASE = (import.meta.env.VITE_API_BASE ?? '').replace(/\/$/, '');

export class ApiError extends Error {
  readonly status: number;
  readonly requestId: string | null;
  readonly retryAfterS: number | null;

  constructor(message: string, status: number, requestId: string | null = null, retryAfterS: number | null = null) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.requestId = requestId;
    this.retryAfterS = retryAfterS;
  }
}

export const apiUrl = (path: string): string => `${API_BASE}/api${path}`;

const isErrorBody = (body: unknown): body is ErrorResponse =>
  typeof body === 'object' && body !== null && typeof (body as ErrorResponse).error === 'string';

export const errorFromResponse = async (res: Response): Promise<ApiError> => {
  const retry = Number(res.headers.get('Retry-After'));
  const retryAfterS = Number.isFinite(retry) && retry > 0 ? retry : null;
  let body: unknown = null;
  try {
    body = await res.json();
  } catch {
    body = null;
  }
  if (isErrorBody(body)) {
    return new ApiError(body.error, res.status, body.request_id, retryAfterS);
  }
  return new ApiError(res.statusText || 'request failed', res.status, res.headers.get('X-Request-ID'), retryAfterS);
};

export const request = async <T>(path: string, init?: RequestInit): Promise<T> => {
  let res: Response;
  try {
    res = await fetch(apiUrl(path), init);
  } catch (exc) {
    if (exc instanceof DOMException && exc.name === 'AbortError') throw exc;
    throw new ApiError('network error', 0);
  }
  if (!res.ok) throw await errorFromResponse(res);
  return (await res.json()) as T;
};

export const getMeta = (signal?: AbortSignal) => request<MetaResponse>('/meta', { signal });

export const getReady = (signal?: AbortSignal) => request<ReadyResponse>('/ready', { signal });

export const getTrace = (traceId: string, signal?: AbortSignal) =>
  request<TraceResponse>(`/traces/${encodeURIComponent(traceId)}`, { signal });
