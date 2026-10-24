import type { MeshTopology } from './store';
import type { Face, FrameResult } from './types';
import { statusColor } from './util';

export interface OverlayOptions {
  boxes: boolean;
  labels: boolean;
  landmarks: 'none' | 'basic' | 'detailed' | 'mesh';
  pose: boolean;
  blur: false | 'blur' | 'pixelate' | 'solid';
  mirrored: boolean;
  topology: MeshTopology | null;
  showAge: boolean;
  showExpression: boolean;
}

export const defaultOverlay: OverlayOptions = {
  boxes: true,
  labels: true,
  landmarks: 'basic',
  pose: false,
  blur: false,
  mirrored: false,
  topology: null,
  showAge: true,
  showExpression: true,
};

let scratch: HTMLCanvasElement | null = null;

function obscure(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, mode: 'blur' | 'pixelate' | 'solid') {
  const pad = 0.15;
  const rx = Math.max(0, x - w * pad);
  const ry = Math.max(0, y - h * pad * 1.2);
  const rw = Math.min(ctx.canvas.width - rx, w * (1 + 2 * pad));
  const rh = Math.min(ctx.canvas.height - ry, h * (1 + 2 * pad));
  if (rw < 2 || rh < 2) return;
  ctx.save();
  if (mode === 'solid') {
    ctx.fillStyle = '#141414';
    ctx.beginPath();
    ctx.ellipse(rx + rw / 2, ry + rh / 2, rw / 2, rh / 2, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();
    return;
  }
  scratch = scratch || document.createElement('canvas');
  // about 7 blocks across the face for pixelation, 6 samples for a heavy blur: enough to hide identity
  const across = mode === 'pixelate' ? 7 : 6;
  scratch.width = across;
  scratch.height = Math.max(2, Math.round((across * rh) / rw));
  const s = scratch.getContext('2d')!;
  s.imageSmoothingEnabled = true;
  s.drawImage(ctx.canvas, rx, ry, rw, rh, 0, 0, scratch.width, scratch.height);
  if (mode === 'blur') {
    ctx.beginPath();
    ctx.ellipse(rx + rw / 2, ry + rh / 2, rw / 2, rh / 2, 0, 0, Math.PI * 2);
    ctx.clip();
  }
  ctx.imageSmoothingEnabled = mode === 'blur';
  ctx.drawImage(scratch, 0, 0, scratch.width, scratch.height, rx, ry, rw, rh);
  ctx.restore();
}

function faceLabel(f: Face, o: OverlayOptions): string[] {
  const lines: string[] = [];
  const r = f.recognition;
  if (r?.status === 'match') lines.push(`${r.name} · ${r.similarity?.toFixed(2)}`);
  else if (r?.status === 'unknown') lines.push('Unknown');
  else if (r?.status === 'ambiguous') lines.push('Ambiguous match');
  else if (r?.status === 'low_quality') lines.push('Low quality');
  const head = `${f.track_id ? `#${f.track_id}` : `Face ${f.index + 1}`} · ${(f.score * 100).toFixed(0)}%${f.low_confidence ? ' (low)' : ''}`;
  lines.unshift(head);
  const a = f.analysis;
  const bits: string[] = [];
  if (o.showAge && a?.age?.range) bits.push(a.age.range[1] === null ? `age ${a.age.range[0]}+` : `age ~${a.age.range[0]}–${a.age.range[1]}`);
  if (o.showExpression && a?.expression) bits.push(`${a.expression.label}${a.expression.uncertain ? '?' : ''}`);
  if (a?.smile?.smiling) bits.push('smiling');
  if (a?.eyes?.both_closed) bits.push('eyes closed');
  if (a?.direction && a.direction !== 'forward') bits.push(`looking ${a.direction}`);
  if (bits.length) lines.push(bits.join(' · '));
  if (a?.quality && !a.quality.suitable_for_matching) lines.push(`quality ${(a.quality.score * 100).toFixed(0)}%`);
  return lines;
}

/** Draw results over a canvas that already shows the frame. sx/sy map result pixels to canvas pixels. */
export function drawOverlay(ctx: CanvasRenderingContext2D, result: FrameResult | null, sx: number, sy: number, o: OverlayOptions) {
  if (!result) return;
  const W = ctx.canvas.width;
  const X = (x: number) => (o.mirrored ? W - x * sx : x * sx);
  const Y = (y: number) => y * sy;
  const scale = Math.max(1, W / 960);
  for (const f of result.faces) {
    const [bx, by, bw, bh] = f.smooth_box || f.box;
    const x0 = o.mirrored ? W - (bx + bw) * sx : bx * sx;
    const y0 = Y(by);
    const w = bw * sx;
    const h = bh * sy;
    if (o.blur) obscure(ctx, x0, y0, w, h, o.blur);
  }
  for (const f of result.faces) {
    const [bx, by, bw, bh] = f.smooth_box || f.box;
    const x0 = o.mirrored ? W - (bx + bw) * sx : bx * sx;
    const y0 = Y(by);
    const w = bw * sx;
    const h = bh * sy;
    const color = f.recognition ? statusColor(f.recognition.status) : f.low_confidence ? '#94a1b2' : '#5fd0e0';
    const pts = f.landmarks?.points;
    if (pts && o.landmarks !== 'none' && !o.blur) {
      ctx.save();
      const all = f.landmarks!.indices === 'all';
      if (o.landmarks === 'mesh' && all && o.topology) {
        ctx.strokeStyle = 'rgba(143,227,238,0.35)';
        ctx.lineWidth = 0.6 * scale;
        ctx.beginPath();
        for (const [a, b] of o.topology.tesselation) {
          ctx.moveTo(X(pts[a][0]), Y(pts[a][1]));
          ctx.lineTo(X(pts[b][0]), Y(pts[b][1]));
        }
        ctx.stroke();
      }
      if ((o.landmarks === 'detailed' || o.landmarks === 'mesh') && all && o.topology) {
        ctx.strokeStyle = 'rgba(232,237,243,0.9)';
        ctx.lineWidth = 1.2 * scale;
        ctx.beginPath();
        for (const group of Object.values(o.topology.groups)) {
          for (const [a, b] of group) {
            ctx.moveTo(X(pts[a][0]), Y(pts[a][1]));
            ctx.lineTo(X(pts[b][0]), Y(pts[b][1]));
          }
        }
        ctx.stroke();
      }
      if (o.landmarks === 'basic' || o.landmarks === 'detailed') {
        ctx.fillStyle = 'rgba(232,237,243,0.85)';
        const r = (all ? 0.9 : 1.3) * scale;
        for (const p of pts) {
          ctx.beginPath();
          ctx.arc(X(p[0]), Y(p[1]), r, 0, Math.PI * 2);
          ctx.fill();
        }
      }
      ctx.restore();
    } else if (o.landmarks !== 'none' && !o.blur) {
      ctx.fillStyle = 'rgba(232,237,243,0.9)';
      for (const p of f.keypoints) {
        ctx.beginPath();
        ctx.arc(X(p[0]), Y(p[1]), 2.2 * scale, 0, Math.PI * 2);
        ctx.fill();
      }
    }
    const axes = f.analysis?.head_pose?.axes;
    if (o.pose && axes && !o.blur) {
      const colors = ['#e8646d', '#5cc98e', '#7aa7f5'];
      ctx.lineWidth = 2.5 * scale;
      for (let i = 1; i < 4; i++) {
        ctx.strokeStyle = colors[i - 1];
        ctx.beginPath();
        ctx.moveTo(X(axes[0][0]), Y(axes[0][1]));
        ctx.lineTo(X(axes[i][0]), Y(axes[i][1]));
        ctx.stroke();
      }
    }
    if (o.boxes) {
      ctx.strokeStyle = color;
      ctx.lineWidth = 2 * scale;
      const c = Math.min(w, h) * 0.22;
      ctx.beginPath(); // corner brackets read as a lens, and keep the face itself visible
      ctx.moveTo(x0, y0 + c); ctx.lineTo(x0, y0); ctx.lineTo(x0 + c, y0);
      ctx.moveTo(x0 + w - c, y0); ctx.lineTo(x0 + w, y0); ctx.lineTo(x0 + w, y0 + c);
      ctx.moveTo(x0 + w, y0 + h - c); ctx.lineTo(x0 + w, y0 + h); ctx.lineTo(x0 + w - c, y0 + h);
      ctx.moveTo(x0 + c, y0 + h); ctx.lineTo(x0, y0 + h); ctx.lineTo(x0, y0 + h - c);
      ctx.stroke();
      ctx.globalAlpha = 0.35;
      ctx.lineWidth = 1 * scale;
      ctx.strokeRect(x0, y0, w, h);
      ctx.globalAlpha = 1;
    }
    if (o.labels) {
      const lines = faceLabel(f, o);
      ctx.font = `${12 * scale}px "IBM Plex Sans", system-ui, sans-serif`;
      const lh = 16 * scale;
      const tw = Math.max(...lines.map((l) => ctx.measureText(l).width)) + 10 * scale;
      let ty = y0 - lines.length * lh - 4 * scale;
      if (ty < 0) ty = y0 + h + 4 * scale;
      ctx.fillStyle = 'rgba(11,14,18,0.82)';
      ctx.fillRect(x0, ty, tw, lines.length * lh + 4 * scale);
      ctx.fillStyle = color;
      ctx.fillRect(x0, ty, 3 * scale, lines.length * lh + 4 * scale);
      lines.forEach((l, i) => {
        ctx.fillStyle = i === 0 ? '#e8edf3' : '#b9c3cf';
        ctx.fillText(l, x0 + 7 * scale, ty + (i + 1) * lh - 3 * scale);
      });
    }
  }
}
