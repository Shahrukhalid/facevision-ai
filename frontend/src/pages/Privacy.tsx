import { Download, Eye, Film, ImageIcon, Trash2, Video } from 'lucide-react';
import { useEffect, useState } from 'react';
import CameraView from '../components/CameraView';
import JobView, { useJob } from '../components/JobView';
import { Alert, Badge, Button, Card, FileDrop, PageHeader, Select, Slider } from '../components/ui';
import { api, errorText } from '../lib/api';
import { useApp } from '../lib/store';
import type { FrameResult, Job } from '../lib/types';
import { downloadBlob, fmtBytes } from '../lib/util';

type Method = 'blur' | 'pixelate' | 'solid';

export default function Privacy() {
  const [tab, setTab] = useState<'photo' | 'video' | 'live'>('photo');
  const { system, refreshSystem } = useApp();
  const [msg, setMsg] = useState<string | null>(null);
  return (
    <div className="space-y-4">
      <PageHeader
        title="Privacy / Face Blur"
        subtitle="Hide faces in photos, videos or the live view. This works without recognition or enrolment."
        actions={
          <div className="flex gap-1 rounded-lg bg-ink-800 p-1">
            <Button variant={tab === 'photo' ? 'primary' : 'ghost'} icon={<ImageIcon className="h-4 w-4" />} onClick={() => setTab('photo')}>Photo</Button>
            <Button variant={tab === 'video' ? 'primary' : 'ghost'} icon={<Film className="h-4 w-4" />} onClick={() => setTab('video')}>Video</Button>
            <Button variant={tab === 'live' ? 'primary' : 'ghost'} icon={<Video className="h-4 w-4" />} onClick={() => setTab('live')}>Live</Button>
          </div>
        }
      />
      {tab === 'photo' && <PhotoAnonymizer />}
      {tab === 'video' && <VideoAnonymizer />}
      {tab === 'live' && <CameraView pageName="Privacy / Face Blur" overlayInitial={{ blur: 'blur', labels: false, landmarks: 'none' }} initial={{ preset: 'fast' }} controls={['blur', 'threshold']} />}
      <Card title="Processing files">
        <div className="flex flex-wrap items-center gap-4 text-sm">
          <span className="text-fog-300">Job outputs and temporary uploads use {fmtBytes((system?.disk.outputs || 0) + (system?.disk.temp || 0))}. They are deleted automatically after the retention period set in Settings.</span>
          <Button variant="danger" icon={<Trash2 className="h-4 w-4" />} onClick={() => api.json<{ removed: number }>('/api/data/clear-cache', {}).then((r) => { setMsg(`Deleted ${r.removed} items.`); refreshSystem(); }).catch((e) => setMsg(errorText(e)))}>
            Delete processing files now
          </Button>
        </div>
        {msg && <div className="mt-2"><Alert tone="info" onClose={() => setMsg(null)}>{msg}</Alert></div>}
      </Card>
    </div>
  );
}

