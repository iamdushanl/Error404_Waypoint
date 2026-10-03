import { apiFetch } from './client';
import type { SyncOperation, SyncResponse } from './types';
export const syncOperations = (operations: SyncOperation[]) => apiFetch<SyncResponse>('/api/v1/sync', { method: 'POST', body: JSON.stringify({ operations }) });
