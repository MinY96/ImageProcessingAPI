import { useMemo, useState } from 'react';

import type {
  FeatureSpec,
  GraphNodeSpec,
  JsonMap,
  OperationSpec,
  PipelineStepSpec,
  RecipeRecord,
  RecipeSummary,
  ScalarOperatorSpec,
} from '../../api';
import { Button, EmptyState, Field, Panel, Tabs } from '../../components/ui';
import type { LibrarySelection } from './LibraryPanel';
import { LooseParameterEditor, ParameterEditor } from './ParameterEditor';
import {
  artifactOf,
  cleanupLinearOrder,
  deepClone,
  formatReference,
  graphSourceOptions,
  linearSourceOptions,
  nodeDisplayName,
  nodeInterface,
  parseTags,
  pipelineStepInterface,
  recipeInputKinds,
  removeGraphNode,
  removeLinearStep,
  type RecipeSelection,
  type SubrecipeInterface,
} from './editor';

function updateParams(params: JsonMap | undefined, name: string, value: unknown): JsonMap {
  const next = { ...(params ?? {}) };
  if (value === '') delete next[name];
  else next[name] = value;
  return next;
}

function NodeHeader({ id, target }: { id: string; target: string }) {
  return <div className="inspector-node-header"><strong>{id}</strong><span>{target}</span></div>;
}

