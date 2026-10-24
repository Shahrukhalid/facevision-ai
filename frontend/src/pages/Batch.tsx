import { Play, X } from 'lucide-react';
import { useState } from 'react';
import JobView, { useJob } from '../components/JobView';
import { Alert, Badge, Button, Card, FileDrop, PageHeader, Select, Slider } from '../components/ui';
import { api, errorText } from '../lib/api';
import type { Job } from '../lib/types';
import { fmtBytes } from '../lib/util';

export default function Batch() {
  const [files, setFiles] = useState<File[]>([]);
  const [mode, setMode] = useState<'analyze' | 'anonymize'>('analyze');
  const [preset, setPreset] = useState('balanced');
  const [method, setMethod] = useState('blur');
  const [concurrency, setConcurrency] = useState(2);
  const [jobId, setJobId] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const job = useJob(jobId);
  const total = files.reduce((s, f) => s + f.size, 0);

  const start = async () => {
    setBusy(true);
    setErr(null);
    try {
      const j = await api.form<Job>('/api/jobs/batch', {
        files,
        options: JSON.stringify({ mode, concurrency, analysis: { preset }, anonymize: { method, strength: 0.7 } }),
      });
      setJobId(j.id);
    } catch (e) {
      setErr(errorText(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-4">
      <PageHeader title="Batch Processing" subtitle="Analyse or anonymise many photos in one go. Files that fail are reported and skipped; the rest carry on." />
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="space-y-4">
          <FileDrop accept="image/jpeg,image/png,image/webp,image/bmp" multiple onFiles={(f) => setFiles((cur) => [...cur, ...f])} label="Add photos" hint="Up to 200 files and 500 MB per batch" />
          {files.length > 0 && (
            <Card title={`${files.length} files · ${fmtBytes(total)}`} actions={<Button variant="ghost" onClick={() => setFiles([])}>Clear</Button>}>
              <ul className="max-h-56 space-y-1 overflow-y-auto text-sm">
                {files.map((f, i) => (
                  <li key={i} className="flex items-center justify-between gap-2">
                    <span className="truncate text-fog-300">{f.name}</span>
                    <span className="flex items-center gap-2 text-xs text-fog-500">{fmtBytes(f.size)}
                      <button aria-label={`Remove ${f.name}`} onClick={() => setFiles(files.filter((_, j) => j !== i))}><X className="h-3.5 w-3.5" /></button>
                    </span>
                  </li>
                ))}
              </ul>
            </Card>
          )}
          {err && <Alert tone="bad">{err}</Alert>}
          {job && <JobView job={job} onDeleted={() => setJobId(null)} />}
          {job?.result && (
            <Card title="Results">
              <table className="w-full text-sm">
                <thead className="text-left text-[11px] uppercase tracking-wider text-fog-500"><tr><th className="pb-2">File</th><th className="pb-2">Faces</th><th className="pb-2">Time</th><th className="pb-2">Status</th></tr></thead>
                <tbody>
                  {job.result.files.map((r: any, i: number) => (
                    <tr key={i} className="border-t border-ink-800">
                      <td className="py-1.5 text-fog-300">{r.file}</td>
                      <td className="py-1.5 font-mono">{r.faces ?? '–'}</td>
                      <td className="py-1.5 font-mono text-xs">{r.ms ? `${r.ms.toFixed(0)} ms` : '–'}</td>
                      <td className="py-1.5">{r.error ? <Badge tone="bad" title={r.error}>failed</Badge> : <Badge tone="ok">done</Badge>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Card>
          )}
        </div>
        <Card title="Options">
          <div className="space-y-3">
            <Select<'analyze' | 'anonymize'> label="Task" value={mode} onChange={setMode} options={[{ value: 'analyze', label: 'Analyse and annotate' }, { value: 'anonymize', label: 'Anonymise faces' }]} />
            {mode === 'analyze' ? (
              <Select label="Analysis" value={preset} onChange={setPreset} options={[{ value: 'fast', label: 'Fast' }, { value: 'balanced', label: 'Balanced' }, { value: 'detailed', label: 'Detailed' }]} />
            ) : (
              <Select label="Method" value={method} onChange={setMethod} options={[{ value: 'blur', label: 'Blur' }, { value: 'pixelate', label: 'Pixelate' }, { value: 'solid', label: 'Solid mask' }]} />
            )}
            <Slider label="Files processed at once" value={concurrency} min={1} max={4} step={1} onChange={setConcurrency} />
            <p className="text-xs text-fog-500">Higher values finish sooner on multi-core machines but use more memory. Each file is read, processed and released one at a time per worker.</p>
            <Button variant="primary" icon={<Play className="h-4 w-4" />} disabled={!files.length} busy={busy} onClick={start}>Start batch</Button>
          </div>
        </Card>
      </div>
    </div>
  );
}
