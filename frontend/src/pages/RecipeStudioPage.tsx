import { useEffect, useMemo, useRef, useState } from 'react';
import { Background, Controls, MiniMap, ReactFlow, type Edge, type Node } from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import { operationsApi, recipesApi, workflowApi, type ExecutionResponse, type GraphNodeSpec, type OperationSpec, type RecipeRecord, type RecipeSummary } from '../api';
import { Badge, Button, EmptyState, Field, InlineError, Loading, Panel, SearchInput, Tabs } from '../components/ui';
import { errorMessage, imageDataUrl } from '../lib/format';

function nodeLabel(node: GraphNodeSpec): string {
  return node.operation ?? node.feature ?? node.operator ?? node.recipe ?? node.node_type;
}

function buildCanvas(record: RecipeRecord | null): {nodes: Node[]; edges: Edge[]} {
  if (!record) return { nodes: [], edges: [] };
  if (record.kind === 'linear' && record.pipeline) {
    const nodes: Node[] = record.pipeline.steps.map((step, index) => ({
      id: step.id,
      position: { x: 50 + index * 220, y: 140 },
      data: { label: `${step.id}\n${step.operation}` },
      style: { width: 170, padding: 10, borderRadius: 7, background: '#19212b', color: '#dce6f3', border: '1px solid #3b4a5d', fontSize: 10, whiteSpace: 'pre-line' },
    }));
    const edges: Edge[] = record.pipeline.steps.slice(1).map((step, index) => ({ id: `${record.pipeline!.steps[index].id}-${step.id}`, source: record.pipeline!.steps[index].id, target: step.id }));
    return { nodes, edges };
  }
  if (record.kind === 'graph' && record.graph) {
    const nodes: Node[] = record.graph.nodes.map((node, index) => ({
      id: node.id,
      position: { x: 40 + (index % 4) * 230, y: 45 + Math.floor(index / 4) * 145 },
      data: { label: `${node.id}\n${nodeLabel(node)}` },
      style: { width: 180, padding: 10, borderRadius: 7, background: node.node_type === 'decision' ? '#241e18' : '#19212b', color: '#dce6f3', border: `1px solid ${node.node_type === 'decision' ? '#755f3f' : '#3b4a5d'}`, fontSize: 10, whiteSpace: 'pre-line' },
    }));
    const edges: Edge[] = [];
    for (const node of record.graph.nodes) {
      for (const ref of Object.values(node.inputs ?? {})) {
        if (ref && typeof ref === 'object' && ref.type === 'node_output' && typeof ref.node_id === 'string') {
          edges.push({ id: `${ref.node_id}-${node.id}-${edges.length}`, source: ref.node_id, target: node.id, animated: false });
        }
      }
    }
    return { nodes, edges };
  }
  return { nodes: [], edges: [] };
}

