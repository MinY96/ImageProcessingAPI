import { api } from './client';
import type { EvaluationResultPage, EvaluationRun, EvaluationRunSummary, EvaluationStatus } from './types';
export type { EvaluationStatus } from './types';

export const evaluationsApi = {
  list: (filters: {datasetId?: string; recipeName?: string; status?: EvaluationStatus} = {}) => {
    const p = new URLSearchParams();
    if (filters.datasetId) p.set('dataset_id', filters.datasetId);
    if (filters.recipeName) p.set('recipe_name', filters.recipeName);
    if (filters.status) p.set('status', filters.status);
    const q = p.toString();
    return api<EvaluationRunSummary[]>(`/evaluations${q ? `?${q}` : ''}`);
  },
  create: (body: unknown) => api<{evaluation_id:string; status:EvaluationStatus; progress:{total:number;processed:number;percent:number};created_at:string}>('/evaluations', { method:'POST', body:JSON.stringify(body) }),
  get: (id: string) => api<EvaluationRun>(`/evaluations/${encodeURIComponent(id)}`),
  cancel: (id: string) => api<EvaluationRun>(`/evaluations/${encodeURIComponent(id)}/cancel`, { method:'POST' }),
  results: (id: string, query='') => api<EvaluationResultPage>(`/evaluations/${encodeURIComponent(id)}/results${query}`),
  remove: (id: string) => api<void>(`/evaluations/${encodeURIComponent(id)}`, { method:'DELETE' }),
};
