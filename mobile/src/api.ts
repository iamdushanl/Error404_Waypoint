import { createClient } from '@supabase/supabase-js';

export function getApiBaseUrl(): string {
  const envUrl = import.meta.env.VITE_API_BASE_URL;
  if (envUrl && !envUrl.includes('localhost')) {
    return envUrl.replace(/\/$/, '');
  }
  if (typeof window !== 'undefined' && !['localhost', '127.0.0.1'].includes(window.location.hostname)) {
    return 'https://error404-waypoint.onrender.com';
  }
  return (envUrl || 'http://localhost:8000').replace(/\/$/, '');
}

const DEFAULT_SUPABASE_URL = 'https://qjhhknmiycfpyozpysxa.supabase.co';
const DEFAULT_SUPABASE_ANON_KEY =
  'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InFqaGhrbm1peWNmcHlvenB5c3hhIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTA5MzU4MDMsImV4cCI6MjEwNjUxMTgwM30.H6FE4Ys_aT5SqDG0NsDNF0luDUATrPLnwCaCwVxqjBg';

const supabaseUrl = (import.meta.env.VITE_SUPABASE_URL as string | undefined) || DEFAULT_SUPABASE_URL;
const supabaseKey = (import.meta.env.VITE_SUPABASE_ANON_KEY as string | undefined) || DEFAULT_SUPABASE_ANON_KEY;
export const supabase = supabaseUrl && supabaseKey ? createClient(supabaseUrl, supabaseKey, { auth: { persistSession: true, autoRefreshToken: true } }) : null;
export type DriverTrip = { id: string; vehicle_id: string; status: string; driver_acknowledged: boolean; stops: Array<{ id: string; outlet_id: string; sequence_number: number; load_position: number; planned_arrival_time: string | null; status: string }> };
export async function apiFetch<T>(path: string, options: RequestInit = {}) {
  const session = (await supabase?.auth.getSession())?.data.session;
  if (!session?.access_token) throw new Error('Driver authentication is required.');
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
    throw new Error(`Unable to connect to Waypoint API at ${baseUrl}. ${(err as Error).message}`);
  }
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      message = typeof body.detail === 'string' ? body.detail : message;
    } catch {
      /* non-JSON error */
    }
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}
export async function getDriverTrip() { const result = await apiFetch<{ data: Array<{ id: string }> }>('/api/v1/trips?limit=1'); return result.data[0] ? apiFetch<DriverTrip>(`/api/v1/trips/${result.data[0].id}`) : null; }
export const acknowledgeDriverTrip = (id: string) => apiFetch<DriverTrip>(`/api/v1/trips/${id}/acknowledge`, { method: 'PATCH', body: JSON.stringify({ role: 'driver' }) });
export const departDriverTrip = (id: string) => apiFetch<DriverTrip>(`/api/v1/trips/${id}/depart`, { method: 'PATCH' });
export const recordDelivery = (body: Record<string, unknown>) => apiFetch<{ id: string }>('/api/v1/deliveries', { method: 'POST', body: JSON.stringify(body) });
export const syncOperations = (operations: unknown[]) => apiFetch<{ results: Array<{ operation_id: string; status: string }>; failed_count: number }>('/api/v1/sync', { method: 'POST', body: JSON.stringify({ operations }) });
export async function sendOtp(contact: string) { if (!supabase) throw new Error('Mobile Supabase configuration is missing.'); const phone = /^\+?[0-9 ()-]{7,}$/.test(contact); const result = phone ? await supabase.auth.signInWithOtp({ phone: contact }) : await supabase.auth.signInWithOtp({ email: contact }); if (result.error) throw result.error; }
export async function verifyOtp(contact: string, token: string) { if (!supabase) throw new Error('Mobile Supabase configuration is missing.'); const phone = /^\+?[0-9 ()-]{7,}$/.test(contact); const result = phone ? await supabase.auth.verifyOtp({ phone: contact, token, type: 'sms' }) : await supabase.auth.verifyOtp({ email: contact, token, type: 'email' }); if (result.error) throw result.error; }
export async function signInWithPassword(email: string, password: string) { if (!supabase) throw new Error('Mobile Supabase configuration is missing.'); const result = await supabase.auth.signInWithPassword({ email, password }); if (result.error) throw result.error; return result.data; }
export async function signOut() { if (supabase) await supabase.auth.signOut(); }
