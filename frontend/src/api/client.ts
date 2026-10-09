import type { TokenResponse } from './types';

const BASE = '/api/v1';

/** Error carrying the API's error envelope: {error: {code, message, details, request_id}}. */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details?: Record<string, string[]>;
  readonly requestId?: string;

  constructor(status: number, code: string, message: string, details?: Record<string, string[]>, requestId?: string) {
    super(message);
    this.status = status;
    this.code = code;
    this.details = details;
    this.requestId = requestId;
  }

  fieldError(field: string): string | undefined {
    const value = this.details?.[field];
    return Array.isArray(value) ? value.join(' ') : undefined;
  }
}

// The access token lives only in memory; the refresh token is an httpOnly cookie the
// browser sends to /api/v1/auth/* automatically. A page reload restores the session via
// refresh() without the token ever touching localStorage.
let accessToken: string | null = null;
let refreshInFlight: Promise<TokenResponse | null> | null = null;
let onSessionExpired: (() => void) | null = null;

export function setAccessToken(token: string | null) {
  accessToken = token;
}

export function setSessionExpiredHandler(handler: (() => void) | null) {
  onSessionExpired = handler;
}

async function parseError(response: Response): Promise<ApiError> {
  try {
    const body = await response.json();
    const err = body?.error ?? {};
    return new ApiError(response.status, err.code ?? 'error', err.message ?? response.statusText, err.details, err.request_id);
  } catch {
    return new ApiError(response.status, 'error', response.statusText || 'Request failed');
  }
}

export function refreshSession(): Promise<TokenResponse | null> {
  // De-duplicate concurrent refreshes (several queries can hit 401 at once).
  refreshInFlight ??= fetch(`${BASE}/auth/refresh`, { method: 'POST', credentials: 'same-origin' })
    .then(async (res) => {
      if (!res.ok) return null;
      const body = (await res.json()) as TokenResponse;
      accessToken = body.access;
      return body;
    })
    .catch(() => null)
    .finally(() => {
      refreshInFlight = null;
    });
  return refreshInFlight;
}

type Query = Record<string, string | number | undefined | null | string[]>;

export function buildQuery(params: Query = {}): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === '') continue;
    if (Array.isArray(value)) {
      if (value.length) search.set(key, value.join(','));
    } else search.set(key, String(value));
  }
  const text = search.toString();
  return text ? `?${text}` : '';
}

interface RequestOptions {
  method?: string;
  query?: Query;
  json?: unknown;
  body?: BodyInit;
  signal?: AbortSignal;
}

export async function api<T>(path: string, options: RequestOptions = {}, retry = true): Promise<T> {
  const headers: Record<string, string> = { Accept: 'application/json' };
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`;
  if (options.json !== undefined) headers['Content-Type'] = 'application/json';

  let response: Response;
  try {
    response = await fetch(`${BASE}${path}${buildQuery(options.query)}`, {
      method: options.method ?? 'GET',
      headers,
      body: options.json !== undefined ? JSON.stringify(options.json) : options.body,
      credentials: 'same-origin',
      signal: options.signal,
    });
  } catch (error) {
    if ((error as Error).name === 'AbortError') throw error;
    throw new ApiError(0, 'network_error', 'Cannot reach the FinPilot API. Check your connection and try again.');
  }

  if (response.status === 401 && retry && !path.startsWith('/auth/')) {
    const refreshed = await refreshSession();
    if (refreshed) return api<T>(path, options, false);
    onSessionExpired?.();
  }
  if (!response.ok) throw await parseError(response);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}
