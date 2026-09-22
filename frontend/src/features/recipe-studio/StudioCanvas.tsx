import { useMemo } from 'react';
import {
  Background,
  Controls,
  Handle,
  MiniMap,
  Position,
  ReactFlow,
  type Connection,
  type Edge,
  type Node,
  type NodeProps,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import type {
  FeatureSpec,
  GraphValueReference,
  OperationSpec,
  PipelineValueReference,
  RecipeRecord,
  ScalarOperatorSpec,
} from '../../api';
import type { NodeInterface, RecipeSelection, SubrecipeInterface } from './editor';
import { nodeDisplayName, nodeInterface, pipelineStepInterface } from './editor';

export type StudioNodeData = {
  title: string;
  subtitle: string;
  nodeKind: string;
  inputs: Array<{ name: string; kind: string; connected: boolean }>;
  outputs: Array<{ name: string; kind: string; exposed?: boolean }>;
  readonly?: boolean;
  pseudo?: 'input' | 'output';
};

type StudioFlowNode = Node<StudioNodeData, 'studio'>;

function StudioNodeView({ data, selected }: NodeProps<StudioFlowNode>) {
  const height = Math.max(data.inputs.length, data.outputs.length, 1) * 20 + 54;
  return <div className={`studio-flow-node ${selected ? 'selected' : ''} ${data.pseudo ? `pseudo ${data.pseudo}` : ''}`} style={{ minHeight: height }}>
    <div className="studio-node-head">
      <span className="studio-node-type">{data.pseudo ? data.pseudo : data.nodeKind}</span>
      <strong>{data.title}</strong>
      {data.readonly && <span className="studio-node-lock">RO</span>}
    </div>
    <div className="studio-node-subtitle">{data.subtitle}</div>
    <div className="studio-port-grid">
      <div className="studio-port-column inputs">
        {data.inputs.map((port, index) => <div className="studio-port-row input" key={port.name}>
          <Handle
            id={port.name}
            type="target"
            position={Position.Left}
            className={`studio-handle ${port.connected ? 'connected' : ''}`}
            style={{ top: '50%' }}
          />
          <span className="port-name">{port.name}</span><span className="port-kind">{port.kind}</span>
        </div>)}
      </div>
      <div className="studio-port-column outputs">
        {data.outputs.map((port, index) => <div className="studio-port-row output" key={port.name}>
          <span className="port-kind">{port.kind}</span><span className="port-name">{port.name}</span>
          <Handle
            id={port.name}
            type="source"
            position={Position.Right}
            className={`studio-handle ${port.exposed ? 'exposed' : ''}`}
            style={{ top: '50%' }}
          />
        </div>)}
      </div>
    </div>
  </div>;
}

const nodeTypes = { studio: StudioNodeView };

function linearNodes(
  record: RecipeRecord,
  operations: Map<string, OperationSpec>,
  positions: Map<string, { x: number; y: number }>,
): StudioFlowNode[] {
  const pipeline = record.pipeline!;
  const nodes: StudioFlowNode[] = [];
  pipeline.inputs.forEach((input, index) => {
    const id = `__input__${input.name}`;
    nodes.push({
      id, type: 'studio', position: positions.get(id) ?? { x: 20, y: 45 + index * 95 },
      data: { title: input.name, subtitle: input.required ? 'required' : 'optional', nodeKind: 'input', inputs: [], outputs: [{ name: 'value', kind: input.kind }], pseudo: 'input', readonly: record.readonly },
    });
  });
  pipeline.steps.forEach((step, index) => {
    const iface = pipelineStepInterface(step, operations);
    const id = step.id;
    nodes.push({
      id, type: 'studio', position: positions.get(id) ?? { x: 260 + index * 225, y: 120 + (index % 2) * 110 },
      data: {
        title: step.id, subtitle: step.operation, nodeKind: 'operation', readonly: record.readonly,
        inputs: iface.inputs.map((port) => ({ ...port, connected: Boolean(step.inputs?.[port.name]) })),
        outputs: iface.outputs.map((port) => ({ ...port, exposed: Object.values(pipeline.outputs).some((ref) => ref.type === 'step_output' && ref.step_id === step.id && ref.output_name === port.name) })),
      },
    });
  });
  Object.entries(pipeline.outputs).forEach(([name, ref], index) => {
    const id = `__output__${name}`;
    nodes.push({
      id, type: 'studio', position: positions.get(id) ?? { x: Math.max(520, 300 + pipeline.steps.length * 225), y: 45 + index * 95 },
      data: { title: name, subtitle: 'recipe output', nodeKind: 'output', inputs: [{ name: 'value', kind: referenceKindLinear(ref, pipeline, operations), connected: true }], outputs: [], pseudo: 'output', readonly: record.readonly },
    });
  });
  return nodes;
}

function graphNodes(
  record: RecipeRecord,
  operations: Map<string, OperationSpec>,
  features: Map<string, FeatureSpec>,
  operators: Map<string, ScalarOperatorSpec>,
  subrecipes: Map<string, SubrecipeInterface>,
  positions: Map<string, { x: number; y: number }>,
): StudioFlowNode[] {
  const graph = record.graph!;
  const nodes: StudioFlowNode[] = [];
  graph.inputs.forEach((input, index) => {
    const id = `__input__${input.name}`;
    nodes.push({
      id, type: 'studio', position: positions.get(id) ?? { x: 20, y: 45 + index * 100 },
      data: { title: input.name, subtitle: input.required ? 'required' : 'optional', nodeKind: 'input', inputs: [], outputs: [{ name: 'value', kind: input.kind }], pseudo: 'input', readonly: record.readonly },
    });
  });
  graph.nodes.forEach((node, index) => {
    const iface = nodeInterface(node, operations, features, operators, subrecipes);
    nodes.push({
      id: node.id, type: 'studio', position: positions.get(node.id) ?? { x: 270 + (index % 4) * 235, y: 55 + Math.floor(index / 4) * 165 },
      data: {
        title: node.id, subtitle: nodeDisplayName(node), nodeKind: node.node_type, readonly: record.readonly,
        inputs: iface.inputs.map((port) => ({ ...port, connected: Boolean(node.inputs?.[port.name]) })),
        outputs: iface.outputs.map((port) => ({ ...port, exposed: Object.values(graph.outputs).some((ref) => ref.type === 'node_output' && ref.node_id === node.id && ref.output_name === port.name) })),
      },
    });
  });
  Object.entries(graph.outputs).forEach(([name, ref], index) => {
    const id = `__output__${name}`;
    nodes.push({
      id, type: 'studio', position: positions.get(id) ?? { x: Math.max(650, 350 + Math.min(4, graph.nodes.length) * 235), y: 45 + index * 100 },
      data: { title: name, subtitle: 'recipe output', nodeKind: 'output', inputs: [{ name: 'value', kind: referenceKindGraph(ref, graph, operations, features, operators, subrecipes), connected: true }], outputs: [], pseudo: 'output', readonly: record.readonly },
    });
  });
  return nodes;
}

function referenceKindLinear(ref: PipelineValueReference, pipeline: NonNullable<RecipeRecord['pipeline']>, operations: Map<string, OperationSpec>): string {
  if (ref.type === 'pipeline_input') return pipeline.inputs.find((item) => item.name === ref.input_name)?.kind ?? 'unknown';
  const step = pipeline.steps.find((item) => item.id === ref.step_id);
  return operations.get(step?.operation ?? '')?.outputs.find((item) => item.name === ref.output_name)?.kind ?? 'unknown';
}

function referenceKindGraph(
  ref: GraphValueReference,
  graph: NonNullable<RecipeRecord['graph']>,
  operations: Map<string, OperationSpec>,
  features: Map<string, FeatureSpec>,
  operators: Map<string, ScalarOperatorSpec>,
  subrecipes: Map<string, SubrecipeInterface>,
): string {
  if (ref.type === 'graph_input') return graph.inputs.find((item) => item.name === ref.input_name)?.kind ?? 'unknown';
  const node = graph.nodes.find((item) => item.id === ref.node_id);
  if (!node) return 'unknown';
  return nodeInterface(node, operations, features, operators, subrecipes).outputs.find((item) => item.name === ref.output_name)?.kind ?? 'unknown';
}

function linearEdges(record: RecipeRecord): Edge[] {
  const pipeline = record.pipeline!;
  const edges: Edge[] = [];
  for (const step of pipeline.steps) {
    for (const [inputName, ref] of Object.entries(step.inputs ?? {})) {
      const source = ref.type === 'pipeline_input' ? `__input__${ref.input_name}` : ref.step_id;
      const sourceHandle = ref.type === 'pipeline_input' ? 'value' : ref.output_name;
      edges.push({ id: `${source}:${sourceHandle}->${step.id}:${inputName}`, source, sourceHandle, target: step.id, targetHandle: inputName, data: { targetType: 'node', targetId: step.id, targetInput: inputName } });
    }
  }
  for (const [name, ref] of Object.entries(pipeline.outputs)) {
    const source = ref.type === 'pipeline_input' ? `__input__${ref.input_name}` : ref.step_id;
    const sourceHandle = ref.type === 'pipeline_input' ? 'value' : ref.output_name;
    edges.push({ id: `${source}:${sourceHandle}->__output__${name}`, source, sourceHandle, target: `__output__${name}`, targetHandle: 'value', data: { targetType: 'output', targetId: name } });
  }
  return edges;
}

function graphEdges(record: RecipeRecord): Edge[] {
  const graph = record.graph!;
  const edges: Edge[] = [];
  for (const node of graph.nodes) {
    for (const [inputName, ref] of Object.entries(node.inputs ?? {})) {
      const source = ref.type === 'graph_input' ? `__input__${ref.input_name}` : ref.node_id;
      const sourceHandle = ref.type === 'graph_input' ? 'value' : ref.output_name;
      edges.push({ id: `${source}:${sourceHandle}->${node.id}:${inputName}`, source, sourceHandle, target: node.id, targetHandle: inputName, data: { targetType: 'node', targetId: node.id, targetInput: inputName } });
    }
  }
  for (const [name, ref] of Object.entries(graph.outputs)) {
    const source = ref.type === 'graph_input' ? `__input__${ref.input_name}` : ref.node_id;
    const sourceHandle = ref.type === 'graph_input' ? 'value' : ref.output_name;
    edges.push({ id: `${source}:${sourceHandle}->__output__${name}`, source, sourceHandle, target: `__output__${name}`, targetHandle: 'value', data: { targetType: 'output', targetId: name } });
  }
  return edges;
}

export function StudioCanvas({
  record,
  operations,
  features,
  operators,
  subrecipes,
  positions,
  onPositionChange,
  selection,
  onSelectionChange,
  onConnect,
  onDeleteEdge,
}: {
  record: RecipeRecord;
  operations: Map<string, OperationSpec>;
  features: Map<string, FeatureSpec>;
  operators: Map<string, ScalarOperatorSpec>;
  subrecipes: Map<string, SubrecipeInterface>;
  positions: Map<string, { x: number; y: number }>;
  onPositionChange: (id: string, position: { x: number; y: number }) => void;
  selection: RecipeSelection;
  onSelectionChange: (selection: RecipeSelection) => void;
  onConnect: (connection: Connection) => void;
  onDeleteEdge: (edge: Edge) => void;
}) {
  const nodes = useMemo(() => record.kind === 'linear'
    ? linearNodes(record, operations, positions)
    : graphNodes(record, operations, features, operators, subrecipes, positions),
  [record, operations, features, operators, subrecipes, positions]);
  const edges = useMemo(() => record.kind === 'linear' ? linearEdges(record) : graphEdges(record), [record]);
  const selectedId = selection.type === 'node' ? selection.id : selection.type === 'input' ? `__input__${selection.name}` : selection.type === 'output' ? `__output__${selection.name}` : '';
  const visibleNodes = nodes.map((node) => ({ ...node, selected: node.id === selectedId }));
  const workNodeCount = record.kind === 'linear' ? (record.pipeline?.steps.length ?? 0) : (record.graph?.nodes.length ?? 0);
  const inputCount = record.kind === 'linear' ? (record.pipeline?.inputs.length ?? 0) : (record.graph?.inputs.length ?? 0);
  const outputCount = record.kind === 'linear' ? Object.keys(record.pipeline?.outputs ?? {}).length : Object.keys(record.graph?.outputs ?? {}).length;

  return <div className="react-flow-wrap">
    <div className="canvas-status-chip">{inputCount} input · {workNodeCount} {record.kind === 'linear' ? 'step' : 'node'} · {outputCount} output</div>
    {workNodeCount === 0 && <div className="canvas-empty-hint"><strong>Recipe Canvas is ready</strong>좌측 Node Library에서 Operation을 + 버튼 또는 더블클릭으로 추가하세요.<br/>Input node는 이미 생성되어 있으며 Node 추가 후 연결할 수 있습니다.</div>}
    <ReactFlow
      key={`${record.name}:${record.kind}`}
      nodes={visibleNodes}
      edges={edges}
      nodeTypes={nodeTypes}
      fitView
      fitViewOptions={{ padding: 0.18 }}
      minZoom={0.25}
      maxZoom={1.6}
      nodesConnectable={!record.readonly}
      edgesReconnectable={false}
      deleteKeyCode={record.readonly ? null : ['Backspace', 'Delete']}
      onNodeClick={(_, node) => {
        if (node.id.startsWith('__input__')) onSelectionChange({ type: 'input', name: node.id.slice('__input__'.length) });
        else if (node.id.startsWith('__output__')) onSelectionChange({ type: 'output', name: node.id.slice('__output__'.length) });
        else onSelectionChange({ type: 'node', id: node.id });
      }}
      onPaneClick={() => onSelectionChange({ type: 'recipe' })}
      onNodesChange={(changes) => {
        for (const change of changes) {
          if (change.type === 'position' && change.position) onPositionChange(change.id, change.position);
        }
      }}
      onNodeDragStop={(_, node) => onPositionChange(node.id, node.position)}
      onConnect={onConnect}
      onEdgesDelete={(deleted) => deleted.forEach(onDeleteEdge)}
    >
      <Background gap={18} size={1}/><MiniMap pannable zoomable/><Controls/>
    </ReactFlow>
  </div>;
}

export function connectionReference(connection: Connection): { sourceRef: GraphValueReference | PipelineValueReference | null; targetId: string; targetHandle: string } {
  if (!connection.source || !connection.target || !connection.targetHandle) return { sourceRef: null, targetId: '', targetHandle: '' };
  const sourceRef = connection.source.startsWith('__input__')
    ? ({ type: 'graph_input', input_name: connection.source.slice('__input__'.length) } as GraphValueReference)
    : ({ type: 'node_output', node_id: connection.source, output_name: connection.sourceHandle ?? 'image' } as GraphValueReference);
  return { sourceRef, targetId: connection.target, targetHandle: connection.targetHandle };
}

export function interfaceForGraphNode(
  record: RecipeRecord,
  nodeId: string,
  operations: Map<string, OperationSpec>,
  features: Map<string, FeatureSpec>,
  operators: Map<string, ScalarOperatorSpec>,
  subrecipes: Map<string, SubrecipeInterface>,
): NodeInterface | null {
  const node = record.graph?.nodes.find((item) => item.id === nodeId);
  return node ? nodeInterface(node, operations, features, operators, subrecipes) : null;
}
