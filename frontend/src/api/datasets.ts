import { api } from './client';
export const datasetsApi = {
  list: () => api<unknown[]>('/test-datasets'),
  create: (body: unknown) => api<unknown>('/test-datasets', { method:'POST', body:JSON.stringify(body) }),
  get: (id: string) => api<unknown>(`/test-datasets/${encodeURIComponent(id)}`),
  update: (id: string, body: unknown) => api<unknown>(`/test-datasets/${encodeURIComponent(id)}`, { method:'PUT', body:JSON.stringify(body) }),
  remove: (id: string) => api<void>(`/test-datasets/${encodeURIComponent(id)}`, { method:'DELETE' }),
  importFolder: (id: string, body: unknown) => api<unknown>(`/test-datasets/${encodeURIComponent(id)}/import-folder`, { method:'POST', body:JSON.stringify(body) }),
  listImages: (id: string, query='') => api<unknown[]>(`/test-datasets/${encodeURIComponent(id)}/images${query}`),
  addImages: (id: string, body: unknown) => api<unknown>(`/test-datasets/${encodeURIComponent(id)}/images`, { method:'POST', body:JSON.stringify(body) }),
  updateImage: (id: string, imageId: string, body: unknown) => api<unknown>(`/test-datasets/${encodeURIComponent(id)}/images/${encodeURIComponent(imageId)}`, { method:'PUT', body:JSON.stringify(body) }),
  removeImage: (id: string, imageId: string) => api<void>(`/test-datasets/${encodeURIComponent(id)}/images/${encodeURIComponent(imageId)}`, { method:'DELETE' }),
  batchGroundTruth: (id: string, body: unknown) => api<unknown>(`/test-datasets/${encodeURIComponent(id)}/ground-truth`, { method:'PUT', body:JSON.stringify(body) }),
};
