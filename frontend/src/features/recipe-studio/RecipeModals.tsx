import { useMemo, useState } from 'react';

import type { ModelSpec, RecipeRecord } from '../../api';
import { Button, Field, Modal } from '../../components/ui';
import { artifactOf, parseTags } from './editor';

export function NewRecipeModal({ onClose, onCreate }: { onClose: () => void; onCreate: (value: { name: string; displayName: string; description: string; version: string; kind: 'linear' | 'graph'; tags: string[] }) => void }) {
  const [name, setName] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [description, setDescription] = useState('');
  const [version, setVersion] = useState('1.0.0');
  const [kind, setKind] = useState<'linear' | 'graph'>('linear');
  const [tags, setTags] = useState('');
  const valid = /^[a-z][a-z0-9_]*$/.test(name) && displayName.trim().length > 0 && version.trim().length > 0;
  return <Modal title="New Recipe" onClose={onClose} footer={<><Button onClick={onClose}>Cancel</Button><Button variant="primary" disabled={!valid} onClick={() => onCreate({ name, displayName: displayName.trim(), description, version, kind, tags: parseTags(tags) })}>Create Draft</Button></>}>
    <div className="form-grid recipe-modal-grid">
      <div className="form-group"><label>Recipe kind</label><select className="select" value={kind} onChange={(e) => setKind(e.target.value as 'linear' | 'graph')}><option value="linear">Linear Pipeline</option><option value="graph">Graph Workflow</option></select></div>
      <div className="form-group"><label>Version</label><input className="input" value={version} onChange={(e) => setVersion(e.target.value)}/></div>
      <div className="form-group"><label>Name</label><input className="input" placeholder="wafer_defect_rule" value={name} onChange={(e) => setName(e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, ''))}/></div>
      <div className="form-group"><label>Display name</label><input className="input" placeholder="Wafer Defect Rule" value={displayName} onChange={(e) => setDisplayName(e.target.value)}/></div>
      <div className="form-group form-span-2"><label>Tags</label><input className="input" placeholder="wafer, inspection" value={tags} onChange={(e) => setTags(e.target.value)}/></div>
      <div className="form-group form-span-2"><label>Description</label><textarea className="textarea" value={description} onChange={(e) => setDescription(e.target.value)}/></div>
    </div>
    <div className="modal-note">초기 draft에는 <code>image:image</code> input이 자동 생성됩니다. Node를 하나 이상 추가한 뒤 Validate/Save하세요.</div>
  </Modal>;
}

export type RecipeRunPayload = {
  inputs: Record<string, unknown>;
  image_inputs: Array<{ input_name: string; file_index: number }>;
  model_inputs: Array<{ input_name: string; model_id: string; version: string }>;
  retain_intermediates: boolean;
  analyze_intermediates: boolean;
};

export function RunRecipeModal({
  record,
  models,
  onClose,
  onRun,
}: {
  record: RecipeRecord;
  models: ModelSpec[];
  onClose: () => void;
  onRun: (payload: RecipeRunPayload, files: File[]) => void;
}) {
  const artifact = artifactOf(record);
  const [files, setFiles] = useState<Record<string, File | null>>({});
  const [modelsByInput, setModelsByInput] = useState<Record<string, string>>({});
  const [jsonInputs, setJsonInputs] = useState<Record<string, string>>({});
  const [retain, setRetain] = useState(true);
  const [analyze, setAnalyze] = useState(false);

  const imageInputs = artifact.inputs.filter((item) => ['image', 'mask', 'template'].includes(item.kind));
  const modelInputs = artifact.inputs.filter((item) => item.kind === 'model');
  const valueInputs = artifact.inputs.filter((item) => !['image', 'mask', 'template', 'model'].includes(item.kind));

  const ready = useMemo(() => artifact.inputs.every((input) => {
    if (!input.required) return true;
    if (['image', 'mask', 'template'].includes(input.kind)) return Boolean(files[input.name]);
    if (input.kind === 'model') return Boolean(modelsByInput[input.name]);
    return Boolean(jsonInputs[input.name]?.trim());
  }), [artifact.inputs, files, modelsByInput, jsonInputs]);

  const submit = () => {
    const uploadFiles: File[] = [];
    const imageBindings: RecipeRunPayload['image_inputs'] = [];
    for (const input of imageInputs) {
      const file = files[input.name];
      if (!file) continue;
      const index = uploadFiles.length; uploadFiles.push(file);
      imageBindings.push({ input_name: input.name, file_index: index });
    }
    const modelBindings: RecipeRunPayload['model_inputs'] = [];
    for (const input of modelInputs) {
      const key = modelsByInput[input.name];
      if (!key) continue;
      const [modelId, version] = key.split('@');
      modelBindings.push({ input_name: input.name, model_id: modelId, version });
    }
    const inputs: Record<string, unknown> = {};
    for (const input of valueInputs) {
      const raw = jsonInputs[input.name];
      if (!raw?.trim()) continue;
      try { inputs[input.name] = JSON.parse(raw); }
      catch { window.alert(`${input.name}의 JSON 값이 올바르지 않습니다.`); return; }
    }
    onRun({ inputs, image_inputs: imageBindings, model_inputs: modelBindings, retain_intermediates: retain, analyze_intermediates: analyze }, uploadFiles);
  };

  return <Modal title={`Run Draft · ${record.name}`} onClose={onClose} footer={<><Button onClick={onClose}>Cancel</Button><Button variant="primary" disabled={!ready} onClick={submit}>Run</Button></>}>
    <div className="run-input-list">
      {imageInputs.map((input) => <div className="run-input-row" key={input.name}>
        <div><strong>{input.name}</strong><small>{input.kind}{input.required ? ' · required' : ''}</small></div>
        <input className="file-input" type="file" accept="image/*" onChange={(e) => setFiles((prev) => ({ ...prev, [input.name]: e.target.files?.[0] ?? null }))}/>
      </div>)}
      {modelInputs.map((input) => <div className="run-input-row" key={input.name}>
        <div><strong>{input.name}</strong><small>model{input.required ? ' · required' : ''}</small></div>
        <select className="select" value={modelsByInput[input.name] ?? ''} onChange={(e) => setModelsByInput((prev) => ({ ...prev, [input.name]: e.target.value }))}><option value="">Select model</option>{models.map((model) => <option key={`${model.model_id}@${model.version}`} value={`${model.model_id}@${model.version}`}>{model.model_id} · {model.version}</option>)}</select>
      </div>)}
      {valueInputs.map((input) => <div className="run-input-row value" key={input.name}>
        <div><strong>{input.name}</strong><small>{input.kind}{input.required ? ' · required' : ''}</small></div>
        <textarea className="json-input compact" placeholder='JSON value, e.g. [1,2,3]' value={jsonInputs[input.name] ?? ''} onChange={(e) => setJsonInputs((prev) => ({ ...prev, [input.name]: e.target.value }))}/>
      </div>)}
    </div>
    {!artifact.inputs.length && <div className="modal-note">이 Recipe는 외부 input이 없습니다.</div>}
    <div className="run-options"><label><input type="checkbox" checked={retain} onChange={(e) => setRetain(e.target.checked)}/> Retain intermediates</label><label><input type="checkbox" checked={analyze} onChange={(e) => setAnalyze(e.target.checked)}/> Analyze intermediates</label></div>
  </Modal>;
}
