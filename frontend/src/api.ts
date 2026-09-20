const PROD_BACKEND_URL = 'https://hireflow-wnko.onrender.com';

/**
 * Returns the resolved API base URL.
 * Strategy:
 * 1. If VITE_API_BASE_URL is provided in environment, use it.
 * 2. In production (Vercel deployment): ALWAYS use Render backend, NEVER localhost.
 * 3. In local development: use empty string so Vite proxy routes to local backend.
 */
export const getApiBaseUrl = (): string => {
  const envUrl = import.meta.env.VITE_API_BASE_URL;
  if (envUrl && typeof envUrl === 'string' && envUrl.trim() !== '') {
    return envUrl.trim().replace(/\/$/, '');
  }

  // Production build/deployment: strictly use Render backend
  if (import.meta.env.PROD) {
    return PROD_BACKEND_URL;
  }

  // Local development fallback (Vite dev server handles proxy to local backend)
  return '';
};

export const API_BASE_URL = getApiBaseUrl();

/**
 * Prepends the active API base URL to any relative endpoint path.
 */
export const apiUrl = (endpoint: string): string => {
  const cleanEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
  const base = getApiBaseUrl();
  return base ? `${base}${cleanEndpoint}` : cleanEndpoint;
};

/**
 * Type-safe API fetch wrapper that guarantees all requests resolve to the production backend.
 */
export const apiFetch = (endpoint: string, init?: RequestInit): Promise<Response> => {
  return fetch(apiUrl(endpoint), init);
};