export function InspectorPanel({
  record,
  selection,
  librarySelection,
  operations,
  features,
  operators,
  recipes,
  subrecipes,
  onChange,
  onSelectionChange,
}: {
  record: RecipeRecord | null;
  selection: RecipeSelection;
  librarySelection: LibrarySelection;
  operations: Map<string, OperationSpec>;
  features: Map<string, FeatureSpec>;
  operators: Map<string, ScalarOperatorSpec>;
  recipes: RecipeSummary[];
  subrecipes: Map<string, SubrecipeInterface>;
  onChange: (record: RecipeRecord) => void;
  onSelectionChange: (selection: RecipeSelection) => void;
}) {
  const [tab, setTab] = useState('Edit');
  const [newInputName, setNewInputName] = useState('');
  const [newInputKind, setNewInputKind] = useState('image');
  const [dynamicInputName, setDynamicInputName] = useState('');
  const [dynamicInputSource, setDynamicInputSource] = useState('');

  const disabled = !record || record.readonly;
  const artifact = record ? artifactOf(record) : null;

  const change = (mutate: (draft: RecipeRecord) => void) => {
    if (!record || record.readonly) return;
    const next = deepClone(record); mutate(next); onChange(next);
  };

  const exposeGraphOutput = (nodeId: string, outputName: string) => {
    if (!record?.graph) return;
    const suggested = outputName === 'label' ? 'result' : outputName;
    const name = window.prompt('Recipe output name', suggested);
    if (!name) return;
    if (!/^[a-z][a-z0-9_]*$/.test(name)) return window.alert('Output name은 영문 소문자/숫자/underscore 형식이어야 합니다.');
    change((draft) => { draft.graph!.outputs[name] = { type: 'node_output', node_id: nodeId, output_name: outputName }; });
    onSelectionChange({ type: 'output', name });
  };

  const exposeLinearOutput = (stepId: string, outputName: string) => {
    if (!record?.pipeline) return;
    const name = window.prompt('Recipe output name', outputName);
    if (!name) return;
    if (!/^[a-z][a-z0-9_]*$/.test(name)) return window.alert('Output name은 영문 소문자/숫자/underscore 형식이어야 합니다.');
    change((draft) => { draft.pipeline!.outputs[name] = { type: 'step_output', step_id: stepId, output_name: outputName }; });
    onSelectionChange({ type: 'output', name });
  };

  const body = (() => {
    if (!record || !artifact) return <EmptyState>Recipe를 선택하세요.</EmptyState>;

    if (selection.type === 'recipe') {
      return <div className="inspector-scroll">
        <div className="inspector-section">
          <div className="inspector-heading">Recipe metadata</div>
          <Field label="Name"><input className="input" value={record.name} readOnly/></Field>
          <Field label="Display name"><input className="input" disabled={disabled} value={artifact.display_name} onChange={(e) => change((draft) => { artifactOf(draft).display_name = e.target.value; })}/></Field>
          <Field label="Version"><input className="input" disabled={disabled} value={artifact.version} onChange={(e) => change((draft) => { artifactOf(draft).version = e.target.value; })}/></Field>
          <Field label="Tags" help="쉼표(,)로 구분"><input className="input" disabled={disabled} value={record.tags.join(', ')} onChange={(e) => change((draft) => { draft.tags = parseTags(e.target.value); })}/></Field>
          <Field label="Description"><textarea className="textarea" disabled={disabled} value={artifact.description ?? ''} onChange={(e) => change((draft) => { artifactOf(draft).description = e.target.value; })}/></Field>
        </div>
        <div className="inspector-section">
          <div className="inspector-heading">Recipe inputs</div>
          <div className="structure-list">
            {artifact.inputs.map((input) => <button key={input.name} className="structure-row" onClick={() => onSelectionChange({ type: 'input', name: input.name })}>
              <span>{input.name}</span><small>{input.kind}{input.required ? ' · required' : ''}</small>
            </button>)}
          </div>
          {!disabled && <div className="inline-add-row">
            <input className="input" placeholder="input_name" value={newInputName} onChange={(e) => setNewInputName(e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, ''))}/>
            <select className="select" value={newInputKind} onChange={(e) => setNewInputKind(e.target.value)}>{recipeInputKinds(record.kind).map((kind) => <option key={kind}>{kind}</option>)}</select>
            <Button onClick={() => {
              if (!newInputName || !/^[a-z][a-z0-9_]*$/.test(newInputName)) return;
              if (artifact.inputs.some((item) => item.name === newInputName)) return;
              change((draft) => { artifactOf(draft).inputs.push({ name: newInputName, kind: newInputKind, required: true }); });
              setNewInputName('');
            }}>Add</Button>
          </div>}
        </div>
        <div className="inspector-section">
          <div className="inspector-heading">Recipe outputs</div>
          {Object.entries(artifact.outputs).length ? <div className="structure-list">
            {Object.entries(artifact.outputs).map(([name, ref]) => <button key={name} className="structure-row" onClick={() => onSelectionChange({ type: 'output', name })}>
              <span>{name}</span><small>{formatReference(ref)}</small>
            </button>)}
          </div> : <div className="inspector-muted">Node output에서 Expose 버튼으로 추가하세요.</div>}
        </div>
      </div>;
    }

    if (selection.type === 'input') {
      const input = artifact.inputs.find((item) => item.name === selection.name);
      if (!input) return <EmptyState>Input이 없습니다.</EmptyState>;
      return <div className="inspector-scroll"><div className="inspector-section">
        <div className="inspector-heading">Recipe input</div>
        <Field label="Name"><input className="input" value={input.name} readOnly/></Field>
        <Field label="Kind"><select className="select" disabled={disabled} value={input.kind} onChange={(e) => change((draft) => {
          const target = artifactOf(draft).inputs.find((item) => item.name === selection.name); if (target) target.kind = e.target.value;
        })}>{recipeInputKinds(record.kind).map((kind) => <option key={kind}>{kind}</option>)}</select></Field>
        <Field label="Required"><label className="switch-row"><input type="checkbox" disabled={disabled} checked={input.required} onChange={(e) => change((draft) => {
          const target = artifactOf(draft).inputs.find((item) => item.name === selection.name); if (target) target.required = e.target.checked;
        })}/><span>{input.required ? 'Required' : 'Optional'}</span></label></Field>
        {!disabled && <Button variant="danger" onClick={() => {
          change((draft) => {
            const art = artifactOf(draft);
            art.inputs = art.inputs.filter((item) => item.name !== selection.name);
            if (draft.kind === 'linear') {
              for (const step of draft.pipeline!.steps) step.inputs = Object.fromEntries(Object.entries(step.inputs ?? {}).filter(([, ref]) => !(ref.type === 'pipeline_input' && ref.input_name === selection.name)));
              draft.pipeline!.outputs = Object.fromEntries(Object.entries(draft.pipeline!.outputs).filter(([, ref]) => !(ref.type === 'pipeline_input' && ref.input_name === selection.name)));
            } else {
              for (const node of draft.graph!.nodes) node.inputs = Object.fromEntries(Object.entries(node.inputs ?? {}).filter(([, ref]) => !(ref.type === 'graph_input' && ref.input_name === selection.name)));
              draft.graph!.outputs = Object.fromEntries(Object.entries(draft.graph!.outputs).filter(([, ref]) => !(ref.type === 'graph_input' && ref.input_name === selection.name)));
            }
          }); onSelectionChange({ type: 'recipe' });
        }}>Remove Input</Button>}
      </div></div>;
    }

    if (selection.type === 'output') {
      const ref = artifact.outputs[selection.name];
      if (!ref) return <EmptyState>Output이 없습니다.</EmptyState>;
      return <div className="inspector-scroll"><div className="inspector-section">
        <div className="inspector-heading">Recipe output</div>
        <Field label="Name"><input className="input" value={selection.name} readOnly/></Field>
        <Field label="Source"><div className="binding-value">{formatReference(ref)}</div></Field>
        {!disabled && <Button variant="danger" onClick={() => { change((draft) => { delete artifactOf(draft).outputs[selection.name]; }); onSelectionChange({ type: 'recipe' }); }}>Remove Output</Button>}
      </div></div>;
    }

    if (selection.type === 'node' && record.kind === 'linear' && record.pipeline) {
      const stepIndex = record.pipeline.steps.findIndex((item) => item.id === selection.id);
      const step = record.pipeline.steps[stepIndex];
      if (!step) return <EmptyState>Step이 없습니다.</EmptyState>;
      const spec = operations.get(step.operation);
      const iface = pipelineStepInterface(step, operations);
      return <div className="inspector-scroll">
        <div className="inspector-section"><NodeHeader id={step.id} target={step.operation}/>
          <Field label="Step ID"><input className="input" value={step.id} readOnly/></Field>
          {!disabled && <div className="node-action-row">
            <Button disabled={stepIndex <= 0} onClick={() => { const next = deepClone(record); const list = next.pipeline!.steps; [list[stepIndex - 1], list[stepIndex]] = [list[stepIndex], list[stepIndex - 1]]; onChange(cleanupLinearOrder(next)); }}>↑ Up</Button>
            <Button disabled={stepIndex >= record.pipeline!.steps.length - 1} onClick={() => { const next = deepClone(record); const list = next.pipeline!.steps; [list[stepIndex + 1], list[stepIndex]] = [list[stepIndex], list[stepIndex + 1]]; onChange(cleanupLinearOrder(next)); }}>↓ Down</Button>
            <Button variant="danger" onClick={() => { onChange(removeLinearStep(record, step.id)); onSelectionChange({ type: 'recipe' }); }}>Delete</Button>
          </div>}
        </div>
        <div className="inspector-section"><div className="inspector-heading">Input bindings</div>
          {iface.inputs.map((port) => {
            const options = linearSourceOptions(record.pipeline!, stepIndex, port.kind, operations);
            const current = step.inputs?.[port.name];
            const currentKey = current ? (current.type === 'pipeline_input' ? `input:${current.input_name}` : `step:${current.step_id}:${current.output_name}`) : '';
            return <Field key={port.name} label={port.name} help={`${port.kind}${port.required ? ' · required' : ''}`}>
              <select className="select" disabled={disabled} value={currentKey} onChange={(e) => change((draft) => {
                const target = draft.pipeline!.steps.find((item) => item.id === step.id)!; target.inputs ??= {};
                if (!e.target.value) delete target.inputs[port.name];
                else target.inputs[port.name] = options.find((item) => item.key === e.target.value)!.reference;
              })}><option value="">Not connected</option>{options.map((item) => <option key={item.key} value={item.key}>{item.label}</option>)}</select>
            </Field>;
          })}
        </div>
        <div className="inspector-section"><div className="inspector-heading">Parameters</div>
          {spec ? <ParameterEditor parameters={spec.parameters} values={step.params ?? {}} disabled={disabled} onChange={(name, value) => change((draft) => {
            const target = draft.pipeline!.steps.find((item) => item.id === step.id)!; target.params = updateParams(target.params, name, value);
          })}/> : <div className="inspector-muted">Operation spec을 찾을 수 없습니다.</div>}
        </div>
        <div className="inspector-section"><div className="inspector-heading">Outputs</div>
          {iface.outputs.map((output) => <div className="output-row" key={output.name}><span>{output.name}</span><small>{output.kind}</small><Button disabled={disabled} onClick={() => exposeLinearOutput(step.id, output.name)}>Expose</Button></div>)}
        </div>
      </div>;
    }

    if (selection.type === 'node' && record.kind === 'graph' && record.graph) {
      const node = record.graph.nodes.find((item) => item.id === selection.id);
      if (!node) return <EmptyState>Node가 없습니다.</EmptyState>;
      const iface = nodeInterface(node, operations, features, operators, subrecipes);
      const opSpec = node.operation ? operations.get(node.operation) : undefined;
      const featureSpec = node.feature ? features.get(node.feature) : undefined;
      const operatorSpec = node.operator ? operators.get(node.operator) : undefined;
      const dynamicOptions = operatorSpec?.max_inputs == null
        ? graphSourceOptions(record.graph!, node.id, 'scalar', operations, features, operators, subrecipes)
        : [];
      return <div className="inspector-scroll">
        <div className="inspector-section"><NodeHeader id={node.id} target={nodeDisplayName(node)}/>
          <Field label="Node type"><div className="binding-value">{node.node_type}</div></Field>
          {node.node_type === 'subrecipe' && <>
            <Field label="Recipe"><select className="select" disabled={disabled} value={node.recipe ?? ''} onChange={(e) => {
              const chosen = recipes.find((item) => item.name === e.target.value); if (!chosen) return;
              change((draft) => { const target = draft.graph!.nodes.find((item) => item.id === node.id)!; target.recipe = chosen.name; target.recipe_kind = chosen.kind; target.recipe_version = chosen.version; target.inputs = {}; });
            }}>{recipes.filter((item) => item.name !== record.name).map((item) => <option key={item.name} value={item.name}>{item.display_name} · {item.kind}</option>)}</select></Field>
            <Field label="Version"><input className="input" disabled={disabled} value={node.recipe_version ?? ''} onChange={(e) => change((draft) => { draft.graph!.nodes.find((item) => item.id === node.id)!.recipe_version = e.target.value || undefined; })}/></Field>
          </>}
          {!disabled && <Button variant="danger" onClick={() => { onChange(removeGraphNode(record, node.id)); onSelectionChange({ type: 'recipe' }); }}>Delete Node</Button>}
        </div>
        <div className="inspector-section"><div className="inspector-heading">Input bindings</div>
          {iface.inputs.map((port) => {
            const options = graphSourceOptions(record.graph!, node.id, port.kind, operations, features, operators, subrecipes);
            const current = node.inputs?.[port.name];
            const currentKey = current ? (current.type === 'graph_input' ? `input:${current.input_name}` : `node:${current.node_id}:${current.output_name}`) : '';
            return <Field key={port.name} label={port.name} help={`${port.kind}${port.required ? ' · required' : ''}`}>
              <select className="select" disabled={disabled} value={currentKey} onChange={(e) => change((draft) => {
                const target = draft.graph!.nodes.find((item) => item.id === node.id)!; target.inputs ??= {};
                if (!e.target.value) delete target.inputs[port.name];
                else target.inputs[port.name] = options.find((item) => item.key === e.target.value)!.reference;
              })}><option value="">Not connected</option>{options.map((item) => <option key={item.key} value={item.key}>{item.label}</option>)}</select>
            </Field>;
          })}
          {node.node_type === 'scalar_operator' && operatorSpec && operatorSpec.max_inputs == null && !disabled && <div className="dynamic-binding-add">
            <input className="input" placeholder="input name" value={dynamicInputName} onChange={(e) => setDynamicInputName(e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, ''))}/>
            <select className="select" value={dynamicInputSource} onChange={(e) => setDynamicInputSource(e.target.value)}><option value="">Source 선택</option>{dynamicOptions.map((item) => <option key={item.key} value={item.key}>{item.label}</option>)}</select>
            <Button disabled={!dynamicInputName || !dynamicInputSource} onClick={() => {
              if (!/^[a-z][a-z0-9_]*$/.test(dynamicInputName)) return;
              const source = dynamicOptions.find((item) => item.key === dynamicInputSource); if (!source) return;
              change((draft) => { const target = draft.graph!.nodes.find((item) => item.id === node.id)!; target.inputs ??= {}; target.inputs[dynamicInputName] = source.reference; });
              setDynamicInputName(''); setDynamicInputSource('');
            }}>Add input</Button>
          </div>}
        </div>
        <div className="inspector-section"><div className="inspector-heading">Parameters</div>
          {opSpec && <ParameterEditor parameters={opSpec.parameters} values={node.params ?? {}} disabled={disabled} onChange={(name, value) => change((draft) => { const target = draft.graph!.nodes.find((item) => item.id === node.id)!; target.params = updateParams(target.params, name, value); })}/>} 
          {featureSpec && <ParameterEditor parameters={featureSpec.parameters} values={node.params ?? {}} disabled={disabled} onChange={(name, value) => change((draft) => { const target = draft.graph!.nodes.find((item) => item.id === node.id)!; target.params = updateParams(target.params, name, value); })}/>} 
          {operatorSpec && <LooseParameterEditor schema={operatorSpec.parameters} values={node.params ?? {}} disabled={disabled} onChange={(name, value) => change((draft) => { const target = draft.graph!.nodes.find((item) => item.id === node.id)!; target.params = updateParams(target.params, name, value); })}/>} 
          {node.node_type === 'roi_crop' && <RoiEditor node={node} disabled={disabled} onChange={(params) => change((draft) => { draft.graph!.nodes.find((item) => item.id === node.id)!.params = params; })}/>} 
          {node.node_type === 'decision' && <DecisionEditor node={node} disabled={disabled} onChange={(params) => change((draft) => { draft.graph!.nodes.find((item) => item.id === node.id)!.params = params; })}/>} 
          {['roi_compose', 'subrecipe'].includes(node.node_type) && <div className="inspector-muted">추가 parameter가 없습니다.</div>}
        </div>
        <div className="inspector-section"><div className="inspector-heading">Outputs</div>
          {iface.outputs.map((output) => <div className="output-row" key={output.name}><span>{output.name}</span><small>{output.kind}</small><Button disabled={disabled} onClick={() => exposeGraphOutput(node.id, output.name)}>Expose</Button></div>)}
        </div>
      </div>;
    }

    return <EmptyState>선택 항목을 찾을 수 없습니다.</EmptyState>;
  })();

  const libraryInfo = useMemo(() => {
    if (!librarySelection) return null;
    if (librarySelection.type === 'operation') return operations.get(librarySelection.name);
    if (librarySelection.type === 'feature') return features.get(librarySelection.name);
    if (librarySelection.type === 'operator') return operators.get(librarySelection.name);
    if (librarySelection.type === 'subrecipe') return recipes.find((item) => item.name === librarySelection.name);
    if (librarySelection.type === 'system') return { name: librarySelection.name, display_name: librarySelection.name.replaceAll('_', ' '), description: 'Graph workflow built-in node.' };
    return null;
  }, [librarySelection, operations, features, operators, recipes]);

  return <Panel title="Inspector" subtitle={selection.type === 'node' ? selection.id : selection.type === 'recipe' ? record?.name ?? '' : selection.name} flush>
    <Tabs items={['Edit', 'Info']} active={tab} onChange={setTab}/>
    {tab === 'Edit' ? body : libraryInfo ? <div className="inspector-scroll"><div className="inspector-section">
      <div className="inspector-heading">Library item</div>
      <div className="info-title">{String(libraryInfo.display_name)}</div>
      <div className="info-code">{String(libraryInfo.name)}</div>
      <p className="info-description">{'description' in libraryInfo ? String(libraryInfo.description ?? 'No description') : 'No description'}</p>
      {'version' in libraryInfo && <div className="mono-small">version: {String(libraryInfo.version)}</div>}
    </div></div> : <EmptyState>Library에서 항목을 선택하면 상세 정보가 표시됩니다.</EmptyState>}
  </Panel>;
}

