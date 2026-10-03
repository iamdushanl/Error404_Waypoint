import { apiFetch } from './client';
import type { PlanGenerateInput, PlanGenerateResult } from './types';
export const generatePlan = (body: PlanGenerateInput) => apiFetch<PlanGenerateResult>('/api/v1/planning/generate', { method: 'POST', body: JSON.stringify(body) });
export const getPlan = (id: string) => apiFetch<PlanGenerateResult>(`/api/v1/planning/plans/${id}`);
export const confirmPlan = (id: string) => apiFetch<Record<string, unknown>>(`/api/v1/planning/plans/${id}/confirm`, { method: 'PATCH' });
export interface CapacityOutlookRow { date: string; order_count: number; demand_weight_kg: number; vehicle_count: number; vehicle_capacity_kg: number; reefer_count: number; capacity_gap_kg: number; }
export const getCapacityOutlook = (startDate: string, days = 5) => apiFetch<CapacityOutlookRow[]>(`/api/v1/planning/capacity-outlook?start_date=${startDate}&days=${days}`);