export function RecipeStudioPage() {
  const [recipes, setRecipes] = useState<RecipeSummary[]>([]);
  const [operations, setOperations] = useState<OperationSpec[]>([]);
  const [features, setFeatures] = useState<unknown[]>([]);
  const [operators, setOperators] = useState<unknown[]>([]);
  const [selectedName, setSelectedName] = useState<string>('');
  const [record, setRecord] = useState<RecipeRecord | null>(null);
  const [selectedOperation, setSelectedOperation] = useState<OperationSpec | null>(null);
  const [recipeSearch, setRecipeSearch] = useState('');
  const [operationSearch, setOperationSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [result, setResult] = useState<ExecutionResponse | null>(null);
  const [previewTab, setPreviewTab] = useState('Preview');
  const fileRef = useRef<HTMLInputElement | null>(null);

  const loadLists = async () => {
    setLoading(true); setError(null);
    try {
      const [r, o, f, so] = await Promise.all([recipesApi.list(), operationsApi.list(), workflowApi.features(), workflowApi.operators()]);
      setRecipes(r); setOperations(o); setFeatures(f); setOperators(so);
      if (!selectedName && r.length) setSelectedName(r[0].name);
    } catch (e) { setError(errorMessage(e)); }
    finally { setLoading(false); }
  };

  useEffect(() => { void loadLists(); }, []);
  useEffect(() => {
    if (!selectedName) { setRecord(null); return; }
    setError(null);
    void recipesApi.get(selectedName).then(setRecord).catch((e) => setError(errorMessage(e)));
  }, [selectedName]);

  const filteredRecipes = useMemo(() => recipes.filter((r) => `${r.name} ${r.display_name} ${r.tags.join(' ')}`.toLowerCase().includes(recipeSearch.toLowerCase())), [recipes, recipeSearch]);
  const groupedOperations = useMemo(() => {
    const map = new Map<string, OperationSpec[]>();
    for (const op of operations.filter((o) => `${o.name} ${o.display_name}`.toLowerCase().includes(operationSearch.toLowerCase()))) {
      const items = map.get(op.category) ?? []; items.push(op); map.set(op.category, items);
    }
    return [...map.entries()].sort(([a],[b]) => a.localeCompare(b));
  }, [operations, operationSearch]);
  const canvas = useMemo(() => buildCanvas(record), [record]);

  const validate = async () => {
    if (!record) return;
    setBusy(true); setError(null); setMessage(null);
    try {
      const response = record.kind === 'linear' && record.pipeline
        ? await (await import('../api')).pipelinesApi.validate(record.pipeline)
        : record.graph ? await workflowApi.validate(record.graph) : null;
      setMessage(response?.valid ? 'Validation passed.' : 'Validation completed.');
    } catch (e) { setError(errorMessage(e)); }
    finally { setBusy(false); }
  };

  const runWithFile = async (file: File) => {
    if (!record) return;
    setBusy(true); setError(null); setResult(null); setPreviewTab('Preview');
    try {
      const artifactInputs = record.kind === 'linear' ? record.pipeline?.inputs : record.graph?.inputs;
      const imageInput = artifactInputs?.find((i) => i.kind === 'image' || i.kind === 'mask')?.name ?? 'image';
      const response = await recipesApi.execute(record.name, {
        image_inputs: [{ input_name: imageInput, file_index: 0 }],
        retain_intermediates: true,
        analyze_intermediates: false,
      }, [file]);
      if (response instanceof Blob) throw new Error('JSON 응답이 필요합니다.');
      setResult(response);
      setMessage(response.success ? 'Recipe execution completed.' : 'Recipe execution failed.');
    } catch (e) { setError(errorMessage(e)); }
    finally { setBusy(false); if (fileRef.current) fileRef.current.value = ''; }
  };

  const clone = async () => {
    if (!record) return;
    const name = window.prompt('새 Recipe name (영문 소문자/숫자/underscore)', `${record.name}_copy`);
    if (!name) return;
    setBusy(true); setError(null);
    try { const cloned = await recipesApi.clone(record.name, { name }); await loadLists(); setSelectedName(cloned.name); }
    catch (e) { setError(errorMessage(e)); }
    finally { setBusy(false); }
  };

  const save = async () => {
    if (!record || record.readonly) return;
    setBusy(true); setError(null);
    try {
      const updated = await recipesApi.update(record.name, { kind: record.kind, pipeline: record.pipeline, graph: record.graph, tags: record.tags, expected_revision: record.revision });
      setRecord(updated); setMessage(`Saved revision ${updated.revision}.`); await loadLists();
    } catch (e) { setError(errorMessage(e)); }
    finally { setBusy(false); }
  };

  const remove = async () => {
    if (!record || record.readonly || !window.confirm(`${record.name} Recipe을 삭제할까요?`)) return;
    setBusy(true); setError(null);
    try { await recipesApi.remove(record.name, record.revision); setSelectedName(''); setRecord(null); await loadLists(); }
    catch (e) { setError(errorMessage(e)); }
    finally { setBusy(false); }
  };

  const outputImages = result ? Object.entries(result.output?.images ?? {}) : [];
  const intermediateImages = result ? Object.entries(result.intermediates ?? {}).flatMap(([step, out]) => Object.entries(out.images ?? {}).map(([name, img]) => [`${step}.${name}`, img] as const)) : [];

  return <div className="page">
    <input ref={fileRef} type="file" accept="image/*" hidden onChange={(e) => e.target.files?.[0] && void runWithFile(e.target.files[0])}/>
    <div className="page-toolbar">
      <div className="page-title">Recipe Studio</div>{record && <Badge status={record.kind === 'graph' ? 'running' : 'completed'}>{record.kind}</Badge>}
      <span className="page-subtitle">{record ? `${record.name} · rev ${record.revision}` : 'Recipe를 선택하세요'}</span>
      <Button onClick={clone} disabled={!record || busy}>Clone</Button><Button onClick={validate} disabled={!record || busy}>Validate</Button>
      <Button variant="primary" onClick={() => fileRef.current?.click()} disabled={!record || busy}>Run</Button>
      <Button onClick={save} disabled={!record || record.readonly || busy}>Save</Button><Button variant="danger" onClick={remove} disabled={!record || record.readonly || busy}>Delete</Button>
    </div>
    {(error || message) && <div className="status-strip">{error ? <InlineError message={error}/> : <span className="status-ok">{message}</span>}</div>}
    <div className="page-content" style={{overflow:'hidden'}}>
      <div className="recipe-layout">
        <div className="recipe-left">
          <Panel title="Recipes" actions={<span className="panel-subtitle">{recipes.length}</span>} flush>
            <div style={{padding:8}}><SearchInput placeholder="Recipe 검색" value={recipeSearch} onChange={(e)=>setRecipeSearch(e.target.value)}/></div>
            <div className="list" style={{overflow:'auto', height:'calc(100% - 46px)'}}>{loading ? <Loading/> : filteredRecipes.length ? filteredRecipes.map((r) => <button className={`list-item list-button ${selectedName===r.name?'active':''}`} key={r.name} onClick={()=>setSelectedName(r.name)}>
              <span style={{color:selectedName===r.name?'#75a5f4':'#6f7b88'}}>◆</span><div style={{minWidth:0,textAlign:'left'}}><div className="ellipsis">{r.display_name}</div><div className="list-sub">{r.name} · {r.source} · v{r.version}</div></div>
            </button>) : <EmptyState/>}</div>
          </Panel>
          <Panel title="Operation Library" actions={<span className="panel-subtitle">{operations.length} ops · {features.length} features · {operators.length} operators</span>} flush>
            <div style={{padding:8}}><SearchInput placeholder="Operation 검색" value={operationSearch} onChange={(e)=>setOperationSearch(e.target.value)}/></div>
            <div style={{overflow:'auto', height:'calc(100% - 46px)'}}>{groupedOperations.map(([group, items]) => <div key={group}><div className="section-label">▾ {group}</div>{items.map((item) => <button className={`list-item list-button ${selectedOperation?.name===item.name?'active':''}`} key={item.name} onClick={()=>setSelectedOperation(item)}><span style={{color:'#72869f'}}>◇</span><span>{item.display_name}</span><span className="list-meta">{item.name}</span></button>)}</div>)}</div>
          </Panel>
        </div>
        <Panel title="Graph Canvas" subtitle={record ? `${record.name} · rev ${record.revision}` : 'No recipe'} flush>
          {record ? <div className="react-flow-wrap"><ReactFlow nodes={canvas.nodes} edges={canvas.edges} fitView nodesDraggable={false} nodesConnectable={false} elementsSelectable><Background gap={18} size={1}/><MiniMap pannable zoomable/><Controls showInteractive={false}/></ReactFlow></div> : <EmptyState>Recipe를 선택하세요.</EmptyState>}
        </Panel>
        <Panel title="Inspector" subtitle={selectedOperation?.display_name ?? record?.name ?? ''} flush>
          <Tabs items={['Parameters','Info']} active="Parameters"/>
          {selectedOperation ? <div className="inspector-section">
            <div className="inspector-heading">{selectedOperation.name}</div>
            {Object.entries(selectedOperation.parameters).map(([name,p]) => <Field key={name} label={p.title || name} help={`${p.type}${p.unit ? ` · ${p.unit}` : ''}`}><input className="input" value={String(p.default ?? '')} readOnly/></Field>)}
            <div className="divider"/><div className="inspector-heading">I/O</div><div className="mono-small">Inputs: {selectedOperation.inputs.map(i=>`${i.name}:${i.kind}`).join(', ') || '-'}<br/>Outputs: {selectedOperation.outputs.map(o=>`${o.name}:${o.kind}`).join(', ') || '-'}</div>
          </div> : record ? <div className="inspector-section"><div className="inspector-heading">Recipe</div><div className="mono-small">kind: {record.kind}<br/>source: {record.source}<br/>readonly: {String(record.readonly)}<br/>tags: {record.tags.join(', ') || '-'}<br/><br/>{(record.pipeline?.description ?? record.graph?.description) || 'No description'}</div></div> : <EmptyState/>}
        </Panel>
        <Panel className="preview-panel" flush>
          <Tabs items={['Preview','Intermediate','Data','Logs']} active={previewTab} onChange={setPreviewTab}/>
          <div className="preview-grid api-preview-grid">
            {previewTab === 'Preview' && (outputImages.length ? outputImages.map(([name,img]) => <div className="preview-card" key={name}><div className="preview-image real"><img src={imageDataUrl(img)} alt={name}/></div><div className="preview-caption"><span>{name}</span><span>{img.width}×{img.height} · {img.color_space}</span></div></div>) : <EmptyState>Run을 실행하면 결과 이미지가 표시됩니다.</EmptyState>)}
            {previewTab === 'Intermediate' && (intermediateImages.length ? intermediateImages.map(([name,img]) => <div className="preview-card" key={name}><div className="preview-image real"><img src={imageDataUrl(img)} alt={name}/></div><div className="preview-caption"><span>{name}</span><span>{img.width}×{img.height}</span></div></div>) : <EmptyState>Intermediate 결과가 없습니다.</EmptyState>)}
            {previewTab === 'Data' && <pre className="json-view">{JSON.stringify(result?.output?.data ?? {}, null, 2)}</pre>}
            {previewTab === 'Logs' && <div className="log-view">{result ? `success=${result.success}\n${JSON.stringify(result.metadata ?? {}, null, 2)}\n${result.error ? JSON.stringify(result.error,null,2) : ''}` : 'No execution yet.'}</div>}
          </div>
        </Panel>
      </div>
    </div>
  </div>;
}
