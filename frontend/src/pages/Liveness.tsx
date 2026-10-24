import { CheckCircle2, Circle, RotateCcw, XCircle } from 'lucide-react';
import { useCallback, useState } from 'react';
import CameraView from '../components/CameraView';
import { Alert, Badge, Button, Card, FileDrop, Meter, PageHeader } from '../components/ui';
import { api, errorText } from '../lib/api';
import { useApp } from '../lib/store';
import type { FrameResult, LivenessState } from '../lib/types';

export default function Liveness() {
  const { modelReady } = useApp();
  const [session, setSession] = useState<LivenessState | null>(null);
  const [passive, setPassive] = useState<{ faces: { index: number; real_score: number; label: string }[]; note: string } | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const begin = async () => {
    setErr(null);
    try {
      setSession(await api.json<LivenessState>('/api/liveness/sessions', {}));
    } catch (e) {
      setErr(errorText(e));
    }
  };
  const onResult = useCallback((r: FrameResult) => r.liveness && setSession(r.liveness), []);
  const checkPhoto = async (f: File) => {
    setErr(null);
    try {
      setPassive(await api.form('/api/liveness/passive', { file: f }));
    } catch (e) {
      setErr(errorText(e));
    }
  };

  const ready = modelReady('face_landmarker');
  return (
    <div className="space-y-4">
      <PageHeader
        title="Liveness Verification"
        subtitle="Asks for three random actions on camera and checks each one, plus a passive check for printed photos and screens. It raises the bar for simple spoofing; it is not proof that a live person is present."
      />
      {!ready && <Alert tone="warn">The active check needs MediaPipe Face Landmarker. Install it in the Model Manager.</Alert>}
      {!modelReady('antispoof') && <Alert tone="info">The passive anti-spoofing models are not installed; only the active challenge will run.</Alert>}
      {err && <Alert tone="bad">{err}</Alert>}
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
        <CameraView pageName="Liveness Verification" compact livenessSession={session?.state === 'running' ? session.session_id : null} onResult={onResult}
          initial={{ preset: 'balanced', landmarks: true, overlay: 'none', expression: false, antispoof: true }} overlayInitial={{ labels: false }} />
        <div className="space-y-4">
          <Card title="Challenge">
            {!session ? (
              <div className="space-y-3 text-sm text-fog-300">
                <p>Start the camera, make sure only one face is visible, then start the check. You have 25 seconds.</p>
                <Button variant="primary" onClick={begin} disabled={!ready}>Start liveness check</Button>
              </div>
            ) : (
              <div className="space-y-3">
                {session.state === 'running' && session.current && (
                  <div className="rounded-lg bg-lens-500/10 px-4 py-3 text-center">
                    <div className="text-xs uppercase tracking-wider text-lens-300">Now</div>
                    <div className="font-display text-2xl font-semibold text-fog-100">{session.current.prompt}</div>
                    <div className="mt-1 font-mono text-xs text-fog-400">{session.seconds_left.toFixed(0)} s left · {session.frames} frames checked</div>
                  </div>
                )}
                {session.state === 'passed' && <Alert tone="ok" title="Check passed">All challenges were completed by one continuously visible face.</Alert>}
                {session.state === 'failed' && <Alert tone="bad" title="Check failed">{session.reason}</Alert>}
                <ul className="space-y-1.5 text-sm">
                  {session.steps.map((s) => (
                    <li key={s.id} className="flex items-center gap-2">
                      {s.done ? <CheckCircle2 className="h-4 w-4 text-ok" /> : session.state === 'failed' ? <XCircle className="h-4 w-4 text-bad" /> : <Circle className="h-4 w-4 text-fog-500" />}
                      <span className={s.done ? 'text-fog-100' : 'text-fog-400'}>{s.prompt}</span>
                    </li>
                  ))}
                </ul>
                {session.passive_real_score !== null && <Meter label="Passive real-face score (average)" value={session.passive_real_score} tone={session.passive_real_score >= 0.5 ? '#5cc98e' : '#e8646d'} />}
                <Button icon={<RotateCcw className="h-4 w-4" />} onClick={begin}>New check</Button>
              </div>
            )}
          </Card>
          <Card title="Passive check on a photo">
            <FileDrop accept="image/jpeg,image/png,image/webp" onFiles={(f) => checkPhoto(f[0])} label="Choose a photo" hint="Scores each face for signs of a print or screen" />
            {passive && (
              <div className="mt-3 space-y-2">
                {passive.faces.length === 0 && <p className="text-sm text-fog-400">No face found.</p>}
                {passive.faces.map((f) => (
                  <div key={f.index} className="flex items-center justify-between text-sm">
                    <span>Face {f.index + 1}</span>
                    <Badge tone={f.real_score >= 0.5 ? 'ok' : 'bad'}>{f.label} · {(f.real_score * 100).toFixed(0)}%</Badge>
                  </div>
                ))}
                <p className="text-xs text-fog-500">{passive.note}</p>
              </div>
            )}
          </Card>
          <Card title="Limitations">
            <ul className="list-disc space-y-1 pl-4 text-xs text-fog-400">
              <li>A webcam sees 2D images. Masks, high-quality replays and real-time deepfakes can pass.</li>
              <li>The passive models were trained by their authors on their own data and have not been independently evaluated here.</li>
              <li>Do not use this as the only safeguard for anything important.</li>
            </ul>
          </Card>
        </div>
      </div>
    </div>
  );
}
