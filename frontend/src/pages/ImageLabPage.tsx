import { useEffect, useMemo, useRef, useState } from 'react';
import { analysisApi, operationsApi, pipelinesApi, recipesApi, type ExecutionResponse, type ImageAnalysisResult, type OperationSpec, type PipelineSpec, type RecipeSummary } from '../api';
import { Button, EmptyState, Field, InlineError, Kpi, Panel, Tabs } from '../components/ui';
import { errorMessage, imageDataUrl, number } from '../lib/format';

function defaultParams(op: OperationSpec | null): Record<string, unknown> {
  if (!op) return {};
  return Object.fromEntries(Object.entries(op.parameters).filter(([,p]) => p.default !== undefined).map(([name,p]) => [name,p.default]));
}

export function ImageLabPage() {
  const [file, setFile] = useState<File | null>(null);
  const [fileUrl, setFileUrl] = useState<string | null>(null);
  const [tab, setTab] = useState('Image Analysis');
  const [operations, setOperations] = useState<OperationSpec[]>([]);
  const [pipelines, setPipelines] = useState<PipelineSpec[]>([]);
  const [recipes, setRecipes] = useState<RecipeSummary[]>([]);
  const [operationName, setOperationName] = useState('');
  const [params, setParams] = useState<Record<string, unknown>>({});
  const [quickType, setQuickType] = useState<'pipeline'|'recipe'>('recipe');
  const [quickName, setQuickName] = useState('');
  const [analysis, setAnalysis] = useState<ImageAnalysisResult | null>(null);
  const [execution, setExecution] = useState<ExecutionResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    void Promise.all([operationsApi.list(), pipelinesApi.list(), recipesApi.list()]).then(([o,p,r]) => {
      setOperations(o); setPipelines(p); setRecipes(r);
      if (o.length) { setOperationName(o[0].name); setParams(defaultParams(o[0])); }
      if (r.length) setQuickName(r[0].name); else if (p.length) { setQuickType('pipeline'); setQuickName(p[0].name); }
    }).catch((e)=>setError(errorMessage(e)));
  }, []);

  useEffect(() => {
    if (!file) { setFileUrl(null); return; }
    const url = URL.createObjectURL(file); setFileUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  const selectedOp = useMemo(() => operations.find((o)=>o.name===operationName) ?? null, [operations, operationName]);
  useEffect(() => { setParams(defaultParams(selectedOp)); }, [selectedOp?.name]);

  const analyze = async () => {
    if (!file) return setError('먼저 이미지를 선택하세요.');
    setBusy(true); setError(null); setExecution(null);
    try { setAnalysis(await analysisApi.analyzeImage({ options: {} }, file)); setTab('Image Analysis'); }
    catch (e) { setError(errorMessage(e)); }
    finally { setBusy(false); }
  };

  const runOperation = async () => {
    if (!file || !selectedOp) return setError('이미지와 Operation을 선택하세요.');
    const imageInput = selectedOp.inputs.find((i)=>i.kind==='image'||i.kind==='mask')?.name ?? 'image';
    setBusy(true); setError(null); setExecution(null);
    try {
      const response = await operationsApi.execute(selectedOp.name, { params, image_inputs:[{input_name:imageInput,file_index:0}], analysis:{} }, [file]);
      if (response instanceof Blob) throw new Error('JSON response expected');
      setExecution(response); setTab('Operation');
    } catch (e) { setError(errorMessage(e)); }
    finally { setBusy(false); }
  };

  const runQuick = async () => {
    if (!file || !quickName) return setError('이미지와 Pipeline/Recipe을 선택하세요.');
    setBusy(true); setError(null); setExecution(null);
    try {
      let imageInput = 'image';
      if (quickType === 'pipeline') {
        const spec = pipelines.find((p)=>p.name===quickName) ?? await pipelinesApi.get(quickName);
        imageInput = spec.inputs.find((i)=>i.kind==='image'||i.kind==='mask')?.name ?? 'image';
      } else {
        const rec = await recipesApi.get(quickName);
        const inputs = rec.kind === 'linear' ? rec.pipeline?.inputs : rec.graph?.inputs;
        imageInput = inputs?.find((i)=>i.kind==='image'||i.kind==='mask')?.name ?? 'image';
      }
      const payload = { image_inputs:[{input_name:imageInput,file_index:0}], retain_intermediates:true, analysis:{}, analyze_intermediates:false };
      const response = quickType === 'pipeline' ? await pipelinesApi.execute(quickName, payload, [file]) : await recipesApi.execute(quickName, payload, [file]);
      if (response instanceof Blob) throw new Error('JSON response expected');
      setExecution(response); setTab('Quick Run');
    } catch (e) { setError(errorMessage(e)); }
    finally { setBusy(false); }
  };

  const firstOutput = execution ? Object.values(execution.output?.images ?? {})[0] : undefined;
  const shownUrl = firstOutput ? imageDataUrl(firstOutput) : fileUrl ?? undefined;
  const hist = analysis?.histograms.gray?.counts ?? [];
  const histSample = hist.length > 64 ? hist.filter((_,i)=>i%4===0) : hist;
  const histMax = Math.max(...histSample, 1);

  return <div className="page">
    <input ref={inputRef} type="file" accept="image/*" hidden onChange={(e)=>{ const f=e.target.files?.[0]??null; setFile(f); setAnalysis(null); setExecution(null); }}/>
    <div className="page-toolbar">
      <div className="page-title">이미지 실험실</div><span className="page-subtitle">단일 이미지 분석 및 Operation/Recipe 빠른 실험</span>
      <Button onClick={()=>inputRef.current?.click()}>Open Image</Button><Button variant="primary" onClick={tab==='Image Analysis'?analyze:tab==='Operation'?runOperation:runQuick} disabled={busy || !file}>{busy?'Running...':'Run'}</Button>
    </div>
    {error && <div className="status-strip"><InlineError message={error}/></div>}
    <div className="page-content" style={{overflow:'hidden'}}>
      <div className="lab-layout">
        <Panel title="Image Viewer" subtitle={file?.name ?? 'No image'} actions={<><Button variant="ghost">1:1</Button><Button variant="ghost">Fit</Button></>} flush>
          <div className="image-stage" style={{height:'100%'}}>{shownUrl ? <img className="lab-image" src={shownUrl} alt="preview"/> : <EmptyState>Open Image로 이미지를 선택하세요.</EmptyState>}{file && <div className="stage-meta">{firstOutput ? `${firstOutput.width} × ${firstOutput.height} · ${firstOutput.color_space}` : `${(file.size/1024/1024).toFixed(2)} MB`}</div>}</div>
        </Panel>
        <Panel title="Experiment" flush>
          <Tabs items={['Image Analysis','Operation','Quick Run']} active={tab} onChange={setTab}/>
          <div style={{padding:10,overflow:'auto',height:'calc(100% - 36px)'}}>
            {tab === 'Image Analysis' && <>
              <div className="inspector-heading">Analysis Options</div><div className="mono-small">Histogram / statistics / feature / profile을 Backend ImageAnalyzer에서 계산합니다.</div>
              <div style={{marginTop:12}}><Button variant="primary" onClick={analyze} disabled={!file||busy}>Analyze Image</Button></div>
            </>}
            {tab === 'Operation' && <>
              <Field label="Operation"><select className="select" value={operationName} onChange={(e)=>setOperationName(e.target.value)}>{operations.map(o=><option key={o.name} value={o.name}>{o.display_name} ({o.name})</option>)}</select></Field>
              <div className="divider"/><div className="inspector-heading">Parameters</div>
              {selectedOp && Object.entries(selectedOp.parameters).map(([name,p]) => <Field key={name} label={p.title || name} help={p.description ?? undefined}>
                {p.type === 'category' ? <select className="select" value={String(params[name] ?? '')} onChange={(e)=>{ const raw=e.target.value; const choice=p.choices?.find(c=>String(c.value)===raw); setParams(v=>({...v,[name]:choice?.value ?? raw})); }}>{p.choices?.map(c=><option key={String(c.value)} value={String(c.value)}>{c.label}</option>)}</select>
                  : <input className="input" type="number" value={String(params[name] ?? '')} min={p.min_value ?? undefined} max={p.max_value ?? undefined} step={p.step ?? (p.type==='discrete'?1:'any')} onChange={(e)=>setParams(v=>({...v,[name]:p.type==='discrete'?Number.parseInt(e.target.value):Number(e.target.value)}))}/>} 
              </Field>)}
              <div style={{display:'flex',gap:6,marginTop:12}}><Button variant="primary" onClick={runOperation} disabled={!file||busy}>Run Operation</Button><Button onClick={()=>setParams(defaultParams(selectedOp))}>Reset</Button></div>
            </>}
            {tab === 'Quick Run' && <>
              <Field label="Type"><select className="select" value={quickType} onChange={(e)=>{const t=e.target.value as 'pipeline'|'recipe'; setQuickType(t); setQuickName(t==='recipe'?(recipes[0]?.name??''):(pipelines[0]?.name??''));}}><option value="recipe">Recipe</option><option value="pipeline">Built-in Pipeline</option></select></Field>
              <Field label={quickType==='recipe'?'Recipe':'Pipeline'}><select className="select" value={quickName} onChange={(e)=>setQuickName(e.target.value)}>{(quickType==='recipe'?recipes:pipelines).map((x)=><option key={x.name} value={x.name}>{'display_name' in x ? x.display_name : x.name}</option>)}</select></Field>
              <Button variant="primary" onClick={runQuick} disabled={!file||!quickName||busy}>Quick Run</Button>
            </>}
            {execution && <><div className="divider"/><div className="inspector-heading">Last Run</div><div className="mono-small">success: {String(execution.success)}<br/>duration: {String((execution.metadata as {duration_ms?:number}|undefined)?.duration_ms ?? '-')} ms<br/>outputs: {Object.keys(execution.output?.images ?? {}).join(', ') || '-'}</div></>}
          </div>
        </Panel>
        <div className="analysis-bottom">
          <Panel title="Histogram" subtitle={analysis?.histograms.gray ? `Gray · ${analysis.histograms.gray.bins} bins` : 'Run Image Analysis'}><div className="histogram-real">{histSample.length ? histSample.map((v,i)=><span key={i} style={{height:`${Math.max(1,(v/histMax)*100)}%`}}/>) : <EmptyState>분석 결과 없음</EmptyState>}</div></Panel>
          <Panel title="Image Statistics">{analysis ? <div className="kpi-grid" style={{gridTemplateColumns:'repeat(2,1fr)'}}><Kpi label="Mean" value={number(analysis.intensity_statistics.mean)}/><Kpi label="Std" value={number(analysis.intensity_statistics.std)}/><Kpi label="Min" value={number(analysis.intensity_statistics.minimum)}/><Kpi label="Max" value={number(analysis.intensity_statistics.maximum)}/></div> : <EmptyState/>}</Panel>
          <Panel title="Image Features">{analysis?.features ? <div className="feature-list">{Object.entries(analysis.features).slice(0,10).map(([k,v])=><div key={k}><span>{k}</span><strong>{typeof v==='number'?number(v,4):String(v)}</strong></div>)}</div> : <EmptyState/>}</Panel>
        </div>
      </div>
    </div>
  </div>;
}
