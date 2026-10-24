import {
  Camera, CameraOff, Circle, FlipHorizontal, Maximize, Minimize, RefreshCw, Square, SwitchCamera, Video,
} from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';
import { wsUrl } from '../lib/api';
import { defaultOverlay, drawOverlay, type OverlayOptions } from '../lib/overlay';
import { useApp } from '../lib/store';
import type { AnalysisOptions, FrameResult } from '../lib/types';
import { downloadBlob, stamp } from '../lib/util';
import { Alert, Badge, Button, Select, Slider, Toggle, cx } from './ui';

export type ControlKey =
  | 'preset' | 'detection' | 'recognition' | 'age' | 'attributes' | 'appearance' | 'landmarks' | 'tracking' | 'blur'
  | 'threshold' | 'expression' | 'pose' | 'source';

const SEND_WIDTH = { fast: 480, balanced: 640, detailed: 960 } as const;

const PERMISSION_HELP: Record<string, string> = {
  NotAllowedError: 'Camera access was blocked. Allow camera access for this page in your browser (and, on macOS, in System Settings → Privacy & Security → Camera), then try again.',
  NotFoundError: 'No camera was found. Connect a webcam and press Start camera again.',
  NotReadableError: 'The camera is in use by another app or could not be started. Close other apps using it and try again.',
  OverconstrainedError: 'The selected camera does not support the requested settings. Choose another camera.',
  SecurityError: 'Camera access needs a secure page. Open FaceVision AI at http://localhost, not a network address.',
};

interface Props {
  initial?: Partial<AnalysisOptions>;
  controls?: ControlKey[];
  overlayInitial?: Partial<OverlayOptions>;
  onResult?: (r: FrameResult) => void;
  livenessSession?: string | null;
  pageName: string;
  compact?: boolean;
}