function PhotoAnonymizer() {
  const [file, setFile] = useState<File | null>(null);
  const [faces, setFaces] = useState<FrameResult['faces']>([]);
  const [chosen, setChosen] = useState<Set<number>>(new Set());
  const [method, setMethod] = useState<Method>('blur');
  const [strength, setStrength] = useState(0.7);
  const [threshold, setThreshold] = useState(0.5);
  const [preview, setPreview] = useState<string | null>(null);
  const [blob, setBlob] = useState<Blob | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const detect = async (f: File, thr = threshold) => {
    setErr(null);
    try {
      const r = await api.form<FrameResult>('/api/detect', { file: f, crops: 'true', score_threshold: String(thr), max_side: '1600' });
      setFaces(r.faces);
      setChosen(new Set(r.faces.map((x) => x.index)));
    } catch (e) {
      setErr(errorText(e));
    }
  };
  useEffect(() => {
    if (!file) return;
    const t = setTimeout(async () => {
      const res = await api.formRaw('/api/anonymize', {
        file, method, strength: String(strength), score_threshold: String(threshold),
        faces: chosen.size ? [...chosen].join(',') : 'none', output_format: 'png',
      });
      if (!res.ok) {
        setErr((await res.json()).detail);
        return;
      }
      const b = await res.blob();
      setBlob(b);
      setPreview((old) => {
        if (old) URL.revokeObjectURL(old);
        return URL.createObjectURL(b);
      });
    }, 250);
    return () => clearTimeout(t);
  }, [file, method, strength, chosen, threshold]);

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
      <div className="space-y-3">
        {!file ? (
          <FileDrop accept="image/jpeg,image/png,image/webp" onFiles={(f) => { setFile(f[0]); detect(f[0]); }} label="Choose a photo to anonymise" />
        ) : (
          <>
            {preview && <img src={preview} alt="Anonymised preview" className="max-h-[70vh] w-full rounded-xl border border-ink-700 bg-black object-contain" />}
            <div className="flex flex-wrap gap-2">
              <Button variant="primary" icon={<Download className="h-4 w-4" />} disabled={!blob} onClick={() => blob && downloadBlob(blob, `${file.name.replace(/\.[^.]+$/, '')}-anonymised.png`)}>Export</Button>
              <Button variant="ghost" onClick={() => { setFile(null); setFaces([]); setPreview(null); setBlob(null); }}>Choose another photo</Button>
            </div>
          </>
        )}
        {err && <Alert tone="bad">{err}</Alert>}
      </div>
      <div className="space-y-4">
        <Card title="Method">
          <div className="space-y-3">
            <Select<Method> value={method} onChange={setMethod} options={[{ value: 'blur', label: 'Blur' }, { value: 'pixelate', label: 'Pixelate' }, { value: 'solid', label: 'Solid mask' }]} />
            {method !== 'solid' && <Slider label="Strength" value={strength} min={0.2} max={1} step={0.05} onChange={setStrength} format={(v) => `${Math.round(v * 100)}%`} />}
            <Slider label="Detection threshold" value={threshold} min={0.3} max={0.9} step={0.05} onChange={(v) => { setThreshold(v); file && detect(file, v); }} format={(v) => v.toFixed(2)} />
            <p className="text-xs text-fog-500">A lower threshold finds more faces (including some false ones). Always check the preview before sharing.</p>
          </div>
        </Card>
        {file && (
          <Card title={`Faces (${chosen.size} of ${faces.length} hidden)`}>
            {faces.length === 0 ? <p className="text-sm text-fog-400">No faces detected. Try a lower threshold.</p> : (
              <div className="grid grid-cols-3 gap-2">
                {faces.map((f) => (
                  <button key={f.index} onClick={() => { const s = new Set(chosen); s.has(f.index) ? s.delete(f.index) : s.add(f.index); setChosen(s); }} className={`relative rounded-lg border-2 ${chosen.has(f.index) ? 'border-lens-400' : 'border-ink-700 opacity-60'}`} aria-pressed={chosen.has(f.index)}>
                    <img src={f.crop} alt={`Face ${f.index + 1}`} className="aspect-square w-full rounded-md object-cover" />
                    <span className="absolute bottom-1 right-1">{chosen.has(f.index) ? <Badge tone="lens">hide</Badge> : <Badge><Eye className="h-3 w-3" /> keep</Badge>}</span>
                  </button>
                ))}
              </div>
            )}
          </Card>
        )}
      </div>
    </div>
  );
}

function VideoAnonymizer() {
  const [file, setFile] = useState<File | null>(null);
  const [method, setMethod] = useState<Method>('blur');
  const [jobId, setJobId] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const job = useJob(jobId);
  const start = async () => {
    if (!file) return;
    try {
      const j = await api.form<Job>('/api/jobs/video', { file, options: JSON.stringify({ anonymize: { method, strength: 0.7 }, analysis: { preset: 'fast', max_side: 960, score_threshold: 0.5 }, export_video: true }) });
      setJobId(j.id);
    } catch (e) {
      setErr(errorText(e));
    }
  };
  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
      <div className="space-y-3">
        <FileDrop accept="video/*,.mkv" onFiles={(f) => setFile(f[0])} label={file ? file.name : 'Choose a video'} hint="Every frame is checked for faces" />
        {err && <Alert tone="bad">{err}</Alert>}
        {job && <JobView job={job} onDeleted={() => setJobId(null)} />}
        {job?.status === 'done' && job.outputs?.video && <video controls src={`/api/jobs/${job.id}/files/${job.outputs.video}`} className="w-full rounded-xl bg-black" />}
      </div>
      <Card title="Method">
        <div className="space-y-3">
          <Select<Method> value={method} onChange={setMethod} options={[{ value: 'blur', label: 'Blur' }, { value: 'pixelate', label: 'Pixelate' }, { value: 'solid', label: 'Solid mask' }]} />
          <p className="text-xs text-fog-500">Detection can miss faces that are very small, turned away or blurred by motion. Review the result before sharing it.</p>
          <Button variant="primary" disabled={!file} onClick={start}>Anonymise video</Button>
        </div>
      </Card>
    </div>
  );
}
