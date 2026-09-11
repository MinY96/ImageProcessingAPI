import { api, apiMultipart } from './client';
export const recipesApi = {
  list: () => api<unknown[]>('/recipes'),
  create: (body: unknown) => api<unknown>('/recipes', { method:'POST', body:JSON.stringify(body) }),
  clone: (name: string, body: unknown) => api<unknown>(`/recipes/${encodeURIComponent(name)}/clone`, { method:'POST', body:JSON.stringify(body) }),
  get: (name: string) => api<unknown>(`/recipes/${encodeURIComponent(name)}`),
  update: (name: string, body: unknown) => api<unknown>(`/recipes/${encodeURIComponent(name)}`, { method:'PUT', body:JSON.stringify(body) }),
  remove: (name: string, expectedRevision?: number) => api<void>(`/recipes/${encodeURIComponent(name)}${expectedRevision ? `?expected_revision=${expectedRevision}` : ''}`, { method:'DELETE' }),
  execute: (name: string, payload: unknown, files: File[] = [], responseFormat: 'json'|'zip' = 'json') =>
    apiMultipart<unknown>(`/recipes/${encodeURIComponent(name)}/execute?response_format=${responseFormat}`, payload, files),
};
