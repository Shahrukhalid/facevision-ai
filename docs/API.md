# API reference

The server exposes a REST API and two WebSockets on `http://localhost:8600` (`FV_PORT` changes the port). The interactive OpenAPI documentation is at **`/api/docs`** (Swagger) and `/api/redoc`; the schema is at `/api/openapi.json`.

## Authentication

| Endpoint group | Needs |
| --- | --- |
| Health, system, models (read), detection, analysis, landmarks, comparison, anonymisation, liveness, jobs | Nothing |
| People, enrolment, recognition, verification, data export/backup/deletion, audit log, API keys | A signed-in session cookie **or** an API key |
| Settings and model changes | Nothing until a passphrase exists, then a session or API key |

Send the API key as `X-API-Key: fv_...` or `Authorization: Bearer fv_...`. Create it in Settings (it is shown once) or when setting the passphrase.

## Limits and safety

- Images: JPG, PNG, WebP, BMP, up to `FV_MAX_IMAGE_MB` (20 MB) and 50 megapixels.
- Videos: MP4, MOV, M4V, AVI, MKV, WebM, up to `FV_MAX_VIDEO_MB` (1 GB).
- Batches: up to `FV_MAX_BATCH_FILES` (200) files.
- Rate limits per client: sign-in 10/min, inference 600/min, jobs 30/min. Excess requests get HTTP 429.
- The server answers only for `localhost`/`127.0.0.1` (and hosts in `FV_ALLOWED_HOSTS`), and rejects state-changing or WebSocket requests from other origins with HTTP 403.

Errors are JSON: `{"detail": "message"}`.

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/health` | Liveness probe and version |
| GET | `/api/system` | CPU, memory, hardware acceleration, loaded models, disk use |
| GET | `/api/models` | Model registry with install state, licences and download progress |
| POST | `/api/models/{id}/install` | Download and verify (`{"accept_license": true}` for research models) |
| POST | `/api/models/{id}/cancel` · `/verify` · `/enable` | Cancel a download, re-check SHA-256, turn on/off (`{"enabled": bool}`) |
| DELETE | `/api/models/{id}` | Remove a model's files |
| POST | `/api/models/warmup` | Load and time every active model |
| GET | `/api/mesh/topology` | Landmark index groups and mesh triangulation for drawing |
| GET / PUT | `/api/settings` | Read or change settings |
| POST | `/api/detect` | Faces, boxes, scores, 5 key points (`crops=true` adds thumbnails) |
| POST | `/api/analyze` | Full analysis; `options` is a JSON object (see below); `annotate_image=true` returns an annotated JPEG |
| POST | `/api/landmarks` | 478-point landmarks and head pose for each face |
| POST | `/api/compare` | `file_a`, `file_b`, optional `face_a`/`face_b`/`threshold` |
| POST | `/api/anonymize` | `method` blur/pixelate/solid, `strength` 0–1, `faces` all/none/`0,2`; returns the image |
| POST | `/api/liveness/sessions` | Start an active liveness challenge |
| POST | `/api/liveness/sessions/{id}/frame` | Submit one frame; returns progress |
| POST | `/api/liveness/passive` | Passive anti-spoofing score for each face |
| POST | `/api/jobs/video` · `/api/jobs/batch` | Start a background job; `options` JSON |
| GET | `/api/jobs` · `/api/jobs/{id}` | List jobs, poll one |
| POST | `/api/jobs/{id}/cancel` | Cancel |
| DELETE | `/api/jobs/{id}` | Delete a finished job and its files |
| GET | `/api/jobs/{id}/files/{name}` | Download an output (`report.json`, `report.csv`, `summary.txt`, `annotated.webm`, `outputs.zip`) |
| GET | `/api/auth/status` | Whether a passphrase exists and whether you are signed in |
| POST | `/api/auth/setup` · `/login` · `/logout` | Passphrase setup (returns the first API key), sign in, sign out |
| POST | `/api/auth/change-passphrase` · `/api-key/rotate` · `/reset` | Manage credentials; reset deletes all enrolled faces |
| GET / POST | `/api/persons` | List people, enrol one (`consent_confirmed` must be true) |
| GET / PATCH / DELETE | `/api/persons/{id}` | Read, rename, delete permanently |
| POST | `/api/persons/{id}/templates` | Add photos (`files[]`); returns per-photo quality, duplicates and consistency warnings |
| DELETE | `/api/persons/{id}/templates/{tid}` | Delete one template |
| POST | `/api/enroll` | Create a person and add photos in one call |
| POST | `/api/recognize` | 1:N against enrolled people |
| POST | `/api/verify` | 1:1 against one enrolled person (`person_id`) |
| GET | `/api/data/summary` | Counts and disk use |
| POST | `/api/data/clear-cache` | Delete job outputs and temporary files |
| GET | `/api/data/export` · `/api/data/backup` | Metadata JSON / encrypted database backup |
| POST | `/api/data/delete-biometrics` · `/api/data/delete-all` | Confirmed deletions |
| GET | `/api/audit` | Administrative audit log |

### Analysis options

```json
{
  "preset": "fast | balanced | detailed",
  "detection": true, "score_threshold": 0.6, "max_side": 640,
  "tracking": true, "landmarks": true, "overlay": "none | basic | detailed | mesh",
  "quality": true, "expression": true, "recognition": false,
  "age": false, "appearance": false, "attributes": false, "antispoof": false
}
```

A preset sets sensible defaults; any field you send overrides it. `appearance` also needs the setting `allow_appearance`.

### Recognition result

```json
{"status": "match", "name": "…", "person_id": 3, "similarity": 0.71, "threshold": 0.363,
 "candidates": [{"person_id": 3, "name": "…", "similarity": 0.71}], "model": "sface"}
