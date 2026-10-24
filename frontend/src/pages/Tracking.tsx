import { Download } from 'lucide-react';
import { useCallback, useRef, useState } from 'react';
import CameraView from '../components/CameraView';
import { Button, Card, Empty, KV, PageHeader } from '../components/ui';
import type { FrameResult } from '../lib/types';
import { downloadText, stamp } from '../lib/util';

interface TrackRow { id: number; first: number; last: number; frames: number; active: boolean; name?: string }
interface EventRow { type: 'enter' | 'exit'; track_id: number; at: number; duration?: number }

export default function Tracking() {
  const [tracks, setTracks] = useState<Record<number, TrackRow>>({});
  const [events, setEvents] = useState<EventRow[]>([]);
  const [stats, setStats] = useState<FrameResult['tracking']>(null);
  const t0 = useRef(Date.now());

  const onResult = useCallback((r: FrameResult) => {
    const now = (Date.now() - t0.current) / 1000;
    setStats(r.tracking ?? null);
    setTracks((prev) => {
      const next = { ...prev };
      for (const k of Object.keys(next)) next[Number(k)] = { ...next[Number(k)], active: false };
      for (const f of r.faces) {
        if (!f.track_id) continue;
        const cur = next[f.track_id] || { id: f.track_id, first: now, last: now, frames: 0, active: true };
        next[f.track_id] = { ...cur, last: now, frames: cur.frames + 1, active: true, name: f.recognition?.status === 'match' ? f.recognition.name : cur.name };
      }
      return next;
    });
    if (r.events?.length) setEvents((e) => [...r.events!.map((ev) => ({ type: ev.type, track_id: ev.track_id, at: now, duration: ev.duration })), ...e].slice(0, 200));
  }, []);

  const rows = Object.values(tracks).sort((a, b) => b.id - a.id);
  return (
    <div className="space-y-4">
      <PageHeader
        title="Face Tracking"
        subtitle="Follows each face across frames with a temporary ID, and logs when faces enter and leave. Track IDs are not identities: a person who leaves and returns gets a new ID."
        actions={<Button icon={<Download className="h-4 w-4" />} disabled={!events.length} onClick={() => downloadText(JSON.stringify({ tracks: rows, events }, null, 2), `tracking-${stamp()}.json`)}>Export log</Button>}
      />
      <CameraView pageName="Face Tracking" onResult={onResult} initial={{ preset: 'fast', tracking: true }} controls={['preset', 'tracking', 'landmarks', 'threshold', 'recognition', 'blur']} />
      <div className="grid gap-4 lg:grid-cols-3">
        <Card title="Tracking statistics">
          <KV k="Active tracks" v={stats?.active_tracks ?? '–'} mono />
          <KV k="Tracks created" v={stats?.created ?? '–'} mono />
          <KV k="Tracks expired" v={stats?.expired ?? '–'} mono />
          <KV k="Frames processed" v={stats?.frames ?? '–'} mono />
          <p className="mt-2 text-xs text-fog-500">A track is confirmed after two consecutive detections and expires after one second without one. Boxes are smoothed to reduce flicker.</p>
        </Card>
        <Card title="Tracks">
          {rows.length === 0 ? <Empty title="No tracks yet" /> : (
            <ul className="max-h-80 space-y-1 overflow-y-auto text-sm">
              {rows.map((t) => (
                <li key={t.id} className="flex justify-between gap-2 rounded px-2 py-1 hover:bg-ink-800">
                  <span><span className={t.active ? 'text-ok' : 'text-fog-500'}>●</span> #{t.id}{t.name ? ` · ${t.name}` : ''}</span>
                  <span className="font-mono text-xs text-fog-400">{(t.last - t.first).toFixed(1)} s · {t.frames} frames</span>
                </li>
              ))}
            </ul>
          )}
        </Card>
        <Card title="Enter / exit events">
          {events.length === 0 ? <Empty title="No events yet" /> : (
            <ul className="max-h-80 space-y-1 overflow-y-auto font-mono text-xs">
              {events.map((e, i) => (
                <li key={i} className="flex justify-between gap-2">
                  <span className={e.type === 'enter' ? 'text-ok' : 'text-warn'}>{e.type === 'enter' ? '→ enter' : '← exit'} #{e.track_id}</span>
                  <span className="text-fog-500">{e.at.toFixed(1)} s{e.duration !== undefined ? ` (stayed ${e.duration.toFixed(1)} s)` : ''}</span>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </div>
  );
}
