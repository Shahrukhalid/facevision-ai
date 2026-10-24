import { AlertTriangle, CheckCircle2, XCircle } from 'lucide-react';
import type { Face } from '../lib/types';
import { fmtNum, fmtPct, statusColor, titleCase } from '../lib/util';
import { Badge, KV, Meter, cx } from './ui';

function PoseDial({ yaw, pitch, roll }: { yaw: number; pitch: number; roll: number }) {
  // a small top-down dial for yaw and a side dial for pitch; numbers carry the precise values
  const r = 26;
  const pt = (deg: number) => [32 + r * Math.sin((deg * Math.PI) / 180), 32 - r * Math.cos((deg * Math.PI) / 180)];
  const [yx, yy] = pt(yaw);
  const [px, py] = pt(-pitch + 90);
  return (
    <div className="flex items-center gap-4">
      {[{ label: 'Yaw', x: yx, y: yy, v: yaw }, { label: 'Pitch', x: px, y: py, v: pitch }].map((d) => (
        <div key={d.label} className="flex flex-col items-center gap-1">
          <svg viewBox="0 0 64 64" className="h-14 w-14" aria-hidden>
            <circle cx="32" cy="32" r={r} fill="none" stroke="#2f3a48" strokeWidth="2" />
            <line x1="32" y1="32" x2={d.x} y2={d.y} stroke="#5fd0e0" strokeWidth="2.5" strokeLinecap="round" />
            <circle cx="32" cy="32" r="3" fill="#e8edf3" />
          </svg>
          <span className="font-mono text-xs tabular-nums text-fog-300">{d.label} {d.v.toFixed(0)}°</span>
        </div>
      ))}
      <div className="flex flex-col items-center gap-1">
        <svg viewBox="0 0 64 64" className="h-14 w-14" aria-hidden>
          <g transform={`rotate(${roll} 32 32)`}>
            <ellipse cx="32" cy="32" rx="16" ry="21" fill="none" stroke="#5fd0e0" strokeWidth="2" />
            <line x1="20" y1="28" x2="44" y2="28" stroke="#e8edf3" strokeWidth="2" />
          </g>
        </svg>
        <span className="font-mono text-xs tabular-nums text-fog-300">Roll {roll.toFixed(0)}°</span>
      </div>
    </div>
  );
}

const Section = ({ title, children }: { title: string; children: React.ReactNode }) => (
  <div className="border-t border-ink-700 pt-3">
    <div className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-fog-500">{title}</div>
    {children}
  </div>
);

