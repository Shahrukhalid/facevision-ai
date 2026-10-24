import { AlertTriangle, CheckCircle2, Info, Loader2, Upload, X, XCircle } from 'lucide-react';
import { useEffect, useId, useRef, useState, type ButtonHTMLAttributes, type ReactNode } from 'react';

const cx = (...c: (string | false | null | undefined)[]) => c.filter(Boolean).join(' ');
export { cx };

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        <h1 className="font-display text-2xl font-semibold tracking-tight text-fog-100">{title}</h1>
        {subtitle && <p className="mt-1 max-w-3xl text-sm text-fog-400">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

export function Card({ title, actions, children, className, pad = true }: { title?: ReactNode; actions?: ReactNode; children: ReactNode; className?: string; pad?: boolean }) {
  return (
    <section className={cx('rounded-xl border border-ink-700 bg-ink-900', className)}>
      {(title || actions) && (
        <header className="flex items-center justify-between gap-3 border-b border-ink-700 px-4 py-3">
          <h2 className="text-[13px] font-semibold uppercase tracking-wider text-fog-300">{title}</h2>
          {actions}
        </header>
      )}
      <div className={pad ? 'p-4' : ''}>{children}</div>
    </section>
  );
}

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger';
export function Button({ variant = 'secondary', busy, icon, children, className, ...rest }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; busy?: boolean; icon?: ReactNode }) {
  const styles: Record<Variant, string> = {
    primary: 'bg-lens-500 text-ink-950 hover:bg-lens-400 font-semibold',
    secondary: 'bg-ink-800 text-fog-100 border border-ink-600 hover:border-ink-500 hover:bg-ink-700',
    ghost: 'text-fog-300 hover:bg-ink-800 hover:text-fog-100',
    danger: 'bg-bad/15 text-bad border border-bad/40 hover:bg-bad/25',
  };
  return (
    <button
      {...rest}
      disabled={rest.disabled || busy}
      className={cx(
        'inline-flex items-center justify-center gap-2 rounded-lg px-3 py-2 text-sm transition focus:outline-none focus-visible:ring-2 focus-visible:ring-lens-400 disabled:cursor-not-allowed disabled:opacity-45',
        styles[variant],
        className,
      )}
    >
      {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : icon}
      {children}
    </button>
  );
}

export function Badge({ tone = 'neutral', children, title }: { tone?: 'neutral' | 'ok' | 'warn' | 'bad' | 'info' | 'lens'; children: ReactNode; title?: string }) {
  const t = {
    neutral: 'bg-ink-700 text-fog-300',
    ok: 'bg-ok/15 text-ok',
    warn: 'bg-warn/15 text-warn',
    bad: 'bg-bad/15 text-bad',
    info: 'bg-info/15 text-info',
    lens: 'bg-lens-500/15 text-lens-300',
  }[tone];
  return (
    <span title={title} className={cx('inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2 py-0.5 text-[11px] font-medium', t)}>
      {children}
    </span>
  );
}

export function Toggle({ label, checked, onChange, disabled, hint }: { label: ReactNode; checked: boolean; onChange: (v: boolean) => void; disabled?: boolean; hint?: string }) {
  const id = useId();
  return (
    <label htmlFor={id} title={hint} className={cx('flex cursor-pointer items-center justify-between gap-3 py-1 text-sm', disabled && 'cursor-not-allowed opacity-50')}>
      <span className="text-fog-300">{label}</span>
      <button
        id={id}
        type="button"
        role="switch"
        aria-checked={checked}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className={cx('relative h-5 w-9 shrink-0 rounded-full transition focus:outline-none focus-visible:ring-2 focus-visible:ring-lens-400', checked ? 'bg-lens-500' : 'bg-ink-600')}
      >
        <span className={cx('absolute top-0.5 h-4 w-4 rounded-full bg-fog-100 transition-all', checked ? 'left-[18px]' : 'left-0.5')} />
      </button>
    </label>
  );
}

export function Select<T extends string>({ label, value, options, onChange, disabled }: { label?: string; value: T; options: { value: T; label: string }[]; onChange: (v: T) => void; disabled?: boolean }) {
  const id = useId();
  return (
    <label htmlFor={id} className="flex flex-col gap-1 text-sm">
      {label && <span className="text-xs text-fog-400">{label}</span>}
      <select
        id={id}
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value as T)}
        className="rounded-lg border border-ink-600 bg-ink-800 px-2.5 py-2 text-fog-100 focus:border-lens-500 focus:outline-none disabled:opacity-50"
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </label>
  );
}

