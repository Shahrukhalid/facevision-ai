import { describe, expect, it } from 'vitest';
import type { FrameResult } from '../src/lib/types';
import { csvCell, facesToCsv, fmtBytes, fmtPct, statusColor, titleCase } from '../src/lib/util';
import { NAV } from '../src/components/Layout';

const result: FrameResult = {
  image: { width: 640, height: 480 },
  face_count: 1,
  timings_ms: { total: 12 },
  faces: [
    {
      index: 0,
      box: [10, 20, 100, 120],
      score: 0.93,
      keypoints: [[0, 0], [0, 0], [0, 0], [0, 0], [0, 0]],
      track_id: 4,
      analysis: {
        head_pose: { yaw: 5, pitch: -3, roll: 1, axes: null, method: 'mesh-transform' },
        direction: 'forward',
        expression: { label: 'happiness', probability: 0.8, uncertain: false, probabilities: { happiness: 0.8 }, note: '' },
        age: { range: [30, 46], source: 'test, "quoted"' },
      },
      recognition: { status: 'unknown', similarity: 0.12 },
    },
  ],
};

describe('formatting', () => {
  it('formats bytes', () => {
    expect(fmtBytes(0)).toBe('0 B');
    expect(fmtBytes(1536)).toBe('1.5 KB');
    expect(fmtBytes(80 * 1024 * 1024)).toBe('80.0 MB');
    expect(fmtBytes(undefined)).toBe('–');
  });
  it('formats percentages and labels', () => {
    expect(fmtPct(0.934)).toBe('93%');
    expect(titleCase('low_quality')).toBe('Low quality');
  });
  it('uses distinct colours for recognition states', () => {
    const colors = ['match', 'unknown', 'ambiguous', 'low_quality'].map(statusColor);
    expect(new Set(colors).size).toBe(4);
  });
});

describe('CSV export', () => {
  it('writes one row per face with escaped values', () => {
    const csv = facesToCsv(result, 'photo.jpg').trim().split('\n');
    expect(csv).toHaveLength(2);
    expect(csv[0].startsWith('source,face,track_id')).toBe(true);
    expect(csv[1]).toContain('photo.jpg,1,4,10.0,20.0,100.0,120.0,0.930');
    expect(csv[1]).toContain('happiness,0.8,30,46');
    expect(csv[1]).toContain('"test, ""quoted"""');
    expect(csv[1]).toContain('unknown');
  });
});

describe('navigation', () => {
  it('has the sixteen required pages with unique routes', () => {
    const items = NAV.flatMap((g) => g.items);
    expect(items).toHaveLength(16);
    expect(new Set(items.map((i) => i.to)).size).toBe(16);
  });
});

describe('csvCell', () => {
  it('neutralises spreadsheet formulas in text but keeps numbers', () => {
    expect(csvCell('=HYPERLINK("http://x")')).toBe(`"'=HYPERLINK(""http://x"")"`);
    expect(csvCell('@SUM(A1)')).toBe("'@SUM(A1)");
    expect(csvCell('-12.5')).toBe('-12.5');
    expect(csvCell(-3)).toBe('-3');
    expect(csvCell('Ada')).toBe('Ada');
  });
});
