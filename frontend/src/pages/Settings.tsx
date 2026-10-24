import { Copy, KeyRound, LogIn, LogOut } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Alert, Button, Card, KV, Modal, PageHeader, Select, Slider, TextInput, Toggle } from '../components/ui';
import { api, errorText } from '../lib/api';
import { useApp } from '../lib/store';
import type { Settings } from '../lib/types';

const DEFAULT_THRESHOLDS: Record<string, number> = { sface: 0.363, insightface_buffalo_s: 0.3 };

export default function SettingsPage() {
  const { settings, saveSettings, auth, refreshAuth, refreshSystem, modelReady, system } = useApp();
  const [err, setErr] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  const [appearanceModal, setAppearanceModal] = useState(false);

  useEffect(() => {
    if (location.hash === '#access') document.getElementById('access')?.scrollIntoView();
  }, []);

  const save = async (s: Partial<Settings>) => {
    setErr(null);
    try {
      await saveSettings(s);
      setOk('Saved');
      setTimeout(() => setOk(null), 1500);
    } catch (e) {
      setErr(errorText(e));
    }
  };
  if (!settings) return null;
  const rid = settings.recognizer;
  const thr = settings.recognition_thresholds[rid] ?? DEFAULT_THRESHOLDS[rid] ?? 0.363;

  return (
    <div className="space-y-4">
      <PageHeader title="Settings" subtitle={auth.configured && !auth.signed_in ? 'Sign in to change settings.' : 'Changes are saved immediately.'} actions={ok && <span className="text-sm text-ok">{ok}</span>} />
      {err && <Alert tone="bad" onClose={() => setErr(null)}>{err}</Alert>}
      <div id="access"><Access onChanged={() => { refreshAuth(); refreshSystem(); }} /></div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Recognition">
          <div className="space-y-3">
            <Select<string>
              label="Recognizer"
              value={rid}
              onChange={(v) => save({ recognizer: v })}
              options={[{ value: 'sface', label: 'SFace (Apache-2.0, default)' }, ...(modelReady('insightface_buffalo_s') ? [{ value: 'insightface_buffalo_s', label: 'ArcFace MobileFaceNet (research licence)' }] : [])]}
            />
            <Slider label="Match threshold (cosine similarity)" value={thr} min={0.2} max={0.7} step={0.005} onChange={(v) => save({ recognition_thresholds: { ...settings.recognition_thresholds, [rid]: v } })} format={(v) => v.toFixed(3)} />
            <div className="flex items-center justify-between text-xs text-fog-500">
              <span>Higher means fewer false matches and more missed matches. Default {DEFAULT_THRESHOLDS[rid]}.</span>
              <Button variant="ghost" onClick={() => { const t = { ...settings.recognition_thresholds }; delete t[rid]; save({ recognition_thresholds: t }); }}>Reset</Button>
            </div>
            <Toggle label="Show other close candidates" checked={settings.show_candidates} onChange={(v) => save({ show_candidates: v })} />
          </div>
        </Card>
        <Card title="Analysis defaults">
          <div className="space-y-3">
            <Select<string> label="Default performance mode" value={settings.preset} onChange={(v) => save({ preset: v })} options={[{ value: 'fast', label: 'Fast' }, { value: 'balanced', label: 'Balanced' }, { value: 'detailed', label: 'Detailed' }]} />
            <Slider label="Detection threshold" value={settings.detection_threshold} min={0.3} max={0.95} step={0.05} onChange={(v) => save({ detection_threshold: v })} format={(v) => v.toFixed(2)} />
            <Slider label="Age range half-width (years)" value={settings.age_band_years} min={3} max={15} step={1} onChange={(v) => save({ age_band_years: v })} />
            <Toggle
              label="Allow the appearance classifier"
              checked={settings.allow_appearance}
              onChange={(v) => (v ? setAppearanceModal(true) : save({ allow_appearance: false }))}
              hint="Off by default"
            />
            <p className="text-xs text-fog-500">FaceVision AI never infers race, ethnicity, religion, health, sexual orientation or similar traits.</p>
          </div>
        </Card>
        <Card title="Privacy and storage">
          <div className="space-y-3">
            <Slider label="Delete job outputs after (days)" value={settings.keep_job_outputs_days} min={0} max={90} step={1} onChange={(v) => save({ keep_job_outputs_days: v })} format={(v) => (v === 0 ? 'never' : `${v} days`)} />
            <p className="text-xs text-fog-500">Live camera frames are never stored. Enrolment photos are turned into encrypted templates and then discarded.</p>
          </div>
        </Card>
        <Card title="Network">
          <KV k="Listening on" v={system ? `${system.binding.host}:${system.binding.port}` : '–'} mono />
          <p className="mt-2 text-xs text-fog-500">FaceVision AI only accepts connections from this computer. To change that, set FV_HOST, FV_ALLOW_REMOTE and FV_ALLOWED_HOSTS in the .env file and restart; read docs/SECURITY.md first.</p>
        </Card>
      </div>
      <Modal
        open={appearanceModal}
        title="Allow the appearance classifier?"
        onClose={() => setAppearanceModal(false)}
        footer={<><Button onClick={() => setAppearanceModal(false)}>Keep it off</Button><Button variant="primary" onClick={() => { save({ allow_appearance: true }); setAppearanceModal(false); }}>Allow</Button></>}
      >
        <p>This model guesses a binary label from how a face looks. It cannot know anyone's gender identity, it is often wrong, and it is less accurate for some groups of people.</p>
        <p>It needs the InsightFace research pack (non-commercial licence) and stays off on each page until you switch it on there.</p>
      </Modal>
    </div>
  );
}