export default function CameraView({ initial, controls = [], overlayInitial, onResult, livenessSession, pageName, compact }: Props) {
  const { settings, topology, setLive, auth, modelReady } = useApp();
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const sendCanvas = useRef<HTMLCanvasElement | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const resultRef = useRef<FrameResult | null>(null);
  const inflight = useRef(false);
  const streamRef = useRef<MediaStream | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const serverFrame = useRef<ImageBitmap | null>(null);
  const fpsTimes = useRef<number[]>([]);
  const switching = useRef(false);

  const [devices, setDevices] = useState<MediaDeviceInfo[]>([]);
  const [deviceId, setDeviceId] = useState<string>('');
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [recording, setRecording] = useState(false);
  const [fullscreen, setFullscreen] = useState(false);
  const [stats, setStats] = useState({ fps: 0, pfps: 0, latency: 0, faces: 0 });
  const [source, setSource] = useState<'browser' | 'server'>('browser');
  const [serverSrc, setServerSrc] = useState('0');
  const [opts, setOpts] = useState<AnalysisOptions>({
    preset: (settings?.preset as AnalysisOptions['preset']) || 'balanced', detection: true, score_threshold: settings?.detection_threshold ?? 0.6,
    max_side: 640, tracking: true, landmarks: true, overlay: 'basic', quality: true, expression: true, recognition: false,
    age: false, appearance: false, attributes: false, antispoof: false, ...initial,
  });
  const [ov, setOv] = useState<OverlayOptions>({ ...defaultOverlay, mirrored: true, ...overlayInitial });
  const optsRef = useRef(opts);
  optsRef.current = opts;

  const has = (k: ControlKey) => controls.includes(k);
  const update = (p: Partial<AnalysisOptions>) => setOpts((o) => ({ ...o, ...p }));

  // keep the server informed of option changes
  useEffect(() => {
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'options', options: wireOptions(opts), liveness_session: livenessSession ?? null }));
    }
  }, [opts, livenessSession]);

  useEffect(() => {
    setOv((o) => ({ ...o, topology, landmarks: opts.landmarks ? (opts.overlay === 'none' ? 'none' : opts.overlay) : 'none' }));
  }, [topology, opts.landmarks, opts.overlay]);

  const listDevices = useCallback(async () => {
    try {
      const all = await navigator.mediaDevices.enumerateDevices();
      setDevices(all.filter((d) => d.kind === 'videoinput'));
    } catch {
      /* ignore */
    }
  }, []);

  const stop = useCallback(() => {
    recorderRef.current?.state === 'recording' && recorderRef.current.stop();
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    if (wsRef.current) {
      try {
        wsRef.current.send(JSON.stringify({ type: 'stop' }));
      } catch {
        /* closed */
      }
      wsRef.current.close();
    }
    wsRef.current = null;
    inflight.current = false;
    resultRef.current = null;
    serverFrame.current = null;
    setRunning(false);
    setLive({ running: false, fps: 0, processingFps: 0, faces: 0, recognized: 0, page: pageName });
  }, [setLive, pageName]);

  const handleResult = useCallback(
    (r: FrameResult) => {
      resultRef.current = r;
      inflight.current = false;
      setStats((s) => ({ ...s, pfps: r.processing_fps ?? 0, latency: r.latency_ms ?? 0, faces: r.face_count }));
      setLive({ running: true, processingFps: r.processing_fps ?? 0, latency: r.latency_ms ?? 0, faces: r.face_count, recognized: r.faces.filter((f) => f.recognition?.status === 'match').length, page: pageName });
      onResult?.(r);
    },
    [onResult, setLive, pageName],
  );

  const openSocket = useCallback(
    (path: string) => {
      const ws = new WebSocket(wsUrl(path));
      ws.binaryType = 'arraybuffer';
      ws.onopen = () => ws.send(JSON.stringify({ type: 'options', options: wireOptions(optsRef.current), liveness_session: livenessSession ?? null }));
      ws.onmessage = async (ev) => {
        if (typeof ev.data !== 'string') {
          const bmp = await createImageBitmap(new Blob([ev.data], { type: 'image/jpeg' }));
          serverFrame.current?.close();
          serverFrame.current = bmp;
          return;
        }
        const msg = JSON.parse(ev.data);
        if (msg.type === 'result') handleResult(msg as FrameResult);
        else if (msg.type === 'error') {
          setError(msg.message);
          inflight.current = false;
        } else if (msg.type === 'ended') setError('The stream ended.');
      };
      ws.onerror = () => setError('Lost connection to the FaceVision AI server.');
      ws.onclose = () => {
        inflight.current = false;
      };
      wsRef.current = ws;
      return ws;
    },
    [handleResult, livenessSession],
  );

  const start = useCallback(async () => {
    setError(null);
    if (source === 'server') {
      const ws = openSocket('/ws/source');
      ws.onopen = () => {
        ws.send(JSON.stringify({ type: 'options', options: wireOptions(optsRef.current) }));
        ws.send(JSON.stringify({ type: 'start', source: serverSrc.trim() }));
      };
      setRunning(true);
      return;
    }
    if (!navigator.mediaDevices?.getUserMedia) {
      setError(PERMISSION_HELP.SecurityError);
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: deviceId ? { deviceId: { exact: deviceId }, width: { ideal: 1280 }, height: { ideal: 720 } } : { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: 'user' },
        audio: false,
      });
      streamRef.current = stream;
      const v = videoRef.current!;
      v.srcObject = stream;
      await v.play();
      const id = stream.getVideoTracks()[0]?.getSettings().deviceId;
      if (id) setDeviceId(id);
      listDevices();
      openSocket('/ws/live');
      setRunning(true);
    } catch (e) {
      const name = (e as DOMException).name;
      setError(PERMISSION_HELP[name] || `Could not start the camera: ${(e as Error).message}`);
    }
  }, [deviceId, listDevices, openSocket, source, serverSrc]);

  useEffect(() => {
    listDevices();
    navigator.mediaDevices?.addEventListener?.('devicechange', listDevices);
    return () => {
      navigator.mediaDevices?.removeEventListener?.('devicechange', listDevices);
    };
  }, [listDevices]);

  useEffect(() => () => stop(), [stop]);

  // render + send loop
  useEffect(() => {
    if (!running) return;
    let raf = 0;
    const loop = () => {
      raf = requestAnimationFrame(loop);
      const canvas = canvasRef.current;
      if (!canvas) return;
      const ctx = canvas.getContext('2d')!;
      const v = videoRef.current;
      const srcW = source === 'server' ? serverFrame.current?.width ?? 0 : v?.videoWidth ?? 0;
      const srcH = source === 'server' ? serverFrame.current?.height ?? 0 : v?.videoHeight ?? 0;
      if (!srcW || !srcH) return;
      if (canvas.width !== srcW || canvas.height !== srcH) {
        canvas.width = srcW;
        canvas.height = srcH;
      }
      const mirrored = ov.mirrored && source === 'browser';
      ctx.save();
      if (mirrored) {
        ctx.translate(srcW, 0);
        ctx.scale(-1, 1);
      }
      if (source === 'server') serverFrame.current && ctx.drawImage(serverFrame.current, 0, 0);
      else ctx.drawImage(v!, 0, 0, srcW, srcH);
      ctx.restore();
      const r = resultRef.current;
      if (r && optsRef.current.detection) drawOverlay(ctx, r, srcW / r.image.width, srcH / r.image.height, { ...ov, mirrored });
      const now = performance.now();
      fpsTimes.current = [...fpsTimes.current.filter((t) => t > now - 1000), now];
      // send the next frame once the previous result has arrived
      const ws = wsRef.current;
      if (source === 'browser' && ws && ws.readyState === WebSocket.OPEN && !inflight.current && optsRef.current.detection && v) {
        inflight.current = true;
        const target = SEND_WIDTH[optsRef.current.preset] || 640;
        const k = Math.min(1, target / srcW);
        const sc = (sendCanvas.current = sendCanvas.current || document.createElement('canvas'));
        sc.width = Math.round(srcW * k);
        sc.height = Math.round(srcH * k);
        sc.getContext('2d')!.drawImage(v, 0, 0, sc.width, sc.height);
        sc.toBlob(
          (b) => {
            if (!b || ws.readyState !== WebSocket.OPEN) {
              inflight.current = false;
              return;
            }
            b.arrayBuffer().then((buf) => ws.send(buf));
          },
          'image/jpeg',
          0.82,
        );
      }
      if (!optsRef.current.detection) resultRef.current = null;
    };
    raf = requestAnimationFrame(loop);
    const t = setInterval(() => {
      const fps = fpsTimes.current.length;
      setStats((s) => ({ ...s, fps }));
      setLive({ fps });
    }, 1000);
    return () => {
      cancelAnimationFrame(raf);
      clearInterval(t);
    };
  }, [running, ov, source, setLive]);

  const switchCamera = async () => {
    if (devices.length < 2) return;
    const i = devices.findIndex((d) => d.deviceId === deviceId);
    const next = devices[(i + 1) % devices.length].deviceId;
    stop();
    setDeviceId(next);
  };
  useEffect(() => {
    // restart automatically after switching camera
    if (!running && deviceId && streamRef.current === null && switching.current) {
      switching.current = false;
      start();
    }
  }, [deviceId, running, start]);

  const screenshot = () => {
    canvasRef.current?.toBlob((b) => b && downloadBlob(b, `facevision-${stamp()}.png`), 'image/png');
  };

  const toggleRecord = () => {
    if (recording) {
      recorderRef.current?.stop();
      return;
    }
    const canvas = canvasRef.current;
    if (!canvas) return;
    const stream = canvas.captureStream(30);
    const type = ['video/webm;codecs=vp9', 'video/webm;codecs=vp8', 'video/webm', 'video/mp4'].find((t) => MediaRecorder.isTypeSupported(t));
    if (!type) {
      setError('This browser cannot record video from a canvas.');
      return;
    }
    const chunks: Blob[] = [];
    const rec = new MediaRecorder(stream, { mimeType: type, videoBitsPerSecond: 4_000_000 });
    rec.ondataavailable = (e) => e.data.size && chunks.push(e.data);
    rec.onstop = () => {
      setRecording(false);
      downloadBlob(new Blob(chunks, { type }), `facevision-recording-${stamp()}.${type.includes('mp4') ? 'mp4' : 'webm'}`);
    };
    rec.start(1000);
    recorderRef.current = rec;
    setRecording(true);
  };

  const toggleFullscreen = async () => {
    if (!document.fullscreenElement) await wrapRef.current?.requestFullscreen?.();
    else await document.exitFullscreen?.();
  };
  useEffect(() => {
    const h = () => setFullscreen(!!document.fullscreenElement);
    document.addEventListener('fullscreenchange', h);
    return () => document.removeEventListener('fullscreenchange', h);
  }, []);

  const recognitionBlocked = !auth.signed_in;
  const presetButtons = (['fast', 'balanced', 'detailed'] as const).map((p) => (
    <button
      key={p}
      onClick={() => update({ ...presetDefaults(p), preset: p })}
      className={cx('rounded-md px-2.5 py-1 text-xs capitalize', opts.preset === p ? 'bg-lens-500 text-ink-950' : 'text-fog-300 hover:bg-ink-700')}
    >
      {p}
    </button>
  ));

  return (
    <div className={cx('grid gap-4', !compact && controls.length > 0 && 'xl:grid-cols-[minmax(0,1fr)_300px]')}>
      <div className="min-w-0 space-y-3">
        <div ref={wrapRef} className={cx('relative overflow-hidden rounded-xl border border-ink-700 bg-black', fullscreen && 'flex items-center justify-center')}>
          <video ref={videoRef} playsInline muted className="hidden" />
          <canvas ref={canvasRef} className={cx('block w-full', fullscreen ? 'max-h-screen object-contain' : 'aspect-video object-contain')} />
          {!running && (
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-ink-950/90 p-6 text-center">
              <Camera className="h-10 w-10 text-fog-500" />
              <p className="max-w-sm text-sm text-fog-400">The camera stays off until you start it. Frames are analysed on this computer and are not saved unless you take a screenshot or record.</p>
              <Button variant="primary" icon={<Camera className="h-4 w-4" />} onClick={start} disabled={!modelReady('yunet')}>
                Start camera
              </Button>
              {!modelReady('yunet') && <p className="text-xs text-warn">Install the face detector in the Model Manager first.</p>}
            </div>
          )}
          {running && (
            <div className="pointer-events-none absolute left-3 top-3 flex flex-wrap gap-2">
              <Badge tone="bad">
                <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-bad" /> Camera on
              </Badge>
              {recording && <Badge tone="bad">● REC</Badge>}
              <Badge tone="neutral">{stats.faces} {stats.faces === 1 ? 'face' : 'faces'}</Badge>
              <Badge tone="neutral">
                <span className="font-mono">{stats.fps} fps · {stats.pfps.toFixed(0)} analysed/s · {stats.latency.toFixed(0)} ms</span>
              </Badge>
            </div>
          )}
          {fullscreen && (
            <button onClick={toggleFullscreen} className="absolute right-3 top-3 rounded-lg bg-ink-900/80 p-2 text-fog-100" aria-label="Exit fullscreen">
              <Minimize className="h-5 w-5" />
            </button>
          )}
        </div>
        {error && <Alert tone="bad" onClose={() => setError(null)}>{error}</Alert>}
        <div className="flex flex-wrap items-center gap-2">
          {running ? (
            <Button variant="danger" icon={<CameraOff className="h-4 w-4" />} onClick={stop}>Stop camera</Button>
          ) : (
            <Button variant="primary" icon={<Camera className="h-4 w-4" />} onClick={start} disabled={!modelReady('yunet')}>Start camera</Button>
          )}
          {source === 'browser' && (
            <Button
              icon={<SwitchCamera className="h-4 w-4" />}
              onClick={() => {
                switching.current = running;
                switchCamera();
              }}
              disabled={devices.length < 2}
              title={devices.length < 2 ? 'Only one camera found' : 'Switch to the next camera'}
            >
              Switch camera
            </Button>
          )}
          <Button icon={<Square className="h-4 w-4" />} onClick={screenshot} disabled={!running} title="Save the current view with overlays as a PNG">Screenshot</Button>
          <Button icon={recording ? <Circle className="h-4 w-4 fill-bad text-bad" /> : <Video className="h-4 w-4" />} onClick={toggleRecord} disabled={!running}>
            {recording ? 'Stop recording' : 'Record'}
          </Button>
          <Button icon={<FlipHorizontal className="h-4 w-4" />} onClick={() => setOv((o) => ({ ...o, mirrored: !o.mirrored }))} disabled={source === 'server'} title="Mirror the preview (analysis is unaffected)">
            Mirror
          </Button>
          <Button icon={<Maximize className="h-4 w-4" />} onClick={toggleFullscreen} disabled={!running}>Fullscreen</Button>
          {devices.length > 0 && source === 'browser' && (
            <select
              aria-label="Camera"
              value={deviceId}
              onChange={(e) => {
                switching.current = running;
                stop();
                setDeviceId(e.target.value);
              }}
              className="max-w-[220px] rounded-lg border border-ink-600 bg-ink-800 px-2 py-2 text-sm text-fog-100"
            >
              {devices.map((d, i) => (
                <option key={d.deviceId || i} value={d.deviceId}>{d.label || `Camera ${i + 1}`}</option>
              ))}
            </select>
          )}
        </div>
      </div>

      {controls.length > 0 && (
        <aside className="space-y-4 rounded-xl border border-ink-700 bg-ink-900 p-4">
          {has('preset') && (
            <div>
              <div className="mb-2 text-[11px] uppercase tracking-wider text-fog-500">Performance mode</div>
              <div className="flex gap-1 rounded-lg bg-ink-800 p-1">{presetButtons}</div>
              <p className="mt-2 text-xs text-fog-500">{PRESET_HELP[opts.preset]}</p>
            </div>
          )}
          <div className="space-y-1">
            {has('detection') && <Toggle label="Face detection" checked={opts.detection} onChange={(v) => update({ detection: v })} />}
            {has('tracking') && <Toggle label="Face tracking" checked={opts.tracking} onChange={(v) => update({ tracking: v })} />}
            {has('landmarks') && <Toggle label="Facial landmarks" checked={opts.landmarks && modelReady('face_landmarker')} onChange={(v) => update({ landmarks: v })} disabled={!modelReady('face_landmarker')} hint={!modelReady('face_landmarker') ? 'Install MediaPipe Face Landmarker' : undefined} />}
            {has('expression') && <Toggle label="Expression" checked={opts.expression && modelReady('ferplus')} onChange={(v) => update({ expression: v })} disabled={!modelReady('ferplus')} />}
            {has('recognition') && (
              <Toggle label="Recognition" checked={opts.recognition && !recognitionBlocked && modelReady('sface')} onChange={(v) => update({ recognition: v })} disabled={recognitionBlocked || !modelReady('sface')} hint={recognitionBlocked ? 'Sign in under Settings to use recognition' : undefined} />
            )}
            {has('age') && <Toggle label="Age estimation" checked={opts.age && (modelReady('clip_attributes') || modelReady('insightface_buffalo_s'))} onChange={(v) => update({ age: v })} disabled={!modelReady('clip_attributes') && !modelReady('insightface_buffalo_s')} hint="Needs CLIP attributes or the research pack" />}
            {has('attributes') && <Toggle label="Glasses / mask / facial hair" checked={opts.attributes && modelReady('clip_attributes')} onChange={(v) => update({ attributes: v })} disabled={!modelReady('clip_attributes')} hint="Experimental CLIP model" />}
            {has('appearance') && (
              <Toggle label="Appearance classifier" checked={opts.appearance && !!settings?.allow_appearance && modelReady('insightface_buffalo_s')} onChange={(v) => update({ appearance: v })} disabled={!settings?.allow_appearance || !modelReady('insightface_buffalo_s')} hint="Off by default. Enable it in Settings first." />
            )}
            {has('pose') && <Toggle label="Head pose axes" checked={ov.pose} onChange={(v) => setOv((o) => ({ ...o, pose: v }))} />}
            {has('blur') && (
              <Select<string>
                label="Blur faces in view"
                value={ov.blur || 'off'}
                onChange={(v) => setOv((o) => ({ ...o, blur: v === 'off' ? false : (v as OverlayOptions['blur']) }))}
                options={[{ value: 'off', label: 'Off' }, { value: 'blur', label: 'Blur' }, { value: 'pixelate', label: 'Pixelate' }, { value: 'solid', label: 'Solid mask' }]}
              />
            )}
          </div>
          {has('landmarks') && (
            <Select<AnalysisOptions['overlay']>
              label="Overlay"
              value={opts.landmarks ? opts.overlay : 'none'}
              onChange={(v) => update({ overlay: v, landmarks: v !== 'none' || opts.landmarks })}
              options={[
                { value: 'none', label: 'No landmarks' }, { value: 'basic', label: 'Basic landmarks' },
                { value: 'detailed', label: 'Detailed landmarks' }, { value: 'mesh', label: 'Full face mesh' },
              ]}
            />
          )}
          <div className="space-y-1">
            <Toggle label="Boxes" checked={ov.boxes} onChange={(v) => setOv((o) => ({ ...o, boxes: v }))} />
            <Toggle label="Labels" checked={ov.labels} onChange={(v) => setOv((o) => ({ ...o, labels: v }))} />
          </div>
          {has('threshold') && (
            <Slider label="Detection threshold" value={opts.score_threshold} min={0.3} max={0.95} step={0.05} onChange={(v) => update({ score_threshold: v })} format={(v) => v.toFixed(2)} />
          )}
          {has('source') && (
            <div className="space-y-2 border-t border-ink-700 pt-3">
              <Select<'browser' | 'server'>
                label="Video source"
                value={source}
                onChange={(v) => {
                  stop();
                  setSource(v);
                }}
                options={[{ value: 'browser', label: 'This browser’s camera' }, { value: 'server', label: 'Server source (experimental)' }]}
              />
              {source === 'server' && (
                <>
                  <input
                    aria-label="Camera number or stream URL"
                    value={serverSrc}
                    onChange={(e) => setServerSrc(e.target.value)}
                    placeholder="0 or rtsp://camera/stream"
                    className="w-full rounded-lg border border-ink-600 bg-ink-800 px-3 py-2 text-sm text-fog-100"
                  />
                  <p className="text-xs text-fog-500">A camera number opened by the server, or an RTSP/HTTP stream URL. Credentials in URLs are sent only to that camera.</p>
                </>
              )}
            </div>
          )}
          {running && (
            <Button variant="ghost" icon={<RefreshCw className="h-4 w-4" />} onClick={() => wsRef.current?.send(JSON.stringify({ type: 'options', options: wireOptions(opts), reset_tracking: true }))}>
              Reset tracking IDs
            </Button>
          )}
        </aside>
      )}
    </div>
  );
}

const PRESET_HELP: Record<string, string> = {
  fast: 'Detection and tracking only, on a smaller frame. Highest frame rate.',
  balanced: 'Adds landmarks, pose, blink and smile, quality, expression and recognition.',
  detailed: 'Adds age, glasses/mask/facial-hair estimates and full-resolution detection. Lower frame rate.',
};

function presetDefaults(p: AnalysisOptions['preset']): Partial<AnalysisOptions> {
  if (p === 'fast') return { landmarks: false, overlay: 'none', expression: false, quality: false, age: false, attributes: false, max_side: 480 };
  if (p === 'detailed') return { landmarks: true, overlay: 'detailed', expression: true, quality: true, age: true, attributes: true, max_side: 960 };
  return { landmarks: true, overlay: 'basic', expression: true, quality: true, age: false, attributes: false, max_side: 640 };
}

function wireOptions(o: AnalysisOptions) {
  // the server also uses the overlay level to decide how many landmark points to return
  return { ...o, overlay: o.landmarks ? o.overlay : 'none' };
}
