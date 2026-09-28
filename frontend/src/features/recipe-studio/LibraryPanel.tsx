import { useMemo, useState } from 'react';

import type { FeatureSpec, OperationSpec, RecipeRecord, RecipeSummary, ScalarOperatorSpec } from '../../api';
import { Button, EmptyState, Panel, SearchInput, Tabs } from '../../components/ui';

export type LibrarySelection =
  | { type: 'operation'; name: string }
  | { type: 'feature'; name: string }
  | { type: 'operator'; name: string }
  | { type: 'system'; name: string }
  | { type: 'subrecipe'; name: string }
  | null;

function AddButton({ disabled, onClick }: { disabled?: boolean; onClick: () => void }) {
  return <Button type="button" className="library-add-btn" disabled={disabled} onClick={onClick}>＋</Button>;
}

function LibraryRow({ active, symbol, symbolClass = '', title, subtitle, disabled, onSelect, onAdd, onDoubleClick }: {
  active: boolean; symbol: string; symbolClass?: string; title: string; subtitle: string; disabled: boolean;
  onSelect: () => void; onAdd: () => void; onDoubleClick: () => void;
}) {
  return <div className={`list-item library-row ${active ? 'active' : ''}`}>
    <button type="button" className="library-select-btn" onClick={onSelect} onDoubleClick={onDoubleClick}>
      <span className={`library-symbol ${symbolClass}`}>{symbol}</span>
      <span className="library-text"><strong>{title}</strong><small>{subtitle}</small></span>
    </button>
    <AddButton disabled={disabled} onClick={onAdd}/>
  </div>;
}

export function LibraryPanel({
  record,
  operations,
  features,
  operators,
  recipes,
  selected,
  onSelect,
  onAddOperation,
  onAddFeature,
  onAddOperator,
  onAddSystem,
  onAddSubrecipe,
}: {
  record: RecipeRecord | null;
  operations: OperationSpec[];
  features: FeatureSpec[];
  operators: ScalarOperatorSpec[];
  recipes: RecipeSummary[];
  selected: LibrarySelection;
  onSelect: (selection: LibrarySelection) => void;
  onAddOperation: (spec: OperationSpec) => void;
  onAddFeature: (spec: FeatureSpec) => void;
  onAddOperator: (spec: ScalarOperatorSpec) => void;
  onAddSystem: (type: string) => void;
  onAddSubrecipe: (recipe: RecipeSummary) => void;
}) {
  const [tab, setTab] = useState('Operations');
  const [search, setSearch] = useState('');
  const readonly = !record || record.readonly;
  const graph = record?.kind === 'graph';

  const grouped = useMemo(() => {
    const map = new Map<string, OperationSpec[]>();
    const q = search.trim().toLowerCase();
    for (const op of operations) {
      if (q && !`${op.name} ${op.display_name} ${op.category}`.toLowerCase().includes(q)) continue;
      const list = map.get(op.category) ?? [];
      list.push(op); map.set(op.category, list);
    }
    return [...map.entries()].sort(([a], [b]) => a.localeCompare(b));
  }, [operations, search]);

  const filteredFeatures = features.filter((item) => `${item.name} ${item.display_name} ${item.category}`.toLowerCase().includes(search.toLowerCase()));
  const filteredOperators = operators.filter((item) => `${item.name} ${item.display_name}`.toLowerCase().includes(search.toLowerCase()));
  const filteredRecipes = recipes.filter((item) => item.name !== record?.name && `${item.name} ${item.display_name}`.toLowerCase().includes(search.toLowerCase()));

  const systemNodes = [
    { name: 'roi_crop', display: 'ROI Crop', desc: '이미지 영역을 crop하고 ROI metadata 출력' },
    { name: 'roi_compose', display: 'ROI Compose', desc: '처리된 patch를 원본 위치에 재합성' },
    { name: 'decision', display: 'Decision', desc: 'Scalar 값을 OK/NG 등 label로 판정' },
  ].filter((item) => `${item.name} ${item.display}`.toLowerCase().includes(search.toLowerCase()));

  return <Panel title="Node Library" actions={<span className="panel-subtitle">{operations.length} ops</span>} flush>
    <Tabs items={graph ? ['Operations', 'Features', 'Operators', 'Graph Nodes', 'SubRecipe'] : ['Operations']} active={graph ? tab : 'Operations'} onChange={setTab}/>
    <div className="library-search"><SearchInput placeholder="Library 검색" value={search} onChange={(e) => setSearch(e.target.value)}/></div>
    <div className="library-list">
      {(tab === 'Operations' || !graph) && (grouped.length ? grouped.map(([group, items]) => <div key={group}>
        <div className="section-label">▾ {group}</div>
        {items.map((item) => <LibraryRow key={item.name}
          active={selected?.type === 'operation' && selected.name === item.name}
          symbol="◇" title={item.display_name} subtitle={item.name} disabled={readonly}
          onSelect={() => onSelect({ type: 'operation', name: item.name })}
          onDoubleClick={() => { if (!readonly) onAddOperation(item); }} onAdd={() => onAddOperation(item)}
        />)}
      </div>) : <EmptyState>Operation이 없습니다.</EmptyState>)}

      {graph && tab === 'Features' && (filteredFeatures.length ? filteredFeatures.map((item) => <LibraryRow key={item.name}
        active={selected?.type === 'feature' && selected.name === item.name}
        symbol="ƒ" symbolClass="feature" title={item.display_name} subtitle={`${item.category} · ${item.name}`} disabled={readonly}
        onSelect={() => onSelect({ type: 'feature', name: item.name })}
        onDoubleClick={() => { if (!readonly) onAddFeature(item); }} onAdd={() => onAddFeature(item)}
      />) : <EmptyState>Feature가 없습니다.</EmptyState>)}

      {graph && tab === 'Operators' && (filteredOperators.length ? filteredOperators.map((item) => <LibraryRow key={item.name}
        active={selected?.type === 'operator' && selected.name === item.name}
        symbol="Σ" symbolClass="operator" title={item.display_name} subtitle={`${item.name} · ${item.min_inputs}..${item.max_inputs ?? 'N'} inputs`} disabled={readonly}
        onSelect={() => onSelect({ type: 'operator', name: item.name })}
        onDoubleClick={() => { if (!readonly) onAddOperator(item); }} onAdd={() => onAddOperator(item)}
      />) : <EmptyState>Scalar Operator가 없습니다.</EmptyState>)}

      {graph && tab === 'Graph Nodes' && systemNodes.map((item) => <LibraryRow key={item.name}
        active={selected?.type === 'system' && selected.name === item.name}
        symbol="▱" symbolClass="system" title={item.display} subtitle={item.desc} disabled={readonly}
        onSelect={() => onSelect({ type: 'system', name: item.name })}
        onDoubleClick={() => { if (!readonly) onAddSystem(item.name); }} onAdd={() => onAddSystem(item.name)}
      />)}

      {graph && tab === 'SubRecipe' && (filteredRecipes.length ? filteredRecipes.map((item) => <LibraryRow key={item.name}
        active={selected?.type === 'subrecipe' && selected.name === item.name}
        symbol="◆" symbolClass="recipe" title={item.display_name} subtitle={`${item.kind} · ${item.name} · v${item.version}`} disabled={readonly}
        onSelect={() => onSelect({ type: 'subrecipe', name: item.name })}
        onDoubleClick={() => { if (!readonly) onAddSubrecipe(item); }} onAdd={() => onAddSubrecipe(item)}
      />) : <EmptyState>사용 가능한 SubRecipe가 없습니다.</EmptyState>)}
    </div>
  </Panel>;
}
