import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { analysisApi, operationsApi, pipelinesApi, recipesApi, workflowApi, type EncodedImage, type ExecutionResponse, type FeatureSpec, type GraphRecipeSpec, type ImageAnalysisResult, type OperationSpec, type PipelineSpec, type RecipeRecord, type RecipeSummary, type ScalarOperatorSpec } from '../api';
import { SaveImageButton } from '../components/SaveImageButton';
import { Button, EmptyState, Field, InlineError, Kpi, Panel, Tabs } from '../components/ui';
import { errorMessage, imageDataUrl, number } from '../lib/format';

const ANALYSIS_TABS = ['Histogram', 'Image Statistics', 'Image Feature', 'Image Analysis'];
const LAB_MODES = ['Operation', 'Features', 'Operators', 'Graph Nodes', 'Quick Run'];
const IMAGE_KINDS = new Set(['image', 'mask', 'template']);

function defaultParams(op: OperationSpec | null): Record<string, unknown> {
  if (!op) return {};
  return Object.fromEntries(Object.entries(op.parameters).filter(([,p]) => p.default !== undefined).map(([name,p]) => [name,p.default]));
}

function defaultFeatureParams(feature: FeatureSpec | null): Record<string, unknown> {
  if (!feature) return {};
  return Object.fromEntries(Object.entries(feature.parameters).filter(([,p]) => p.default !== undefined).map(([name,p]) => [name,p.default]));
}

function operatorInputNames(operator: ScalarOperatorSpec, requestedCount = operator.min_inputs): string[] {
  const names = [...operator.required_input_names];
  const count = Math.max(operator.min_inputs, names.length, requestedCount);
  for (let index = names.length; index < count; index += 1) names.push(`value_${index + 1}`);
  return names;
}

function normalizePortKind(kind: string): string {
  return kind === 'markers' || kind === 'points' ? 'array' : kind === 'model' ? 'metrics' : kind;
}

function encodedImageFile(image: EncodedImage, name: string): File {
  const binary = atob(image.data ?? '');
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
  return new File([bytes], name, { type: image.media_type || 'image/png' });
}

function useObjectUrl(blob: Blob | null) {
  const [url, setUrl] = useState('');
  useEffect(() => {
    if (!blob) { setUrl(''); return; }
    const next = URL.createObjectURL(blob);
    setUrl(next);
    return () => URL.revokeObjectURL(next);
  }, [blob]);
  return url;
}

function ObjectImage({ file, alt }: { file: File; alt: string }) {
  const url = useObjectUrl(file);
  return url ? <img className="lab-image" src={url} alt={alt}/> : null;
}

function AnalysisDetails({ analysis, active }: { analysis: ImageAnalysisResult | null; active: string }) {
  if (!analysis) return <EmptyState>이미지를 선택하고 Analyze를 실행하세요.</EmptyState>;
  if (active === 'Histogram') {
    const histogram = analysis.histograms.gray ?? Object.values(analysis.histograms.rgb)[0];
    if (!histogram) return <EmptyState>표시할 histogram이 없습니다.</EmptyState>;
    const sample = histogram.counts.length > 64 ? histogram.counts.filter((_, i) => i % Math.ceil(histogram.counts.length / 64) === 0) : histogram.counts;
    const max = Math.max(...sample, 1);
    return <div className="lab-histogram" aria-label={`${histogram.channel} histogram`}>{sample.map((value, i) => <span key={i} title={`${i}: ${value}`} style={{ height: `${Math.max(2, value / max * 100)}%` }}/>)}</div>;
  }
  if (active === 'Image Statistics') {
    const s = analysis.intensity_statistics;
    return <div className="lab-stat-grid"><Kpi label="Mean" value={number(s.mean)}/><Kpi label="Std" value={number(s.std)}/><Kpi label="Min / Max" value={`${number(s.minimum)} / ${number(s.maximum)}`}/><Kpi label="Dynamic range" value={number(s.dynamic_range)}/></div>;
  }
  if (active === 'Image Feature') {
    const features = Object.entries(analysis.features ?? {});
    return features.length ? <div className="lab-feature-list">{features.map(([key, value]) => <div key={key}><span>{key.replaceAll('_', ' ')}</span><strong>{typeof value === 'number' ? number(value, 4) : String(value ?? '-')}</strong></div>)}</div> : <EmptyState>Feature 결과가 없습니다.</EmptyState>;
  }
  const m = analysis.metadata;
  return <div className="lab-analysis-list"><span>Size</span><strong>{m.width} × {m.height}</strong><span>Channels / bit depth</span><strong>{m.channels} / {m.bit_depth_per_channel} bit</strong><span>Pixels / decoded</span><strong>{m.pixel_count.toLocaleString()} / {(m.decoded_size_bytes / 1024 / 1024).toFixed(2)} MB</strong><span>Color space / dtype</span><strong>{m.color_space} / {m.dtype}</strong><span>Profile data</span><strong>{Object.keys(analysis.profiles ?? {}).length ? 'Available' : 'None'}</strong></div>;
}

