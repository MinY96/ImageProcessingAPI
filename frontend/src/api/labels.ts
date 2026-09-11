import { api } from './client';
export const labelsApi = {
  list: (query='') => api<unknown[]>(`/labels${query}`),
  create: (body: unknown) => api<unknown>('/labels', { method:'POST', body:JSON.stringify(body) }),
  classes: () => api<unknown[]>('/labels/classes'),
  get: (imageId: string) => api<unknown>(`/labels/${encodeURIComponent(imageId)}`),
  update: (imageId: string, body: unknown) => api<unknown>(`/labels/${encodeURIComponent(imageId)}`, { method:'PUT', body:JSON.stringify(body) }),
  remove: (imageId: string) => api<void>(`/labels/${encodeURIComponent(imageId)}`, { method:'DELETE' }),
  addAnnotation: (imageId: string, body: unknown) => api<unknown>(`/labels/${encodeURIComponent(imageId)}/annotations`, { method:'POST', body:JSON.stringify(body) }),
  updateAnnotation: (imageId: string, annotationId: string, body: unknown) => api<unknown>(`/labels/${encodeURIComponent(imageId)}/annotations/${encodeURIComponent(annotationId)}`, { method:'PUT', body:JSON.stringify(body) }),
  removeAnnotation: (imageId: string, annotationId: string) => api<void>(`/labels/${encodeURIComponent(imageId)}/annotations/${encodeURIComponent(annotationId)}`, { method:'DELETE' }),
};
