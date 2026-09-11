import { api, apiMultipart } from './client';
export const workflowApi = {
  features: () => api<unknown[]>('/workflow/features'),
  operators: () => api<unknown[]>('/workflow/operators'),
  validate: (body: unknown) => api<unknown>('/workflow/validate', { method:'POST', body:JSON.stringify(body) }),
  execute: (payload: unknown, files: File[] = [], responseFormat: 'json'|'zip' = 'json') =>
    apiMultipart<unknown>(`/workflow/execute?response_format=${responseFormat}`, payload, files),
};
