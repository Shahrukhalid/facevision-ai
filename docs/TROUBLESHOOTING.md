# Troubleshooting

Run the built-in check first. It prints versions, hardware acceleration, model status and warm-up timings:

```bash
.venv/bin/python -m facevision doctor          # macOS / Linux
.\.venv\Scripts\python.exe -m facevision doctor  # Windows
```

## Setup

| Problem | Fix |
| --- | --- |
| `Python 3.10-3.13 is required` | Install Python 3.12 (see the install guides). Python 3.14 is not supported yet because some dependencies have no wheels for it. |
| `pip` fails building a package | Upgrade pip (`python -m pip install -U pip`) and make sure you are on a 64-bit Python. |
| Linux: `libGLESv2.so.2: cannot open shared object file` (landmarks, eyes and smile missing) | MediaPipe needs the OpenGL ES and EGL libraries. On Debian/Ubuntu: `sudo apt-get install libgles2 libegl1`, then restart FaceVision AI. |
| `Node.js was not found` | Install Node.js 20 or later and run the setup script again. The API works without the web app at `/api/docs`. |
| PowerShell says scripts are disabled | Run it as `powershell -ExecutionPolicy Bypass -File scripts\setup.ps1`. |

## Models

| Problem | Fix |
| --- | --- |
| Download fails or times out | Check your internet connection, proxy or firewall. Files come from `github.com`, `media.githubusercontent.com` and `storage.googleapis.com`. Retry from the Model Manager. |
| `checksum mismatch` | The file was corrupted or changed. FaceVision AI already deleted it; retry. If it keeps failing, open an issue. |
| Offline computer | Download the files elsewhere, copy them over and run `python -m facevision models install --defaults --from-dir FOLDER`. |
| A feature shows "not installed" | Install the model listed next to it in the Model Manager, or turn it on there. |
| A model "failed to load" | Settings → Run models on → CPU only, then warm up again. Report the error message in an issue. |

## Camera

| Problem | Fix |
| --- | --- |
| "Camera access was blocked" | Allow camera access for your browser in the OS privacy settings and for `localhost` in the browser, then reload. |
| "No camera was found" | Connect a webcam. On a Mac with the lid closed, the built-in camera is unavailable. |
| "The camera is in use" | Close other apps using it. |
| "needs a secure page" | Open `http://localhost:8600`. Browsers block cameras on plain `http://` addresses other than localhost. |
| Low frame rate | Use the Fast mode, turn off age and attributes, or close other heavy apps. The badge on the video shows analysed frames per second and latency. |

## Recognition

| Problem | Fix |
| --- | --- |
| Recognition toggle is greyed out | Sign in (Settings → Access). Recognition needs your passphrase. |
| Enrolled person shows as Unknown | Add more photos with different lighting and angles. Check the photos passed the quality checks. Lower the threshold slightly in Settings. |
| Wrong person recognised | Raise the threshold. Make sure each person's photos are really of them (enrolment warns about mismatches and duplicates). |
| "Low quality" | Move closer, face the camera and improve lighting. |
| Forgot the passphrase | Settings → Forgot passphrase. Enrolled faces cannot be recovered and are deleted. |

## Videos

| Problem | Fix |
| --- | --- |
| "Could not open the video" | Convert it to H.264 MP4 (for example with HandBrake or ffmpeg). |
| Annotated video does not play in the browser | MP4 output uses MPEG-4 Part 2, which some browsers cannot play. Download it and open it in VLC, or use a build with VP8 support (WebM output). |

## Server

| Problem | Fix |
| --- | --- |
| Port 8600 is in use | Put `FV_PORT=8601` in `.env` and restart. |
| "Host not allowed" | You opened FaceVision AI with an address other than localhost. See [SECURITY.md](../SECURITY.md) before allowing it. |
| Logs | Start with `FV_LOG_LEVEL=DEBUG` for detailed logs in the terminal. |
