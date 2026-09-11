import type { ButtonHTMLAttributes, PropsWithChildren, ReactNode } from 'react';

type ButtonProps = PropsWithChildren<ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'default'|'primary'|'danger'|'ghost' }>;
export function Button({ children, variant = 'default', className = '', ...props }: ButtonProps) {
  return <button className={`btn ${variant === 'default' ? '' : variant} ${className}`} {...props}>{children}</button>;
}

export function IconButton({ children, title }: PropsWithChildren<{ title?: string }>) {
  return <button className="icon-btn" title={title}>{children}</button>;
}

export function Panel({ title, subtitle, actions, children, className = '', flush = false }: PropsWithChildren<{ title?: string; subtitle?: string; actions?: ReactNode; className?: string; flush?: boolean }>) {
  return <section className={`panel ${className}`}>
    {(title || subtitle || actions) && <div className="panel-header">
      <div>
        {title && <div className="panel-title">{title}</div>}
        {subtitle && <div className="panel-subtitle">{subtitle}</div>}
      </div>
      {actions && <div className="panel-actions">{actions}</div>}
    </div>}
    <div className={`panel-body ${flush ? 'flush' : ''}`}>{children}</div>
  </section>;
}

export function Badge({ status, children }: PropsWithChildren<{ status?: string }>) {
  return <span className={`badge ${status ?? ''}`}>{children}</span>;
}

export function ProgressBar({ value }: { value: number }) {
  const safe = Math.max(0, Math.min(100, value));
  return <div className="progress"><span style={{ width: `${safe}%` }} /></div>;
}

export function SearchInput({ placeholder = '검색' }: { placeholder?: string }) {
  return <div className="search"><input className="input" placeholder={placeholder} /></div>;
}

export function Tabs({ items, active, onChange }: { items: string[]; active: string; onChange?: (item: string) => void }) {
  return <div className="tabs">{items.map((item) => <button key={item} onClick={() => onChange?.(item)} className={`tab ${item === active ? 'active' : ''}`}>{item}</button>)}</div>;
}

export function Modal({ title, children, onClose, footer }: PropsWithChildren<{ title: string; onClose: () => void; footer?: ReactNode }>) {
  return <div className="modal-backdrop" onMouseDown={onClose}><div className="modal" onMouseDown={(e) => e.stopPropagation()}>
    <div className="modal-header"><div className="panel-title">{title}</div><button className="icon-btn" onClick={onClose}>×</button></div>
    <div className="modal-body">{children}</div>
    {footer && <div className="modal-footer">{footer}</div>}
  </div></div>;
}


export function Field({ label, children, help }: PropsWithChildren<{ label: string; help?: string }>) {
  return <div className="field"><div className="field-label">{label}</div><div className="field-stack">{children}{help && <div className="help">{help}</div>}</div></div>;
}

export function Kpi({ label, value, meta }: { label: string; value: string; meta?: string }) {
  return <div className="kpi"><div className="kpi-label">{label}</div><div className="kpi-value">{value}</div>{meta && <div className="kpi-meta">{meta}</div>}</div>;
}
