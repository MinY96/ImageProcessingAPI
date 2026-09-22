import type {
  FeatureSpec,
  GraphNodeSpec,
  GraphRecipeSpec,
  GraphValueReference,
  InputSlotSpec,
  OperationSpec,
  ParameterSpec,
  PipelineSpec,
  PipelineStepSpec,
  PipelineValueReference,
  RecipeRecord,
  RecipeSummary,
  ScalarOperatorSpec,
} from '../../api';

export type RecipeSelection =
  | { type: 'recipe' }
  | { type: 'node'; id: string }
  | { type: 'input'; name: string }
  | { type: 'output'; name: string };

export type PortInfo = { name: string; kind: string; required?: boolean };
export type NodeInterface = { inputs: PortInfo[]; outputs: PortInfo[] };

export type SubrecipeInterface = {
  inputs: PortInfo[];
  outputs: PortInfo[];
  version: string;
  kind: 'linear' | 'graph';
};

export const IMAGE_LIKE_KINDS = new Set(['image', 'mask', 'template']);

export function deepClone<T>(value: T): T {
  return structuredClone(value);
}

export function artifactOf(record: RecipeRecord): PipelineSpec | GraphRecipeSpec {
  const artifact = record.kind === 'linear' ? record.pipeline : record.graph;
  if (!artifact) throw new Error(`Recipe ${record.name} has no ${record.kind} artifact.`);
  return artifact;
}

export function defaultsFromParameters(parameters: Record<string, ParameterSpec>): Record<string, unknown> {
  const result: Record<string, unknown> = {};
  for (const [name, spec] of Object.entries(parameters)) {
    if (spec.default !== undefined && spec.default !== null) result[name] = spec.default;
  }
  return result;
}

export function defaultsFromLooseSchema(parameters: Record<string, Record<string, unknown>>): Record<string, unknown> {
  const result: Record<string, unknown> = {};
  for (const [name, spec] of Object.entries(parameters)) {
    if ('default' in spec) result[name] = spec.default;
  }
  return result;
}

export function uniqueId(base: string, existing: Iterable<string>): string {
  const normalized = base
    .toLowerCase()
    .replace(/[^a-z0-9_]+/g, '_')
    .replace(/^_+|_+$/g, '') || 'node';
  const safe = /^[a-z]/.test(normalized) ? normalized : `n_${normalized}`;
  const used = new Set(existing);
  if (!used.has(safe)) return safe;
  let index = 2;
  while (used.has(`${safe}_${index}`)) index += 1;
  return `${safe}_${index}`;
}

export function createDraftRecipe(input: {
  name: string;
  displayName: string;
  description?: string;
  version?: string;
  kind: 'linear' | 'graph';
  tags?: string[];
}): RecipeRecord {
  const common = {
    name: input.name,
    display_name: input.displayName || input.name,
    description: input.description ?? '',
    version: input.version || '1.0.0',
    inputs: [{ name: 'image', kind: 'image', required: true }] satisfies InputSlotSpec[],
    outputs: {},
  };
  return {
    name: input.name,
    kind: input.kind,
    pipeline: input.kind === 'linear' ? { ...common, steps: [] } : null,
    graph: input.kind === 'graph' ? { ...common, nodes: [] } : null,
    source: 'user',
    readonly: false,
    tags: input.tags ?? [],
    revision: 1,
    created_at: null,
    updated_at: null,
  };
}

export function nodeDisplayName(node: GraphNodeSpec): string {
  return node.operation ?? node.feature ?? node.operator ?? node.recipe ?? node.node_type;
}

