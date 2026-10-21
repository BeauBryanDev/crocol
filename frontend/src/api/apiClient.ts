import axios, { AxiosRequestConfig, AxiosResponse } from 'axios';
import { ErrorResponse, MetaResponse, ReadyResponse, TraceResponse } from '../types/api.types';

// Empty in development: Vite proxies /api to FastAPI (vite.config.ts).
export const API_BASE = (import.meta.env.VITE_API_BASE ?? '').replace(/\/$/, '');
const JSON_TIMEOUT_MS = 30_000;

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

export const http = axios.create({
  baseURL: `${API_BASE}/api`,
  timeout: JSON_TIMEOUT_MS,
  headers: { Accept: 'application/json' }
});

const isErrorBody = (body: unknown): body is ErrorResponse =>
  typeof body === 'object' && body !== null && typeof (body as ErrorResponse).error === 'string';

const header = (res: AxiosResponse, name: string): string | null => {
  const value = res.headers[name];
  return typeof value === 'string' ? value : null;
};

export const errorFromResponse = (res: AxiosResponse, body: unknown): ApiError => {
  const retry = Number(header(res, 'retry-after'));
  const retryAfterS = Number.isFinite(retry) && retry > 0 ? retry : null;
  if (isErrorBody(body)) {
    return new ApiError(body.error, res.status, body.request_id, retryAfterS);
  }
  return new ApiError(res.statusText || 'request failed', res.status, header(res, 'x-request-id'), retryAfterS);
};

// Axios errors become ApiError; a cancelled request stays an AbortError, as callers expect.
export const toApiError = (exc: unknown): unknown => {
  if (axios.isCancel(exc)) return new DOMException('aborted', 'AbortError');
  if (!axios.isAxiosError(exc)) return exc;
  if (!exc.response) return new ApiError('network error', 0);
  return errorFromResponse(exc.response, exc.response.data);
};

export const request = async <T>(path: string, config?: AxiosRequestConfig): Promise<T> => {
  try {
    const res = await http.get<T>(path, config);
    return res.data;
  } catch (exc) {
    throw toApiError(exc);
  }
};

export const post = async <T>(path: string, body: unknown, config?: AxiosRequestConfig): Promise<T> => {
  try {
    const res = await http.post<T>(path, body, config);
    return res.data;
  } catch (exc) {
    throw toApiError(exc);
  }
};

export const getMeta = (signal?: AbortSignal) => request<MetaResponse>('/meta', { signal });

export const getReady = (signal?: AbortSignal) => request<ReadyResponse>('/ready', { signal });

export const getTrace = (traceId: string, signal?: AbortSignal) =>
  request<TraceResponse>(`/traces/${encodeURIComponent(traceId)}`, { signal });
