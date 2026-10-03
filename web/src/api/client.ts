import type { Session } from '@supabase/supabase-js';
import { supabase } from './supabase';

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/$/, '');
export class ApiError extends Error { constructor(public status: number, message: string) { super(message); this.name = 'ApiError'; } }
export async function getSession(): Promise<Session | null> { if (!supabase) return null; const { data } = await supabase.auth.getSession(); return data.session; }
export async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const session = await getSession();
  if (!session?.access_token) throw new ApiError(401, 'Please sign in to continue.');
  const response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${session.access_token}`, ...options.headers } });
  if (!response.ok) { let message = `Request failed (${response.status})`; try { const body = await response.json(); message = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail ?? body); } catch { /* non-JSON error */ } throw new ApiError(response.status, message); }
  return response.json() as Promise<T>;
}
export function apiConfigError() { return !supabase ? 'Set VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY to connect authentication.' : ''; }
