import { Download, Trash2, XCircle } from 'lucide-react';
import { useEffect, useState } from 'react';
import { api, errorText } from '../lib/api';
import type { Job } from '../lib/types';
import { fmtTime } from '../lib/util';
import { Alert, Badge, Button, Progress } from './ui';

export function useJob(id: string | null) {
  const [job, setJob] = useState<Job | null>(null);
  useEffect(() => {
    if (!id) {
      setJob(null);
      return;
    }
    let stop = false;
    const tick = async () => {
      try {
        const j = await api.get<Job>(`/api/jobs/${id}`);
        if (stop) return;
        setJob(j);
        if (j.status === 'queued' || j.status === 'running') setTimeout(tick, 700);
      } catch {
        if (!stop) setTimeout(tick, 2000);
      }
    };
    tick();
    return () => {
      stop = true;
    };
  }, [id]);
  return job;
}

const tone = (s: Job['status']) => (s === 'done' ? 'ok' : s === 'failed' ? 'bad' : s === 'cancelled' ? 'warn' : 'lens');
const LABEL: Record<string, string> = { json: 'Report (JSON)', csv: 'Report (CSV)', summary: 'Summary (TXT)', video: 'Annotated video', zip: 'Output images (ZIP)' };

export function fileUrl(job: Job, name: string, download = false) {
  return `/api/jobs/${job.id}/files/${encodeURIComponent(name)}${download ? '?download=true' : ''}`;
}

export default function JobView({ job, onDeleted }: { job: Job; onDeleted?: () => void }) {
  const [err, setErr] = useState<string | null>(null);
  const running = job.status === 'queued' || job.status === 'running';
  return (
    <div className="space-y-3 rounded-xl border border-ink-700 bg-ink-900 p-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={tone(job.status)}>{job.status}</Badge>
        <span className="font-mono text-xs text-fog-400">{job.id}</span>
        <span className="text-xs text-fog-500">{job.kind} · {(job.options?.inputs || []).slice(0, 3).join(', ')}{(job.options?.inputs?.length || 0) > 3 ? ' …' : ''}</span>
        <span className="ml-auto text-xs text-fog-500">{fmtTime(job.created_at)}</span>
      </div>
      {running && (
        <>
          <Progress value={job.progress} />
          <div className="flex items-center justify-between text-xs text-fog-400">
            <span>{job.message}</span>
            <Button variant="ghost" icon={<XCircle className="h-4 w-4" />} onClick={() => api.json(`/api/jobs/${job.id}/cancel`, {}).catch((e) => setErr(errorText(e)))}>
              Cancel
            </Button>
          </div>
        </>
      )}
      {job.status === 'failed' && <Alert tone="bad" title="The job failed">{job.error}</Alert>}
      {job.outputs && (
        <div className="flex flex-wrap gap-2">
          {Object.entries(job.outputs).map(([k, name]) => (
            <a key={k} href={fileUrl(job, name, true)} className="inline-flex items-center gap-1.5 rounded-lg border border-ink-600 bg-ink-800 px-3 py-1.5 text-sm text-fog-100 hover:border-ink-500">
              <Download className="h-3.5 w-3.5" /> {LABEL[k] || name}
            </a>
          ))}
          {!running && (
            <Button
              variant="ghost"
              icon={<Trash2 className="h-4 w-4" />}
              onClick={() => api.del(`/api/jobs/${job.id}`).then(() => onDeleted?.()).catch((e) => setErr(errorText(e)))}
            >
              Delete outputs
            </Button>
          )}
        </div>
      )}
      {err && <Alert tone="bad" onClose={() => setErr(null)}>{err}</Alert>}
    </div>
  );
}
