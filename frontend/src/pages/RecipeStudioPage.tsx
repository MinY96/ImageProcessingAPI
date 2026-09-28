import { useEffect, useMemo, useRef, useState } from 'react';
import type { Connection, Edge } from '@xyflow/react';

import {
  ApiError,
  modelsApi,
  operationsApi,
  pipelinesApi,
  recipesApi,
  workflowApi,
  type ExecutionResponse,
  type FeatureSpec,
  type GraphNodeSpec,
  type ModelSpec,
  type OperationSpec,
  type RecipeRecord,
  type RecipeSummary,
  type ScalarOperatorSpec,
} from '../api';
import { Badge, Button, EmptyState, InlineError, Loading, Panel, SearchInput, Tabs } from '../components/ui';
import { SaveImageButton } from '../components/SaveImageButton';
import {
  createDraftRecipe,
  deepClone,
  defaultGraphNode,
  defaultsFromParameters,
  kindsCompatible,
  cleanupLinearOrder,
  linearSourceOptions,
  nodeInterface,
  pipelineStepInterface,
  removeLinearStep,
  subrecipeInterfaceFromRecord,
  uniqueId,
  type RecipeSelection,
  type SubrecipeInterface,
} from '../features/recipe-studio/editor';
import { InspectorPanel } from '../features/recipe-studio/InspectorPanel';
import { LibraryPanel, type LibrarySelection } from '../features/recipe-studio/LibraryPanel';
import { NewRecipeModal, RunRecipeModal, type RecipeRunPayload } from '../features/recipe-studio/RecipeModals';
import { StudioCanvas } from '../features/recipe-studio/StudioCanvas';
import { errorMessage, imageDataUrl } from '../lib/format';

function sameRecipe(a: RecipeRecord | null, b: RecipeRecord | null): boolean {
  return JSON.stringify(a) === JSON.stringify(b);
}

function validationDetail(error: unknown): unknown {
  if (error instanceof ApiError) return error.detail;
  return { message: errorMessage(error) };
}

type ValidationIssue = { location: string; code?: string; message?: string };
function validationIssues(value: unknown): ValidationIssue[] {
  if (!value || typeof value !== 'object') return [];
  const object=value as Record<string,unknown>;
  const error=object.error && typeof object.error==='object' ? object.error as Record<string,unknown> : null;
  const details=error?.details && typeof error.details==='object' ? error.details as Record<string,unknown> : null;
  const candidates=[object.issues,error?.issues,details?.issues];
  const issues=candidates.find(Array.isArray) as unknown[]|undefined;
  return (issues??[]).filter((item):item is ValidationIssue=>Boolean(item&&typeof item==='object'&&typeof (item as ValidationIssue).location==='string'));
}

