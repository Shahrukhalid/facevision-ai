import { useEffect, useRef } from 'react';
import { defaultOverlay, drawOverlay, type OverlayOptions } from '../lib/overlay';
import { useApp } from '../lib/store';
import type { FrameResult } from '../lib/types';

/** Draws an uploaded image with the analysis overlay. `canvasRef` lets parents export the composite. */
export default function ImageResult({ src, result, overlay, canvasRef, onFaceClick }: {
  src: string;
  result: FrameResult | null;
  overlay?: Partial<OverlayOptions>;
  canvasRef?: React.MutableRefObject<HTMLCanvasElement | null>;
  onFaceClick?: (index: number) => void;
}) {
  const ref = useRef<HTMLCanvasElement>(null);
  const { topology } = useApp();
  const ovKey = JSON.stringify(overlay);
  useEffect(() => {
    const img = new Image();
    img.onload = () => {
      const c = ref.current;
      if (!c) return;
      c.width = img.naturalWidth;
      c.height = img.naturalHeight;
      const ctx = c.getContext('2d')!;
      ctx.drawImage(img, 0, 0);
      if (result) drawOverlay(ctx, result, c.width / result.image.width, c.height / result.image.height, { ...defaultOverlay, topology, ...overlay });
    };
    img.src = src;
    if (canvasRef) canvasRef.current = ref.current;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [src, result, topology, ovKey]);

  const click = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!onFaceClick || !result) return;
    const c = ref.current!;
    const rect = c.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width) * result.image.width;
    const y = ((e.clientY - rect.top) / rect.height) * result.image.height;
    const hit = result.faces.find((f) => x >= f.box[0] && x <= f.box[0] + f.box[2] && y >= f.box[1] && y <= f.box[1] + f.box[3]);
    if (hit) onFaceClick(hit.index);
  };
  return <canvas ref={ref} onClick={click} className={`max-h-[70vh] w-full rounded-xl border border-ink-700 bg-black object-contain ${onFaceClick ? 'cursor-pointer' : ''}`} />;
}
