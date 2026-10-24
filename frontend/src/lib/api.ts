// Thin client for the local FaceVision AI API. All requests are same-origin; the session cookie is HttpOnly.

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function handle<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let msg = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (body?.detail) msg = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* not JSON */
    }
    throw new ApiError(res.status, msg);
  }
  const type = res.headers.get('content-type') || '';
  return (type.includes('application/json') ? res.json() : (res.blob() as unknown)) as Promise<T>;
}

export const api = {
  get: <T>(url: string) => fetch(url, { credentials: 'same-origin' }).then((r) => handle<T>(r)),
  del: <T>(url: string) => fetch(url, { method: 'DELETE', credentials: 'same-origin' }).then((r) => handle<T>(r)),
  json: <T>(url: string, body: unknown, method = 'POST') =>
    fetch(url, {
      method,
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body ?? {}),
    }).then((r) => handle<T>(r)),
  form: <T>(url: string, fields: Record<string, string | Blob | Blob[] | undefined | null>) => {
    const fd = new FormData();
    for (const [k, v] of Object.entries(fields)) {
      if (v === undefined || v === null) continue;
      if (Array.isArray(v)) v.forEach((b) => fd.append(k, b, (b as File).name || 'file'));
      else if (v instanceof Blob) fd.append(k, v, (v as File).name || 'file');
      else fd.append(k, v);
    }
    return fetch(url, { method: 'POST', credentials: 'same-origin', body: fd }).then((r) => handle<T>(r));
  },
  formRaw: (url: string, fields: Record<string, string | Blob>) => {
    const fd = new FormData();
    for (const [k, v] of Object.entries(fields)) {
      if (v instanceof Blob) fd.append(k, v, (v as File).name || 'file');
      else fd.append(k, v);
    }
    return fetch(url, { method: 'POST', credentials: 'same-origin', body: fd });
  },
};

export function wsUrl(path: string) {
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${proto}//${location.host}${path}`;
}

export function errorText(e: unknown) {
  if (e instanceof ApiError) return e.message;
  if (e instanceof Error) return e.message;
  return String(e);
}
