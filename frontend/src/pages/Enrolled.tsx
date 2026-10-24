import { AlertTriangle, Search, Trash2, UserPlus } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import AuthNotice from '../components/AuthNotice';
import CapturePhotos from '../components/CapturePhotos';
import { Alert, Badge, Button, Card, Empty, FileDrop, KV, Modal, PageHeader, TextInput } from '../components/ui';
import { api, errorText } from '../lib/api';
import { useApp } from '../lib/store';
import type { Person } from '../lib/types';
import { fmtPct, fmtTime } from '../lib/util';

const CONSENT_TEXT =
  'This person has given informed consent to have their face enrolled for recognition on this computer. They know what it is used for, how long it is kept, and that they can ask for it to be deleted at any time.';

interface EnrolResult {
  added: number;
  model: string;
  results: { file: string; added: boolean; reason?: string; warnings?: string[]; crop?: string; quality?: { score: number }; similarity_to_existing?: number }[];
}

export default function Enrolled() {
  const { auth } = useApp();
  const [people, setPeople] = useState<Person[]>([]);
  const [query, setQuery] = useState('');
  const [selected, setSelected] = useState<Person | null>(null);
  const [creating, setCreating] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!auth.signed_in) return;
    try {
      setPeople(await api.get<Person[]>('/api/persons'));
    } catch (e) {
      setErr(errorText(e));
    }
  }, [auth.signed_in]);
  useEffect(() => {
    load();
  }, [load]);

  const open = async (id: number) => setSelected(await api.get<Person>(`/api/persons/${id}`));
  const shown = people.filter((p) => p.name.toLowerCase().includes(query.toLowerCase()));

  return (
    <div className="space-y-4">
      <PageHeader
        title="Enrolled Faces"
        subtitle="People who agreed to be recognised on this computer. Face templates are stored encrypted; photos are not kept. Deleting a person removes their templates permanently."
        actions={auth.signed_in && <Button variant="primary" icon={<UserPlus className="h-4 w-4" />} onClick={() => setCreating(true)}>Enrol a person</Button>}
      />
      <AuthNotice what="manage enrolled faces" />
      {err && <Alert tone="bad" onClose={() => setErr(null)}>{err}</Alert>}
      {auth.signed_in && (
        <div className="grid gap-4 lg:grid-cols-[320px_minmax(0,1fr)]">
          <Card title={`People (${people.length})`}>
            <label className="mb-3 flex items-center gap-2 rounded-lg border border-ink-600 bg-ink-800 px-2.5 py-1.5">
              <Search className="h-4 w-4 text-fog-500" />
              <input aria-label="Search people" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search" className="w-full bg-transparent text-sm outline-none" />
            </label>
            {shown.length === 0 ? (
              <Empty title={people.length ? 'No matches' : 'Nobody enrolled'}>{people.length ? '' : 'Enrol a consenting person to start.'}</Empty>
            ) : (
              <ul className="space-y-1">
                {shown.map((p) => (
                  <li key={p.id}>
                    <button onClick={() => open(p.id)} className={`flex w-full items-center justify-between gap-2 rounded-lg px-2.5 py-2 text-left text-sm hover:bg-ink-800 ${selected?.id === p.id ? 'bg-ink-800' : ''}`}>
                      <span className="truncate">{p.name}</span>
                      <Badge tone={p.template_count ? 'ok' : 'warn'}>{p.template_count} photos</Badge>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </Card>
          {selected ? (
            <PersonDetail key={selected.id} person={selected} onChange={async () => { await load(); await open(selected.id); }} onDeleted={() => { setSelected(null); load(); }} />
          ) : (
            <Empty title="Select a person">Choose someone on the left, or enrol a new person.</Empty>
          )}
        </div>
      )}
      <CreatePerson open={creating} onClose={() => setCreating(false)} onCreated={async (p) => { setCreating(false); await load(); open(p.id); }} />
    </div>
  );
}

function CreatePerson({ open, onClose, onCreated }: { open: boolean; onClose: () => void; onCreated: (p: Person) => void }) {
  const [name, setName] = useState('');
  const [ext, setExt] = useState('');
  const [note, setNote] = useState('');
  const [consent, setConsent] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const submit = async () => {
    setBusy(true);
    setErr(null);
    try {
      const p = await api.json<Person>('/api/persons', { name, external_id: ext, consent_confirmed: consent, consent_note: note });
      setName(''); setExt(''); setNote(''); setConsent(false);
      onCreated(p);
    } catch (e) {
      setErr(errorText(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <Modal open={open} title="Enrol a person" onClose={onClose} footer={<><Button onClick={onClose}>Cancel</Button><Button variant="primary" busy={busy} disabled={!consent || !name.trim()} onClick={submit}>Create and add photos</Button></>}>
      <TextInput label="Name or identifier" value={name} onChange={setName} />
      <TextInput label="Reference (optional)" value={ext} onChange={setExt} placeholder="e.g. staff number" />
      <TextInput label="How consent was given (optional)" value={note} onChange={setNote} placeholder="e.g. signed form, 23 Oct 2026" />
      <label className="flex gap-3 rounded-lg border border-ink-600 bg-ink-800 p-3">
        <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} className="mt-1 accent-[#33b6c9]" />
        <span className="text-sm text-fog-100">{CONSENT_TEXT}</span>
      </label>
      {err && <Alert tone="bad">{err}</Alert>}
    </Modal>
  );
}

function PersonDetail({ person, onChange, onDeleted }: { person: Person; onChange: () => void; onDeleted: () => void }) {
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<EnrolResult | null>(null);
  const [allowLow, setAllowLow] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [name, setName] = useState(person.name);

  const upload = async (files: File[]) => {
    setBusy(true);
    setErr(null);
    try {
      setResult(await api.form<EnrolResult>(`/api/persons/${person.id}/templates`, { files, allow_low_quality: allowLow ? 'true' : 'false' }));
      onChange();
    } catch (e) {
      setErr(errorText(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-4">
      <Card title="Person" actions={<Button variant="danger" icon={<Trash2 className="h-4 w-4" />} onClick={() => setConfirmDelete(true)}>Delete permanently</Button>}>
        <div className="grid gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <TextInput label="Name" value={name} onChange={setName} />
            <Button disabled={name === person.name || !name.trim()} onClick={() => api.json(`/api/persons/${person.id}`, { name }, 'PATCH').then(onChange).catch((e) => setErr(errorText(e)))}>Save name</Button>
          </div>
          <div>
            <KV k="Consent recorded" v={fmtTime(person.consent_at)} />
            {person.consent_note && <KV k="Consent note" v={person.consent_note} />}
            {person.external_id && <KV k="Reference" v={person.external_id} />}
            <KV k="Enrolled" v={fmtTime(person.created_at)} />
          </div>
        </div>
      </Card>

      <Card title={`Face templates (${person.templates?.length ?? 0})`}>
        {person.templates?.length ? (
          <table className="w-full text-sm">
            <thead className="text-left text-[11px] uppercase tracking-wider text-fog-500"><tr><th className="pb-2">#</th><th className="pb-2">Model</th><th className="pb-2">Quality</th><th className="pb-2">Added</th><th /></tr></thead>
            <tbody>
              {person.templates.map((t) => (
                <tr key={t.id} className="border-t border-ink-800">
                  <td className="py-1.5 font-mono text-xs">{t.id}</td>
                  <td className="py-1.5">{t.model_id}</td>
                  <td className="py-1.5">{fmtPct(t.quality)}</td>
                  <td className="py-1.5 text-xs text-fog-400">{fmtTime(t.created_at)}</td>
                  <td className="py-1.5 text-right">
                    <Button variant="ghost" aria-label="Delete template" icon={<Trash2 className="h-4 w-4" />} onClick={() => api.del(`/api/persons/${person.id}/templates/${t.id}`).then(onChange).catch((e) => setErr(errorText(e)))} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <Empty title="No templates yet">Add 3–5 clear, front-facing photos with only this person in them.</Empty>
        )}
        <p className="mt-3 text-xs text-fog-500">Templates are tied to the recognizer that made them. If you switch recognizer in Settings, add photos again.</p>
      </Card>

      <Card title="Add photos">
        <div className="grid gap-4 lg:grid-cols-2">
          <div className="space-y-3">
            <FileDrop accept="image/jpeg,image/png,image/webp" multiple onFiles={upload} label="Upload photos" hint="Up to 20 at a time. One face per photo." />
            <label className="flex items-center gap-2 text-xs text-fog-400">
              <input type="checkbox" checked={allowLow} onChange={(e) => setAllowLow(e.target.checked)} className="accent-[#33b6c9]" />
              Keep photos that fail the quality checks (not recommended)
            </label>
          </div>
          <CapturePhotos onDone={upload} />
        </div>
        {busy && <p className="mt-3 text-sm text-fog-400">Processing…</p>}
        {err && <div className="mt-3"><Alert tone="bad">{err}</Alert></div>}
        {result && (
          <div className="mt-4 space-y-2">
            <div className="text-sm text-fog-300">{result.added} of {result.results.length} photos added ({result.model}).</div>
            <ul className="grid gap-2 sm:grid-cols-2">
              {result.results.map((r, i) => (
                <li key={i} className="flex gap-3 rounded-lg border border-ink-700 p-2">
                  {r.crop ? <img src={r.crop} alt="" className="h-14 w-14 rounded object-cover" /> : <div className="h-14 w-14 rounded bg-ink-800" />}
                  <div className="min-w-0 text-xs">
                    <div className="truncate text-fog-100">{r.file}</div>
                    {r.added ? <Badge tone="ok">added</Badge> : <Badge tone="warn">skipped</Badge>}
                    {r.reason && <div className="mt-1 text-fog-400">{r.reason}</div>}
                    {r.warnings?.map((w, j) => <div key={j} className="mt-1 flex gap-1 text-warn"><AlertTriangle className="h-3 w-3 shrink-0" /> {w}</div>)}
                  </div>
                </li>
              ))}
            </ul>
          </div>
        )}
      </Card>

      <Modal
        open={confirmDelete}
        title={`Delete ${person.name}?`}
        onClose={() => setConfirmDelete(false)}
        footer={<><Button onClick={() => setConfirmDelete(false)}>Keep</Button><Button variant="danger" onClick={() => api.del(`/api/persons/${person.id}`).then(onDeleted).catch((e) => setErr(errorText(e)))}>Delete permanently</Button></>}
      >
        <p>This removes the person and all {person.templates?.length ?? 0} face templates from this computer. It cannot be undone. Backups you made earlier still contain them.</p>
      </Modal>
    </div>
  );
}
