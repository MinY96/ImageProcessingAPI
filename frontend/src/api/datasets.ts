import { api } from './client';
import type { TestDatasetImagePage, TestDatasetSummary } from './types';

export const datasetsApi = {
  list: (query='') => api<TestDatasetSummary[]>(`/test-datasets${query}`),
  create: (body: unknown) => api<unknown>('/test-datasets', { method:'POST', body:JSON.stringify(body) }),
  get: (id: string) => api<TestDatasetSummary>(`/test-datasets/${encodeURIComponent(id)}`),
  update: (id: string, body: unknown) => api<unknown>(`/test-datasets/${encodeURIComponent(id)}`, { method:'PUT', body:JSON.stringify(body) }),
  remove: (id: string, expectedRevision?: number) => api<void>(`/test-datasets/${encodeURIComponent(id)}${expectedRevision ? `?expected_revision=${expectedRevision}` : ''}`, { method:'DELETE' }),
  importFolder: (id: string, body: unknown) => api<unknown>(`/test-datasets/${encodeURIComponent(id)}/import-folder`, { method:'POST', body:JSON.stringify(body) }),
  listImages: (id: string, query='') => api<TestDatasetImagePage>(`/test-datasets/${encodeURIComponent(id)}/images${query}`),
  addImages: (id: string, body: unknown) => api<unknown>(`/test-datasets/${encodeURIComponent(id)}/images`, { method:'POST', body:JSON.stringify(body) }),
  updateImage: (id: string, imageId: string, body: unknown) => api<unknown>(`/test-datasets/${encodeURIComponent(id)}/images/${encodeURIComponent(imageId)}`, { method:'PUT', body:JSON.stringify(body) }),
  removeImage: (id: string, imageId: string, expectedRevision?: number) => api<unknown>(`/test-datasets/${encodeURIComponent(id)}/images/${encodeURIComponent(imageId)}${expectedRevision ? `?expected_revision=${expectedRevision}` : ''}`, { method:'DELETE' }),
  batchGroundTruth: (id: string, body: unknown) => api<unknown>(`/test-datasets/${encodeURIComponent(id)}/ground-truth`, { method:'PUT', body:JSON.stringify(body) }),
};