```

`status` is `match`, `unknown`, `ambiguous` (two people within 0.05 above the threshold), `low_quality` (would match, but quality checks failed), `no_gallery` or `locked` (not signed in). A name is included only for `match`.

## WebSocket: `/ws/live`

1. Connect (the session cookie is sent automatically by the browser; recognition needs it).
2. Send `{"type": "options", "options": {...}, "liveness_session": null}`.
3. Send a JPEG frame as a binary message.
4. Receive one JSON result per frame: faces with `track_id`, `events` (enter/exit), `processing_fps`, `latency_ms`, `timings_ms`.
5. Send the next frame after the result arrives. Optionally send `{"type":"options", ..., "reset_tracking": true}`.

## WebSocket: `/ws/source` (experimental)

Send `{"type": "start", "source": "0"}` for a camera opened by the server, or an `rtsp://` / `http(s)://` URL. The server streams a JSON result followed by a binary JPEG for each frame. Send `{"type": "stop"}` to end. Needs sign-in once a passphrase exists.

## Examples

```bash
curl -F file=@group.jpg -F crops=true http://localhost:8600/api/detect

curl -F file=@photo.jpg -F 'options={"preset":"detailed","antispoof":true}' -F annotate_image=true \
     http://localhost:8600/api/analyze

curl -F file_a=@a.jpg -F file_b=@b.jpg http://localhost:8600/api/compare

curl -F file=@crowd.jpg -F method=blur -F strength=0.8 -o crowd-blurred.jpg http://localhost:8600/api/anonymize

curl -H "X-API-Key: $FV_KEY" -F name="Volunteer" -F consent_confirmed=true \
     -F files=@1.jpg -F files=@2.jpg -F files=@3.jpg http://localhost:8600/api/enroll

curl -H "X-API-Key: $FV_KEY" -F file=@query.jpg http://localhost:8600/api/recognize

curl -F file=@clip.mp4 -F 'options={"analysis":{"preset":"fast"},"sample_every":2}' http://localhost:8600/api/jobs/video
```

Python:

```python
import requests
r = requests.post("http://localhost:8600/api/analyze", files={"file": open("photo.jpg", "rb")},
                  data={"options": '{"preset": "balanced"}'})
for face in r.json()["faces"]:
    print(face["box"], face["analysis"]["head_pose"], face["analysis"].get("expression", {}).get("label"))
```
