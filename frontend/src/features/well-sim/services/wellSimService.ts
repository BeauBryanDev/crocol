import { post, request } from '../../../api/apiClient';
import {
  WellDefaultsResponse,
  WellParams,
  WellRunResponse,
  WellSweepOptions,
  WellSweepResponse
} from '../../../types/api.types';

// A sweep may wait 5 s for the simulator slot and run up to 30 s.
const SWEEP_TIMEOUT_MS = 45_000;

export const getWellDefaults = (signal?: AbortSignal) =>
  request<WellDefaultsResponse>('/wellsim/defaults', { signal });

export const runWell = (well: WellParams, signal?: AbortSignal) =>
  post<WellRunResponse>('/wellsim/run', well, { signal });

export const sweepWell = (well: WellParams, options: WellSweepOptions, signal?: AbortSignal) =>
  post<WellSweepResponse>('/wellsim/sweep', { well, options }, { signal, timeout: SWEEP_TIMEOUT_MS });
