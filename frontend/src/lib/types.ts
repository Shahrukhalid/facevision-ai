export type Box = [number, number, number, number];

export interface Recognition {
  status: 'match' | 'unknown' | 'ambiguous' | 'low_quality' | 'locked' | 'no_gallery';
  name?: string;
  person_id?: number;
  similarity?: number | null;
  threshold?: number;
  model?: string;
  note?: string;
  candidates?: { person_id: number; name: string; similarity: number }[];
  cached?: boolean;
}

export interface HeadPose {
  yaw: number;
  pitch: number;
  roll: number;
  axes: [number, number][] | null;
  method: string;
}

export interface QualityCheck {
  value: unknown;
  ok: boolean;
  detail: string;
}

export interface Analysis {
  head_pose?: HeadPose;
  direction?: string;
  eyes?: {
    left_closed_score: number;
    right_closed_score: number;
    left_open: boolean;
    right_open: boolean;
    both_closed: boolean;
    ear_image_left: number;
    ear_image_right: number;
    blink_count: number;
  };
  mouth?: { open: boolean; jaw_open_score: number; mouth_aspect_ratio: number; center: [number, number] };
  smile?: { smiling: boolean; score: number };
  expression?: { label: string; probability: number; uncertain: boolean; probabilities: Record<string, number>; note: string };
  age?: {
    estimate?: number;
    range?: [number, number | null];
    source?: string;
    note?: string;
    clip_bracket?: { top: string; probability: number; distribution: Record<string, number>; experimental: boolean };
  };
  appearance?: { model_label: string; probability: number; note: string };
  attributes?: { probabilities: Record<string, number>; model: string; experimental: boolean };
  quality?: { score: number; suitable_for_matching: boolean; failed: string[]; checks: Record<string, QualityCheck> };
  occlusion?: { likely: boolean; reasons: string[] };
  symmetry?: { mean_deviation_pct: number; score: number };
  proportions?: { height_to_width?: number; jaw_to_cheek?: number; forehead_to_cheek?: number; outline?: string; note?: string };
  antispoof?: { real_score: number; label: string; class_probabilities: number[] };
  landmark_count?: number;
  unavailable?: Record<string, string>;
}

export interface Face {
  index: number;
  box: Box;
  smooth_box?: Box;
  score: number;
  low_confidence?: boolean;
  truncated?: boolean;
  keypoints: [number, number][];
  track_id?: number;
  track_confirmed?: boolean;
  landmarks?: { indices: 'basic' | 'all'; points: [number, number][] };
  analysis?: Analysis;
  recognition?: Recognition;
  crop?: string;
}

export interface FrameResult {
  type?: string;
  frame?: number;
  image: { width: number; height: number };
  face_count: number;
  faces: Face[];
  events?: { type: 'enter' | 'exit'; track_id: number; t: number; duration?: number }[];
  tracking?: { active_tracks: number; created: number; expired: number; frames: number } | null;
  processing_fps?: number;
  latency_ms?: number;
  timings_ms: Record<string, number>;
  liveness?: LivenessState;
  annotated_image?: string;
  options?: AnalysisOptions;
}

export interface AnalysisOptions {
  preset: 'fast' | 'balanced' | 'detailed';
  detection: boolean;
  score_threshold: number;
  max_side: number;
  tracking: boolean;
  landmarks: boolean;
  overlay: 'none' | 'basic' | 'detailed' | 'mesh';
  quality: boolean;
  expression: boolean;
  recognition: boolean;
  age: boolean;
  appearance: boolean;
  attributes: boolean;
  antispoof: boolean;
}

export interface ModelInfo {
  id: string;
  name: string;
  task: string;
  version: string;
  license: string;
  license_url: string;
  commercial_use: boolean;
  research_only: boolean;
  source: string;
  description: string;
  evaluation: string;
  default: boolean;
  required: boolean;
  installed: boolean;
  enabled: boolean;
  license_accepted: boolean;
  download_size: number;
  files: { name: string; sha256: string; size: number; urls: string[] }[];
  download: { status: string; bytes_done: number; bytes_total: number; message: string };
}

export interface SystemInfo {
  version: string;
  platform: { system: string; release: string; machine: string; python: string };
  cpu: { percent: number; count: number; process_percent: number };
  memory: { total: number; available: number; percent: number; process_rss: number };
  hardware: {
    machine: string;
    system: string;
    onnxruntime: string;
    providers: string[];
    accelerators: { coreml: boolean; directml: boolean; cuda: boolean };
    preference: string;
  };
  libraries: Record<string, string | null>;
  models: { loaded: Record<string, { provider: string; load_ms: number }>; errors: Record<string, string> };
  disk: Record<string, number>;
  auth: { configured: boolean; signed_in: boolean };
  binding: { host: string; port: number };
  offline_mode: boolean;
}

export interface Settings {
  preset: string;
  detection_threshold: number;
  recognizer: string;
  recognition_thresholds: Record<string, number>;
  show_candidates: boolean;
  age_band_years: number;
  allow_appearance: boolean;
  keep_job_outputs_days: number;
  accelerator: 'auto' | 'cpu';
  max_faces_live: number;
}

export interface Person {
  id: number;
  name: string;
  external_id?: string;
  notes?: string;
  consent_confirmed: number;
  consent_note?: string;
  consent_at: string;
  created_at: string;
  updated_at: string;
  template_count?: number;
  models?: string[];
  templates?: { id: number; model_id: string; quality: number; source: string; created_at: string }[];
}

export interface Job {
  id: string;
  kind: 'video' | 'batch';
  status: 'queued' | 'running' | 'done' | 'failed' | 'cancelled';
  progress: number;
  message?: string;
  options?: Record<string, unknown> & { inputs?: string[] };
  result?: any;
  error?: string;
  outputs?: Record<string, string> | null;
  created_at: string;
  updated_at: string;
}

export interface LivenessState {
  session_id: string;
  state: 'running' | 'passed' | 'failed';
  reason: string;
  steps: { id: string; prompt: string; done: boolean }[];
  current: { id: string; prompt: string } | null;
  seconds_left: number;
  passive_real_score: number | null;
  frames: number;
}
