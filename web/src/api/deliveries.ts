import { apiFetch } from './client';
import type { Delivery, DeliveryOutcome } from './types';
export const recordDelivery = (body: { trip_stop_id: string; outcome: DeliveryOutcome; recipient_name?: string; notes?: string; delivered_at?: string; offline_operation_id?: string }) => apiFetch<Delivery>('/api/v1/deliveries', { method: 'POST', body: JSON.stringify(body) });
export const recordPod = (id: string, body: { recipient_name: string; photo_url?: string; recipient_signature_url?: string; recorded_at: string }) => apiFetch(`/api/v1/deliveries/${id}/pod`, { method: 'POST', body: JSON.stringify(body) });
export const confirmReceipt = (id: string, body: { items_received: Record<string, number>; issues_noted?: string }) => apiFetch(`/api/v1/deliveries/${id}/confirm`, { method: 'POST', body: JSON.stringify(body) });
export const listOutletDeliveries = (outletId: string) => apiFetch<Delivery[]>(`/api/v1/outlets/${outletId}/deliveries`);
export const recordShortfall = (tripId: string, stopId: string, body: { issue_type: 'missing' | 'damaged' | 'wrong_item'; sku: string; description: string; expected_quantity: number; actual_quantity: number; photo_url?: string; notes?: string }) => apiFetch(`/api/v1/trips/${tripId}/stops/${stopId}/shortfalls`, { method: 'POST', body: JSON.stringify(body) });