function ImageViewer({
  title, subtitle, src, saveSource, analysis, onAnalyze, loading, onApply, applyDisabled, fallback,
}: {
  title: string; subtitle: string; src?: string; saveSource?: Blob | string | null;
  analysis: ImageAnalysisResult | null; onAnalyze?: () => void; loading?: boolean;
  onApply?: () => void; applyDisabled?: boolean;
  fallback?: ReactNode;
}) {
  const [tab, setTab] = useState(ANALYSIS_TABS[0]);
  return <Panel title={title} subtitle={subtitle} className="lab-viewer" flush actions={<>
    {onAnalyze && <Button variant="ghost" disabled={!src || loading} onClick={onAnalyze}>{loading ? 'Analyzing…' : 'Analyze'}</Button>}
    <SaveImageButton source={saveSource} fileName={subtitle || 'image'}/>
  </>}>
    <div className="lab-viewer-content">
      <div className="lab-image-stage checkerboard">{src ? <img className="lab-image" src={src} alt={title}/> : fallback ?? <EmptyState>이미지를 불러오거나 Run을 실행하세요.</EmptyState>}</div>
      <div className="lab-viewer-analysis"><Tabs items={ANALYSIS_TABS} active={tab} onChange={setTab}/><div className="lab-analysis-content"><AnalysisDetails analysis={analysis} active={tab}/></div></div>
      {onApply && <div className="lab-apply-row"><span>결과를 적용하면 현재 이미지가 갱신되고 이전 이미지는 History에 보관됩니다.</span><Button variant="primary" disabled={applyDisabled} onClick={onApply}>Apply</Button></div>}
    </div>
  </Panel>;
}

