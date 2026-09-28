import { useEffect, useMemo, useRef, useState } from 'react';
import { analysisApi, operationsApi, pipelinesApi, recipesApi, type EncodedImage, type ExecutionResponse, type ImageAnalysisResult, type OperationSpec, type PipelineSpec, type RecipeSummary } from '../api';
import { SaveImageButton } from '../components/SaveImageButton';
import { Button, EmptyState, Field, InlineError, Kpi, Panel, Tabs } from '../components/ui';
import { errorMessage, imageDataUrl, number } from '../lib/format';

const ANALYSIS_TABS = ['Histogram', 'Image Statistics', 'Image Feature', 'Image Analysis'];

function defaultParams(op: OperationSpec | null): Record<string, unknown> {
  if (!op) return {};
  return Object.fromEntries(Object.entries(op.parameters).filter(([,p]) => p.default !== undefined).map(([name,p]) => [name,p.default]));
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
  title, subtitle, src, saveSource, analysis, onAnalyze, loading, onApply, applyDisabled,
}: {
  title: string; subtitle: string; src?: string; saveSource?: Blob | string | null;
  analysis: ImageAnalysisResult | null; onAnalyze?: () => void; loading?: boolean;
  onApply?: () => void; applyDisabled?: boolean;
}) {
  const [tab, setTab] = useState(ANALYSIS_TABS[0]);
  return <Panel title={title} subtitle={subtitle} className="lab-viewer" flush actions={<>
    {onAnalyze && <Button variant="ghost" disabled={!src || loading} onClick={onAnalyze}>{loading ? 'Analyzing…' : 'Analyze'}</Button>}
    <SaveImageButton source={saveSource} fileName={subtitle || 'image'}/>
  </>}>
    <div className="lab-viewer-content">
      <div className="lab-image-stage checkerboard">{src ? <img className="lab-image" src={src} alt={title}/> : <EmptyState>이미지를 불러오거나 Run을 실행하세요.</EmptyState>}</div>
      <div className="lab-viewer-analysis"><Tabs items={ANALYSIS_TABS} active={tab} onChange={setTab}/><div className="lab-analysis-content"><AnalysisDetails analysis={analysis} active={tab}/></div></div>
      {onApply && <div className="lab-apply-row"><span>결과를 적용하면 현재 이미지가 갱신되고 이전 이미지는 History에 보관됩니다.</span><Button variant="primary" disabled={applyDisabled} onClick={onApply}>Apply</Button></div>}
    </div>
  </Panel>;
}

