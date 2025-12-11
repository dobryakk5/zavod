export type ApiRequestOptions = {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
  body?: unknown;
  headers?: HeadersInit;
  next?: RequestInit['next'];
};

export class ApiError extends Error {
  status: number;
  body?: string;

  constructor(message: string, status: number, body?: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.body = body;
  }
}

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:4000/api';
export const BACKEND_BASE_URL = API_BASE_URL.replace(/\/api\/?$/, '');

let isRefreshing = false;
let refreshPromise: Promise<boolean> | null = null;

/**
 * Refresh access token using refresh token from cookies
 */
async function refreshAccessToken(): Promise<boolean> {
  if (isRefreshing && refreshPromise) {
    return refreshPromise;
  }

  isRefreshing = true;
  refreshPromise = (async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/auth/refresh/`, {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (response.ok) {
        return true;
      }
      return false;
    } catch (error) {
      console.error('Token refresh failed:', error);
      return false;
    } finally {
      isRefreshing = false;
      refreshPromise = null;
    }
  })();

  return refreshPromise;
}

export async function apiFetch<TResponse>(endpoint: string, options: ApiRequestOptions = {}): Promise<TResponse> {
  const { method = 'GET', body, headers, next } = options;
  const isFormData = typeof FormData !== 'undefined' && body instanceof FormData;
  const hasJsonBody = body !== undefined && !isFormData;
  const requestBody = hasJsonBody ? JSON.stringify(body) : body;

  const makeRequest = async (): Promise<Response> => {
    return fetch(`${API_BASE_URL}${endpoint}`, {
      method,
      headers: {
        ...(hasJsonBody ? { 'Content-Type': 'application/json' } : {}),
        ...headers
      },
      body: requestBody as BodyInit | undefined,
      credentials: 'include',
      next
    });
  };

  let response = await makeRequest();

  // If we get 401 and it's not already a refresh/login endpoint, try to refresh token
  if (response.status === 401 && !endpoint.includes('/auth/refresh') && !endpoint.includes('/auth/token')) {
    const refreshed = await refreshAccessToken();

    if (refreshed) {
      // Retry the original request with refreshed token
      response = await makeRequest();
    } else {
      // Refresh failed, redirect to login
      if (typeof window !== 'undefined') {
        window.location.href = '/login';
      }
    }
  }

  if (!response.ok) {
    const text = await response.text();
    const message = response.status === 401 ? 'unauthorized' : (text || 'API request failed');
    throw new ApiError(message, response.status, text);
  }

  if (response.status === 204) {
    return undefined as TResponse;
  }

  return (await response.json()) as TResponse;
}