export function nodeInterface(
  node: GraphNodeSpec,
  operations: Map<string, OperationSpec>,
  features: Map<string, FeatureSpec>,
  operators: Map<string, ScalarOperatorSpec>,
  subrecipes: Map<string, SubrecipeInterface>,
): NodeInterface {
  if (node.node_type === 'operation' && node.operation) {
    const spec = operations.get(node.operation);
    return {
      inputs: spec?.inputs.map((item) => ({ name: item.name, kind: item.kind, required: item.required })) ?? [],
      outputs: spec?.outputs.map((item) => ({ name: item.name, kind: item.kind })) ?? [],
    };
  }
  if (node.node_type === 'feature' && node.feature) {
    const spec = features.get(node.feature);
    return {
      inputs: spec?.inputs.map((item) => ({ name: item.name, kind: item.kind, required: item.required })) ?? [],
      outputs: spec?.outputs.map((item) => ({ name: item.name, kind: item.kind })) ?? [],
    };
  }
  if (node.node_type === 'scalar_operator' && node.operator) {
    const spec = operators.get(node.operator);
    const current = Object.keys(node.inputs ?? {});
    const names = [...new Set([...(spec?.required_input_names ?? []), ...current])];
    if (!names.length) names.push('value');
    return {
      inputs: names.map((name) => ({ name, kind: 'scalar', required: spec?.required_input_names.includes(name) ?? false })),
      outputs: [{ name: 'value', kind: 'scalar' }],
    };
  }
  if (node.node_type === 'roi_crop') {
    return { inputs: [{ name: 'image', kind: 'image', required: true }], outputs: [{ name: 'image', kind: 'image' }, { name: 'region', kind: 'roi' }] };
  }
  if (node.node_type === 'roi_compose') {
    return {
      inputs: [
        { name: 'base', kind: 'image', required: true },
        { name: 'patch', kind: 'image', required: true },
        { name: 'region', kind: 'roi', required: true },
      ],
      outputs: [{ name: 'image', kind: 'image' }],
    };
  }
  if (node.node_type === 'decision') {
    return {
      inputs: [{ name: 'value', kind: 'scalar', required: true }],
      outputs: [{ name: 'value', kind: 'scalar' }, { name: 'passed', kind: 'boolean' }, { name: 'label', kind: 'decision' }],
    };
  }
  if (node.node_type === 'subrecipe' && node.recipe) {
    return subrecipes.get(node.recipe) ?? {
      inputs: Object.keys(node.inputs ?? {}).map((name) => ({ name, kind: 'unknown' })),
      outputs: [{ name: 'output', kind: 'unknown' }],
    };
  }
  return { inputs: [], outputs: [] };
}

export function pipelineStepInterface(step: PipelineStepSpec, operations: Map<string, OperationSpec>): NodeInterface {
  const spec = operations.get(step.operation);
  return {
    inputs: spec?.inputs.map((item) => ({ name: item.name, kind: item.kind, required: item.required })) ?? [],
    outputs: spec?.outputs.map((item) => ({ name: item.name, kind: item.kind })) ?? [],
  };
}

export function kindsCompatible(source: string, target: string): boolean {
  if (!source || !target || source === 'unknown' || target === 'unknown') return true;
  if (source === target) return true;
  if (IMAGE_LIKE_KINDS.has(source) && IMAGE_LIKE_KINDS.has(target)) {
    if (target === 'image') return true;
    return source === target || source === 'mask';
  }
  if (source === 'profile' && target === 'array') return true;
  return false;
}

export function formatReference(reference?: PipelineValueReference | GraphValueReference): string {
  if (!reference) return 'Not connected';
  if (reference.type === 'pipeline_input' || reference.type === 'graph_input') return `Input · ${reference.input_name}`;
  if (reference.type === 'step_output') return `${reference.step_id}.${reference.output_name}`;
  return `${reference.node_id}.${reference.output_name}`;
}

export function parseTags(value: string): string[] {
  return [...new Set(value.split(',').map((item) => item.trim()).filter(Boolean))].sort();
}

export function recipeInputKinds(kind: 'linear' | 'graph'): string[] {
  return kind === 'linear'
    ? ['image', 'mask', 'template', 'markers', 'contours', 'points', 'array', 'model']
    : ['image', 'mask', 'template', 'array', 'contours', 'metrics', 'scalar', 'profile', 'roi', 'roi_set', 'boolean', 'decision'];
}

