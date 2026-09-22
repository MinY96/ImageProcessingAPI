import { api, apiMultipart } from './client';
import type { ExecutionResponse, OperationSpec } from './types';

export const operationsApi = {
  list: () => api<OperationSpec[]>('/operations'),
  get: (operation: string) => api<OperationSpec>(`/operations/${encodeURIComponent(operation)}`),
  execute: (operation: string, payload: unknown, files: File[] = [], responseFormat: 'json'|'zip' = 'json') =>
    apiMultipart<ExecutionResponse | Blob>(`/operations/${encodeURIComponent(operation)}/execute?response_format=${responseFormat}`, payload, files),
};
