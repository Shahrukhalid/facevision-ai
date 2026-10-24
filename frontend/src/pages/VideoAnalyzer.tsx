import { Play } from 'lucide-react';
import { useState } from 'react';
import JobView, { fileUrl, useJob } from '../components/JobView';
import { Alert, Button, Card, FileDrop, KV, PageHeader, Select, Slider, Toggle } from '../components/ui';
import { api, errorText } from '../lib/api';
import { useApp } from '../lib/store';
import type { Job } from '../lib/types';

export default function VideoAnalyzer() {
  const { auth } = useApp();
  const [file, setFile] = useState<File | null>(null);
  const [preset, setPreset] = useState('fast');
  const [sample, setSample] = useState(2);
  const [exportVideo, setExportVideo] = useState(true);
  const [recognise, setRecognise] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const job = useJob(jobId);

  const start = async () => {
    if (!file) return;
    setBusy(true);
    setErr(null);
    try {
      const j = await api.form<Job>('/api/jobs/video', {
        file,
        options: JSON.stringify({ analysis: { preset, recognition: recognise, overlay: preset === 'fast' ? 'none' : 'basic' }, sample_every: sample, export_video: exportVideo }),
      });
      setJobId(j.id);
    } catch (e) {
      setErr(errorText(e));
    } finally {
      setBusy(false);
    }
  };

  const r = job?.result;
  return (
    <div className="space-y-4">
      <PageHeader title="Video Analyzer" subtitle="Process a recorded video in the background: track faces frame by frame, log when they enter and leave, and export an annotated copy." />
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="space-y-4">
          <FileDrop accept="video/mp4,video/quicktime,video/x-msvideo,video/webm,video/x-matroska,.mkv,.m4v" onFiles={(f) => setFile(f[0])} label={file ? file.name : 'Choose a video'} hint="MP4, MOV, AVI, MKV or WebM, up to 1 GB. Codec support depends on OpenCV." />
          {err && <Alert tone="bad">{err}</Alert>}
          {job && <JobView job={job} onDeleted={() => setJobId(null)} />}
          {job?.status === 'done' && job.outputs?.video && (
            <Card title="Annotated video">
              <video controls src={fileUrl(job, job.outputs.video)} className="w-full rounded-lg bg-black" />
              {job.outputs.video.endsWith('.mp4') && <p className="mt-2 text-xs text-fog-500">This file uses MPEG-4 Part 2, which some browsers cannot play. Download it to watch in a video player.</p>}
            </Card>
          )}
          {r && (
            <div className="grid gap-4 md:grid-cols-2">
              <Card title="Summary">
                <KV k="Duration" v={`${r.summary.duration_s} s (${r.summary.frames} frames at ${r.summary.fps} fps)`} />
                <KV k="Analysed frames" v={`${r.summary.processed_frames} (every ${r.summary.sample_every})`} />
                <KV k="Processing speed" v={`${r.summary.processing_fps} frames/s`} />
                <KV k="Faces tracked" v={r.summary.tracks} />
                <KV k="Most faces at once" v={r.summary.max_faces_in_frame} />
              </Card>
              <Card title={`Tracks (${r.tracks.length})`}>
                <ul className="max-h-64 space-y-1 overflow-y-auto text-sm">
                  {r.tracks.map((t: any) => (
                    <li key={t.track_id} className="flex justify-between gap-2">
                      <span>#{t.track_id}{t.recognized_as ? ` · ${t.recognized_as}` : ''}</span>
                      <span className="font-mono text-xs text-fog-400">{t.first_seen_s}–{t.last_seen_s} s</span>
                    </li>
                  ))}
                </ul>
              </Card>
              <Card title="Entry and exit events" className="md:col-span-2">
                <ul className="max-h-64 space-y-1 overflow-y-auto font-mono text-xs">
                  {r.events.map((e: any, i: number) => (
                    <li key={i} className={e.type === 'enter' ? 'text-ok' : 'text-warn'}>{e.t.toFixed(2)} s · frame {e.frame} · {e.type} · track #{e.track_id}{e.duration !== undefined ? ` (on screen ${e.duration} s)` : ''}</li>
                  ))}
                </ul>
              </Card>
            </div>
          )}
        </div>
        <Card title="Options">
          <div className="space-y-3">
            <Select label="Analysis" value={preset} onChange={setPreset} options={[{ value: 'fast', label: 'Fast: detection and tracking' }, { value: 'balanced', label: 'Balanced: adds landmarks, expression' }, { value: 'detailed', label: 'Detailed: adds age, attributes' }]} />
            <Slider label="Analyse every Nth frame" value={sample} min={1} max={10} step={1} onChange={setSample} format={(v) => (v === 1 ? 'every frame' : `every ${v}`)} />
            <Toggle label="Export annotated video" checked={exportVideo} onChange={setExportVideo} />
            <Toggle label="Recognise enrolled people" checked={recognise} onChange={setRecognise} disabled={!auth.signed_in} hint={!auth.signed_in ? 'Sign in first' : undefined} />
            <p className="text-xs text-fog-500">Sampling fewer frames is faster; boxes are carried over to skipped frames in the exported video. To blur faces in a video, use Privacy / Face Blur, which checks every frame.</p>
            <Button variant="primary" icon={<Play className="h-4 w-4" />} disabled={!file} busy={busy} onClick={start}>Start processing</Button>
          </div>
        </Card>
      </div>
    </div>
  );
}
