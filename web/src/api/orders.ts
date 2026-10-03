import { apiFetch } from './client';
import type { Order, OrderCreateInput, Paged } from './types';
export const listOrders = (params = '') => apiFetch<Paged<Order>>(`/api/v1/orders${params}`);
export const createOrder = (body: OrderCreateInput) => apiFetch<Order>('/api/v1/orders', { method: 'POST', body: JSON.stringify(body) });
export const submitOrder = (id: string) => apiFetch<Order>(`/api/v1/orders/${id}/submit`, { method: 'POST' });
export const updateOrderStatus = (id: string, status: string, notes?: string) => apiFetch<Order>(`/api/v1/orders/${id}/status`, { method: 'PATCH', body: JSON.stringify({ status, notes }) });
