import { apiMultipart } from './client';
export const analysisApi = {
  analyzeImage: (payload: unknown, file: File) => apiMultipart<unknown>('/analysis/image', payload, [file], 'file'),
};