export default function FacePanel({ face, title }: { face: Face; title?: string }) {
  const a = face.analysis || {};
  const rec = face.recognition;
  return (
    <div className="space-y-3 rounded-xl border border-ink-700 bg-ink-900 p-4 text-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          {face.crop && <img src={face.crop} alt="" className="h-14 w-14 rounded-lg object-cover" />}
          <div>
            <div className="font-display font-semibold text-fog-100">{title || (face.track_id ? `Track #${face.track_id}` : `Face ${face.index + 1}`)}</div>
            <div className="text-xs text-fog-400">
              Detection {fmtPct(face.score)}{face.low_confidence && ' · low confidence'}{face.truncated && ' · cut off by frame edge'}
            </div>
          </div>
        </div>
        {rec && (
          <span className="rounded-full px-2.5 py-1 text-xs font-medium" style={{ background: `${statusColor(rec.status)}22`, color: statusColor(rec.status) }}>
            {rec.status === 'match' ? rec.name : titleCase(rec.status)}
          </span>
        )}
      </div>

      {rec && rec.status !== 'locked' && (
        <Section title="Recognition">
          <KV k="Similarity" v={rec.similarity !== undefined && rec.similarity !== null ? rec.similarity.toFixed(3) : '–'} mono />
          <KV k="Threshold" v={rec.threshold?.toFixed(3) ?? '–'} mono />
          {rec.candidates && rec.candidates.length > 1 && (
            <div className="mt-1 text-xs text-fog-400">Next closest: {rec.candidates.slice(1).map((c) => `${c.name} ${c.similarity.toFixed(2)}`).join(', ')}</div>
          )}
          {rec.note && <div className="mt-1 text-xs text-warn">{rec.note}</div>}
        </Section>
      )}
      {rec?.status === 'locked' && <div className="text-xs text-info">{rec.note}</div>}

      {a.head_pose && (
        <Section title={`Head pose · ${a.direction}`}>
          <PoseDial yaw={a.head_pose.yaw} pitch={a.head_pose.pitch} roll={a.head_pose.roll} />
          {a.head_pose.method === 'approximate-5pt' && <div className="mt-1 text-xs text-fog-500">Approximate (5 key points). Install the landmark model for a full estimate.</div>}
        </Section>
      )}

      {(a.eyes || a.mouth || a.smile) && (
        <Section title="Eyes and mouth">
          <div className="flex flex-wrap gap-1.5">
            {a.eyes && <Badge tone={a.eyes.both_closed ? 'warn' : 'ok'}>{a.eyes.both_closed ? 'Eyes closed' : 'Eyes open'}</Badge>}
            {a.eyes && <Badge tone="neutral">{a.eyes.blink_count} blinks</Badge>}
            {a.mouth && <Badge tone={a.mouth.open ? 'info' : 'neutral'}>{a.mouth.open ? 'Mouth open' : 'Mouth closed'}</Badge>}
            {a.smile && <Badge tone={a.smile.smiling ? 'lens' : 'neutral'}>{a.smile.smiling ? 'Smiling' : 'Not smiling'}</Badge>}
          </div>
          {a.eyes && (
            <div className="mt-2 grid grid-cols-2 gap-2">
              <Meter label="Image-left eye closed" value={a.eyes.right_closed_score} />
              <Meter label="Image-right eye closed" value={a.eyes.left_closed_score} />
              {a.smile && <Meter label="Smile" value={a.smile.score} />}
              {a.mouth && <Meter label="Jaw open" value={a.mouth.jaw_open_score} />}
            </div>
          )}
        </Section>
      )}

      {a.expression && (
        <Section title="Observable expression">
          <div className="space-y-1.5">
            {Object.entries(a.expression.probabilities).slice(0, 4).map(([k, v]) => (
              <Meter key={k} label={titleCase(k)} value={v} tone={k === a.expression!.label ? '#5fd0e0' : '#4a5869'} />
            ))}
          </div>
          {a.expression.uncertain && <div className="mt-1 text-xs text-warn">Uncertain: no class above 50%.</div>}
          <div className="mt-1 text-xs text-fog-500">{a.expression.note}</div>
        </Section>
      )}

      {a.age && (
        <Section title="Estimated age">
          {a.age.range && (
            <div className="font-display text-xl font-semibold text-fog-100">
              {a.age.range[1] === null ? `${a.age.range[0]}+` : `${a.age.range[0]}–${a.age.range[1]}`} <span className="text-sm font-normal text-fog-400">years</span>
            </div>
          )}
          <div className="text-xs text-fog-500">{a.age.source}{a.age.note ? `. ${a.age.note}` : ''}</div>
          {a.age.clip_bracket && (
            <div className="mt-2 space-y-1">
              {Object.entries(a.age.clip_bracket.distribution).slice(0, 3).map(([k, v]) => <Meter key={k} label={`${k} (CLIP)`} value={v} tone="#4a5869" />)}
            </div>
          )}
        </Section>
      )}

      {a.appearance && (
        <Section title="Appearance classifier (optional)">
          <KV k="Model label" v={`${a.appearance.model_label} · ${fmtPct(a.appearance.probability)}`} />
          <div className="text-xs text-fog-500">{a.appearance.note}</div>
        </Section>
      )}

      {a.attributes && (
        <Section title="Visible attributes · experimental">
          <div className="grid grid-cols-2 gap-2">
            {Object.entries(a.attributes.probabilities).map(([k, v]) => <Meter key={k} label={titleCase(k)} value={v} tone={v > 0.6 ? '#5fd0e0' : '#4a5869'} />)}
          </div>
          <div className="mt-1 text-xs text-fog-500">Zero-shot CLIP probabilities. They can be wrong and biased.</div>
        </Section>
      )}

      {a.quality && (
        <Section title={`Quality · ${fmtPct(a.quality.score)}`}>
          <div className={cx('mb-1 flex items-center gap-1.5 text-xs', a.quality.suitable_for_matching ? 'text-ok' : 'text-warn')}>
            {a.quality.suitable_for_matching ? <CheckCircle2 className="h-3.5 w-3.5" /> : <AlertTriangle className="h-3.5 w-3.5" />}
            {a.quality.suitable_for_matching ? 'Suitable for matching' : 'Not suitable for matching'}
          </div>
          <ul className="space-y-0.5 text-xs">
            {Object.entries(a.quality.checks).map(([k, c]) => (
              <li key={k} className="flex items-center gap-1.5" title={c.detail}>
                {c.ok ? <CheckCircle2 className="h-3 w-3 text-ok" /> : <XCircle className="h-3 w-3 text-warn" />}
                <span className="text-fog-300">{titleCase(k)}</span>
                <span className="ml-auto font-mono text-fog-500">{typeof c.value === 'object' ? '' : String(c.value)}</span>
              </li>
            ))}
          </ul>
        </Section>
      )}

      {a.occlusion && (
        <Section title="Occlusion">
          <div className="text-xs text-fog-300">{a.occlusion.likely ? `Likely: ${a.occlusion.reasons.join(', ')}` : 'No signs of occlusion detected'}</div>
        </Section>
      )}

      {(a.symmetry || a.proportions) && (
        <Section title="Geometry">
          {a.symmetry && <KV k="Landmark symmetry" v={`${fmtPct(a.symmetry.score)} (mean deviation ${fmtNum(a.symmetry.mean_deviation_pct)}%)`} />}
          {a.proportions?.height_to_width !== undefined ? (
            <>
              <KV k="Height : width" v={fmtNum(a.proportions.height_to_width, 2)} mono />
              <KV k="Jaw : cheek width" v={fmtNum(a.proportions.jaw_to_cheek, 2)} mono />
              <KV k="Forehead : cheek width" v={fmtNum(a.proportions.forehead_to_cheek, 2)} mono />
              <KV k="Outline" v={a.proportions.outline} />
            </>
          ) : (
            a.proportions?.note && <div className="text-xs text-fog-500">{a.proportions.note}</div>
          )}
          <div className="mt-1 text-xs text-fog-500">Measurements of landmark positions. They depend on pose and camera.</div>
        </Section>
      )}

      {a.antispoof && (
        <Section title="Passive anti-spoofing">
          <Meter label={`Real-face score (${a.antispoof.label})`} value={a.antispoof.real_score} tone={a.antispoof.real_score >= 0.5 ? '#5cc98e' : '#e8646d'} />
        </Section>
      )}

      {a.unavailable && Object.keys(a.unavailable).length > 0 && (
        <Section title="Not available">
          <ul className="space-y-0.5 text-xs text-fog-500">
            {Object.entries(a.unavailable).map(([k, v]) => <li key={k}><span className="text-fog-300">{titleCase(k)}:</span> {v}</li>)}
          </ul>
        </Section>
      )}
    </div>
  );
}
