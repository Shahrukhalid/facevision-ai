import type { Face, FrameResult } from './types';

export const fmtBytes = (n?: number | null) => {
  if (n === undefined || n === null) return '–';
  const u = ['B', 'KB', 'MB', 'GB', 'TB'];
  let i = 0;
  let v = n;
  while (v >= 1024 && i < u.length - 1) {
    v /= 1024;
    i++;
  }
  return `${v.toFixed(v >= 100 || i === 0 ? 0 : 1)} ${u[i]}`;
};

export const fmtPct = (v?: number | null, digits = 0) => (v === undefined || v === null ? '–' : `${(v * 100).toFixed(digits)}%`);
export const fmtNum = (v?: number | null, digits = 1) => (v === undefined || v === null ? '–' : v.toFixed(digits));
export const fmtTime = (iso?: string) => (iso ? new Date(iso).toLocaleString() : '–');

export function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

export function downloadText(text: string, filename: string, type = 'application/json') {
  downloadBlob(new Blob([text], { type }), filename);
}

export async function dataUrlToBlob(url: string) {
  return (await fetch(url)).blob();
}

export const stamp = () => new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);

export const csvCell = (v: unknown) => {
  let s = v === undefined || v === null ? '' : String(v);
  // Spreadsheet formula injection: text such as a file or person name starting with = + - @ is prefixed with '
  if (typeof v === 'string' && /^[=+\-@\t\r]/.test(s) && !Number.isFinite(Number(s))) s = `'${s}`;
  return /[",\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
};

/** One row per face, with the main estimates and their uncertainty indicators. */
export function facesToCsv(result: FrameResult, source = '') {
  const head = [
    'source', 'face', 'track_id', 'x', 'y', 'w', 'h', 'detection_score', 'low_confidence', 'yaw', 'pitch', 'roll', 'direction',
    'expression', 'expression_probability', 'age_low', 'age_high', 'age_source', 'smiling', 'eyes_closed', 'mouth_open',
    'quality_score', 'suitable_for_matching', 'recognition_status', 'recognized_name', 'similarity',
  ];
  const rows = result.faces.map((f: Face) => {
    const a = f.analysis || {};
    return [
      source, f.index + 1, f.track_id ?? '', ...f.box.map((v) => v.toFixed(1)), f.score.toFixed(3), f.low_confidence ? 'yes' : 'no',
      a.head_pose?.yaw ?? '', a.head_pose?.pitch ?? '', a.head_pose?.roll ?? '', a.direction ?? '',
      a.expression?.label ?? '', a.expression?.probability ?? '', a.age?.range?.[0] ?? '', a.age?.range?.[1] ?? '', a.age?.source ?? '',
      a.smile ? (a.smile.smiling ? 'yes' : 'no') : '', a.eyes ? (a.eyes.both_closed ? 'yes' : 'no') : '',
      a.mouth ? (a.mouth.open ? 'yes' : 'no') : '', a.quality?.score ?? '', a.quality ? (a.quality.suitable_for_matching ? 'yes' : 'no') : '',
      f.recognition?.status ?? '', f.recognition?.name ?? '', f.recognition?.similarity ?? '',
    ];
  });
  return [head, ...rows].map((r) => r.map(csvCell).join(',')).join('\n') + '\n';
}

export const titleCase = (s: string) => s.replace(/_/g, ' ').replace(/^\w/, (c) => c.toUpperCase());

export function statusColor(status?: string) {
  switch (status) {
    case 'match':
      return '#5cc98e';
    case 'unknown':
      return '#e9a93c';
    case 'ambiguous':
      return '#f0c75e';
    case 'low_quality':
      return '#94a1b2';
    case 'locked':
      return '#7aa7f5';
    default:
      return '#5fd0e0';
  }
}