function RoiEditor({ node, disabled, onChange }: { node: GraphNodeSpec; disabled: boolean; onChange: (params: JsonMap) => void }) {
  const params = node.params ?? {};
  const patch = (name: string, value: unknown) => onChange({ ...params, [name]: value });
  const relative = (params.coordinate_mode ?? 'pixels') === 'relative';
  return <div className="parameter-list">
    <Field label="Mode"><select className="select" disabled={disabled} value={String(params.coordinate_mode ?? 'pixels')} onChange={(e) => patch('coordinate_mode', e.target.value)}><option value="pixels">pixels</option><option value="relative">relative</option></select></Field>
    {['x', 'y', 'width', 'height'].map((name) => <Field key={name} label={name}><input className="input" type="number" disabled={disabled} min={0} max={relative ? 1 : undefined} step={relative ? 0.01 : 1} value={String(params[name] ?? (name === 'width' || name === 'height' ? (relative ? 0.5 : 100) : 0))} onChange={(e) => patch(name, Number(e.target.value))}/></Field>)}
    <Field label="Clamp"><label className="switch-row"><input type="checkbox" disabled={disabled} checked={Boolean(params.clamp ?? false)} onChange={(e) => patch('clamp', e.target.checked)}/><span>{Boolean(params.clamp) ? 'On' : 'Off'}</span></label></Field>
  </div>;
}

