import type { JsonMap, ParameterSpec } from '../../api';
import { Field } from '../../components/ui';

function coerceNumber(value: string, integer: boolean): number | '' {
  if (value === '') return '';
  const parsed = integer ? Number.parseInt(value, 10) : Number.parseFloat(value);
  return Number.isFinite(parsed) ? parsed : '';
}

export function ParameterEditor({
  parameters,
  values,
  disabled = false,
  onChange,
}: {
  parameters: Record<string, ParameterSpec>;
  values: JsonMap;
  disabled?: boolean;
  onChange: (name: string, value: unknown) => void;
}) {
  const entries = Object.entries(parameters).sort(([, a], [, b]) => (a.order ?? 0) - (b.order ?? 0));
  if (!entries.length) return <div className="inspector-muted">Parameters 없음</div>;

  return <div className="parameter-list">
    {entries.map(([name, spec]) => {
      const value = values[name] ?? spec.default ?? '';
      const help = [spec.description, spec.unit ? `unit: ${spec.unit}` : null].filter(Boolean).join(' · ');
      if (spec.type === 'category') {
        const choices = spec.choices ?? [];
        const selectedIndex = Math.max(0, choices.findIndex((choice) => Object.is(choice.value, value)));
        return <Field key={name} label={spec.title || name} help={help || undefined}>
          <select
            className="select"
            disabled={disabled}
            value={String(selectedIndex)}
            onChange={(event) => {
              const choice = choices[Number(event.target.value)];
              if (choice) onChange(name, choice.value);
            }}
          >
            {choices.map((choice, index) => <option key={`${name}-${index}`} value={index}>{choice.label}</option>)}
          </select>
        </Field>;
      }
      if (spec.type === 'discrete' && spec.values?.length) {
        return <Field key={name} label={spec.title || name} help={help || undefined}>
          <select className="select" disabled={disabled} value={String(value)} onChange={(event) => onChange(name, Number(event.target.value))}>
            {spec.values.map((item) => <option key={String(item)} value={String(item)}>{String(item)}</option>)}
          </select>
        </Field>;
      }
      const integer = spec.type === 'discrete';
      return <Field key={name} label={spec.title || name} help={help || undefined}>
        <input
          className="input"
          type="number"
          disabled={disabled}
          value={String(value)}
          min={spec.min_value ?? undefined}
          max={spec.max_value ?? undefined}
          step={spec.step ?? (integer ? 1 : 'any')}
          onChange={(event) => onChange(name, coerceNumber(event.target.value, integer))}
        />
      </Field>;
    })}
  </div>;
}

export function LooseParameterEditor({
  schema,
  values,
  disabled = false,
  onChange,
}: {
  schema: Record<string, JsonMap>;
  values: JsonMap;
  disabled?: boolean;
  onChange: (name: string, value: unknown) => void;
}) {
  if (!Object.keys(schema).length) return <div className="inspector-muted">Parameters 없음</div>;
  return <div className="parameter-list">
    {Object.entries(schema).map(([name, spec]) => {
      const type = String(spec.type ?? 'string');
      const value = values[name] ?? spec.default ?? (type === 'boolean' ? false : type === 'object' ? {} : '');
      if (type === 'boolean') {
        return <Field key={name} label={name} help={typeof spec.description === 'string' ? spec.description : undefined}>
          <label className="switch-row"><input type="checkbox" disabled={disabled} checked={Boolean(value)} onChange={(e) => onChange(name, e.target.checked)}/><span>{Boolean(value) ? 'True' : 'False'}</span></label>
        </Field>;
      }
      if (type === 'object' || type === 'array') {
        return <Field key={name} label={name} help={typeof spec.description === 'string' ? spec.description : undefined}>
          <textarea
            className="json-input compact"
            disabled={disabled}
            value={JSON.stringify(value, null, 2)}
            onChange={(event) => {
              try { onChange(name, JSON.parse(event.target.value)); } catch { /* keep last valid value */ }
            }}
          />
        </Field>;
      }
      return <Field key={name} label={name} help={typeof spec.description === 'string' ? spec.description : undefined}>
        <input
          className="input"
          type={type === 'number' || type === 'integer' ? 'number' : 'text'}
          disabled={disabled}
          value={String(value)}
          onChange={(event) => onChange(name, type === 'number' || type === 'integer' ? Number(event.target.value) : event.target.value)}
        />
      </Field>;
    })}
  </div>;
}
