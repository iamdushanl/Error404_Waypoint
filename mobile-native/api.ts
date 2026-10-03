import AsyncStorage from '@react-native-async-storage/async-storage';
import { createClient } from '@supabase/supabase-js';

const API_BASE = (process.env.EXPO_PUBLIC_API_BASE_URL || 'http://localhost:8000').replace(/\/$/, '');
const url = process.env.EXPO_PUBLIC_SUPABASE_URL;
const key = process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY;
export const supabase = url && key ? createClient(url, key, { auth: { persistSession: true, autoRefreshToken: true } }) : null;
const QUEUE_KEY = 'waypoint.driver.sync-queue.v1';
export async function apiFetch<T>(path: string, options: RequestInit = {}) { const session = (await supabase?.auth.getSession())?.data.session; if (!session?.access_token) throw new Error('Driver authentication is required.'); const response = await fetch(`${API_BASE}${path}`, { ...options, headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${session.access_token}`, ...options.headers } }); if (!response.ok) throw new Error(`Request failed (${response.status})`); return response.json() as Promise<T>; }
export const sendOtp = (contact: string) => { if (!supabase) throw new Error('Native Supabase configuration is missing.'); return supabase.auth.signInWithOtp(contact.startsWith('+') ? { phone: contact } : { email: contact }); };
export const verifyOtp = (contact: string, token: string) => { if (!supabase) throw new Error('Native Supabase configuration is missing.'); return supabase.auth.verifyOtp(contact.startsWith('+') ? { phone: contact, token, type: 'sms' } : { email: contact, token, type: 'email' }); };
export async function enqueue(operation: Record<string, unknown>) { const current = JSON.parse((await AsyncStorage.getItem(QUEUE_KEY)) || '[]'); await AsyncStorage.setItem(QUEUE_KEY, JSON.stringify([...current, operation])); }
export async function syncQueue() { const current = JSON.parse((await AsyncStorage.getItem(QUEUE_KEY)) || '[]'); if (!current.length) return { applied_count: 0, failed_count: 0 }; const result = await apiFetch<{ results: Array<{ operation_id: string; status: string }>; applied_count: number; failed_count: number }>('/api/v1/sync', { method: 'POST', body: JSON.stringify({ operations: current }) }); const failed = new Set(result.results.filter(item => item.status === 'failed').map(item => item.operation_id)); await AsyncStorage.setItem(QUEUE_KEY, JSON.stringify(current.filter((item: { operation_id: string }) => failed.has(item.operation_id)))); return result; }