export function Slider({ label, value, min, max, step, onChange, format }: { label: string; value: number; min: number; max: number; step: number; onChange: (v: number) => void; format?: (v: number) => string }) {
  const id = useId();
  return (
    <label htmlFor={id} className="flex flex-col gap-1 text-sm">
      <span className="flex justify-between text-xs text-fog-400">
        <span>{label}</span>
        <span className="font-mono text-fog-300">{format ? format(value) : value}</span>
      </span>
      <input id={id} type="range" min={min} max={max} step={step} value={value} onChange={(e) => onChange(Number(e.target.value))} className="accent-[#33b6c9]" />
    </label>
  );
}

export function TextInput({ label, value, onChange, type = 'text', placeholder, autoComplete }: { label: string; value: string; onChange: (v: string) => void; type?: string; placeholder?: string; autoComplete?: string }) {
  const id = useId();
  return (
    <label htmlFor={id} className="flex flex-col gap-1 text-sm">
      <span className="text-xs text-fog-400">{label}</span>
      <input
        id={id}
        type={type}
        value={value}
        placeholder={placeholder}
        autoComplete={autoComplete}
        onChange={(e) => onChange(e.target.value)}
        className="rounded-lg border border-ink-600 bg-ink-800 px-3 py-2 text-fog-100 placeholder:text-fog-500 focus:border-lens-500 focus:outline-none"
      />
    </label>
  );
}

export function Alert({ tone = 'info', title, children, onClose }: { tone?: 'info' | 'warn' | 'bad' | 'ok'; title?: string; children?: ReactNode; onClose?: () => void }) {
  const Icon = { info: Info, warn: AlertTriangle, bad: XCircle, ok: CheckCircle2 }[tone];
  const color = { info: 'border-info/30 bg-info/10 text-info', warn: 'border-warn/30 bg-warn/10 text-warn', bad: 'border-bad/30 bg-bad/10 text-bad', ok: 'border-ok/30 bg-ok/10 text-ok' }[tone];
  return (
    <div role={tone === 'bad' ? 'alert' : 'status'} className={cx('flex gap-3 rounded-lg border px-3 py-2.5 text-sm', color)}>
      <Icon className="mt-0.5 h-4 w-4 shrink-0" />
      <div className="min-w-0 flex-1 text-fog-100">
        {title && <div className="font-medium">{title}</div>}
        {children && <div className="text-fog-300">{children}</div>}
      </div>
      {onClose && (
        <button onClick={onClose} aria-label="Dismiss" className="text-fog-400 hover:text-fog-100">
          <X className="h-4 w-4" />
        </button>
      )}
    </div>
  );
}

export function Progress({ value, tone = 'lens' }: { value: number; tone?: 'lens' | 'ok' | 'warn' | 'bad' }) {
  const c = { lens: 'bg-lens-500', ok: 'bg-ok', warn: 'bg-warn', bad: 'bg-bad' }[tone];
  return (
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-ink-700" role="progressbar" aria-valuenow={Math.round(value * 100)} aria-valuemin={0} aria-valuemax={100}>
      <div className={cx('h-full rounded-full transition-all', c)} style={{ width: `${Math.max(0, Math.min(1, value)) * 100}%` }} />
    </div>
  );
}

export function Stat({ label, value, sub, tone }: { label: string; value: ReactNode; sub?: ReactNode; tone?: 'ok' | 'warn' | 'bad' }) {
  const t = tone ? { ok: 'text-ok', warn: 'text-warn', bad: 'text-bad' }[tone] : 'text-fog-100';
  return (
    <div className="min-w-0">
      <div className="text-[11px] uppercase tracking-wider text-fog-500">{label}</div>
      <div className={cx('mt-1 font-display text-2xl font-semibold tabular-nums', t)}>{value}</div>
      {sub && <div className="mt-0.5 truncate text-xs text-fog-400">{sub}</div>}
    </div>
  );
}

export function Empty({ icon, title, children }: { icon?: ReactNode; title: string; children?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-ink-600 px-6 py-10 text-center">
      {icon && <div className="text-fog-500">{icon}</div>}
      <div className="font-medium text-fog-300">{title}</div>
      {children && <div className="max-w-md text-sm text-fog-400">{children}</div>}
    </div>
  );
}

