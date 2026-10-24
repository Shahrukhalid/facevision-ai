import { Download, FileJson, FileSpreadsheet, ImageDown, Scissors } from 'lucide-react';
import { useRef, useState } from 'react';
import FacePanel from '../components/FacePanel';
import ImageResult from '../components/ImageResult';
import { Alert, Button, Card, Empty, FileDrop, PageHeader, Select, Slider, Toggle } from '../components/ui';
import { api, errorText } from '../lib/api';
import { useApp } from '../lib/store';
import type { AnalysisOptions, FrameResult } from '../lib/types';
import { dataUrlToBlob, downloadBlob, downloadText, facesToCsv, stamp } from '../lib/util';

export default function ImageAnalyzer() {
  const { auth, modelReady } = useApp();
  const [file, setFile] = useState<File | null>(null);
  const [src, setSrc] = useState<string | null>(null);
  const [result, setResult] = useState<FrameResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [overlay, setOverlay] = useState<'none' | 'basic' | 'detailed' | 'mesh'>('basic');
  const [pose, setPose] = useState(false);
  const [opts, setOpts] = useState<Partial<AnalysisOptions>>({ preset: 'balanced', score_threshold: 0.6, age: false, attributes: false, recognition: false });
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  const run = async (f: File | null = file, o = opts) => {
    if (!f) return;
    setBusy(true);
    setErr(null);
    try {
      const r = await api.form<FrameResult>('/api/analyze', { file: f, options: JSON.stringify({ ...o, overlay: 'detailed', max_side: 1600 }), crops: 'true' });
      setResult(r);
    } catch (e) {
      setErr(errorText(e));
      setResult(null);
    } finally {
      setBusy(false);
    }
  };
  const choose = (f: File) => {
    setFile(f);
    setSrc(URL.createObjectURL(f));
    run(f);
  };
  const base = file?.name.replace(/\.[^.]+$/, '') || 'image';

  return (
    <div className="space-y-4">
      <PageHeader title="Image Analyzer" subtitle="Analyse a photo with several faces, inspect each one and export the results." />
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_340px]">
        <div className="min-w-0 space-y-3">
          {!src && <FileDrop accept="image/jpeg,image/png,image/webp" onFiles={(f) => choose(f[0])} label="Drop a photo or click to choose" hint="JPG, JPEG, PNG or WebP, up to 20 MB" />}
          {src && <ImageResult src={src} result={result} canvasRef={canvasRef} overlay={{ landmarks: overlay, pose }} />}
          {busy && <p className="text-sm text-fog-400">Analysing…</p>}
          {err && <Alert tone="bad">{err}</Alert>}
          {result && (
            <div className="flex flex-wrap gap-2">
              <Button icon={<ImageDown className="h-4 w-4" />} onClick={() => canvasRef.current?.toBlob((b) => b && downloadBlob(b, `${base}-annotated.png`), 'image/png')}>Annotated image</Button>
              <Button icon={<FileJson className="h-4 w-4" />} onClick={() => downloadText(JSON.stringify({ file: file?.name, analysed_at: new Date().toISOString(), ...result, faces: result.faces.map(({ crop, ...f }) => f) }, null, 2), `${base}-analysis.json`)}>JSON</Button>
              <Button icon={<FileSpreadsheet className="h-4 w-4" />} onClick={() => downloadText(facesToCsv(result, file?.name), `${base}-faces.csv`, 'text/csv')}>CSV</Button>
              <Button icon={<Scissors className="h-4 w-4" />} disabled={!result.faces.length} onClick={async () => { for (const f of result.faces) if (f.crop) downloadBlob(await dataUrlToBlob(f.crop), `${base}-face-${f.index + 1}.jpg`); }}>Face crops</Button>
              <Button variant="ghost" icon={<Download className="h-4 w-4" />} onClick={() => { setSrc(null); setFile(null); setResult(null); }}>New image</Button>
            </div>
          )}
          {result && (
            <div className="grid gap-4 md:grid-cols-2">
              {result.faces.map((f) => <FacePanel key={f.index} face={f} />)}
            </div>
          )}
        </div>
        <div className="space-y-4">
          <Card title="Analysis">
            <div className="space-y-2">
              <Select<string> label="Mode" value={opts.preset as string} onChange={(v) => setOpts({ ...opts, preset: v as AnalysisOptions['preset'] })} options={[{ value: 'fast', label: 'Fast (detection only)' }, { value: 'balanced', label: 'Balanced' }, { value: 'detailed', label: 'Detailed' }]} />
              <Slider label="Detection threshold" value={opts.score_threshold ?? 0.6} min={0.3} max={0.95} step={0.05} onChange={(v) => setOpts({ ...opts, score_threshold: v })} format={(v) => v.toFixed(2)} />
              <Toggle label="Age estimation" checked={!!opts.age} onChange={(v) => setOpts({ ...opts, age: v })} disabled={!modelReady('clip_attributes') && !modelReady('insightface_buffalo_s')} />
              <Toggle label="Glasses / mask / facial hair" checked={!!opts.attributes} onChange={(v) => setOpts({ ...opts, attributes: v })} disabled={!modelReady('clip_attributes')} />
              <Toggle label="Recognise enrolled people" checked={!!opts.recognition} onChange={(v) => setOpts({ ...opts, recognition: v })} disabled={!auth.signed_in} hint={!auth.signed_in ? 'Sign in first' : undefined} />
              <Button variant="primary" busy={busy} disabled={!file} onClick={() => run()}>Analyse again</Button>
            </div>
          </Card>
          <Card title="Display">
            <Select<'none' | 'basic' | 'detailed' | 'mesh'> label="Landmarks" value={overlay} onChange={setOverlay} options={[{ value: 'none', label: 'None' }, { value: 'basic', label: 'Basic' }, { value: 'detailed', label: 'Detailed' }, { value: 'mesh', label: 'Full mesh' }]} />
            <div className="mt-2"><Toggle label="Head pose axes" checked={pose} onChange={setPose} /></div>
          </Card>
          {result && (
            <Card title="Summary">
              <div className="text-sm text-fog-300">{result.face_count} face{result.face_count === 1 ? '' : 's'} · {result.image.width}×{result.image.height}px · {result.timings_ms.total.toFixed(0)} ms</div>
            </Card>
          )}
          {!result && !busy && <Empty title="No image yet">Results appear here.</Empty>}
        </div>
      </div>
    </div>
  );
}
