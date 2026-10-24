import { Camera, CameraOff } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { Alert, Button } from './ui';

/** Captures still photos from the webcam for enrolment. Nothing is kept after they are handed to onDone. */
export default function CapturePhotos({ count = 5, onDone }: { count?: number; onDone: (files: File[]) => void }) {
  const video = useRef<HTMLVideoElement>(null);
  const stream = useRef<MediaStream | null>(null);
  const [on, setOn] = useState(false);
  const [shots, setShots] = useState<File[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const stop = () => {
    stream.current?.getTracks().forEach((t) => t.stop());
    stream.current = null;
    setOn(false);
  };
  useEffect(() => () => stop(), []);

  const start = async () => {
    setErr(null);
    try {
      stream.current = await navigator.mediaDevices.getUserMedia({ video: { width: { ideal: 1280 }, height: { ideal: 720 } } });
      video.current!.srcObject = stream.current;
      await video.current!.play();
      setOn(true);
    } catch (e) {
      setErr(`Could not open the camera: ${(e as Error).message}`);
    }
  };

  const capture = async () => {
    setBusy(true);
    const files: File[] = [];
    for (let i = 0; i < count; i++) {
      await new Promise((r) => setTimeout(r, 700));
      const v = video.current!;
      const c = document.createElement('canvas');
      c.width = v.videoWidth;
      c.height = v.videoHeight;
      c.getContext('2d')!.drawImage(v, 0, 0);
      const blob = await new Promise<Blob | null>((r) => c.toBlob(r, 'image/jpeg', 0.92));
      if (blob) files.push(new File([blob], `capture-${i + 1}.jpg`, { type: 'image/jpeg' }));
      setShots([...files]);
    }
    setBusy(false);
    stop();
    onDone(files);
    setShots([]);
  };

  return (
    <div className="space-y-2">
      <div className="relative overflow-hidden rounded-lg border border-ink-700 bg-black">
        <video ref={video} playsInline muted className="aspect-video w-full -scale-x-100 object-cover" />
        {!on && <div className="absolute inset-0 flex items-center justify-center text-sm text-fog-500">Camera off</div>}
        {busy && <div className="absolute left-2 top-2 rounded bg-ink-900/80 px-2 py-1 text-xs">Capturing {shots.length + 1} of {count}… turn your head slightly between shots</div>}
      </div>
      {err && <Alert tone="bad">{err}</Alert>}
      <div className="flex gap-2">
        {on ? (
          <>
            <Button variant="primary" icon={<Camera className="h-4 w-4" />} busy={busy} onClick={capture}>Capture {count} photos</Button>
            <Button icon={<CameraOff className="h-4 w-4" />} onClick={stop} disabled={busy}>Close camera</Button>
          </>
        ) : (
          <Button icon={<Camera className="h-4 w-4" />} onClick={start}>Use camera</Button>
        )}
      </div>
    </div>
  );
}
