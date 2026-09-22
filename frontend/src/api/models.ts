import { api } from './client';
import type { ModelSpec } from './types';
export const modelsApi = {
  list: () => api<ModelSpec[]>('/models'),
  get: (modelId: string, version: string) => api<ModelSpec>(`/models/${encodeURIComponent(modelId)}/${encodeURIComponent(version)}`),
};