function Access({ onChanged }: { onChanged: () => void }) {
  const { auth } = useApp();
  const [pass, setPass] = useState('');
  const [pass2, setPass2] = useState('');
  const [oldPass, setOldPass] = useState('');
  const [apiKey, setApiKey] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [reset, setReset] = useState(false);
  const [resetText, setResetText] = useState('');

  const run = async (fn: () => Promise<unknown>) => {
    setErr(null);
    try {
      await fn();
      setPass(''); setPass2(''); setOldPass('');
      onChanged();
    } catch (e) {
      setErr(errorText(e));
    }
  };

  return (
    <Card title="Access">
      {err && <div className="mb-3"><Alert tone="bad">{err}</Alert></div>}
      {apiKey && (
        <div className="mb-3">
          <Alert tone="ok" title="Your API key (shown once)">
            <div className="mt-1 flex items-center gap-2">
              <code className="break-all rounded bg-ink-800 px-2 py-1 font-mono text-xs text-fog-100">{apiKey}</code>
              <Button variant="ghost" icon={<Copy className="h-4 w-4" />} onClick={() => navigator.clipboard?.writeText(apiKey).catch(() => undefined)}>Copy</Button>
            </div>
            <div className="mt-1 text-xs">Send it as the X-API-Key header to use biometric API endpoints from scripts.</div>
          </Alert>
        </div>
      )}
      {!auth.configured ? (
        <div className="grid gap-3 md:grid-cols-[1fr_1fr_auto] md:items-end">
          <TextInput label="New passphrase (10+ characters)" type="password" value={pass} onChange={setPass} autoComplete="new-password" />
          <TextInput label="Repeat passphrase" type="password" value={pass2} onChange={setPass2} autoComplete="new-password" />
          <Button variant="primary" icon={<KeyRound className="h-4 w-4" />} disabled={pass.length < 10 || pass !== pass2} onClick={() => run(async () => setApiKey((await api.json<{ api_key: string }>('/api/auth/setup', { passphrase: pass })).api_key))}>Set passphrase</Button>
          <p className="text-xs text-fog-500 md:col-span-3">The passphrase protects enrolled faces: their templates are encrypted with a key that is only unlocked when you sign in. If you forget it, the only way back is to delete all enrolled faces.</p>
        </div>
      ) : !auth.signed_in ? (
        <div className="flex flex-wrap items-end gap-3">
          <div className="min-w-[240px] flex-1"><TextInput label="Passphrase" type="password" value={pass} onChange={setPass} autoComplete="current-password" /></div>
          <Button variant="primary" icon={<LogIn className="h-4 w-4" />} disabled={!pass} onClick={() => run(() => api.json('/api/auth/login', { passphrase: pass }))}>Sign in</Button>
          <Button variant="ghost" onClick={() => setReset(true)}>Forgot passphrase</Button>
        </div>
      ) : (
        <div className="space-y-4">
          <div className="flex flex-wrap gap-2">
            <Button icon={<LogOut className="h-4 w-4" />} onClick={() => run(() => api.json('/api/auth/logout', {}))}>Sign out</Button>
            <Button icon={<KeyRound className="h-4 w-4" />} onClick={() => run(async () => setApiKey((await api.json<{ api_key: string }>('/api/auth/api-key/rotate', {})).api_key))}>Create new API key</Button>
          </div>
          <div className="grid gap-3 md:grid-cols-[1fr_1fr_1fr_auto] md:items-end">
            <TextInput label="Current passphrase" type="password" value={oldPass} onChange={setOldPass} autoComplete="current-password" />
            <TextInput label="New passphrase" type="password" value={pass} onChange={setPass} autoComplete="new-password" />
            <TextInput label="Repeat new passphrase" type="password" value={pass2} onChange={setPass2} autoComplete="new-password" />
            <Button disabled={!oldPass || pass.length < 10 || pass !== pass2} onClick={() => run(() => api.json('/api/auth/change-passphrase', { old_passphrase: oldPass, new_passphrase: pass }))}>Change</Button>
          </div>
        </div>
      )}
      <Modal open={reset} title="Reset access" onClose={() => setReset(false)} footer={<><Button onClick={() => setReset(false)}>Cancel</Button><Button variant="danger" disabled={resetText !== 'DELETE ALL ENROLLED FACES'} onClick={() => run(async () => { await api.json('/api/auth/reset', { confirm: resetText }); setReset(false); setResetText(''); })}>Delete and reset</Button></>}>
        <p>Enrolled faces are encrypted with your passphrase and cannot be recovered without it. Resetting deletes every enrolled person and template, then lets you set a new passphrase.</p>
        <TextInput label="Type DELETE ALL ENROLLED FACES to confirm" value={resetText} onChange={setResetText} />
      </Modal>
    </Card>
  );
}
