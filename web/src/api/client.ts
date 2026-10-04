import type { Session } from '@supabase/supabase-js';
import { supabase } from './supabase';

export function getApiBaseUrl(): string {
  const envUrl = import.meta.env.VITE_API_BASE_URL;
  if (envUrl && !envUrl.includes('localhost')) {
    return envUrl.replace(/\/$/, '');
  }
  // When running in a deployed browser environment (e.g. Vercel) but VITE_API_BASE_URL was omitted or left as localhost
  if (typeof window !== 'undefined' && !['localhost', '127.0.0.1'].includes(window.location.hostname)) {
    return 'https://error404-waypoint.onrender.com';
  }
  return (envUrl || 'http://localhost:8000').replace(/\/$/, '');
}

export const API_BASE_URL = getApiBaseUrl();

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = 'ApiError';
  }
}

export async function getSession(): Promise<Session | null> {
  if (!supabase) return null;
  const { data } = await supabase.auth.getSession();
  return data.session;
}

export async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const session = await getSession();
  if (!session?.access_token) throw new ApiError(401, 'Please sign in to continue.');

  const baseUrl = getApiBaseUrl();
  let response: Response;
  try {
    response = await fetch(`${baseUrl}${path}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${session.access_token}`,
        ...options.headers,
      },
    });
  } catch (err) {
    throw new ApiError(503, `Unable to connect to Waypoint API at ${baseUrl}. ${(err as Error).message}`);
  }

  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      message = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail ?? body);
    } catch {
      /* non-JSON error */
    }
    throw new ApiError(response.status, message);
  }
  return response.json() as Promise<T>;
}

export function apiConfigError() {
  return !supabase ? 'Set VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY to connect authentication.' : '';
}

