# Security policy

## Reporting a vulnerability

Please report security problems privately through GitHub: **Security → Report a vulnerability** on this repository. Do not open a public issue for anything that could expose biometric data. You should get a reply within a week.

## Security model

FaceVision AI is a single-user application that runs on your own computer.

**Network exposure**
- The server binds to `127.0.0.1` and refuses to start on another address unless `FV_ALLOW_REMOTE=1` is set.
- Requests whose `Host` header is not `localhost`, `127.0.0.1`, `[::1]` or listed in `FV_ALLOWED_HOSTS` are rejected, which blocks DNS-rebinding attacks.
- State-changing requests and WebSockets from another origin are rejected, which blocks cross-site request forgery from web pages you visit.
- Responses carry a strict Content-Security-Policy, `X-Frame-Options: DENY`, `nosniff` and `no-referrer`.

**Access control**
- Biometric endpoints (people, templates, recognition, verification, exports, audit log) need a signed-in session or an API key.
- The passphrase is stored as a scrypt hash (N=2^15, r=8, p=1). Sessions are random tokens in an HttpOnly, SameSite=Strict cookie and expire after 12 hours of inactivity.
- Sign-in attempts are rate-limited (10 per minute per client).

**Template encryption**
- Templates are encrypted with AES-256-GCM, bound to the person and model through associated data.
- The data key is stored only in wrapped form: once under a key derived from the passphrase (scrypt), once under a key derived from the API key (HKDF). It is unlocked into memory on sign-in.
- A copy of the database alone does not reveal templates. While FaceVision AI is running and unlocked, the key is in memory; someone with control of your user account at that moment can read it.

**Inputs**
- Upload size, pixel count, file type and batch size limits. Images are decoded with OpenCV; malformed files are rejected.
- Job output downloads are restricted to files the job produced.

## Exposing FaceVision AI on a network

Only do this on a network you trust, and understand that video frames then travel over the network unencrypted unless you add HTTPS.

```
FV_HOST=0.0.0.0
FV_ALLOW_REMOTE=1
FV_ALLOWED_HOSTS=mypc.local,192.168.1.20
```

Put it behind a reverse proxy with HTTPS (browsers also only allow cameras on HTTPS pages for non-localhost addresses). Never forward the port to the internet.

## Supply chain

- Python dependencies are pinned in `requirements.lock`; JavaScript dependencies in `frontend/package-lock.json`.
- Model files are pinned by SHA-256 and verified on every download.
- CI scans each commit for committed secrets and checks dependency licences.