export function RecipeStudioPage() {
  const [recipes, setRecipes] = useState<RecipeSummary[]>([]);
  const [operations, setOperations] = useState<OperationSpec[]>([]);
  const [features, setFeatures] = useState<FeatureSpec[]>([]);
  const [operators, setOperators] = useState<ScalarOperatorSpec[]>([]);
  const [models, setModels] = useState<ModelSpec[]>([]);
  const [subrecipes, setSubrecipes] = useState<Map<string, SubrecipeInterface>>(new Map());

  const [selectedName, setSelectedName] = useState('');
  const [record, setRecord] = useState<RecipeRecord | null>(null);
  const [baseRecord, setBaseRecord] = useState<RecipeRecord | null>(null);
  const [isNew, setIsNew] = useState(false);
  const [selection, setSelection] = useState<RecipeSelection>({ type: 'recipe' });
  const [selectedNodeIds, setSelectedNodeIds] = useState<string[]>([]);
  const [librarySelection, setLibrarySelection] = useState<LibrarySelection>(null);
  const [positions, setPositions] = useState<Map<string, { x: number; y: number }>>(new Map());
  const [undoStack, setUndoStack] = useState<RecipeRecord[]>([]);
  const [redoStack, setRedoStack] = useState<RecipeRecord[]>([]);
  const [clipboard, setClipboard] = useState<GraphNodeSpec[]>([]);

  const [recipeSearch, setRecipeSearch] = useState('');
  const [recipeKind, setRecipeKind] = useState<'all' | 'linear' | 'graph'>('all');
  const [recipeSource, setRecipeSource] = useState<'all' | 'builtin' | 'user'>('all');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [result, setResult] = useState<ExecutionResponse | null>(null);
  const [validation, setValidation] = useState<unknown | null>(null);
  const [focusNodeId, setFocusNodeId] = useState<string | null>(null);
  const [previewTab, setPreviewTab] = useState('Preview');
  const [showNew, setShowNew] = useState(false);
  const [showRun, setShowRun] = useState(false);

  const opMap = useMemo(() => new Map(operations.map((item) => [item.name, item])), [operations]);
  const featureMap = useMemo(() => new Map(features.map((item) => [item.name, item])), [features]);
  const operatorMap = useMemo(() => new Map(operators.map((item) => [item.name, item])), [operators]);
  const dirty = Boolean(record) && (isNew || !sameRecipe(record, baseRecord));

  const loadLists = async () => {
    setLoading(true); setError(null);
    try {
      const [r, o, f, so, m] = await Promise.all([
        recipesApi.list(), operationsApi.list(), workflowApi.features(), workflowApi.operators(), modelsApi.list(),
      ]);
      setRecipes(r); setOperations(o); setFeatures(f); setOperators(so); setModels(m);
      return r;
    } catch (e) {
      setError(errorMessage(e)); return [];
    } finally { setLoading(false); }
  };

  const cacheSubrecipe = async (name: string) => {
    if (!name || subrecipes.has(name)) return;
    try {
      const child = await recipesApi.get(name);
      setSubrecipes((prev) => {
        const next = new Map(prev); next.set(name, subrecipeInterfaceFromRecord(child)); return next;
      });
    } catch { /* validation will surface missing subrecipe */ }
  };

  const adoptRecord = (next: RecipeRecord, options?: { isNew?: boolean }) => {
    setRecord(deepClone(next));
    setBaseRecord(options?.isNew ? null : deepClone(next));
    setIsNew(Boolean(options?.isNew));
    setSelectedName(next.name);
    setSelection({ type: 'recipe' });
    setLibrarySelection(null);
    setPositions(new Map());
    setUndoStack([]); setRedoStack([]); setSelectedNodeIds([]); setFocusNodeId(null);
    setResult(null); setValidation(null); setMessage(null); setError(null);
    for (const node of next.graph?.nodes ?? []) if (node.recipe) void cacheSubrecipe(node.recipe);
  };

  const chooseRecipe = async (name: string) => {
    if (name === selectedName && record) return;
    if (dirty && !window.confirm('저장하지 않은 변경사항이 있습니다. 버리고 다른 Recipe를 열까요?')) return;
    setBusy(true); setError(null);
    try { adoptRecord(await recipesApi.get(name)); }
    catch (e) { setError(errorMessage(e)); }
    finally { setBusy(false); }
  };

  useEffect(() => {
    void (async () => {
      const list = await loadLists();
      if (list.length) {
        try { adoptRecord(await recipesApi.get(list[0].name)); }
        catch (e) { setError(errorMessage(e)); }
      }
    })();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const handler = (event: BeforeUnloadEvent) => { if (dirty) event.preventDefault(); };
    window.addEventListener('beforeunload', handler);
    return () => window.removeEventListener('beforeunload', handler);
  }, [dirty]);

  const filteredRecipes = useMemo(() => {
    const q = recipeSearch.trim().toLowerCase();
    return recipes.filter((item) => {
      if (recipeKind !== 'all' && item.kind !== recipeKind) return false;
      if (recipeSource !== 'all' && item.source !== recipeSource) return false;
      return !q || `${item.name} ${item.display_name} ${item.tags.join(' ')}`.toLowerCase().includes(q);
    });
  }, [recipes, recipeSearch, recipeKind, recipeSource]);

  const updateRecord = (next: RecipeRecord) => {
    if (record && JSON.stringify(record)!==JSON.stringify(next)) setUndoStack((items)=>[...items,deepClone(record)].slice(-100));
    setRedoStack([]);
    setRecord(next); setMessage(null); setError(null); setValidation(null);
  };

  const undo = () => {
    if(!record||!undoStack.length)return;
    const previous=undoStack[undoStack.length-1];
    setRedoStack((items)=>[...items,deepClone(record)].slice(-100));
    setUndoStack((items)=>items.slice(0,-1)); setRecord(deepClone(previous)); setSelectedNodeIds([]); setSelection({type:'recipe'}); setValidation(null); setError(null);
  };

  const redo = () => {
    if(!record||!redoStack.length)return;
    const next=redoStack[redoStack.length-1];
    setUndoStack((items)=>[...items,deepClone(record)].slice(-100));
    setRedoStack((items)=>items.slice(0,-1)); setRecord(deepClone(next)); setSelectedNodeIds([]); setSelection({type:'recipe'}); setValidation(null); setError(null);
  };

  const addLinearOperation = (spec: OperationSpec) => {
    if (!record?.pipeline || record.readonly) return;
    const next = deepClone(record);
    const pipeline = next.pipeline!;
    const id = uniqueId(spec.name, pipeline.steps.map((item) => item.id));
    const inputs: NonNullable<typeof pipeline.steps[number]['inputs']> = {};
    for (const slot of spec.inputs) {
      const options = linearSourceOptions(pipeline, pipeline.steps.length, slot.kind, opMap);
      if (options.length) inputs[slot.name] = options[options.length - 1].reference;
    }
    pipeline.steps.push({ id, operation: spec.name, inputs, params: defaultsFromParameters(spec.parameters) });
    updateRecord(next); setSelection({ type: 'node', id });
  };

  const addGraphNode = (node: ReturnType<typeof defaultGraphNode>) => {
    if (!record?.graph || record.readonly) return;
    const next = deepClone(record); next.graph!.nodes.push(node);
    updateRecord(next); setSelection({ type: 'node', id: node.id });
    if (node.recipe) void cacheSubrecipe(node.recipe);
  };

  const addAnnotationNode = (type:'group'|'comment') => {
    if(!record?.graph||record.readonly)return;
    const members=type==='group'?selectedNodeIds.filter((id)=>record.graph!.nodes.some((node)=>node.id===id&&node.node_type!=='group'&&node.node_type!=='comment')):[];
    if(type==='group'&&!members.length){setError('그룹으로 묶을 Graph Node를 Shift 클릭으로 먼저 선택하세요.');return;}
    const id=uniqueId(type,record.graph.nodes.map((node)=>node.id));
    const node:GraphNodeSpec=type==='group'?{id,node_type:'group',label:'New Group',members,inputs:{},params:{}}:{id,node_type:'comment',label:'Comment',text:'메모를 입력하세요.',inputs:{},params:{}};
    const next=deepClone(record);if(type==='group')for(const existing of next.graph!.nodes)if(existing.node_type==='group')existing.members=(existing.members??[]).filter((member)=>!members.includes(member));next.graph!.nodes.push(node);updateRecord(next);setSelection({type:'node',id});setSelectedNodeIds([id]);
    setPositions((current)=>{const positioned=new Map(current);positioned.set(id,{x:285,y:400});return positioned;});
  };

  const deleteNodeIds = (ids:string[]) => {
    if(!record||record.readonly||!ids.length)return;
    let next=deepClone(record);
    if(next.kind==='graph'){
      const removing=new Set(ids);
      next.graph!.nodes=next.graph!.nodes.filter((node)=>!removing.has(node.id));
      for(const node of next.graph!.nodes){
        node.inputs=Object.fromEntries(Object.entries(node.inputs??{}).filter(([,ref])=>ref.type!=='node_output'||!removing.has(ref.node_id)));
        if(node.node_type==='group')node.members=(node.members??[]).filter((id)=>!removing.has(id));
      }
      next.graph!.outputs=Object.fromEntries(Object.entries(next.graph!.outputs).filter(([,ref])=>ref.type!=='node_output'||!removing.has(ref.node_id)));
    }else{
      for(const id of ids)next=removeLinearStep(next,id);
      next=cleanupLinearOrder(next);
    }
    updateRecord(next);setSelectedNodeIds([]);setSelection({type:'recipe'});
  };

  const copySelectedNodes = () => {
    if(record?.kind!=='graph')return;
    const nodes=record.graph!.nodes.filter((node)=>selectedNodeIds.includes(node.id)&&node.node_type!=='group');
    setClipboard(deepClone(nodes));
  };

  const pasteNodes = () => {
    if(!record?.graph||record.readonly||!clipboard.length)return;
    const next=deepClone(record);const existing=next.graph!.nodes.map((node)=>node.id);const remap=new Map<string,string>();
    for(const node of clipboard)remap.set(node.id,uniqueId(`${node.id}_copy`,[...existing,...remap.values()]));
    const copies=deepClone(clipboard).map((node)=>{
      node.id=remap.get(node.id)!;
      node.inputs=Object.fromEntries(Object.entries(node.inputs??{}).map(([name,ref])=>[name,ref.type==='node_output'&&remap.has(ref.node_id)?{...ref,node_id:remap.get(ref.node_id)!}:ref]));
      if(node.node_type==='group')node.members=(node.members??[]).map((id)=>remap.get(id)??id);
      return node;
    });
    next.graph!.nodes.push(...copies);updateRecord(next);
    const selected=copies.map((node)=>node.id);setSelectedNodeIds(selected);if(selected.length===1)setSelection({type:'node',id:selected[0]});
    setPositions((current)=>{const positioned=new Map(current);clipboard.forEach((node,index)=>{const old=current.get(node.id)??{x:285+index*30,y:220+index*30};positioned.set(remap.get(node.id)!,{x:old.x+48,y:old.y+48});});return positioned;});
  };

  const autoLayout = () => {
    if(!record)return;
    const layout=new Map<string,{x:number;y:number}>();
    if(record.kind==='linear'){
      record.pipeline!.inputs.forEach((input,index)=>layout.set(`__input__${input.name}`,{x:20,y:70+index*110}));
      record.pipeline!.steps.forEach((step,index)=>layout.set(step.id,{x:260+index*230,y:90+(index%2)*95}));
      Object.keys(record.pipeline!.outputs).forEach((name,index)=>layout.set(`__output__${name}`,{x:Math.max(560,300+record.pipeline!.steps.length*230),y:70+index*100}));
    }else{
      const graph=record.graph!;const nodeMap=new Map(graph.nodes.map((node)=>[node.id,node]));const level=new Map<string,number>();const depth=(id:string,stack=new Set<string>()):number=>{
        if(level.has(id))return level.get(id)!;if(stack.has(id))return 0;const node=nodeMap.get(id);if(!node)return 0;const parents=Object.values(node.inputs??{}).filter((ref)=>ref.type==='node_output').map((ref)=>ref.node_id).filter((parent)=>nodeMap.get(parent)?.node_type!=='group'&&nodeMap.get(parent)?.node_type!=='comment');
        const result=parents.length?1+Math.max(...parents.map((parent)=>depth(parent,new Set([...stack,id])))):0;level.set(id,result);return result;
      };
      const lane=new Map<number,number>();for(const node of graph.nodes.filter((item)=>item.node_type!=='group'&&item.node_type!=='comment')){const x=depth(node.id);const row=lane.get(x)??0;lane.set(x,row+1);layout.set(node.id,{x:255+x*255,y:60+row*155});}
      graph.inputs.forEach((input,index)=>layout.set(`__input__${input.name}`,{x:15,y:65+index*105}));
      const end=Math.max(0,...Array.from(level.values()));Object.keys(graph.outputs).forEach((name,index)=>layout.set(`__output__${name}`,{x:300+(end+1)*255,y:65+index*105}));
      graph.nodes.filter((node)=>node.node_type==='comment').forEach((node,index)=>layout.set(node.id,{x:265+index*240,y:460}));
    }
    setPositions(layout);setMessage('Canvas를 자동 배치했습니다.');
  };

  const actionRef=useRef({undo,redo,copySelectedNodes,pasteNodes});
  actionRef.current={undo,redo,copySelectedNodes,pasteNodes};
  useEffect(()=>{
    const handler=(event:KeyboardEvent)=>{
      const target=event.target as HTMLElement|null;
      if(target?.closest('input,textarea,select,[contenteditable="true"]'))return;
      const key=event.key.toLowerCase();
      if((event.ctrlKey||event.metaKey)&&key==='z'){event.preventDefault();if(event.shiftKey)actionRef.current.redo();else actionRef.current.undo();}
      else if((event.ctrlKey||event.metaKey)&&key==='y'){event.preventDefault();actionRef.current.redo();}
      else if((event.ctrlKey||event.metaKey)&&key==='c'){event.preventDefault();actionRef.current.copySelectedNodes();}
      else if((event.ctrlKey||event.metaKey)&&key==='v'){event.preventDefault();actionRef.current.pasteNodes();}
      else if(event.key==='Escape'){setSelectedNodeIds([]);setSelection({type:'recipe'});}
    };
    window.addEventListener('keydown',handler);return()=>window.removeEventListener('keydown',handler);
  },[]);

  const validate = async () => {
    if (!record) return;
    if (record.kind === 'linear' && !record.pipeline?.steps.length) { setError('Linear Recipe에는 Step이 하나 이상 필요합니다.'); return; }
    if (record.kind === 'graph' && !record.graph?.nodes.length) { setError('Graph Recipe에는 Node가 하나 이상 필요합니다.'); return; }
    setBusy(true); setError(null); setMessage(null); setValidation(null);
    try {
      const response = record.kind === 'linear'
        ? await pipelinesApi.validate(record.pipeline!)
        : await workflowApi.validate(record.graph!);
      setValidation(response); setMessage('Validation passed.'); setPreviewTab('Validation');
    } catch (e) {
      setValidation(validationDetail(e)); setError('Validation failed. 아래 Validation 탭에서 상세 내용을 확인하세요.'); setPreviewTab('Validation');
    } finally { setBusy(false); }
  };

  const save = async () => {
    if (!record || record.readonly) return;
    if (record.kind === 'linear' && !record.pipeline?.steps.length) { setError('Step을 하나 이상 추가한 후 저장하세요.'); return; }
    if (record.kind === 'graph' && !record.graph?.nodes.length) { setError('Node를 하나 이상 추가한 후 저장하세요.'); return; }
    setBusy(true); setError(null); setMessage(null);
    try {
      const body = { kind: record.kind, pipeline: record.pipeline, graph: record.graph, tags: record.tags };
      const saved = isNew
        ? await recipesApi.create(body)
        : await recipesApi.update(record.name, { ...body, expected_revision: record.revision });
      adoptRecord(saved);
      await loadLists();
      setMessage(`Saved revision ${saved.revision}.`);
    } catch (e) {
      setError(errorMessage(e));
    } finally { setBusy(false); }
  };

  const reload = async () => {
    if (!record || isNew) return;
    if (dirty && !window.confirm('현재 변경사항을 버리고 서버의 최신 Recipe를 다시 불러올까요?')) return;
    setBusy(true);
    try { adoptRecord(await recipesApi.get(record.name)); setMessage('Recipe reloaded.'); }
    catch (e) { setError(errorMessage(e)); }
    finally { setBusy(false); }
  };

  const clone = async () => {
    if (!record) return;
    const name = window.prompt('새 Recipe name (영문 소문자/숫자/underscore)', `${record.name}_copy`);
    if (!name) return;
    setBusy(true); setError(null);
    try {
      const cloned = await recipesApi.clone(record.name, { name });
      await loadLists(); adoptRecord(cloned); setMessage(`Cloned from ${record.name}.`);
    } catch (e) { setError(errorMessage(e)); }
    finally { setBusy(false); }
  };

  const remove = async () => {
    if (!record || record.readonly) return;
    if (isNew) { setRecord(null); setBaseRecord(null); setIsNew(false); setSelectedName(''); return; }
    if (!window.confirm(`${record.name} Recipe을 삭제할까요?`)) return;
    setBusy(true); setError(null);
    try {
      await recipesApi.remove(record.name, record.revision);
      const list = await loadLists();
      if (list.length) adoptRecord(await recipesApi.get(list[0].name));
      else { setRecord(null); setBaseRecord(null); setSelectedName(''); }
    } catch (e) { setError(errorMessage(e)); }
    finally { setBusy(false); }
  };

  const runDraft = async (payload: RecipeRunPayload, files: File[]) => {
    if (!record) return;
    setShowRun(false); setBusy(true); setError(null); setMessage(null); setResult(null); setPreviewTab('Preview');
    try {
      const response = record.kind === 'linear'
        ? await pipelinesApi.executeDraft({ ...payload, pipeline: record.pipeline }, files)
        : await workflowApi.execute({ ...payload, graph: record.graph }, files);
      if (response instanceof Blob) throw new Error('JSON response가 필요합니다.');
      setResult(response); setMessage(response.success ? 'Draft execution completed.' : 'Draft execution failed.');
    } catch (e) { setError(errorMessage(e)); }
    finally { setBusy(false); }
  };

  const sourceKind = (sourceId: string, handle: string | null): string => {
    if (!record) return 'unknown';
    if (sourceId.startsWith('__input__')) return (record.kind === 'linear' ? record.pipeline!.inputs : record.graph!.inputs).find((item) => item.name === sourceId.slice('__input__'.length))?.kind ?? 'unknown';
    if (record.kind === 'linear') {
      const step = record.pipeline!.steps.find((item) => item.id === sourceId);
      return opMap.get(step?.operation ?? '')?.outputs.find((item) => item.name === handle)?.kind ?? 'unknown';
    }
    const node = record.graph!.nodes.find((item) => item.id === sourceId);
    return node ? nodeInterface(node, opMap, featureMap, operatorMap, subrecipes).outputs.find((item) => item.name === handle)?.kind ?? 'unknown' : 'unknown';
  };

  const targetKind = (targetId: string, handle: string | null): string => {
    if (!record || !handle) return 'unknown';
    if (targetId.startsWith('__output__')) return 'unknown';
    if (record.kind === 'linear') {
      const step = record.pipeline!.steps.find((item) => item.id === targetId);
      return step ? pipelineStepInterface(step, opMap).inputs.find((item) => item.name === handle)?.kind ?? 'unknown' : 'unknown';
    }
    const node = record.graph!.nodes.find((item) => item.id === targetId);
    return node ? nodeInterface(node, opMap, featureMap, operatorMap, subrecipes).inputs.find((item) => item.name === handle)?.kind ?? 'unknown' : 'unknown';
  };

  const connect = (connection: Connection) => {
    if (!record || record.readonly || !connection.source || !connection.target || !connection.sourceHandle || !connection.targetHandle) return;
    const sKind = sourceKind(connection.source, connection.sourceHandle);
    const tKind = targetKind(connection.target, connection.targetHandle);
    if (!connection.target.startsWith('__output__') && !kindsCompatible(sKind, tKind)) {
      setError(`연결할 수 없는 Data Kind입니다: ${sKind} → ${tKind}`); return;
    }
    const next = deepClone(record);
    if (record.kind === 'graph') {
      const sourceRef = connection.source.startsWith('__input__')
        ? { type: 'graph_input' as const, input_name: connection.source.slice('__input__'.length) }
        : { type: 'node_output' as const, node_id: connection.source, output_name: connection.sourceHandle };
      if (connection.target.startsWith('__output__')) next.graph!.outputs[connection.target.slice('__output__'.length)] = sourceRef;
      else {
        const target = next.graph!.nodes.find((item) => item.id === connection.target); if (!target) return;
        target.inputs ??= {}; target.inputs[connection.targetHandle] = sourceRef;
      }
    } else {
      const sourceRef = connection.source.startsWith('__input__')
        ? { type: 'pipeline_input' as const, input_name: connection.source.slice('__input__'.length) }
        : { type: 'step_output' as const, step_id: connection.source, output_name: connection.sourceHandle };
      if (connection.target.startsWith('__output__')) next.pipeline!.outputs[connection.target.slice('__output__'.length)] = sourceRef;
      else {
        const sourceIndex = next.pipeline!.steps.findIndex((item) => item.id === connection.source);
        const targetIndex = next.pipeline!.steps.findIndex((item) => item.id === connection.target);
        if (!connection.source.startsWith('__input__') && sourceIndex >= targetIndex) { setError('Linear Pipeline은 이전 Step의 output만 연결할 수 있습니다.'); return; }
        const target = next.pipeline!.steps[targetIndex]; if (!target) return;
        target.inputs ??= {}; target.inputs[connection.targetHandle] = sourceRef;
      }
    }
    updateRecord(next);
  };

  const deleteEdge = (edge: Edge) => {
    if (!record || record.readonly) return;
    const data = edge.data as { targetType?: string; targetId?: string; targetInput?: string } | undefined;
    if (!data?.targetId) return;
    const next = deepClone(record);
    if (data.targetType === 'output') {
      if (next.kind === 'linear') delete next.pipeline!.outputs[data.targetId];
      else delete next.graph!.outputs[data.targetId];
      if (selection.type === 'output' && selection.name === data.targetId) setSelection({ type: 'recipe' });
    } else if (data.targetType === 'node' && data.targetInput) {
      if (next.kind === 'linear') {
        const target = next.pipeline!.steps.find((item) => item.id === data.targetId); if (target?.inputs) delete target.inputs[data.targetInput];
      } else {
        const target = next.graph!.nodes.find((item) => item.id === data.targetId); if (target?.inputs) delete target.inputs[data.targetInput];
      }
    }
    updateRecord(next);
  };

  const outputImages = result ? Object.entries(result.output?.images ?? {}) : [];
  const intermediateImages = result ? Object.entries(result.intermediates ?? {}).flatMap(([step, out]) => Object.entries(out.images ?? {}).map(([name, img]) => [`${step}.${name}`, img] as const)) : [];
  const invalidNodeIds=useMemo(()=>validationIssues(validation).map((issue)=>issue.location.match(/(?:nodes|steps)\.([a-z][a-z0-9_]*)/)?.[1]).filter((id):id is string=>Boolean(id)),[validation]);
  const focusValidationIssue=(issue:ValidationIssue)=>{
    const id=issue.location.match(/(?:nodes|steps)\.([a-z][a-z0-9_]*)/)?.[1];
    if(!id)return;
    setFocusNodeId(id);setSelection({type:'node',id});setSelectedNodeIds([id]);
  };

  return <div className="page">
    <div className="page-toolbar recipe-toolbar">
      <div className="page-title">Recipe Studio</div>
      {record && <Badge status={record.kind === 'graph' ? 'running' : 'completed'}>{record.kind}</Badge>}
      {record?.readonly && <Badge>readonly</Badge>}
      {dirty && <Badge status="warning">unsaved</Badge>}
      <span className="page-subtitle">{record ? `${record.name} · ${isNew ? 'new draft' : `rev ${record.revision}`}` : 'Recipe를 선택하세요'}</span>
      <Button onClick={() => setShowNew(true)} disabled={busy}>New</Button>
      <Button onClick={clone} disabled={!record || busy || isNew}>Clone</Button>
      <Button onClick={reload} disabled={!record || busy || isNew}>Reload</Button>
      <Button onClick={validate} disabled={!record || busy}>Validate</Button>
      <Button variant="primary" onClick={() => setShowRun(true)} disabled={!record || busy}>Run Draft</Button>
      <Button onClick={save} disabled={!record || record.readonly || busy || !dirty}>Save</Button>
      <Button variant="danger" onClick={remove} disabled={!record || record.readonly || busy}>Delete</Button>
    </div>

    {(error || message) && <div className="status-strip">{error ? <InlineError message={error}/> : <span className="status-ok">{message}</span>}</div>}

    <div className="page-content recipe-page-content">
      <div className="recipe-layout enhanced">
        <div className="recipe-left">
          <Panel title="Recipes" actions={<span className="panel-subtitle">{recipes.length}{isNew ? ' + draft' : ''}</span>} flush>
            <div className="recipe-list-controls">
              <SearchInput placeholder="Recipe 검색" value={recipeSearch} onChange={(e) => setRecipeSearch(e.target.value)}/>
              <div className="compact-filters"><select className="select" value={recipeKind} onChange={(e) => setRecipeKind(e.target.value as typeof recipeKind)}><option value="all">All kinds</option><option value="linear">Linear</option><option value="graph">Graph</option></select><select className="select" value={recipeSource} onChange={(e) => setRecipeSource(e.target.value as typeof recipeSource)}><option value="all">All sources</option><option value="builtin">Built-in</option><option value="user">User</option></select></div>
            </div>
            <div className="list recipe-list-scroll">
              {isNew && record && <button className="list-item list-button active"><span className="recipe-kind-icon">✦</span><div className="recipe-list-text"><div className="ellipsis">{record.pipeline?.display_name ?? record.graph?.display_name}</div><div className="list-sub">{record.name} · local draft</div></div><Badge status="warning">new</Badge></button>}
              {loading ? <Loading/> : filteredRecipes.length ? filteredRecipes.map((item) => <button className={`list-item list-button ${!isNew && selectedName === item.name ? 'active' : ''}`} key={item.name} onClick={() => void chooseRecipe(item.name)}>
                <span className="recipe-kind-icon">{item.kind === 'graph' ? '◆' : '━'}</span><div className="recipe-list-text"><div className="ellipsis">{item.display_name}</div><div className="list-sub">{item.name} · {item.source} · v{item.version}</div></div><span className="list-meta">{item.kind === 'graph' ? item.node_count : item.step_count}</span>
              </button>) : <EmptyState>Recipe가 없습니다.</EmptyState>}
            </div>
          </Panel>

          <LibraryPanel
            record={record} operations={operations} features={features} operators={operators} recipes={recipes}
            selected={librarySelection} onSelect={setLibrarySelection}
            onAddOperation={(spec) => record?.kind === 'linear' ? addLinearOperation(spec) : addGraphNode(defaultGraphNode('operation', spec.name, record!, { operation: spec }))}
            onAddFeature={(spec) => record && addGraphNode(defaultGraphNode('feature', spec.name, record, { feature: spec }))}
            onAddOperator={(spec) => record && addGraphNode(defaultGraphNode('scalar_operator', spec.name, record, { operator: spec }))}
            onAddSystem={(name) => record && addGraphNode(defaultGraphNode(name, name, record))}
            onAddSubrecipe={(recipe) => { if (!record) return; void (async () => { await cacheSubrecipe(recipe.name); addGraphNode(defaultGraphNode('subrecipe', recipe.name, record, { recipe })); })(); }}
          />
        </div>

        <Panel title="Recipe Canvas" subtitle={record ? `${record.name} · ${record.kind}` : 'No recipe'} flush>
          {record ? <div className="studio-editor-panel">
            <div className="studio-editor-toolbar">
              <Button title="Undo (Ctrl+Z)" disabled={!undoStack.length||busy||record.readonly} onClick={undo}>↶ Undo</Button>
              <Button title="Redo (Ctrl+Y)" disabled={!redoStack.length||busy||record.readonly} onClick={redo}>↷ Redo</Button>
              <Button onClick={autoLayout} disabled={busy}>Auto layout</Button>
              {record.kind==='graph' && <>
                <Button onClick={copySelectedNodes} disabled={!selectedNodeIds.length}>Copy</Button>
                <Button onClick={pasteNodes} disabled={!clipboard.length||record.readonly}>Paste</Button>
                <Button onClick={()=>addAnnotationNode('group')} disabled={record.readonly||!selectedNodeIds.some((id)=>record.graph!.nodes.some((node)=>node.id===id&&node.node_type!=='group'&&node.node_type!=='comment'))}>Group</Button>
                <Button onClick={()=>addAnnotationNode('comment')} disabled={record.readonly}>Comment</Button>
              </>}
              <Button variant="danger" onClick={()=>deleteNodeIds(selectedNodeIds)} disabled={!selectedNodeIds.length||record.readonly}>Delete selected</Button>
              <span className="studio-editor-hint">Shift+클릭 다중 선택 · Ctrl+C/V 복사/붙여넣기</span>
            </div>
            <div className="studio-editor-canvas"><StudioCanvas
              record={record} operations={opMap} features={featureMap} operators={operatorMap} subrecipes={subrecipes}
              positions={positions} selectedNodeIds={selectedNodeIds} validationErrorNodeIds={invalidNodeIds} focusNodeId={focusNodeId}
              onPositionChange={(id, position) => setPositions((prev) => { const next = new Map(prev); next.set(id, position); return next; })}
              selection={selection} onSelectionChange={setSelection} onConnect={connect} onDeleteEdge={deleteEdge}
              onMultiSelect={setSelectedNodeIds} onDeleteNodes={deleteNodeIds}
            /></div>
          </div> : <EmptyState>Recipe를 선택하거나 New Recipe를 생성하세요.</EmptyState>}
        </Panel>

        <InspectorPanel
          record={record} selection={selection} librarySelection={librarySelection}
          operations={opMap} features={featureMap} operators={operatorMap} recipes={recipes} subrecipes={subrecipes}
          onChange={updateRecord} onSelectionChange={setSelection}
        />

        <Panel className="preview-panel" flush>
          <Tabs items={['Preview', 'Intermediate', 'Data', 'Validation', 'Logs']} active={previewTab} onChange={setPreviewTab}/>
          <div className="preview-grid api-preview-grid">
            {previewTab === 'Preview' && (outputImages.length ? outputImages.map(([name, img]) => <div className="preview-card" key={name}><div className="preview-image real"><img src={imageDataUrl(img)} alt={name}/></div><div className="preview-caption"><span>{name} · {img.width}×{img.height} · {img.color_space}</span><SaveImageButton source={imageDataUrl(img)} fileName={name}/></div></div>) : <EmptyState>Run Draft를 실행하면 output image가 표시됩니다.</EmptyState>)}
            {previewTab === 'Intermediate' && (intermediateImages.length ? intermediateImages.map(([name, img]) => <div className="preview-card" key={name}><div className="preview-image real"><img src={imageDataUrl(img)} alt={name}/></div><div className="preview-caption"><span>{name} · {img.width}×{img.height}</span><SaveImageButton source={imageDataUrl(img)} fileName={name.replaceAll('.', '_')}/></div></div>) : <EmptyState>Intermediate 결과가 없습니다.</EmptyState>)}
            {previewTab === 'Data' && <pre className="json-view">{JSON.stringify(result?.output?.data ?? {}, null, 2)}</pre>}
            {previewTab === 'Validation' && <div className="validation-result-wrap">{validationIssues(validation).length>0&&<div className="validation-issue-list">{validationIssues(validation).map((issue,index)=><button type="button" className="validation-issue" key={`${issue.location}-${index}`} onClick={()=>focusValidationIssue(issue)}><strong>{issue.location}</strong><span>{issue.message??issue.code??'Validation error'}</span></button>)}</div>}<pre className="json-view">{validation ? JSON.stringify(validation, null, 2) : 'Validate를 실행하면 결과가 표시됩니다.'}</pre></div>}
            {previewTab === 'Logs' && <div className="log-view">{result ? `success=${result.success}\n${JSON.stringify(result.metadata ?? {}, null, 2)}\n${result.error ? JSON.stringify(result.error, null, 2) : ''}` : 'No execution yet.'}</div>}
          </div>
        </Panel>
      </div>
    </div>

    {showNew && <NewRecipeModal onClose={() => setShowNew(false)} onCreate={(value) => {
      if (dirty && !window.confirm('현재 변경사항을 버리고 새 Recipe를 만들까요?')) return;
      setShowNew(false); adoptRecord(createDraftRecipe(value), { isNew: true });
    }}/>} 
    {showRun && record && <RunRecipeModal record={record} models={models} onClose={() => setShowRun(false)} onRun={(payload, files) => void runDraft(payload, files)}/>} 
  </div>;
}