export function subrecipeInterfaceFromRecord(record: RecipeRecord): SubrecipeInterface {
  const artifact = artifactOf(record);
  const outputs = Object.keys(artifact.outputs).map((name) => ({ name, kind: 'unknown' }));
  return {
    inputs: artifact.inputs.map((item) => ({ name: item.name, kind: item.kind, required: item.required })),
    outputs,
    version: artifact.version,
    kind: record.kind,
  };
}

export function graphSourceOptions(
  graph: GraphRecipeSpec,
  targetNodeId: string,
  targetKind: string,
  operations: Map<string, OperationSpec>,
  features: Map<string, FeatureSpec>,
  operators: Map<string, ScalarOperatorSpec>,
  subrecipes: Map<string, SubrecipeInterface>,
): Array<{ key: string; label: string; kind: string; reference: GraphValueReference }> {
  const options: Array<{ key: string; label: string; kind: string; reference: GraphValueReference }> = [];
  for (const input of graph.inputs) {
    if (kindsCompatible(input.kind, targetKind)) {
      options.push({ key: `input:${input.name}`, label: `Input · ${input.name} (${input.kind})`, kind: input.kind, reference: { type: 'graph_input', input_name: input.name } });
    }
  }
  for (const node of graph.nodes) {
    if (node.id === targetNodeId) continue;
    const iface = nodeInterface(node, operations, features, operators, subrecipes);
    for (const output of iface.outputs) {
      if (kindsCompatible(output.kind, targetKind)) {
        options.push({
          key: `node:${node.id}:${output.name}`,
          label: `${node.id}.${output.name} (${output.kind})`,
          kind: output.kind,
          reference: { type: 'node_output', node_id: node.id, output_name: output.name },
        });
      }
    }
  }
  return options;
}

export function linearSourceOptions(
  pipeline: PipelineSpec,
  targetStepIndex: number,
  targetKind: string,
  operations: Map<string, OperationSpec>,
): Array<{ key: string; label: string; kind: string; reference: PipelineValueReference }> {
  const options: Array<{ key: string; label: string; kind: string; reference: PipelineValueReference }> = [];
  for (const input of pipeline.inputs) {
    if (kindsCompatible(input.kind, targetKind)) {
      options.push({ key: `input:${input.name}`, label: `Input · ${input.name} (${input.kind})`, kind: input.kind, reference: { type: 'pipeline_input', input_name: input.name } });
    }
  }
  for (const step of pipeline.steps.slice(0, targetStepIndex)) {
    const iface = pipelineStepInterface(step, operations);
    for (const output of iface.outputs) {
      if (kindsCompatible(output.kind, targetKind)) {
        options.push({
          key: `step:${step.id}:${output.name}`,
          label: `${step.id}.${output.name} (${output.kind})`,
          kind: output.kind,
          reference: { type: 'step_output', step_id: step.id, output_name: output.name },
        });
      }
    }
  }
  return options;
}

export function autoBindLinearStep(step: PipelineStepSpec, pipeline: PipelineSpec, operations: Map<string, OperationSpec>): PipelineStepSpec {
  const spec = operations.get(step.operation);
  if (!spec) return step;
  const stepIndex = pipeline.steps.length;
  const inputs: Record<string, PipelineValueReference> = {};
  for (const slot of spec.inputs) {
    const options = linearSourceOptions(pipeline, stepIndex, slot.kind, operations);
    if (options.length) inputs[slot.name] = options[options.length - 1].reference;
  }
  return { ...step, inputs };
}

