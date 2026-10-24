import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { api } from './api';
import type { ModelInfo, Settings, SystemInfo } from './types';

export interface LiveStats {
  running: boolean;
  fps: number;
  processingFps: number;
  latency: number;
  faces: number;
  recognized: number;
  updated: number;
  page?: string;
}

export interface MeshTopology {
  basic_indices: number[];
  groups: Record<string, [number, number][]>;
  tesselation: [number, number][];
}

interface Ctx {
  system: SystemInfo | null;
  cpuHistory: number[];
  settings: Settings | null;
  models: ModelInfo[];
  auth: { configured: boolean; signed_in: boolean };
  topology: MeshTopology | null;
  live: LiveStats;
  setLive: (s: Partial<LiveStats>) => void;
  refreshSystem: () => Promise<void>;
  refreshSettings: () => Promise<void>;
  refreshModels: () => Promise<void>;
  refreshAuth: () => Promise<void>;
  saveSettings: (s: Partial<Settings>) => Promise<Settings>;
  modelReady: (id: string) => boolean;
  backendOnline: boolean;
}

const AppCtx = createContext<Ctx | null>(null);

export function AppProvider({ children }: { children: ReactNode }) {
  const [system, setSystem] = useState<SystemInfo | null>(null);
  const [cpuHistory, setCpuHistory] = useState<number[]>([]);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [auth, setAuth] = useState({ configured: false, signed_in: false });
  const [topology, setTopology] = useState<MeshTopology | null>(null);
  const [backendOnline, setOnline] = useState(true);
  const [live, setLiveState] = useState<LiveStats>({ running: false, fps: 0, processingFps: 0, latency: 0, faces: 0, recognized: 0, updated: 0 });
  const liveRef = useRef(live);

  const refreshSystem = useCallback(async () => {
    try {
      const s = await api.get<SystemInfo>('/api/system');
      setSystem(s);
      setAuth(s.auth);
      setCpuHistory((h) => [...h.slice(-59), s.cpu.percent]);
      setOnline(true);
    } catch {
      setOnline(false);
    }
  }, []);
  const refreshSettings = useCallback(async () => setSettings(await api.get<Settings>('/api/settings')), []);
  const refreshModels = useCallback(async () => setModels(await api.get<ModelInfo[]>('/api/models')), []);
  const refreshAuth = useCallback(async () => setAuth(await api.get('/api/auth/status')), []);
  const saveSettings = useCallback(async (s: Partial<Settings>) => {
    const next = await api.json<Settings>('/api/settings', s, 'PUT');
    setSettings(next);
    return next;
  }, []);
  const setLive = useCallback((s: Partial<LiveStats>) => {
    liveRef.current = { ...liveRef.current, ...s, updated: Date.now() };
    setLiveState(liveRef.current);
  }, []);

  useEffect(() => {
    refreshSystem();
    refreshSettings().catch(() => undefined);
    refreshModels().catch(() => undefined);
    api.get<MeshTopology>('/api/mesh/topology').then(setTopology).catch(() => undefined);
    const t = setInterval(refreshSystem, 3000);
    return () => clearInterval(t);
  }, [refreshSystem, refreshSettings, refreshModels]);

  const modelReady = useCallback((id: string) => !!models.find((m) => m.id === id && m.installed && m.enabled), [models]);

  const value = useMemo(
    () => ({ system, cpuHistory, settings, models, auth, topology, live, setLive, refreshSystem, refreshSettings, refreshModels, refreshAuth, saveSettings, modelReady, backendOnline }),
    [system, cpuHistory, settings, models, auth, topology, live, setLive, refreshSystem, refreshSettings, refreshModels, refreshAuth, saveSettings, modelReady, backendOnline],
  );
  return <AppCtx.Provider value={value}>{children}</AppCtx.Provider>;
}

export function useApp() {
  const c = useContext(AppCtx);
  if (!c) throw new Error('useApp outside provider');
  return c;
}
