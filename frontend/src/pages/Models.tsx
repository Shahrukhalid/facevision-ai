import { CheckCircle2, Download, ExternalLink, Flame, ShieldAlert, Trash2, XCircle } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Alert, Badge, Button, Card, KV, Modal, PageHeader, Progress, Select, Toggle } from '../components/ui';
import { api, errorText } from '../lib/api';
import { useApp } from '../lib/store';
import type { ModelInfo } from '../lib/types';
import { fmtBytes } from '../lib/util';

const TASKS: Record<string, string> = {
  detection: 'Face detection', recognition: 'Face embeddings', landmarks: 'Landmarks and mesh', expression: 'Expression',
  liveness: 'Anti-spoofing', attributes: 'Attributes and age', research: 'Research pack',
};

export default function Models() {
  const { models, refreshModels, system, settings, saveSettings, refreshSystem } = useApp();
  const [err, setErr] = useState<string | null>(null);
  const [licence, setLicence] = useState<ModelInfo | null>(null);
  const [verify, setVerify] = useState<Record<string, Record<string, string>>>({});
  const [warm, setWarm] = useState<Record<string, number | string> | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const downloading = models.some((m) => m.download.status === 'downloading' || m.download.status === 'verifying');
  useEffect(() => {
    if (!downloading) return;
    const t = setInterval(refreshModels, 800);
    return () => clearInterval(t);
  }, [downloading, refreshModels]);

  const act = async (fn: () => Promise<unknown>) => {
    setErr(null);
    try {
      await fn();
    } catch (e) {
      setErr(errorText(e));
    }
    refreshModels();
  };
  const install = (m: ModelInfo, accept = false) => act(() => api.json(`/api/models/${m.id}/install`, { accept_license: accept }));
  const missingDefaults = models.filter((m) => m.default && !m.installed && !m.research_only);

  return (
    <div className="space-y-4">
      <PageHeader
        title="Model Manager"
        subtitle="Each model is downloaded once from its published source, checked against a SHA-256 checksum and stored on this computer. After that everything works offline."
        actions={
          <>
            {missingDefaults.length > 0 && <Button variant="primary" icon={<Download className="h-4 w-4" />} onClick={() => missingDefaults.forEach((m) => install(m))}>Install defaults</Button>}
            <Button icon={<Flame className="h-4 w-4" />} busy={busy === 'warm'} onClick={async () => { setBusy('warm'); try { setWarm((await api.json<{ timings_ms: Record<string, number> }>('/api/models/warmup', {})).timings_ms); refreshSystem(); } catch (e) { setErr(errorText(e)); } setBusy(null); }}>Warm up and time</Button>
          </>
        }
      />
      {err && <Alert tone="bad" onClose={() => setErr(null)}>{err}</Alert>}
      {system?.offline_mode && <Alert tone="info">Offline mode is on (FV_OFFLINE=1). Downloads are disabled.</Alert>}
      <div className="grid gap-4 lg:grid-cols-3">
        <Card title="Compute">
          <Select<'auto' | 'cpu'>
            label="Run models on"
            value={settings?.accelerator || 'auto'}
            onChange={(v) => saveSettings({ accelerator: v }).catch((e) => setErr(errorText(e)))}
            options={[{ value: 'auto', label: 'Accelerator when available, otherwise CPU' }, { value: 'cpu', label: 'CPU only' }]}
          />
          <div className="mt-3 space-y-0.5 text-sm">
            <KV k="ONNX Runtime" v={system?.hardware.onnxruntime ?? '–'} mono />
            <KV k="Providers" v={<span className="text-xs">{system?.hardware.providers.map((p) => p.replace('ExecutionProvider', '')).join(', ')}</span>} />
            <KV k="OpenCV" v={system?.libraries.opencv ?? '–'} mono />
            <KV k="MediaPipe" v={system?.libraries.mediapipe ?? '–'} mono />
          </div>
          <p className="mt-2 text-xs text-fog-500">YuNet, SFace and MediaPipe run on the CPU through OpenCV and MediaPipe. ONNX models (FER+, anti-spoofing, CLIP, research pack) use Core ML on Apple Silicon or DirectML on Windows when the matching ONNX Runtime package is installed, and fall back to the CPU if a model cannot run there.</p>
        </Card>
        <Card title="Warm-up timings" className="lg:col-span-2">
          {warm ? (
            <div className="grid gap-x-6 sm:grid-cols-2">
              {Object.entries(warm).map(([k, v]) => <KV key={k} k={k} v={typeof v === 'number' ? `${v} ms` : v} mono />)}
            </div>
          ) : (
            <p className="text-sm text-fog-400">Loads each active model and times one run on a blank frame, so the first real frame is not slow. Times include first-run setup.</p>
          )}
          {system && Object.keys(system.models.errors).length > 0 && (
            <div className="mt-3 space-y-1">{Object.entries(system.models.errors).map(([k, v]) => <Alert key={k} tone="bad" title={`${k} failed to load`}>{v}</Alert>)}</div>
          )}
        </Card>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        {models.map((m) => {
          const d = m.download;
          const active = d.status === 'downloading' || d.status === 'verifying';
          return (
            <Card key={m.id} title={TASKS[m.task] || m.task} actions={m.installed ? (m.enabled ? <Badge tone="ok">active</Badge> : <Badge>off</Badge>) : <Badge tone="warn">not installed</Badge>}>
              <div className="space-y-3">
                <div>
                  <div className="font-display text-lg font-semibold text-fog-100">{m.name}</div>
                  <p className="mt-1 text-sm text-fog-400">{m.description}</p>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  <Badge tone={m.research_only ? 'warn' : 'lens'}>{m.license}</Badge>
                  <Badge>{m.commercial_use ? 'commercial use allowed' : 'non-commercial only'}</Badge>
                  <Badge>{fmtBytes(m.download_size)}</Badge>
                  <Badge>version {m.version}</Badge>
                  {m.required && <Badge tone="info">required</Badge>}
                </div>
                <p className="text-xs text-fog-500">{m.evaluation}</p>
                <div className="flex flex-wrap gap-3 text-xs">
                  <a className="inline-flex items-center gap-1 text-lens-300 hover:underline" href={m.source} target="_blank" rel="noreferrer">Source <ExternalLink className="h-3 w-3" /></a>
                  <a className="inline-flex items-center gap-1 text-lens-300 hover:underline" href={m.license_url} target="_blank" rel="noreferrer">Licence <ExternalLink className="h-3 w-3" /></a>
                </div>
                {active && (
                  <div className="space-y-1">
                    <Progress value={d.bytes_total ? d.bytes_done / d.bytes_total : 0} />
                    <div className="flex justify-between text-xs text-fog-400"><span>{d.status === 'verifying' ? 'Verifying checksum…' : d.message}</span><span>{fmtBytes(d.bytes_done)} / {fmtBytes(d.bytes_total)}</span></div>
                  </div>
                )}
                {d.status === 'error' && <Alert tone="bad" title="Download failed">{d.message}</Alert>}
                {verify[m.id] && (
                  <ul className="space-y-0.5 text-xs">
                    {Object.entries(verify[m.id]).map(([f, s]) => (
                      <li key={f} className="flex items-center gap-1.5">{s === 'ok' ? <CheckCircle2 className="h-3.5 w-3.5 text-ok" /> : <XCircle className="h-3.5 w-3.5 text-bad" />}<span className="font-mono">{f}</span><span className="text-fog-500">{s}</span></li>
                    ))}
                  </ul>
                )}
                <div className="flex flex-wrap items-center gap-2 border-t border-ink-700 pt-3">
                  {!m.installed && !active && (
                    <Button variant="primary" icon={<Download className="h-4 w-4" />} onClick={() => (m.research_only && !m.license_accepted ? setLicence(m) : install(m))}>Install</Button>
                  )}
                  {active && <Button onClick={() => act(() => api.json(`/api/models/${m.id}/cancel`, {}))}>Cancel</Button>}
                  {m.installed && (
                    <>
                      <div className="w-36"><Toggle label="Active" checked={m.enabled} disabled={m.required} onChange={(v) => act(() => api.json(`/api/models/${m.id}/enable`, { enabled: v }))} /></div>
                      <Button icon={<CheckCircle2 className="h-4 w-4" />} onClick={() => act(async () => setVerify({ ...verify, [m.id]: (await api.json<{ files: Record<string, string> }>(`/api/models/${m.id}/verify`, {})).files }))}>Verify checksum</Button>
                      {!m.required && <Button variant="ghost" icon={<Trash2 className="h-4 w-4" />} onClick={() => act(() => api.del(`/api/models/${m.id}`))}>Remove</Button>}
                      {m.required && <Button variant="ghost" icon={<Download className="h-4 w-4" />} onClick={() => install(m)}>Reinstall</Button>}
                    </>
                  )}
                </div>
              </div>
            </Card>
          );
        })}
      </div>

      <Modal
        open={!!licence}
        title="Research licence"
        onClose={() => setLicence(null)}
        footer={<><Button onClick={() => setLicence(null)}>Cancel</Button><Button variant="primary" icon={<ShieldAlert className="h-4 w-4" />} onClick={() => { if (licence) install(licence, true); setLicence(null); }}>I accept, download</Button></>}
      >
        <p><strong className="text-fog-100">{licence?.name}</strong> is published by InsightFace for <strong className="text-fog-100">non-commercial research only</strong>. It is downloaded directly from InsightFace, not distributed by this project.</p>
        <p>By continuing you confirm that your use is non-commercial research and that you have read the licence terms at <a className="text-lens-300 underline" href={licence?.license_url} target="_blank" rel="noreferrer">{licence?.license_url}</a>.</p>
        <p>The pack adds a numeric age estimate, an alternative recognizer and an appearance classifier that stays off unless you enable it in Settings.</p>
      </Modal>
    </div>
  );
}
