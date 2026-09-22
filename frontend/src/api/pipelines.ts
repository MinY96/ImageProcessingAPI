import { api, apiMultipart } from './client';
import type { ExecutionResponse, PipelineSpec } from './types';

export const pipelinesApi = {
  list: () => api<PipelineSpec[]>('/pipelines'),
  get: (name: string) => api<PipelineSpec>(`/pipelines/${encodeURIComponent(name)}`),
  validate: (body: PipelineSpec) => api<{valid:boolean; pipeline:string; registry_revision?:number|null; output_names:string[]; error?:unknown}>('/pipelines/validate', { method:'POST', body:JSON.stringify(body) }),
  executeDraft: (payload: unknown, files: File[] = [], responseFormat: 'json'|'zip' = 'json') =>
    apiMultipart<ExecutionResponse | Blob>(`/pipelines/execute?response_format=${responseFormat}`, payload, files),
  execute: (name: string, payload: unknown, files: File[] = [], responseFormat: 'json'|'zip' = 'json') =>
    apiMultipart<ExecutionResponse | Blob>(`/pipelines/${encodeURIComponent(name)}/execute?response_format=${responseFormat}`, payload, files),
};
