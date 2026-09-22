import { api, apiMultipart } from './client';
import type { ExecutionResponse, RecipeRecord, RecipeSummary } from './types';

export const recipesApi = {
  list: (query='') => api<RecipeSummary[]>(`/recipes${query}`),
  create: (body: unknown) => api<RecipeRecord>('/recipes', { method:'POST', body:JSON.stringify(body) }),
  clone: (name: string, body: unknown) => api<RecipeRecord>(`/recipes/${encodeURIComponent(name)}/clone`, { method:'POST', body:JSON.stringify(body) }),
  get: (name: string) => api<RecipeRecord>(`/recipes/${encodeURIComponent(name)}`),
  update: (name: string, body: unknown) => api<RecipeRecord>(`/recipes/${encodeURIComponent(name)}`, { method:'PUT', body:JSON.stringify(body) }),
  remove: (name: string, expectedRevision?: number) => api<void>(`/recipes/${encodeURIComponent(name)}${expectedRevision ? `?expected_revision=${expectedRevision}` : ''}`, { method:'DELETE' }),
  execute: (name: string, payload: unknown, files: File[] = [], responseFormat: 'json'|'zip' = 'json') =>
    apiMultipart<ExecutionResponse | Blob>(`/recipes/${encodeURIComponent(name)}/execute?response_format=${responseFormat}`, payload, files),
};
