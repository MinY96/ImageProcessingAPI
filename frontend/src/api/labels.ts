import { api } from './client';
import type { LabelClassSummary, LabelDocument, LabelListResponse } from './types';

export const labelsApi = {
  list: (query='') => api<LabelListResponse>(`/labels${query}`),
  create: (body: unknown) => api<LabelDocument>('/labels', { method:'POST', body:JSON.stringify(body) }),
  classes: () => api<LabelClassSummary[]>('/labels/classes'),
  get: (imageId: string) => api<LabelDocument>(`/labels/${encodeURIComponent(imageId)}`),
  update: (imageId: string, body: unknown) => api<LabelDocument>(`/labels/${encodeURIComponent(imageId)}`, { method:'PUT', body:JSON.stringify(body) }),
  remove: (imageId: string, expectedRevision?: number) => api<void>(`/labels/${encodeURIComponent(imageId)}${expectedRevision ? `?expected_revision=${expectedRevision}` : ''}`, { method:'DELETE' }),
  addAnnotation: (imageId: string, body: unknown) => api<LabelDocument>(`/labels/${encodeURIComponent(imageId)}/annotations`, { method:'POST', body:JSON.stringify(body) }),
  updateAnnotation: (imageId: string, annotationId: string, body: unknown) => api<LabelDocument>(`/labels/${encodeURIComponent(imageId)}/annotations/${encodeURIComponent(annotationId)}`, { method:'PUT', body:JSON.stringify(body) }),
  removeAnnotation: (imageId: string, annotationId: string, expectedRevision?: number) => api<LabelDocument>(`/labels/${encodeURIComponent(imageId)}/annotations/${encodeURIComponent(annotationId)}${expectedRevision ? `?expected_revision=${expectedRevision}` : ''}`, { method:'DELETE' }),
};