export function ImageLabPage() {
  const [file, setFile] = useState<File | null>(null);
  const [tab, setTab] = useState('Operation');
  const [operations, setOperations] = useState<OperationSpec[]>([]);
  const [features, setFeatures] = useState<FeatureSpec[]>([]);
  const [operators, setOperators] = useState<ScalarOperatorSpec[]>([]);
  const [pipelines, setPipelines] = useState<PipelineSpec[]>([]);
  const [recipes, setRecipes] = useState<RecipeSummary[]>([]);
  const [operationName, setOperationName] = useState('');
  const [params, setParams] = useState<Record<string, unknown>>({});
  const [featureName, setFeatureName] = useState('');
  const [featureParams, setFeatureParams] = useState<Record<string, unknown>>({});
  const [operatorName, setOperatorName] = useState('');
  const [operatorInputCount, setOperatorInputCount] = useState(1);
  const [operatorInputs, setOperatorInputs] = useState<Record<string, number>>({});
  const [operatorParamsText, setOperatorParamsText] = useState('{}');
  const [graphNodeType, setGraphNodeType] = useState<'roi_crop'|'roi_compose'|'decision'|'subrecipe'>('roi_crop');
  const [graphParams, setGraphParams] = useState<Record<string, unknown>>({ coordinate_mode:'pixels', x:0, y:0, width:100, height:100, clamp:true });
  const [subrecipeName, setSubrecipeName] = useState('');
  const [graphInputsText, setGraphInputsText] = useState('{\n  "value": 0\n}');
  const [quickType, setQuickType] = useState<'pipeline'|'recipe'>('recipe');
  const [quickName, setQuickName] = useState('');
  const [analysis, setAnalysis] = useState<ImageAnalysisResult | null>(null);
  const [outputAnalysis, setOutputAnalysis] = useState<ImageAnalysisResult | null>(null);
  const [execution, setExecution] = useState<ExecutionResponse | null>(null);
  const [outputImage, setOutputImage] = useState<EncodedImage | null>(null);
  const [outputFile, setOutputFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [analyzingOutput, setAnalyzingOutput] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [history, setHistory] = useState<File[]>([]);
  const [historyOpen, setHistoryOpen] = useState(false);
  const inputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    void Promise.all([operationsApi.list(), pipelinesApi.list(), recipesApi.list(), workflowApi.features(), workflowApi.operators()]).then(([o,p,r,f,s]) => {
      setOperations(o); setPipelines(p); setRecipes(r); setFeatures(f); setOperators(s);
      if (o.length) { setOperationName(o[0].name); setParams(defaultParams(o[0])); }
      if (f.length) { setFeatureName(f[0].name); setFeatureParams(defaultFeatureParams(f[0])); }
      if (s.length) {
        setOperatorName(s[0].name);
        setOperatorInputCount(s[0].min_inputs);
        setOperatorInputs(Object.fromEntries(operatorInputNames(s[0], s[0].min_inputs).map((name) => [name, 0])));
        setOperatorParamsText(JSON.stringify(Object.fromEntries(Object.entries(s[0].parameters).filter(([, spec]) => spec.default !== undefined).map(([name, spec]) => [name, spec.default])), null, 2));
      }
      if (r.length) setQuickName(r[0].name); else if (p.length) { setQuickType('pipeline'); setQuickName(p[0].name); }
      const firstGraph = r.find((item) => item.kind === 'graph');
      if (firstGraph) setSubrecipeName(firstGraph.name);
    }).catch((e)=>setError(errorMessage(e)));
  }, []);

  const selectedOp = useMemo(() => operations.find((o)=>o.name===operationName) ?? null, [operations, operationName]);
  const selectedFeature = useMemo(() => features.find((item)=>item.name===featureName) ?? null, [features, featureName]);
  const selectedOperator = useMemo(() => operators.find((item)=>item.name===operatorName) ?? null, [operators, operatorName]);
  const selectedSubrecipe = useMemo(() => recipes.find((item)=>item.name===subrecipeName) ?? null, [recipes, subrecipeName]);
  useEffect(() => { setParams(defaultParams(selectedOp)); }, [selectedOp?.name]);
  useEffect(() => { setFeatureParams(defaultFeatureParams(selectedFeature)); }, [selectedFeature?.name]);
  useEffect(() => {
    if (!selectedOperator) return;
    setOperatorInputCount(selectedOperator.min_inputs);
    setOperatorInputs(Object.fromEntries(operatorInputNames(selectedOperator, selectedOperator.min_inputs).map((name) => [name, 0])));
    setOperatorParamsText(JSON.stringify(Object.fromEntries(Object.entries(selectedOperator.parameters).filter(([, spec]) => spec.default !== undefined).map(([name, spec]) => [name, spec.default])), null, 2));
  }, [selectedOperator?.name]);

  const selectFile = (next: File | null) => {
    setFile(next); setAnalysis(null); setOutputAnalysis(null); setOutputImage(null); setOutputFile(null); setExecution(null); setError(null);
  };

  const analyzeCurrent = async () => {
    if (!file) return;
    setBusy(true); setError(null);
    try { setAnalysis(await analysisApi.analyzeImage({ options: {} }, file)); }
    catch (e) { setError(errorMessage(e)); }
    finally { setBusy(false); }
  };

  const runOperation = async () => {
    if (!file || !selectedOp) return setError('이미지와 Operation을 선택하세요.');
    const imageInputs = selectedOp.inputs.filter((i)=>IMAGE_KINDS.has(i.kind)).map((input)=>({input_name:input.name,file_index:0}));
    setBusy(true); setError(null); setExecution(null); setOutputAnalysis(null);
    try {
      const response = await operationsApi.execute(selectedOp.name, { params, image_inputs:imageInputs.length ? imageInputs : [{input_name:'image',file_index:0}], analysis:{} }, [file]);
      if (response instanceof Blob) throw new Error('JSON response expected');
      await adoptExecution(response);
    } catch (e) { setError(errorMessage(e)); }
    finally { setBusy(false); }
  };

  const runQuick = async () => {
    if (!file || !quickName) return setError('이미지와 Pipeline/Recipe을 선택하세요.');
    setBusy(true); setError(null); setExecution(null); setOutputAnalysis(null);
    try {
      let imageInput = 'image';
      let imageInputs: string[] = [];
      if (quickType === 'pipeline') {
        const spec = pipelines.find((p)=>p.name===quickName) ?? await pipelinesApi.get(quickName);
        imageInputs = spec.inputs.filter((i)=>IMAGE_KINDS.has(i.kind)).map((i)=>i.name);
        imageInput = imageInputs[0] ?? 'image';
      } else {
        const rec = await recipesApi.get(quickName);
        const inputs = rec.kind === 'linear' ? rec.pipeline?.inputs : rec.graph?.inputs;
        imageInputs = inputs?.filter((i)=>IMAGE_KINDS.has(i.kind)).map((i)=>i.name) ?? [];
        imageInput = imageInputs[0] ?? 'image';
      }
      const payload = { image_inputs:(imageInputs.length ? imageInputs : [imageInput]).map((input_name)=>({input_name,file_index:0})), retain_intermediates:true, analysis:{}, analyze_intermediates:false };
      const response = quickType === 'pipeline' ? await pipelinesApi.execute(quickName, payload, [file]) : await recipesApi.execute(quickName, payload, [file]);
      if (response instanceof Blob) throw new Error('JSON response expected');
      await adoptExecution(response);
    } catch (e) { setError(errorMessage(e)); }
    finally { setBusy(false); }
  };

  const runGraph = async (graph: GraphRecipeSpec, values: Record<string, unknown> = {}, imagePortNames: string[] = ['image']) => {
    if (!file) return setError('먼저 입력 이미지를 불러오세요.');
    setBusy(true); setError(null); setExecution(null); setOutputAnalysis(null);
    try {
      const payload = {
        graph, inputs: values,
        image_inputs: [...new Set(imagePortNames)].map((input_name) => ({ input_name, file_index: 0 })),
        retain_intermediates: true, analysis: {}, analyze_intermediates: false,
      };
      const response = await workflowApi.execute(payload, [file]);
      if (response instanceof Blob) throw new Error('JSON response expected');
      await adoptExecution(response);
    } catch (e) { setError(errorMessage(e)); }
    finally { setBusy(false); }
  };

  const runFeature = async () => {
    if (!selectedFeature) return setError('Feature를 선택하세요.');
    const imagePorts = selectedFeature.inputs.filter((port) => IMAGE_KINDS.has(port.kind));
    const unsupported = selectedFeature.inputs.filter((port) => !IMAGE_KINDS.has(port.kind));
    if (unsupported.length) return setError(`단일 이미지 입력으로 처리할 수 없는 Feature 포트가 있습니다: ${unsupported.map((port) => `${port.name} (${port.kind})`).join(', ')}`);
    const graph: GraphRecipeSpec = {
      name:`image_lab_${selectedFeature.name}`, display_name:selectedFeature.display_name, version:'1.0.0',
      inputs:imagePorts.map((port)=>({ name:port.name, kind:port.kind, required:port.required })),
      nodes:[{ id:'feature', node_type:'feature', feature:selectedFeature.name, params:featureParams, inputs:Object.fromEntries(imagePorts.map((port)=>[port.name,{ type:'graph_input', input_name:port.name }])) }],
      outputs:Object.fromEntries(selectedFeature.outputs.map((output)=>[output.name,{ type:'node_output', node_id:'feature', output_name:output.name }])),
    };
    await runGraph(graph, {}, imagePorts.map((port)=>port.name));
  };

  const runOperator = async () => {
    if (!selectedOperator) return setError('Operator를 선택하세요.');
    let values: Record<string, unknown>;
    try { values = JSON.parse(operatorParamsText || '{}') as Record<string, unknown>; }
    catch { return setError('Operator Parameters JSON 형식을 확인하세요.'); }
    const names = operatorInputNames(selectedOperator, operatorInputCount);
    const graph: GraphRecipeSpec = {
      name:`image_lab_${selectedOperator.name}`, display_name:selectedOperator.display_name, version:'1.0.0',
      inputs:names.map((name)=>({ name, kind:'scalar', required:true })),
      nodes:[{ id:'operator', node_type:'scalar_operator', operator:selectedOperator.name, params:values, inputs:Object.fromEntries(names.map((name)=>[name,{ type:'graph_input', input_name:name }])) }],
      outputs:{ value:{ type:'node_output', node_id:'operator', output_name:'value' }},
    };
    await runGraph(graph, Object.fromEntries(names.map((name)=>[name,Number(operatorInputs[name] ?? 0)])), []);
  };

  const runGraphNode = async () => {
    if (!file) return setError('먼저 입력 이미지를 불러오세요.');
    if (graphNodeType === 'decision') {
      let values: Record<string, unknown>;
      try { values = JSON.parse(graphInputsText || '{}') as Record<string, unknown>; }
      catch { return setError('Graph input 값은 JSON 객체로 입력하세요.'); }
      if (typeof values.value !== 'number') return setError('Decision 입력 value를 JSON 숫자로 지정하세요.');
      const graph: GraphRecipeSpec = {
        name:'image_lab_decision', display_name:'Decision Node Test', version:'1.0.0',
        inputs:[{ name:'value', kind:'scalar', required:true }],
        nodes:[{ id:'decision', node_type:'decision', params:{ operator:'gt', threshold:0, lower:0, upper:1, pass_label:'OK', fail_label:'NG', ...graphParams }, inputs:{ value:{ type:'graph_input', input_name:'value' } } }],
        outputs:{ value:{ type:'node_output', node_id:'decision', output_name:'value' }, passed:{ type:'node_output', node_id:'decision', output_name:'passed' }, label:{ type:'node_output', node_id:'decision', output_name:'label' } },
      };
      await runGraph(graph, values, []); return;
    }
    if (graphNodeType === 'subrecipe') {
      if (!selectedSubrecipe) return setError('SubRecipe로 실행할 Recipe를 선택하세요.');
      try {
        const record: RecipeRecord = await recipesApi.get(selectedSubrecipe.name);
        const sourceInputs = record.kind === 'graph' ? (record.graph?.inputs ?? []) : (record.pipeline?.inputs ?? []);
        const inputs = sourceInputs.map((port)=>({ name:port.name, kind:normalizePortKind(port.kind), required:port.required }));
        const imagePorts = inputs.filter((port)=>IMAGE_KINDS.has(port.kind));
        const otherPorts = inputs.filter((port)=>!IMAGE_KINDS.has(port.kind));
        let values: Record<string, unknown>;
        try { values = JSON.parse(graphInputsText || '{}') as Record<string, unknown>; }
        catch { return setError('Graph input 값은 JSON 객체로 입력하세요.'); }
        const missing = otherPorts.filter((port)=>values[port.name] === undefined).map((port)=>port.name);
        if (missing.length) return setError(`JSON에 이미지 외 Recipe 입력값을 추가하세요: ${missing.join(', ')}`);
        const outputNames = record.kind === 'graph' ? Object.keys(record.graph?.outputs ?? {}) : Object.keys(record.pipeline?.outputs ?? {});
        const firstOutput = outputNames[0];
        if (!firstOutput) return setError('선택한 Recipe에 노출된 output이 없습니다.');
        const graph: GraphRecipeSpec = {
          name:`image_lab_subrecipe_${record.name}`, display_name:`SubRecipe · ${record.name}`, version:'1.0.0', inputs,
          nodes:[{ id:'subrecipe', node_type:'subrecipe', recipe:record.name, recipe_kind:record.kind, inputs:Object.fromEntries(inputs.map((port)=>[port.name,{ type:'graph_input', input_name:port.name }])) }],
          outputs:{ [firstOutput]:{ type:'node_output', node_id:'subrecipe', output_name:firstOutput } },
        };
        await runGraph(graph, values, imagePorts.map((port)=>port.name));
      } catch (e) { setError(errorMessage(e)); }
      return;
    }
    const inputs = [{ name:'image', kind:'image', required:true }];
    const crop: GraphRecipeSpec['nodes'][number] = { id:'crop', node_type:'roi_crop', params:graphParams, inputs:{ image:{ type:'graph_input', input_name:'image' } } };
    let graph: GraphRecipeSpec;
    if (graphNodeType === 'roi_crop') {
      graph = { name:'image_lab_roi_crop', display_name:'ROI Crop Node Test', version:'1.0.0', inputs, nodes:[crop], outputs:{ image:{ type:'node_output', node_id:'crop', output_name:'image' }, region:{ type:'node_output', node_id:'crop', output_name:'region' } } };
    } else {
      graph = { name:'image_lab_roi_compose', display_name:'ROI Compose Node Test', version:'1.0.0', inputs,
        nodes:[crop,{ id:'compose', node_type:'roi_compose', inputs:{ base:{ type:'graph_input', input_name:'image' }, patch:{ type:'node_output', node_id:'crop', output_name:'image' }, region:{ type:'node_output', node_id:'crop', output_name:'region' } } }],
        outputs:{ image:{ type:'node_output', node_id:'compose', output_name:'image' } } };
    }
    await runGraph(graph, {}, ['image']);
  };

  const adoptExecution = async (response: ExecutionResponse) => {
    setExecution(response);
    const image = Object.values(response.output?.images ?? {})[0] ?? null;
    setOutputImage(image);
    if (!image?.data) { setOutputFile(null); setOutputAnalysis(null); return; }
    const nextFile = encodedImageFile(image, `${image.name || 'processed-image'}.png`);
    setOutputFile(nextFile);
    setAnalyzingOutput(true);
    try { setOutputAnalysis(await analysisApi.analyzeImage({ options: {} }, nextFile)); }
    catch (e) { setError(`결과 이미지는 생성됐지만 분석에 실패했습니다: ${errorMessage(e)}`); }
    finally { setAnalyzingOutput(false); }
  };

  const applyOutput = () => {
    if (!file || !outputFile) return;
    setHistory((items) => [file, ...items].slice(0, 20));
    setFile(outputFile);
    setAnalysis(outputAnalysis);
    setOutputImage(null); setOutputFile(null); setOutputAnalysis(null); setExecution(null);
  };

  const restoreHistory = (index: number) => {
    const restored = history[index];
    if (!restored) return;
    if (file) setHistory((items) => [file, ...items.filter((_, i) => i !== index)].slice(0, 20));
    setFile(restored); setAnalysis(null); setOutputImage(null); setOutputFile(null); setOutputAnalysis(null); setExecution(null);
    setHistoryOpen(false);
  };

  const inputUrl = useObjectUrl(file);
  const resultUrl = imageDataUrl(outputImage);

  return <div className="page">
    <input ref={inputRef} type="file" accept="image/*" hidden onChange={(e)=>selectFile(e.target.files?.[0]??null)}/>
    <div className="page-toolbar">
      <div className="page-title">이미지 실험실</div><span className="page-subtitle">입력 이미지 → 설정 → 결과 미리보기 및 적용</span>
      <Button onClick={()=>inputRef.current?.click()}>Open Image</Button>
      <Button onClick={()=>setHistoryOpen((value)=>!value)}>History {history.length} {historyOpen ? 'Hide' : 'Show'}</Button>
    </div>
    {error && <div className="status-strip"><InlineError message={error}/></div>}
    <div className="page-content lab-page-content">
      <div className="lab-workspace">
        <ImageViewer title="Input Image Viewer" subtitle={file?.name ?? 'No image'} src={inputUrl || undefined} saveSource={file} analysis={analysis} onAnalyze={analyzeCurrent} loading={busy}/>
        <Panel title="Settings" subtitle="Single image · Workflow components" className="lab-settings" flush>
          <Tabs items={LAB_MODES} active={tab} onChange={setTab}/>
          <div className="lab-settings-scroll">
            {tab === 'Operation' ? <>
              <Field label="Operation"><select className="select" value={operationName} onChange={(e)=>setOperationName(e.target.value)}>{operations.map(o=><option key={o.name} value={o.name}>{o.display_name} ({o.name})</option>)}</select></Field>
              {selectedOp?.description && <p className="lab-operation-description">{selectedOp.description}</p>}
              <div className="divider"/><div className="inspector-heading">Parameters</div>
              {selectedOp && Object.entries(selectedOp.parameters).map(([name,p]) => <Field key={name} label={p.title || name} help={p.description ?? undefined}>
                {p.type === 'category' ? <select className="select" value={String(params[name] ?? '')} onChange={(e)=>{ const raw=e.target.value; const choice=p.choices?.find(c=>String(c.value)===raw); setParams(v=>({...v,[name]:choice?.value ?? raw})); }}>{p.choices?.map(c=><option key={String(c.value)} value={String(c.value)}>{c.label}</option>)}</select>
                  : <input className="input" type="number" value={String(params[name] ?? '')} min={p.min_value ?? undefined} max={p.max_value ?? undefined} step={p.step ?? (p.type==='discrete'?1:'any')} onChange={(e)=>setParams(v=>({...v,[name]:p.type==='discrete'?Number.parseInt(e.target.value):Number(e.target.value)}))}/>} 
              </Field>)}
            </> : tab === 'Features' ? <>
              <Field label="Feature"><select className="select" value={featureName} onChange={(e)=>setFeatureName(e.target.value)}>{features.map((item)=><option key={item.name} value={item.name}>{item.display_name} · {item.category}</option>)}</select></Field>
              {selectedFeature?.description && <p className="lab-operation-description">{selectedFeature.description}</p>}
              <div className="divider"/><div className="inspector-heading">Parameters</div>
              {selectedFeature && Object.entries(selectedFeature.parameters).map(([name,p])=><Field key={name} label={p.title || name} help={p.description ?? undefined}>
                {p.type === 'category' ? <select className="select" value={String(featureParams[name] ?? p.default ?? '')} onChange={(e)=>{const raw=e.target.value;const choice=p.choices?.find((item)=>String(item.value)===raw);setFeatureParams((current)=>({...current,[name]:choice?.value ?? raw}));}}>{p.choices?.map((choice)=><option key={String(choice.value)} value={String(choice.value)}>{choice.label}</option>)}</select>
                  : <input className="input" type="number" value={String(featureParams[name] ?? p.default ?? '')} min={p.min_value ?? undefined} max={p.max_value ?? undefined} step={p.step ?? (p.type==='discrete'?1:'any')} onChange={(e)=>setFeatureParams((current)=>({...current,[name]:p.type==='discrete'?Number.parseInt(e.target.value):Number(e.target.value)}))}/>}
              </Field>)}
              <div className="help">Feature 출력은 결과 이미지의 Data JSON에 표시됩니다. 두 장의 비교가 필요한 Feature는 현재 이미지를 양쪽 입력으로 사용합니다.</div>
            </> : tab === 'Operators' ? <>
              <Field label="Scalar Operator"><select className="select" value={operatorName} onChange={(e)=>setOperatorName(e.target.value)}>{operators.map((item)=><option key={item.name} value={item.name}>{item.display_name} · {item.name}</option>)}</select></Field>
              {selectedOperator?.description && <p className="lab-operation-description">{selectedOperator.description}</p>}
              {selectedOperator && selectedOperator.max_inputs == null && <Field label="Input count"><select className="select" value={operatorInputCount} onChange={(e)=>{const count=Number(e.target.value);setOperatorInputCount(count);setOperatorInputs((current)=>Object.fromEntries(operatorInputNames(selectedOperator,count).map((name)=>[name,current[name] ?? 0])));}}>{Array.from({length:8-selectedOperator.min_inputs+1},(_,index)=>selectedOperator.min_inputs+index).map((count)=><option key={count} value={count}>{count}</option>)}</select></Field>}
              {selectedOperator && operatorInputNames(selectedOperator,operatorInputCount).map((name)=><Field key={name} label={name}><input className="input" type="number" value={String(operatorInputs[name] ?? 0)} onChange={(e)=>setOperatorInputs((current)=>({...current,[name]:Number(e.target.value)}))}/></Field>)}
              {selectedOperator && Object.keys(selectedOperator.parameters).length > 0 && <Field label="Parameters JSON" help="Operator별 추가 설정을 JSON으로 입력합니다."><textarea className="textarea json-input" value={operatorParamsText} onChange={(e)=>setOperatorParamsText(e.target.value)}/></Field>}
              <div className="help">단일 이미지에서 바로 계산되는 기능이 아니라 scalar 값을 조합하는 Operator입니다. 값과 추가 파라미터를 입력해 결과를 확인합니다.</div>
            </> : tab === 'Graph Nodes' ? <>
              <Field label="Node type"><select className="select" value={graphNodeType} onChange={(e)=>setGraphNodeType(e.target.value as typeof graphNodeType)}><option value="roi_crop">ROI Crop</option><option value="roi_compose">ROI Compose</option><option value="decision">Decision</option><option value="subrecipe">SubRecipe</option></select></Field>
              {(graphNodeType === 'roi_crop' || graphNodeType === 'roi_compose') && <>
                <Field label="Coordinate mode"><select className="select" value={String(graphParams.coordinate_mode ?? 'pixels')} onChange={(e)=>setGraphParams((current)=>({...current,coordinate_mode:e.target.value}))}><option value="pixels">Pixels</option><option value="relative">Relative (0–1)</option></select></Field>
                {['x','y','width','height'].map((key)=><Field key={key} label={key}><input className="input" type="number" min={0} max={graphParams.coordinate_mode==='relative'?1:undefined} step={graphParams.coordinate_mode==='relative'?0.01:1} value={String(graphParams[key] ?? (key==='width'||key==='height'?100:0))} onChange={(e)=>setGraphParams((current)=>({...current,[key]:Number(e.target.value)}))}/></Field>)}
                {graphNodeType === 'roi_compose' && <p className="lab-operation-description">ROI를 잘라낸 뒤 같은 위치에 재합성해 원본 크기 이미지를 반환합니다. 변환 파이프라인은 ROI Crop과 Compose 사이에 Recipe Studio에서 추가할 수 있습니다.</p>}
              </>}
              {graphNodeType === 'decision' && <>
                <Field label="Input values JSON" help="예: { &quot;value&quot;: 0.42 }"><textarea className="textarea json-input" value={graphInputsText} onChange={(e)=>setGraphInputsText(e.target.value)}/></Field>
                <Field label="Operator"><select className="select" value={String(graphParams.operator ?? 'gt')} onChange={(e)=>setGraphParams((current)=>({...current,operator:e.target.value}))}>{['gt','gte','lt','lte','inside_range','outside_range'].map((value)=><option key={value} value={value}>{value}</option>)}</select></Field>
                {['inside_range','outside_range'].includes(String(graphParams.operator)) ? <><Field label="Lower"><input className="input" type="number" value={String(graphParams.lower ?? 0)} onChange={(e)=>setGraphParams((current)=>({...current,lower:Number(e.target.value)}))}/></Field><Field label="Upper"><input className="input" type="number" value={String(graphParams.upper ?? 1)} onChange={(e)=>setGraphParams((current)=>({...current,upper:Number(e.target.value)}))}/></Field></> : <Field label="Threshold"><input className="input" type="number" value={String(graphParams.threshold ?? 0)} onChange={(e)=>setGraphParams((current)=>({...current,threshold:Number(e.target.value)}))}/></Field>}
                <Field label="Pass / Fail labels"><div className="lab-inline-inputs"><input className="input" value={String(graphParams.pass_label ?? 'OK')} onChange={(e)=>setGraphParams((current)=>({...current,pass_label:e.target.value}))}/><input className="input" value={String(graphParams.fail_label ?? 'NG')} onChange={(e)=>setGraphParams((current)=>({...current,fail_label:e.target.value}))}/></div></Field>
              </>}
              {graphNodeType === 'subrecipe' && <>
                <Field label="Recipe"><select className="select" value={subrecipeName} onChange={(e)=>setSubrecipeName(e.target.value)}>{recipes.map((item)=><option key={item.name} value={item.name}>{item.display_name} · {item.kind}</option>)}</select></Field>
                <Field label="Non-image inputs JSON" help="필요한 scalar 등 입력만 작성하세요. 이미지 포트는 현재 이미지를 자동 연결합니다."><textarea className="textarea json-input" value={graphInputsText} onChange={(e)=>setGraphInputsText(e.target.value)}/></Field>
              </>}
            </> : <>
              <Field label="Run type"><select className="select" value={quickType} onChange={(e)=>{const type=e.target.value as 'pipeline'|'recipe'; setQuickType(type); setQuickName(type==='recipe'?(recipes[0]?.name??''):(pipelines[0]?.name??''));}}><option value="recipe">Recipe</option><option value="pipeline">Built-in Pipeline</option></select></Field>
              <Field label={quickType==='recipe'?'Recipe':'Pipeline'}><select className="select" value={quickName} onChange={(e)=>setQuickName(e.target.value)}>{(quickType==='recipe'?recipes:pipelines).map((item)=><option key={item.name} value={item.name}>{item.display_name}</option>)}</select></Field>
              <p className="lab-operation-description">Quick Run은 저장된 Recipe 또는 Built-in Pipeline을 현재 입력 이미지에 실행합니다.</p>
            </>}
          </div>
          <div className="lab-settings-footer"><Button variant="primary" disabled={!file||busy||analyzingOutput||(tab==='Operation'&&!selectedOp)||(tab==='Features'&&!selectedFeature)||(tab==='Operators'&&!selectedOperator)||(tab==='Quick Run'&&!quickName)||(tab==='Graph Nodes'&&graphNodeType==='subrecipe'&&!selectedSubrecipe)} onClick={()=>void (tab==='Operation'?runOperation():tab==='Features'?runFeature():tab==='Operators'?runOperator():tab==='Graph Nodes'?runGraphNode():runQuick())}>{busy?'Running…':'Run'}</Button><Button disabled={busy} onClick={()=>{if(tab==='Operation')setParams(defaultParams(selectedOp));else if(tab==='Features')setFeatureParams(defaultFeatureParams(selectedFeature));else if(tab==='Operators'&&selectedOperator){setOperatorInputCount(selectedOperator.min_inputs);setOperatorInputs(Object.fromEntries(operatorInputNames(selectedOperator,selectedOperator.min_inputs).map((name)=>[name,0])));setOperatorParamsText('{}');}else if(tab==='Graph Nodes')setGraphParams({coordinate_mode:'pixels',x:0,y:0,width:100,height:100,clamp:true,operator:'gt',threshold:0,lower:0,upper:1,pass_label:'OK',fail_label:'NG'});}}>Reset</Button></div>
          {execution && <div className={`lab-run-status ${execution.success?'success':'failed'}`}>{execution.success ? `완료 · ${String((execution.metadata as {duration_ms?:number}|undefined)?.duration_ms ?? '-')} ms` : execution.error?.message ?? '실행 실패'}</div>}
        </Panel>
        <ImageViewer title="Result Image Viewer" subtitle={outputImage?.name ?? (outputImage ? 'Processed image' : 'No image output')} src={resultUrl} saveSource={resultUrl} analysis={outputAnalysis} loading={analyzingOutput} onApply={applyOutput} applyDisabled={!outputFile || busy} fallback={execution ? <pre className="lab-result-data">{JSON.stringify(execution.output.data, null, 2)}</pre> : undefined}/>
        {historyOpen && <aside className="lab-history-panel"><div className="lab-history-header"><strong>History</strong><Button variant="ghost" onClick={()=>setHistoryOpen(false)}>Hide</Button></div>{history.length ? history.map((item,index)=><button type="button" className="lab-history-item" key={`${item.name}-${item.lastModified}-${index}`} onClick={()=>restoreHistory(index)}><ObjectImage file={item} alt="History snapshot"/><span>{item.name}</span><small>{(item.size/1024/1024).toFixed(2)} MB</small></button>) : <EmptyState>Apply를 실행하면 이전 이미지가 여기에 저장됩니다.</EmptyState>}</aside>}
      </div>
    </div>
  </div>;
}
