import { Camera, ImageIcon } from 'lucide-react';
import { useState } from 'react';
import CameraView from '../components/CameraView';
import FacePanel from '../components/FacePanel';
import ImageResult from '../components/ImageResult';
import { Alert, Button, Empty, FileDrop, PageHeader } from '../components/ui';
import { api, errorText } from '../lib/api';
import type { FrameResult } from '../lib/types';

const DETAILED = { preset: 'detailed', overlay: 'detailed', age: true, attributes: true, expression: true, quality: true, landmarks: true };

export default function Analysis() {
  const [mode, setMode] = useState<'camera' | 'photo'>('camera');
  const [result, setResult] = useState<FrameResult | null>(null);
  const [src, setSrc] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const analyse = async (f: File) => {
    setErr(null);
    setBusy(true);
    setSrc(URL.createObjectURL(f));
    try {
      setResult(await api.form<FrameResult>('/api/analyze', { file: f, options: JSON.stringify({ ...DETAILED, antispoof: true }), crops: 'true' }));
    } catch (e) {
      setErr(errorText(e));
      setResult(null);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <PageHeader
        title="Facial Analysis"
        subtitle="Landmarks, head pose, eyes, mouth, expression, quality, geometry and optional estimates for each face. Estimates are model outputs with uncertainty, not facts about a person."
        actions={
          <div className="flex gap-1 rounded-lg bg-ink-800 p-1">
            <Button variant={mode === 'camera' ? 'primary' : 'ghost'} icon={<Camera className="h-4 w-4" />} onClick={() => { setMode('camera'); setResult(null); }}>Camera</Button>
            <Button variant={mode === 'photo' ? 'primary' : 'ghost'} icon={<ImageIcon className="h-4 w-4" />} onClick={() => { setMode('photo'); setResult(null); }}>Photo</Button>
          </div>
        }
      />
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_380px]">
        <div className="min-w-0 space-y-3">
          {mode === 'camera' ? (
            <CameraView pageName="Facial Analysis" compact onResult={setResult} initial={DETAILED as any} overlayInitial={{ pose: true }} controls={[]} />
          ) : (
            <>
              <FileDrop accept="image/jpeg,image/png,image/webp" onFiles={(f) => analyse(f[0])} label="Drop a photo or click to choose" hint="JPG, PNG or WebP. Analysed on this computer." />
              {busy && <div className="text-sm text-fog-400">Analysing…</div>}
              {err && <Alert tone="bad">{err}</Alert>}
              {src && <ImageResult src={src} result={result} overlay={{ landmarks: 'detailed', pose: true }} />}
            </>
          )}
        </div>
        <div className="space-y-3">
          {result?.faces.length ? (
            result.faces.map((f) => <FacePanel key={f.track_id ?? f.index} face={f} />)
          ) : (
            <Empty title="No face analysed yet">{mode === 'camera' ? 'Start the camera. The panel updates with each analysed frame.' : 'Choose a photo to analyse.'}</Empty>
          )}
        </div>
      </div>
    </div>
  );
}
