import { Archive, FileJson, RefreshCw, Trash2 } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import AuthNotice from '../components/AuthNotice';
import JobView from '../components/JobView';
import { Alert, Button, Card, Empty, KV, Modal, PageHeader, TextInput } from '../components/ui';
import { api, errorText } from '../lib/api';
import { useApp } from '../lib/store';
import type { Job } from '../lib/types';
import { fmtBytes, fmtTime } from '../lib/util';

interface Summary { persons: number; templates: number; jobs: number; audit_entries: number; disk: Record<string, number>; data_dir: string; retention_days: number }

export default function Reports() {
  const { auth, refreshAuth } = useApp();
  const [jobs, setJobs] = useState<Job[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [audit, setAudit] = useState<{ at: string; action: string; detail: string }[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [danger, setDanger] = useState<null | 'bio' | 'all'>(null);
  const [confirm, setConfirm] = useState('');

  const load = useCallback(async () => {
    try {
      setJobs(await api.get<Job[]>('/api/jobs'));
      setSummary(await api.get<Summary>('/api/data/summary'));
      if (auth.signed_in) setAudit(await api.get('/api/audit?limit=100'));
    } catch (e) {
      setErr(errorText(e));
    }
  }, [auth.signed_in]);
  useEffect(() => {
    load();
  }, [load]);

  const wipe = async () => {
    try {
      if (danger === 'bio') await api.json('/api/data/delete-biometrics', { confirm });
      else await api.json('/api/data/delete-all', { confirm });
      setDanger(null);
      setConfirm('');
      await refreshAuth();
      load();
    } catch (e) {
      setErr(errorText(e));
    }
  };

  return (
    <div className="space-y-4">
      <PageHeader title="Reports & Export" subtitle="Download reports from processing jobs, export or back up your data, and delete what you no longer need." actions={<Button icon={<RefreshCw className="h-4 w-4" />} onClick={load}>Refresh</Button>} />
      {err && <Alert tone="bad" onClose={() => setErr(null)}>{err}</Alert>}
      <div className="grid gap-4 lg:grid-cols-3">
        <Card title="Stored on this computer">
          <KV k="Enrolled people" v={summary?.persons ?? '–'} mono />
          <KV k="Face templates (encrypted)" v={summary?.templates ?? '–'} mono />
          <KV k="Jobs" v={summary?.jobs ?? '–'} mono />
          <KV k="Database" v={fmtBytes(summary?.disk.database)} />
          <KV k="Job outputs" v={fmtBytes(summary?.disk.outputs)} />
          <KV k="Keep job outputs for" v={summary ? `${summary.retention_days} days` : '–'} />
          <div className="mt-2 break-all font-mono text-[11px] text-fog-500">{summary?.data_dir}</div>
        </Card>
        <Card title="Export and backup">
          <AuthNotice what="export or back up data" />
          <div className="mt-3 space-y-2">
            <a href="/api/data/export" className={`flex items-center gap-2 rounded-lg border border-ink-600 px-3 py-2 text-sm ${auth.signed_in ? 'hover:border-ink-500' : 'pointer-events-none opacity-50'}`}><FileJson className="h-4 w-4" /> Export data (JSON, no face templates)</a>
            <a href="/api/data/backup" className={`flex items-center gap-2 rounded-lg border border-ink-600 px-3 py-2 text-sm ${auth.signed_in ? 'hover:border-ink-500' : 'pointer-events-none opacity-50'}`}><Archive className="h-4 w-4" /> Back up database (ZIP, templates stay encrypted)</a>
            <p className="text-xs text-fog-500">A backup can only be used with the passphrase that was active when it was made. Store it as carefully as the computer itself.</p>
          </div>
        </Card>
        <Card title="Delete data">
          <div className="space-y-2">
            <Button variant="danger" icon={<Trash2 className="h-4 w-4" />} disabled={!auth.signed_in} onClick={() => setDanger('bio')}>Delete all enrolled faces</Button>
            <Button variant="danger" icon={<Trash2 className="h-4 w-4" />} disabled={!auth.signed_in} onClick={() => setDanger('all')}>Delete everything (factory reset)</Button>
            <p className="text-xs text-fog-500">Factory reset removes people, templates, jobs, settings, the audit log and the passphrase. Installed models are kept.</p>
          </div>
        </Card>
      </div>
      <Card title={`Processing jobs (${jobs.length})`}>
        {jobs.length === 0 ? <Empty title="No reports yet">Run a video or batch job to create one.</Empty> : (
          <div className="space-y-3">{jobs.map((j) => <JobView key={j.id} job={j} onDeleted={load} />)}</div>
        )}
      </Card>
      {auth.signed_in && (
        <Card title="Audit log">
          <p className="mb-2 text-xs text-fog-500">Administrative actions only. Individual recognitions are not logged, so no movement history is built up.</p>
          <ul className="max-h-72 space-y-0.5 overflow-y-auto font-mono text-xs">
            {audit.map((a, i) => <li key={i} className="flex gap-3"><span className="text-fog-500">{fmtTime(a.at)}</span><span className="text-fog-100">{a.action}</span><span className="text-fog-400">{a.detail}</span></li>)}
          </ul>
        </Card>
      )}
      <Modal
        open={danger !== null}
        title={danger === 'bio' ? 'Delete all enrolled faces?' : 'Delete everything?'}
        onClose={() => setDanger(null)}
        footer={<><Button onClick={() => setDanger(null)}>Cancel</Button><Button variant="danger" disabled={confirm !== (danger === 'bio' ? 'DELETE' : 'DELETE EVERYTHING')} onClick={wipe}>Delete permanently</Button></>}
      >
        <p>{danger === 'bio' ? 'All enrolled people and their face templates are deleted. This cannot be undone.' : 'All people, templates, jobs, reports, settings, the audit log and your passphrase are deleted. This cannot be undone.'}</p>
        <TextInput label={`Type ${danger === 'bio' ? 'DELETE' : 'DELETE EVERYTHING'} to confirm`} value={confirm} onChange={setConfirm} />
      </Modal>
    </div>
  );
}
