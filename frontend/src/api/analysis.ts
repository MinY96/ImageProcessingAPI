import { apiMultipart } from './client';
import type { ImageAnalysisResult } from './types';

export const analysisApi = {
  analyzeImage: (payload: unknown, file: File) => apiMultipart<ImageAnalysisResult>('/analysis/image', payload, [file], 'file'),
};
