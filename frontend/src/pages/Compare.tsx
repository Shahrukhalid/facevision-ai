import { ArrowLeftRight } from 'lucide-react';
import { useState } from 'react';
import { Alert, Badge, Button, Card, FileDrop, KV, PageHeader, Slider } from '../components/ui';
import { api, errorText } from '../lib/api';
import { useApp } from '../lib/store';
import { fmtPct } from '../lib/util';

interface Side {
  faces: { index: number; box: number[]; score: number; crop: string }[];
  selected: number;
  aligned: string;
  quality: { score: number; suitable_for_matching: boolean; failed: string[] };
  embedding: { dim: number; norm: number; preview: number[] };
}
interface CompareResult { model: string; similarity: number; threshold: number; match: boolean; decision: string; note: string; warnings: string[]; a: Side; b: Side }

export default function Compare() {
  const { settings } = useApp();
  const [files, setFiles] = useState<{ a?: File; b?: File }>({});
  const [sel, setSel] = useState({ a: 0, b: 0 });
  const [res, setRes] = useState<CompareResult | null>(null);
  const [thr, setThr] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const run = async (f = files, s = sel) => {
    if (!f.a || !f.b) return;
    setBusy(true);
    setErr(null);
    try {
      const r = await api.form<CompareResult>('/api/compare', { file_a: f.a, file_b: f.b, face_a: String(s.a), face_b: String(s.b) });
      setRes(r);
      setThr((t) => t ?? r.threshold);
    } catch (e) {
      setErr(errorText(e));
      setRes(null);
    } finally {
      setBusy(false);
    }
  };
  const threshold = thr ?? res?.threshold ?? 0.363;
  const match = res ? res.similarity >= threshold : false;

  const side = (key: 'a' | 'b', label: string) => (
    <Card title={label}>
      <FileDrop accept="image/jpeg,image/png,image/webp" onFiles={(f) => { const next = { ...files, [key]: f[0] }; const s = { ...sel, [key]: 0 }; setFiles(next); setSel(s); run(next, s); }} label={files[key]?.name || `Choose photo ${label.slice(-1)}`} />
      {files[key] && <img src={URL.createObjectURL(files[key]!)} alt="" className="mt-3 max-h-56 w-full rounded-lg object-contain" />}
      {res && (
        <div className="mt-3 space-y-3">
          {res[key].faces.length > 1 && (
            <div>
              <div className="mb-1 text-xs text-fog-400">{res[key].faces.length} faces found. Choose one:</div>
              <div className="flex flex-wrap gap-2">
                {res[key].faces.map((f) => (
                  <button key={f.index} onClick={() => { const s = { ...sel, [key]: f.index }; setSel(s); run(files, s); }} className={`rounded-lg border-2 ${res[key].selected === f.index ? 'border-lens-400' : 'border-transparent'}`}>
                    <img src={f.crop} alt={`Face ${f.index + 1}`} className="h-14 w-14 rounded-md" />
                  </button>
                ))}
              </div>
            </div>
          )}
          <div className="flex items-center gap-3">
            <img src={res[key].aligned} alt="Aligned face" className="h-24 w-24 rounded-lg" />
            <div className="text-xs">
              <div className="text-fog-400">Aligned crop used for the embedding</div>
              <div className="mt-1">Quality {fmtPct(res[key].quality.score)} {res[key].quality.suitable_for_matching ? <Badge tone="ok">good</Badge> : <Badge tone="warn">low</Badge>}</div>
              <div className="mt-1 font-mono text-fog-500">{res[key].embedding.dim}-d embedding, |v| = {res[key].embedding.norm}</div>
            </div>
          </div>
          <div className="overflow-x-auto font-mono text-[10px] text-fog-500">[{res[key].embedding.preview.map((v) => v.toFixed(3)).join(', ')}, …]</div>
        </div>
      )}
    </Card>
  );

  return (
    <div className="space-y-4">
      <PageHeader title="Face Comparison" subtitle="Compare one face in each of two photos. Nothing is stored and no enrolled data is used." />
      <div className="grid gap-4 lg:grid-cols-2">
        {side('a', 'Photo A')}
        {side('b', 'Photo B')}
      </div>
      {err && <Alert tone="bad">{err}</Alert>}
      {busy && <p className="text-sm text-fog-400">Comparing…</p>}
      {res && (
        <Card title="Result" actions={<Button variant="ghost" icon={<ArrowLeftRight className="h-4 w-4" />} onClick={() => run()}>Run again</Button>}>
          <div className="grid gap-6 md:grid-cols-[auto_minmax(0,1fr)]">
            <div className="text-center">
              <div className={`font-display text-4xl font-semibold tabular-nums ${match ? 'text-ok' : 'text-warn'}`}>{res.similarity.toFixed(3)}</div>
              <div className="text-xs text-fog-400">cosine similarity</div>
              <div className="mt-2"><Badge tone={match ? 'ok' : 'warn'}>{match ? 'Same person likely' : 'Different people likely'}</Badge></div>
            </div>
            <div className="space-y-3">
              <div className="relative h-3 rounded-full bg-ink-700">
                <div className="absolute inset-y-0 left-0 rounded-full bg-lens-500/60" style={{ width: `${Math.max(0, res.similarity) * 100}%` }} />
                <div className="absolute -top-1 h-5 w-0.5 bg-fog-100" style={{ left: `${threshold * 100}%` }} title="Threshold" />
              </div>
              <Slider label="Verification threshold" value={threshold} min={0.1} max={0.9} step={0.005} onChange={setThr} format={(v) => v.toFixed(3)} />
              <KV k="Model" v={res.model} />
              <KV k="Default threshold" v={`${res.threshold.toFixed(3)}${settings?.recognizer === res.model ? '' : ''}`} mono />
              <p className="text-xs text-fog-500">{res.note} The default threshold comes from the model's published guidance and this project's evaluation; see docs/EVALUATION.md.</p>
              {res.warnings.map((w, i) => <Alert key={i} tone="warn">{w}</Alert>)}
            </div>
          </div>
        </Card>
      )}
    </div>
  );
}
