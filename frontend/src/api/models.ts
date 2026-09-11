import { api } from './client';
export const modelsApi = {
  list: () => api<unknown[]>('/models'),
  get: (modelId: string, version: string) => api<unknown>(`/models/${encodeURIComponent(modelId)}/${encodeURIComponent(version)}`),
};
