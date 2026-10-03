import { apiFetch } from './client';
import { supabase } from './supabase';
import type { UserProfile } from './types';
export async function signInWithOtp(emailOrPhone: string) { if (!supabase) throw new Error('Supabase Auth is not configured.'); const isPhone = /^\+?[0-9 ()-]{7,}$/.test(emailOrPhone); const result = isPhone ? await supabase.auth.signInWithOtp({ phone: emailOrPhone }) : await supabase.auth.signInWithOtp({ email: emailOrPhone }); if (result.error) throw result.error; return result.data; }
export async function verifyOtp(emailOrPhone: string, token: string) { if (!supabase) throw new Error('Supabase Auth is not configured.'); const isPhone = /^\+?[0-9 ()-]{7,}$/.test(emailOrPhone); const result = isPhone ? await supabase.auth.verifyOtp({ phone: emailOrPhone, token, type: 'sms' }) : await supabase.auth.verifyOtp({ email: emailOrPhone, token, type: 'email' }); if (result.error) throw result.error; return result.data; }
export async function signInWithGoogle() { if (!supabase) throw new Error('Supabase Auth is not configured.'); const { error } = await supabase.auth.signInWithOAuth({ provider: 'google', options: { redirectTo: window.location.origin } }); if (error) throw error; }
export async function signOut() { await supabase?.auth.signOut(); }
export async function getCurrentUser() { return apiFetch<UserProfile>('/api/v1/auth/me'); }
