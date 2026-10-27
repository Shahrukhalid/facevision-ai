import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import AuthNotice from '../components/AuthNotice';
import CameraView from '../components/CameraView';
import ImageResult from '../components/ImageResult';
import { Alert, Badge, Card, Empty, FileDrop, KV, PageHeader } from '../components/ui';
import { api, errorText } from '../lib/api';
import { useApp } from '../lib/store';
import type { FrameResult } from '../lib/types';
import { useObjectUrl } from '../lib/useObjectUrl';
import { statusColor, titleCase } from '../lib/util';

export default function Recognition() {
  const { auth, settings, system } = useApp();
  const [live, setLive] = useState<FrameResult | null>(null);
  const [photo, setPhoto] = useState<{ file: File; result: FrameResult } | null>(null);
  const photoSrc = useObjectUrl(photo?.file);
  const [err, setErr] = useState<string | null>(null);
  const [count, setCount] = useState<number | null>(null);

  useEffect(() => {
    if (auth.signed_in) api.get<unknown[]>('/api/persons').then((p) => setCount(p.length)).catch(() => undefined);
  }, [auth.signed_in]);

  const recognisePhoto = async (f: File) => {
    setErr(null);
    try {
      const r = await api.form<FrameResult>('/api/analyze', { file: f, options: JSON.stringify({ preset: 'balanced', recognition: true, max_side: 1280 }) });
      setPhoto({ file: f, result: r });
    } catch (e) {
      setErr(errorText(e));
    }
  };

  const faces = live?.faces || [];
  const threshold = settings?.recognition_thresholds?.[settings.recognizer];
  return (
    <div className="space-y-4">
      <PageHeader
        title="Face Recognition"
        subtitle="Compares faces only against people enrolled on this computer with their consent. A name appears only for a confident match; everyone else is shown as Unknown."
      />
      <AuthNotice />
      {auth.signed_in && count === 0 && (
        <Alert tone="info" title="Nobody is enrolled yet">
          Enrol a consenting person on the <Link className="text-lens-300 underline" to="/enrolled">Enrolled Faces</Link> page first.
        </Alert>
      )}
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_340px]">
        <CameraView pageName="Face Recognition" compact onResult={setLive} initial={{ preset: 'balanced', recognition: auth.signed_in, landmarks: false, overlay: 'none', expression: false }} controls={[]} />
        <div className="space-y-4">
          <Card title="In view now">
            {faces.length === 0 ? (
              <Empty title="No faces">Start the camera to recognise enrolled people.</Empty>
            ) : (
              <ul className="space-y-2">
                {faces.map((f) => (
                  <li key={f.track_id ?? f.index} className="flex items-center justify-between gap-2 rounded-lg border border-ink-700 px-3 py-2">
                    <span className="text-sm">
                      <span className="font-mono text-xs text-fog-500">#{f.track_id} </span>
                      <span style={{ color: statusColor(f.recognition?.status) }}>{f.recognition?.status === 'match' ? f.recognition.name : titleCase(f.recognition?.status || 'detected')}</span>
                    </span>
                    <span className="font-mono text-xs text-fog-400">{f.recognition?.similarity?.toFixed(3) ?? ''}</span>
                  </li>
                ))}
              </ul>
            )}
          </Card>
          <Card title="Matching rules">
            <KV k="Recognizer" v={settings?.recognizer === 'insightface_buffalo_s' ? 'ArcFace MobileFaceNet (research)' : 'SFace'} />
            <KV k="Threshold" v={threshold ? threshold.toFixed(3) : 'model default'} mono />
            <KV k="Runs on" v={system?.models.loaded.sface?.provider || 'loads on first use'} />
            <p className="mt-2 text-xs text-fog-500">
              Each tracked face is matched once and then re-checked every 2 seconds or so, rather than on every frame. Ambiguous
              matches (two people within 0.05) and low-quality faces never show a name. Change the threshold in Settings.
            </p>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {(['match', 'unknown', 'ambiguous', 'low_quality'] as const).map((s) => (
                <Badge key={s}><span className="h-2 w-2 rounded-full" style={{ background: statusColor(s) }} /> {titleCase(s)}</Badge>
              ))}
            </div>
          </Card>
        </div>
      </div>
      <Card title="Recognise a photo">
        <div className="grid gap-4 lg:grid-cols-[320px_minmax(0,1fr)]">
          <FileDrop accept="image/jpeg,image/png,image/webp" onFiles={(f) => recognisePhoto(f[0])} label="Choose a photo" hint="Compared with enrolled people only" />
          <div className="min-w-0">
            {err && <Alert tone="bad">{err}</Alert>}
            {photo && photoSrc && <ImageResult src={photoSrc} result={photo.result} overlay={{ landmarks: 'none' }} />}
          </div>
        </div>
      </Card>
    </div>
  );
}