export function FileDrop({ accept, multiple, onFiles, label, hint }: { accept: string; multiple?: boolean; onFiles: (f: File[]) => void; label: string; hint?: string }) {
  const [over, setOver] = useState(false);
  const ref = useRef<HTMLInputElement>(null);
  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setOver(false);
        const files = Array.from(e.dataTransfer.files);
        if (files.length) onFiles(multiple ? files : files.slice(0, 1));
      }}
      onClick={() => ref.current?.click()}
      onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && ref.current?.click()}
      role="button"
      tabIndex={0}
      className={cx(
        'flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed px-6 py-8 text-center transition focus:outline-none focus-visible:ring-2 focus-visible:ring-lens-400',
        over ? 'border-lens-400 bg-lens-500/5' : 'border-ink-600 hover:border-ink-500',
      )}
    >
      <Upload className="h-6 w-6 text-fog-400" />
      <div className="text-sm font-medium text-fog-100">{label}</div>
      {hint && <div className="text-xs text-fog-400">{hint}</div>}
      <input
        ref={ref}
        type="file"
        accept={accept}
        multiple={multiple}
        className="hidden"
        onChange={(e) => {
          const files = Array.from(e.target.files || []);
          if (files.length) onFiles(files);
          e.target.value = '';
        }}
      />
    </div>
  );
}

export function Modal({ open, title, children, onClose, footer }: { open: boolean; title: string; children: ReactNode; onClose: () => void; footer?: ReactNode }) {
  useEffect(() => {
    if (!open) return;
    const h = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', h);
    return () => window.removeEventListener('keydown', h);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4" onMouseDown={onClose}>
      <div role="dialog" aria-modal="true" aria-label={title} className="max-h-[90vh] w-full max-w-lg overflow-auto rounded-xl border border-ink-600 bg-ink-900 shadow-2xl" onMouseDown={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between border-b border-ink-700 px-5 py-3">
          <h3 className="font-display text-lg font-semibold text-fog-100">{title}</h3>
          <button onClick={onClose} aria-label="Close" className="text-fog-400 hover:text-fog-100">
            <X className="h-5 w-5" />
          </button>
        </div>
        <div className="space-y-4 px-5 py-4 text-sm text-fog-300">{children}</div>
        {footer && <div className="flex justify-end gap-2 border-t border-ink-700 px-5 py-3">{footer}</div>}
      </div>
    </div>
  );
}

export function Meter({ label, value, max = 1, tone, suffix }: { label: string; value: number; max?: number; tone?: string; suffix?: string }) {
  const pct = Math.max(0, Math.min(1, value / max));
  return (
    <div className="text-xs">
      <div className="mb-1 flex justify-between">
        <span className="text-fog-400">{label}</span>
        <span className="font-mono tabular-nums text-fog-300">{suffix ?? `${Math.round(pct * 100)}%`}</span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-ink-700">
        <div className="h-full rounded-full" style={{ width: `${pct * 100}%`, background: tone || '#33b6c9' }} />
      </div>
    </div>
  );
}

export function KV({ k, v, mono }: { k: ReactNode; v: ReactNode; mono?: boolean }) {
  return (
    <div className="flex items-baseline justify-between gap-3 py-1 text-sm">
      <span className="text-fog-400">{k}</span>
      <span className={cx('text-right text-fog-100', mono && 'font-mono tabular-nums')}>{v}</span>
    </div>
  );
}

export function Sparkline({ data, max = 100, height = 36, color = '#5fd0e0' }: { data: number[]; max?: number; height?: number; color?: string }) {
  const w = 160;
  if (data.length < 2) return <div style={{ height }} />;
  const pts = data.map((v, i) => [(i / (data.length - 1)) * w, height - (Math.min(max, v) / max) * (height - 4) - 2]);
  const line = pts.map((p, i) => `${i ? 'L' : 'M'}${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(' ');
  const last = pts[pts.length - 1];
  return (
    <svg viewBox={`0 0 ${w} ${height}`} className="w-full" style={{ height }} preserveAspectRatio="none" aria-hidden>
      <path d={`${line} L${w},${height} L0,${height} Z`} fill={color} opacity={0.12} />
      <path d={line} fill="none" stroke={color} strokeWidth={1.5} vectorEffect="non-scaling-stroke" />
      <circle cx={last[0]} cy={last[1]} r={2.5} fill={color} />
    </svg>
  );
}
