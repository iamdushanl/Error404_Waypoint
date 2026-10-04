import { apiFetch } from './client';
import { supabase } from './supabase';
import type { BackendRole, UserProfile } from './types';

export function detectRoleFromEmail(email: string): BackendRole {
  const norm = email.trim().toLowerCase();
  if (norm.includes('loader')) return 'loader';
  if (norm.includes('dispatcher') || norm.includes('dispatch')) return 'dispatcher';
  if (norm.includes('driver')) return 'driver';
  if (norm.includes('store') || norm.includes('manager') || norm.includes('outlet')) return 'store_manager';
  return 'store_manager';
}

export interface RoleMeta {
  role: BackendRole;
  displayTitle: string;
  icon: string;
  badgeTone: 'cyan' | 'amber' | 'emerald' | 'blue';
  tagline: string;
  description: string;
  assignment: string;
  screens: string[];
}

export function getRoleMeta(role: BackendRole): RoleMeta {
  switch (role) {
    case 'dispatcher':
      return {
        role: 'dispatcher',
        displayTitle: 'Dispatcher',
        icon: '◈',
        badgeTone: 'cyan',
        tagline: 'Control Tower',
        description: 'Multi-depot route optimization, constraint solving & delivery tracking',
        assignment: 'Central Operations · Peliyagoda & Kandy',
        screens: ['Order queue', 'Plan & allocate', 'Live delivery board', 'Capacity outlook'],
      };
    case 'loader':
      return {
        role: 'loader',
        displayTitle: 'Loader',
        icon: '▤',
        badgeTone: 'amber',
        tagline: 'Depot Loading Bay',
        description: 'Reverse-unload pallet sequencing, crate tally & shortfall reporting',
        assignment: 'Depot Loading Bay · Peliyagoda',
        screens: ['Load list', 'Flag shortfall', 'Plan changed'],
      };
    case 'driver':
      return {
        role: 'driver',
        displayTitle: 'Driver',
        icon: '◉',
        badgeTone: 'blue',
        tagline: 'Fleet Operations',
        description: 'Delivery execution, offline signature capture & proof of delivery',
        assignment: 'Vehicle WP-CAB-9241 · Kandy Corridor',
        screens: ['Delivery route', 'Stop execution', 'Offline sync'],
      };
    case 'store_manager':
    default:
      return {
        role: 'store_manager',
        displayTitle: 'Store Manager',
        icon: '＋',
        badgeTone: 'emerald',
        tagline: 'Retail Store Outlet',
        description: 'Next-day order placement, cutoff management & receipt confirmation',
        assignment: 'Assigned Outlet OUT001 · Highland Mart',
        screens: ['Place order', 'Confirmed order', 'Deferral notice', 'Confirm receipt'],
      };
  }
}

export async function signInWithPassword(email: string, password: string) {
  if (!supabase) throw new Error('Supabase Auth is not configured.');
  const result = await supabase.auth.signInWithPassword({ email, password });
  if (result.error) throw result.error;
  return result.data;
}

export async function signUpWithPassword(email: string, password: string, fullName: string) {
  if (!supabase) throw new Error('Supabase Auth is not configured.');
  const role = detectRoleFromEmail(email);

  const result = await supabase.auth.signUp({
    email,
    password,
    options: {
      data: {
        full_name: fullName,
        role,
      },
    },
  });
  if (result.error) throw result.error;

  // If user profile can be created or if session returned immediately
  if (result.data.session && result.data.user) {
    try {
      await supabase.from('users').upsert({
        id: result.data.user.id,
        email: result.data.user.email ?? email,
        full_name: fullName,
        role,
        outlet_id: role === 'store_manager' ? 'OUT001' : null,
        depot: role === 'loader' || role === 'driver' || role === 'dispatcher' ? 'Peliyagoda' : null,
        vehicle_id: null,
      });
    } catch {
      // Backend auto-provisions user profile via service-role token
    }
  } else if (!result.data.session) {
    // Attempt automatic login if confirmation is disabled
    try {
      const login = await supabase.auth.signInWithPassword({ email, password });
      if (login.data.session) {
        return login.data;
      }
    } catch {
      // Email confirmation may be required by Supabase project settings
    }
  }

  return result.data;
}

export async function signOut() {
  await supabase?.auth.signOut();
}

export async function getCurrentUser(): Promise<UserProfile> {
  try {
    return await apiFetch<UserProfile>('/api/v1/auth/me');
  } catch (err) {
    if (supabase) {
      const { data } = await supabase.auth.getSession();
      const user = data.session?.user;
      if (user?.email) {
        const role = (user.user_metadata?.role as BackendRole) || detectRoleFromEmail(user.email);
        return {
          id: user.id,
          email: user.email,
          full_name: (user.user_metadata?.full_name as string) || (user.email.split('@')[0].toUpperCase()),
          role,
          outlet_id: role === 'store_manager' ? 'OUT001' : null,
          depot: role === 'store_manager' ? null : 'Peliyagoda',
          vehicle_id: role === 'driver' ? 'WP-CAB-9241' : null,
        };
      }
    }
    throw err;
  }
}


