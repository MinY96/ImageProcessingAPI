import { api, apiMultipart } from './client';
export const pipelinesApi = {
  list: () => api<unknown[]>('/pipelines'),
  get: (name: string) => api<unknown>(`/pipelines/${encodeURIComponent(name)}`),
  validate: (body: unknown) => api<unknown>('/pipelines/validate', { method:'POST', body:JSON.stringify(body) }),
  executeDraft: (payload: unknown, files: File[] = [], responseFormat: 'json'|'zip' = 'json') =>
    apiMultipart<unknown>(`/pipelines/execute?response_format=${responseFormat}`, payload, files),
  execute: (name: string, payload: unknown, files: File[] = [], responseFormat: 'json'|'zip' = 'json') =>
    apiMultipart<unknown>(`/pipelines/${encodeURIComponent(name)}/execute?response_format=${responseFormat}`, payload, files),
};
