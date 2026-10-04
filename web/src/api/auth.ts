import { apiFetch } from './client';
import { supabase } from './supabase';
import type { UserProfile } from './types';

export async function signInWithPassword(email: string, password: string) {
  if (!supabase) throw new Error('Supabase Auth is not configured.');
  const result = await supabase.auth.signInWithPassword({ email, password });
  if (result.error) throw result.error;
  return result.data;
}

export async function signOut() {
  await supabase?.auth.signOut();
}

export async function getCurrentUser() {
  return apiFetch<UserProfile>('/api/v1/auth/me');
}
