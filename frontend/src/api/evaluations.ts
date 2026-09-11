import { api } from './client';
export type EvaluationStatus = 'queued'|'running'|'completed'|'failed'|'cancel_requested'|'cancelled';
export const evaluationsApi = {
  list: (query='') => api<unknown[]>(`/evaluations${query}`),
  create: (body: unknown) => api<unknown>('/evaluations', { method:'POST', body:JSON.stringify(body) }),
  get: (id: string) => api<unknown>(`/evaluations/${encodeURIComponent(id)}`),
  cancel: (id: string) => api<unknown>(`/evaluations/${encodeURIComponent(id)}/cancel`, { method:'POST' }),
  results: (id: string, query='') => api<unknown>(`/evaluations/${encodeURIComponent(id)}/results${query}`),
  remove: (id: string) => api<void>(`/evaluations/${encodeURIComponent(id)}`, { method:'DELETE' }),
};