export function ImageLabPage() {
  const [file, setFile] = useState<File | null>(null);
  const [tab, setTab] = useState<'Operation'|'Quick Run'>('Operation');
  const [operations, setOperations] = useState<OperationSpec[]>([]);
  const [pipelines, setPipelines] = useState<PipelineSpec[]>([]);
  const [recipes, setRecipes] = useState<RecipeSummary[]>([]);
  const [operationName, setOperationName] = useState('');
  const [params, setParams] = useState<Record<string, unknown>>({});
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
    void Promise.all([operationsApi.list(), pipelinesApi.list(), recipesApi.list()]).then(([o,p,r]) => {
      setOperations(o); setPipelines(p); setRecipes(r);
      if (o.length) { setOperationName(o[0].name); setParams(defaultParams(o[0])); }
      if (r.length) setQuickName(r[0].name); else if (p.length) { setQuickType('pipeline'); setQuickName(p[0].name); }
    }).catch((e)=>setError(errorMessage(e)));
  }, []);

  const selectedOp = useMemo(() => operations.find((o)=>o.name===operationName) ?? null, [operations, operationName]);
  useEffect(() => { setParams(defaultParams(selectedOp)); }, [selectedOp?.name]);

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
    const imageInput = selectedOp.inputs.find((i)=>i.kind==='image'||i.kind==='mask')?.name ?? 'image';
    setBusy(true); setError(null); setExecution(null); setOutputAnalysis(null);
    try {
      const response = await operationsApi.execute(selectedOp.name, { params, image_inputs:[{input_name:imageInput,file_index:0}], analysis:{} }, [file]);
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
      await adoptExecution(response);
    } catch (e) { setError(errorMessage(e)); }
    finally { setBusy(false); }
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
        <Panel title="Settings" subtitle="Operation / Quick Run" className="lab-settings" flush>
          <Tabs items={['Operation','Quick Run']} active={tab} onChange={(value)=>setTab(value as 'Operation'|'Quick Run')}/>
          <div className="lab-settings-scroll">
            {tab === 'Operation' ? <>
              <Field label="Operation"><select className="select" value={operationName} onChange={(e)=>setOperationName(e.target.value)}>{operations.map(o=><option key={o.name} value={o.name}>{o.display_name} ({o.name})</option>)}</select></Field>
              {selectedOp?.description && <p className="lab-operation-description">{selectedOp.description}</p>}
              <div className="divider"/><div className="inspector-heading">Parameters</div>
              {selectedOp && Object.entries(selectedOp.parameters).map(([name,p]) => <Field key={name} label={p.title || name} help={p.description ?? undefined}>
                {p.type === 'category' ? <select className="select" value={String(params[name] ?? '')} onChange={(e)=>{ const raw=e.target.value; const choice=p.choices?.find(c=>String(c.value)===raw); setParams(v=>({...v,[name]:choice?.value ?? raw})); }}>{p.choices?.map(c=><option key={String(c.value)} value={String(c.value)}>{c.label}</option>)}</select>
                  : <input className="input" type="number" value={String(params[name] ?? '')} min={p.min_value ?? undefined} max={p.max_value ?? undefined} step={p.step ?? (p.type==='discrete'?1:'any')} onChange={(e)=>setParams(v=>({...v,[name]:p.type==='discrete'?Number.parseInt(e.target.value):Number(e.target.value)}))}/>}
              </Field>)}
            </> : <>
              <Field label="Run type"><select className="select" value={quickType} onChange={(e)=>{const type=e.target.value as 'pipeline'|'recipe'; setQuickType(type); setQuickName(type==='recipe'?(recipes[0]?.name??''):(pipelines[0]?.name??''));}}><option value="recipe">Recipe</option><option value="pipeline">Built-in Pipeline</option></select></Field>
              <Field label={quickType==='recipe'?'Recipe':'Pipeline'}><select className="select" value={quickName} onChange={(e)=>setQuickName(e.target.value)}>{(quickType==='recipe'?recipes:pipelines).map((item)=><option key={item.name} value={item.name}>{item.display_name}</option>)}</select></Field>
              <p className="lab-operation-description">Quick Run은 저장된 Recipe 또는 Built-in Pipeline을 현재 입력 이미지에 실행합니다.</p>
            </>}
          </div>
          <div className="lab-settings-footer"><Button variant="primary" disabled={!file||busy||analyzingOutput||(tab==='Operation'&&!selectedOp)||(tab==='Quick Run'&&!quickName)} onClick={()=>void (tab==='Operation'?runOperation():runQuick())}>{busy?'Running…':'Run'}</Button><Button disabled={!selectedOp||busy} onClick={()=>setParams(defaultParams(selectedOp))}>Reset</Button></div>
          {execution && <div className={`lab-run-status ${execution.success?'success':'failed'}`}>{execution.success ? `완료 · ${String((execution.metadata as {duration_ms?:number}|undefined)?.duration_ms ?? '-')} ms` : execution.error?.message ?? '실행 실패'}</div>}
        </Panel>
        <ImageViewer title="Result Image Viewer" subtitle={outputImage?.name ?? (outputImage ? 'Processed image' : 'No result')} src={resultUrl} saveSource={resultUrl} analysis={outputAnalysis} loading={analyzingOutput} onApply={applyOutput} applyDisabled={!outputFile || busy}/>
        {historyOpen && <aside className="lab-history-panel"><div className="lab-history-header"><strong>History</strong><Button variant="ghost" onClick={()=>setHistoryOpen(false)}>Hide</Button></div>{history.length ? history.map((item,index)=><button type="button" className="lab-history-item" key={`${item.name}-${item.lastModified}-${index}`} onClick={()=>restoreHistory(index)}><ObjectImage file={item} alt="History snapshot"/><span>{item.name}</span><small>{(item.size/1024/1024).toFixed(2)} MB</small></button>) : <EmptyState>Apply를 실행하면 이전 이미지가 여기에 저장됩니다.</EmptyState>}</aside>}
      </div>
    </div>
  </div>;
}
