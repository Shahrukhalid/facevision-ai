import {
  Activity, Boxes, Camera, FileBarChart, FileImage, Film, GalleryHorizontalEnd, Gauge, GitCompare, HelpCircle, Layers,
  Lock, LockOpen, Menu, ScanFace, Settings as SettingsIcon, ShieldCheck, Users, Waypoints, X, EyeOff,
} from 'lucide-react';
import { useState, type ReactNode } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import { useApp } from '../lib/store';
import { Badge, cx } from './ui';

export const NAV: { group: string; items: { to: string; label: string; icon: typeof Camera }[] }[] = [
  { group: 'Overview', items: [{ to: '/', label: 'Dashboard', icon: Gauge }] },
  {
    group: 'Live',
    items: [
      { to: '/live', label: 'Live Face Detection', icon: Camera },
      { to: '/analysis', label: 'Facial Analysis', icon: ScanFace },
      { to: '/recognition', label: 'Face Recognition', icon: ShieldCheck },
      { to: '/tracking', label: 'Face Tracking', icon: Waypoints },
      { to: '/liveness', label: 'Liveness Verification', icon: Activity },
    ],
  },
  {
    group: 'People',
    items: [
      { to: '/enrolled', label: 'Enrolled Faces', icon: Users },
      { to: '/compare', label: 'Face Comparison', icon: GitCompare },
    ],
  },
  {
    group: 'Files',
    items: [
      { to: '/image', label: 'Image Analyzer', icon: FileImage },
      { to: '/video', label: 'Video Analyzer', icon: Film },
      { to: '/batch', label: 'Batch Processing', icon: GalleryHorizontalEnd },
      { to: '/privacy', label: 'Privacy / Face Blur', icon: EyeOff },
      { to: '/reports', label: 'Reports & Export', icon: FileBarChart },
    ],
  },
  {
    group: 'System',
    items: [
      { to: '/models', label: 'Model Manager', icon: Boxes },
      { to: '/settings', label: 'Settings', icon: SettingsIcon },
      { to: '/help', label: 'Help & Documentation', icon: HelpCircle },
    ],
  },
];

export default function Layout({ children }: { children: ReactNode }) {
  const { auth, live, backendOnline, system } = useApp();
  const [open, setOpen] = useState(false);
  const loc = useLocation();
  const nav = (
    <nav className="flex flex-col gap-5 px-3 py-4" aria-label="Main">
      {NAV.map((g) => (
        <div key={g.group}>
          <div className="px-2 pb-1.5 text-[10px] font-semibold uppercase tracking-[0.14em] text-fog-500">{g.group}</div>
          <ul className="space-y-0.5">
            {g.items.map(({ to, label, icon: Icon }) => (
              <li key={to}>
                <NavLink
                  to={to}
                  end={to === '/'}
                  onClick={() => setOpen(false)}
                  className={({ isActive }) =>
                    cx(
                      'flex items-center gap-2.5 rounded-lg px-2 py-1.5 text-sm transition',
                      isActive ? 'bg-lens-500/10 text-lens-300' : 'text-fog-300 hover:bg-ink-800 hover:text-fog-100',
                    )
                  }
                >
                  <Icon className="h-4 w-4 shrink-0" />
                  <span className="truncate">{label}</span>
                </NavLink>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </nav>
  );

  return (
    <div className="flex min-h-screen bg-ink-950 text-fog-100">
      <aside className="sticky top-0 hidden h-screen w-60 shrink-0 overflow-y-auto border-r border-ink-800 bg-ink-900 lg:block">
        <Brand />
        {nav}
      </aside>
      {open && (
        <div className="fixed inset-0 z-40 bg-black/60 lg:hidden" onClick={() => setOpen(false)}>
          <aside className="h-full w-64 overflow-y-auto bg-ink-900" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between pr-3">
              <Brand />
              <button onClick={() => setOpen(false)} aria-label="Close menu" className="text-fog-400"><X className="h-5 w-5" /></button>
            </div>
            {nav}
          </aside>
        </div>
      )}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex items-center gap-3 border-b border-ink-800 bg-ink-950/90 px-4 py-2.5 backdrop-blur sm:px-6">
          <button className="text-fog-300 lg:hidden" onClick={() => setOpen(true)} aria-label="Open menu"><Menu className="h-5 w-5" /></button>
          <div className="flex min-w-0 flex-1 flex-wrap items-center gap-2 text-xs">
            {backendOnline ? <Badge tone="ok">Engine running</Badge> : <Badge tone="bad">Engine offline</Badge>}
            {live.running && <Badge tone="bad"><span className="h-1.5 w-1.5 animate-pulse rounded-full bg-bad" /> Camera on</Badge>}
            {system && (
              <Badge tone="neutral" title="Bound address">
                <Layers className="h-3 w-3" /> {system.binding.host}:{system.binding.port}
              </Badge>
            )}
          </div>
          <NavLink to="/settings#access" className="flex items-center gap-1.5 rounded-lg px-2 py-1 text-xs text-fog-300 hover:bg-ink-800">
            {auth.signed_in ? <LockOpen className="h-3.5 w-3.5 text-ok" /> : <Lock className="h-3.5 w-3.5" />}
            {auth.signed_in ? 'Signed in' : auth.configured ? 'Sign in' : 'Set up access'}
          </NavLink>
        </header>
        <main key={loc.pathname} className="mx-auto w-full max-w-[1500px] flex-1 px-4 py-6 sm:px-6">{children}</main>
      </div>
    </div>
  );
}

function Brand() {
  return (
    <div className="flex items-center gap-2.5 px-5 pb-1 pt-5">
      <svg viewBox="0 0 32 32" className="h-7 w-7" aria-hidden>
        <rect width="32" height="32" rx="7" fill="#19202a" />
        <path d="M7 11V8a1 1 0 0 1 1-1h3M21 7h3a1 1 0 0 1 1 1v3M25 21v3a1 1 0 0 1-1 1h-3M11 25H8a1 1 0 0 1-1-1v-3" stroke="#5fd0e0" strokeWidth="2" fill="none" strokeLinecap="round" />
        <circle cx="16" cy="16" r="4.5" fill="none" stroke="#e8edf3" strokeWidth="2" />
      </svg>
      <div>
        <div className="font-display text-[15px] font-semibold leading-tight">FaceVision AI</div>
        <div className="text-[10px] uppercase tracking-[0.16em] text-fog-500">Local · consent-based</div>
      </div>
    </div>
  );
}
