import { ArrowRight, Boxes, Camera, Cpu, ShieldCheck } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Badge, Card, Empty, KV, PageHeader, Sparkline, Stat } from '../components/ui';
import { api } from '../lib/api';
import { useApp } from '../lib/store';
import type { Job } from '../lib/types';
import { fmtBytes, fmtTime } from '../lib/util';

export default function Dashboard() {
  const { system, cpuHistory, models, live, auth, refreshModels } = useApp();
  const [jobs, setJobs] = useState<Job[]>([]);
  const [camPermission, setCamPermission] = useState<string>('unknown');
  const [cameras, setCameras] = useState<number | null>(null);
  const [people, setPeople] = useState<number | null>(null);

  useEffect(() => {
    refreshModels();
    api.get<Job[]>('/api/jobs').then((j) => setJobs(j.slice(0, 6))).catch(() => undefined);
    api.get<{ persons: number }>('/api/data/summary').then((s) => setPeople(s.persons)).catch(() => undefined);
    navigator.permissions?.query({ name: 'camera' as PermissionName }).then((p) => {
      setCamPermission(p.state);
      p.onchange = () => setCamPermission(p.state);
    }).catch(() => setCamPermission('unknown'));
    navigator.mediaDevices?.enumerateDevices().then((d) => setCameras(d.filter((x) => x.kind === 'videoinput').length)).catch(() => undefined);
  }, [refreshModels]);

  const accel = system?.hardware.accelerators;
  const installed = models.filter((m) => m.installed);
  const active = models.filter((m) => m.enabled);
  const detectorReady = models.find((m) => m.id === 'yunet')?.installed;

  return (
    <div className="space-y-6">
      <PageHeader title="Dashboard" subtitle="Everything runs on this computer. Nothing is uploaded, and the camera only starts when you start it." />
      {!detectorReady && models.length > 0 && (
        <div className="flex flex-wrap items-center gap-3 rounded-xl border border-lens-500/40 bg-lens-500/10 px-4 py-3 text-sm">
          <Boxes className="h-4 w-4 text-lens-300" />
          <span className="flex-1">Install the default models to get started (about 80 MB, downloaded once with checksum verification).</span>
          <Link to="/models" className="rounded-lg bg-lens-500 px-3 py-1.5 font-medium text-ink-950">Open Model Manager</Link>
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Card>
          <Stat label="Camera" value={live.running ? 'On' : 'Off'} tone={live.running ? 'ok' : undefined}
            sub={`${cameras ?? '–'} camera${cameras === 1 ? '' : 's'} found · permission ${camPermission}`} />
        </Card>
        <Card>
          <Stat label="Processing" value={live.running ? `${live.processingFps.toFixed(0)} fps` : '–'}
            sub={live.running ? `${live.latency.toFixed(0)} ms per frame · display ${live.fps} fps` : 'Start a live view to measure'} />
        </Card>
        <Card>
          <Stat label="Faces in view" value={live.running ? live.faces : '–'} sub={live.running ? `${live.recognized} recognised` : `on ${live.page || 'no live page'}`} />
        </Card>
        <Card>
          <Stat label="Recognition" value={auth.signed_in ? 'Unlocked' : auth.configured ? 'Locked' : 'Not set up'} tone={auth.signed_in ? 'ok' : undefined}
            sub={people !== null ? `${people} enrolled ${people === 1 ? 'person' : 'people'}` : 'Sign in to see enrolled people'} />
        </Card>
      </div>

      <div className="grid gap-4 xl:grid-cols-3">
        <Card title="Resources" actions={<Cpu className="h-4 w-4 text-fog-500" />}>
          <div className="flex items-end justify-between">
            <Stat label="CPU" value={`${system?.cpu.percent.toFixed(0) ?? '–'}%`} sub={`${system?.cpu.count ?? '–'} logical cores · app ${system?.cpu.process_percent.toFixed(0) ?? '–'}%`} />
            <div className="w-40"><Sparkline data={cpuHistory} /></div>
          </div>
          <div className="mt-4 space-y-0.5">
            <KV k="Memory used" v={`${system?.memory.percent.toFixed(0) ?? '–'}% of ${fmtBytes(system?.memory.total)}`} />
            <KV k="FaceVision AI memory" v={fmtBytes(system?.memory.process_rss)} />
            <KV k="Models on disk" v={fmtBytes(system?.disk.models)} />
            <KV k="Processing files" v={fmtBytes(system?.disk.outputs)} />
          </div>
        </Card>

        <Card title="Hardware acceleration">
          <div className="space-y-0.5">
            <KV k="Platform" v={`${system?.platform.system ?? '–'} · ${system?.platform.machine ?? ''}`} />
            <KV k="Apple Core ML" v={accel ? (accel.coreml ? <Badge tone="ok">available</Badge> : <Badge>not available</Badge>) : '–'} />
            <KV k="DirectML (Windows GPU)" v={accel ? (accel.directml ? <Badge tone="ok">available</Badge> : <Badge>not available</Badge>) : '–'} />
            <KV k="CUDA" v={accel ? (accel.cuda ? <Badge tone="ok">available</Badge> : <Badge>not available</Badge>) : '–'} />
            <KV k="Preference" v={system?.hardware.preference === 'cpu' ? 'CPU only' : 'Accelerator when available'} />
          </div>
          <div className="mt-3 text-xs text-fog-500">
            Loaded models and the engine they run on:
            <ul className="mt-1 space-y-0.5">
              {Object.entries(system?.models.loaded || {}).map(([k, v]) => (
                <li key={k} className="flex justify-between gap-2"><span className="text-fog-300">{k}</span><span className="truncate font-mono">{v.provider.replace('ExecutionProvider', '')}</span></li>
              ))}
              {!Object.keys(system?.models.loaded || {}).length && <li>None loaded yet. They load on first use.</li>}
            </ul>
          </div>
        </Card>

        <Card title="Models" actions={<Link to="/models" className="text-xs text-lens-300 hover:underline">Manage</Link>}>
          <div className="mb-3 flex gap-6">
            <Stat label="Installed" value={`${installed.length}/${models.length}`} />
            <Stat label="Active" value={active.length} />
          </div>
          <ul className="space-y-1.5 text-sm">
            {models.map((m) => (
              <li key={m.id} className="flex items-center justify-between gap-2">
                <span className="truncate text-fog-300">{m.name}</span>
                {m.enabled ? <Badge tone="ok">active</Badge> : m.installed ? <Badge>off</Badge> : <Badge tone="warn">not installed</Badge>}
              </li>
            ))}
          </ul>
        </Card>
      </div>

      <div className="grid gap-4 xl:grid-cols-3">
        <Card title="Recent processing jobs" className="xl:col-span-2" actions={<Link to="/reports" className="text-xs text-lens-300 hover:underline">All reports</Link>}>
          {jobs.length === 0 ? (
            <Empty title="No jobs yet">Video and batch jobs you run appear here.</Empty>
          ) : (
            <table className="w-full text-sm">
              <thead className="text-left text-[11px] uppercase tracking-wider text-fog-500">
                <tr><th className="pb-2">Job</th><th className="pb-2">Type</th><th className="pb-2">Status</th><th className="pb-2 text-right">Started</th></tr>
              </thead>
              <tbody>
                {jobs.map((j) => (
                  <tr key={j.id} className="border-t border-ink-800">
                    <td className="py-2 font-mono text-xs text-fog-300">{j.id}</td>
                    <td className="py-2 text-fog-300">{j.kind}</td>
                    <td className="py-2"><Badge tone={j.status === 'done' ? 'ok' : j.status === 'failed' ? 'bad' : 'lens'}>{j.status}</Badge></td>
                    <td className="py-2 text-right text-xs text-fog-400">{fmtTime(j.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>
        <Card title="Start">
          <div className="space-y-2">
            {[
              { to: '/live', icon: Camera, label: 'Live face detection', sub: 'Webcam with tracking and overlays' },
              { to: '/enrolled', icon: ShieldCheck, label: 'Enrol a consenting person', sub: 'Needs their informed consent' },
              { to: '/privacy', icon: Boxes, label: 'Blur faces in a photo or video', sub: 'No recognition needed' },
            ].map(({ to, icon: Icon, label, sub }) => (
              <Link key={to} to={to} className="flex items-center gap-3 rounded-lg border border-ink-700 px-3 py-2.5 hover:border-ink-500">
                <Icon className="h-4 w-4 text-lens-400" />
                <div className="flex-1"><div className="text-sm text-fog-100">{label}</div><div className="text-xs text-fog-500">{sub}</div></div>
                <ArrowRight className="h-4 w-4 text-fog-500" />
              </Link>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}
