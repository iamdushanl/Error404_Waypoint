import { apiFetch } from './client';
import type { Paged, Trip, TripWithStops } from './types';
export const listTrips = (params = '') => apiFetch<Paged<Trip>>(`/api/v1/trips${params}`);
export const getTrip = (id: string) => apiFetch<TripWithStops>(`/api/v1/trips/${id}`);
export const acknowledgeTrip = (id: string, role: 'loader' | 'driver') => apiFetch<Trip>(`/api/v1/trips/${id}/acknowledge`, { method: 'PATCH', body: JSON.stringify({ role }) });
export const departTrip = (id: string) => apiFetch<Trip>(`/api/v1/trips/${id}/depart`, { method: 'PATCH' });
export const completeTrip = (id: string) => apiFetch<Trip>(`/api/v1/trips/${id}/complete`, { method: 'PATCH' });