function DecisionEditor({ node, disabled, onChange }: { node: GraphNodeSpec; disabled: boolean; onChange: (params: JsonMap) => void }) {
  const params = node.params ?? {};
  const patch = (name: string, value: unknown) => onChange({ ...params, [name]: value });
  const operator = String(params.operator ?? 'gt');
  const range = operator === 'inside_range' || operator === 'outside_range';
  return <div className="parameter-list">
    <Field label="Operator"><select className="select" disabled={disabled} value={operator} onChange={(e) => patch('operator', e.target.value)}>{['gt', 'gte', 'lt', 'lte', 'inside_range', 'outside_range'].map((item) => <option key={item}>{item}</option>)}</select></Field>
    {range ? <><Field label="Lower"><input className="input" type="number" disabled={disabled} value={String(params.lower ?? 0)} onChange={(e) => patch('lower', Number(e.target.value))}/></Field><Field label="Upper"><input className="input" type="number" disabled={disabled} value={String(params.upper ?? 1)} onChange={(e) => patch('upper', Number(e.target.value))}/></Field></> : <Field label="Threshold"><input className="input" type="number" disabled={disabled} value={String(params.threshold ?? 0)} onChange={(e) => patch('threshold', Number(e.target.value))}/></Field>}
    <Field label="Pass label"><input className="input" disabled={disabled} value={String(params.pass_label ?? 'OK')} onChange={(e) => patch('pass_label', e.target.value)}/></Field>
    <Field label="Fail label"><input className="input" disabled={disabled} value={String(params.fail_label ?? 'NG')} onChange={(e) => patch('fail_label', e.target.value)}/></Field>
  </div>;
}
