# Privacy

FaceVision AI processes biometric data, so its defaults keep that data on your computer, collect as little as possible and make deletion easy.

## What is stored, and where

All data lives in one folder (shown under Reports & Export):

| OS | Default data folder |
| --- | --- |
| macOS | `~/Library/Application Support/FaceVision AI` |
| Windows | `%LOCALAPPDATA%\FaceVision AI` |
| Linux | `~/.local/share/facevision-ai` |

Set `FV_DATA_DIR` to use another folder.

| Data | Stored? | How |
| --- | --- | --- |
| Live camera frames | No | Processed in memory and discarded |
| Screenshots and recordings | Only when you press the button | Saved by your browser to your downloads folder |
| Enrolment photos | No | Converted to a template, then discarded |
| Face templates | Yes, for enrolled people | AES-256-GCM encrypted in `facevision.db`; key unlocked by passphrase or API key |
| Name, reference, consent note and date | Yes, for enrolled people | `facevision.db` |
| Uploaded photos for analysis | No | Processed in memory |
| Uploaded videos and batch files | Temporarily | Deleted when the job ends |
| Job outputs (annotated media, reports) | Yes | `outputs/`, deleted after the retention period (default 7 days) |
| Individual recognitions | No | Not logged, so no movement history builds up |
| Audit log | Yes | Administrative actions only (enrolment, deletion, sign-in, settings) |

## Consent

Enrolment requires ticking a consent statement and records when it was confirmed, with an optional note on how consent was given (for example a signed form). Only enrol people who understand what enrolment means and how to have it removed.

## Network

- No telemetry or analytics. ONNX Runtime contains a telemetry client; FaceVision AI disables it with `ORT_DISABLE_TELEMETRY=1` before the library loads, and `tests/test_privacy.py` fails if analysis attempts any network connection.
- The only outbound connections are model downloads you start in the Model Manager, from the URLs listed in [MODELS.md](MODELS.md).
- The web app loads no third-party scripts, fonts or images; everything is bundled.

## Deleting data

- **One person**: Enrolled Faces → Delete permanently. Their templates are removed and the database is compacted so the deleted bytes do not linger in the file.
- **All enrolled faces**: Reports & Export → Delete all enrolled faces.
- **Everything**: Reports & Export → Delete everything (keeps downloaded models).
- **Processing files**: Privacy / Face Blur → Delete processing files now, or set the retention period in Settings.
- **Backups** you downloaded are separate files. Delete them yourself.

## Exports

- *Export data* gives a JSON file with settings, people's names and consent records, job list and audit log. It contains no face templates.
- *Back up database* gives a copy of the database with templates still encrypted. It can only be used with the passphrase that was active when it was made.

## Legal

Biometric data is specially protected in many places, including the EU and UK (GDPR, special category data), Illinois (BIPA), Texas and Washington. You are responsible for having a lawful basis, informing people, and honouring deletion requests. This document is not legal advice.