export function defaultGraphNode(kind: string, target: string, record: RecipeRecord, specs?: {
  operation?: OperationSpec;
  feature?: FeatureSpec;
  operator?: ScalarOperatorSpec;
  recipe?: RecipeSummary;
}): GraphNodeSpec {
  const existing = record.graph?.nodes.map((item) => item.id) ?? [];
  if (kind === 'operation' && specs?.operation) {
    return {
      id: uniqueId(specs.operation.name, existing), node_type: 'operation', operation: specs.operation.name,
      inputs: {}, params: defaultsFromParameters(specs.operation.parameters),
    };
  }
  if (kind === 'feature' && specs?.feature) {
    return {
      id: uniqueId(specs.feature.name, existing), node_type: 'feature', feature: specs.feature.name,
      inputs: {}, params: defaultsFromParameters(specs.feature.parameters),
    };
  }
  if (kind === 'scalar_operator' && specs?.operator) {
    return {
      id: uniqueId(specs.operator.name, existing), node_type: 'scalar_operator', operator: specs.operator.name,
      inputs: {}, params: defaultsFromLooseSchema(specs.operator.parameters),
    };
  }
  if (kind === 'roi_crop') return { id: uniqueId('roi_crop', existing), node_type: 'roi_crop', inputs: {}, params: { coordinate_mode: 'relative', x: 0, y: 0, width: 0.5, height: 0.5, clamp: true } };
  if (kind === 'roi_compose') return { id: uniqueId('roi_compose', existing), node_type: 'roi_compose', inputs: {}, params: {} };
  if (kind === 'decision') return { id: uniqueId('decision', existing), node_type: 'decision', inputs: {}, params: { operator: 'gt', threshold: 0, pass_label: 'OK', fail_label: 'NG' } };
  if (kind === 'subrecipe' && specs?.recipe) {
    return {
      id: uniqueId(specs.recipe.name, existing), node_type: 'subrecipe', recipe: specs.recipe.name,
      recipe_kind: specs.recipe.kind, recipe_version: specs.recipe.version, inputs: {}, params: {},
    };
  }
  return { id: uniqueId(target || kind, existing), node_type: kind, inputs: {}, params: {} };
}

export function removeGraphNode(record: RecipeRecord, nodeId: string): RecipeRecord {
  if (!record.graph) return record;
  const next = deepClone(record);
  next.graph!.nodes = next.graph!.nodes.filter((node) => node.id !== nodeId);
  for (const node of next.graph!.nodes) {
    node.inputs = Object.fromEntries(Object.entries(node.inputs ?? {}).filter(([, ref]) => !(ref.type === 'node_output' && ref.node_id === nodeId)));
  }
  next.graph!.outputs = Object.fromEntries(Object.entries(next.graph!.outputs).filter(([, ref]) => !(ref.type === 'node_output' && ref.node_id === nodeId)));
  return next;
}

export function removeLinearStep(record: RecipeRecord, stepId: string): RecipeRecord {
  if (!record.pipeline) return record;
  const next = deepClone(record);
  next.pipeline!.steps = next.pipeline!.steps.filter((step) => step.id !== stepId);
  for (const step of next.pipeline!.steps) {
    step.inputs = Object.fromEntries(Object.entries(step.inputs ?? {}).filter(([, ref]) => !(ref.type === 'step_output' && ref.step_id === stepId)));
  }
  next.pipeline!.outputs = Object.fromEntries(Object.entries(next.pipeline!.outputs).filter(([, ref]) => !(ref.type === 'step_output' && ref.step_id === stepId)));
  return next;
}

export function cleanupLinearOrder(record: RecipeRecord): RecipeRecord {
  if (!record.pipeline) return record;
  const next = deepClone(record);
  const position = new Map(next.pipeline!.steps.map((step, index) => [step.id, index]));
  next.pipeline!.steps.forEach((step, index) => {
    step.inputs = Object.fromEntries(Object.entries(step.inputs ?? {}).filter(([, ref]) => {
      if (ref.type !== 'step_output') return true;
      return (position.get(ref.step_id) ?? Number.MAX_SAFE_INTEGER) < index;
    }));
  });
  return next;
}
