import { api, apiMultipart } from './client';
import type { ExecutionResponse, FeatureSpec, GraphRecipeSpec, ScalarOperatorSpec } from './types';

export type WorkflowValidationResponse = {
  valid: boolean;
  recipe?: string;
  registry_revision?: number | null;
  output_names?: string[];
  execution_order?: string[];
  error?: unknown;
};

export const workflowApi = {
  features: () => api<FeatureSpec[]>('/workflow/features'),
  operators: () => api<ScalarOperatorSpec[]>('/workflow/operators'),
  validate: (body: GraphRecipeSpec) => api<WorkflowValidationResponse>('/workflow/validate', { method:'POST', body:JSON.stringify(body) }),
  execute: (payload: unknown, files: File[] = [], responseFormat: 'json'|'zip' = 'json') =>
    apiMultipart<ExecutionResponse | Blob>(`/workflow/execute?response_format=${responseFormat}`, payload, files),
};
