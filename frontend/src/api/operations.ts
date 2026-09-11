import { api, apiMultipart } from './client';
export const operationsApi = {
  list: () => api<unknown[]>('/operations'),
  get: (operation: string) => api<unknown>(`/operations/${encodeURIComponent(operation)}`),
  execute: (operation: string, payload: unknown, files: File[] = [], responseFormat: 'json'|'zip' = 'json') =>
    apiMultipart<unknown>(`/operations/${encodeURIComponent(operation)}/execute?response_format=${responseFormat}`, payload, files),
};
