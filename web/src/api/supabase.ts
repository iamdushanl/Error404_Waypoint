import { createClient } from '@supabase/supabase-js';

const DEFAULT_SUPABASE_URL = 'https://qjhhknmiycfpyozpysxa.supabase.co';
const DEFAULT_SUPABASE_ANON_KEY =
  'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InFqaGhrbm1peWNmcHlvenB5c3hhIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTA5MzU4MDMsImV4cCI6MjEwNjUxMTgwM30.H6FE4Ys_aT5SqDG0NsDNF0luDUATrPLnwCaCwVxqjBg';

const url = (import.meta.env.VITE_SUPABASE_URL as string | undefined) || DEFAULT_SUPABASE_URL;
const key = (import.meta.env.VITE_SUPABASE_ANON_KEY as string | undefined) || DEFAULT_SUPABASE_ANON_KEY;

export const supabase = url && key ? createClient(url, key, { auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true } }) : null;

