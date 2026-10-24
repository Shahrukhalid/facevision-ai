# Installing on Windows

Works on Windows 10 and 11 (64-bit).

## 1. Install the requirements

- **Python 3.12** from [python.org](https://www.python.org/downloads/windows/). In the installer, tick *Add python.exe to PATH*. The `py` launcher is installed by default.
- **Node.js LTS** from [nodejs.org](https://nodejs.org).
- **Git** from [git-scm.com](https://git-scm.com/download/win), or download the repository as a ZIP from GitHub.

Or with winget:

```powershell
winget install Python.Python.3.12 OpenJS.NodeJS.LTS Git.Git
```

## 2. Set up FaceVision AI

In PowerShell:

```powershell
git clone https://github.com/Shahrukhalid/facevision-ai.git
cd facevision-ai
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
```

`-ExecutionPolicy Bypass` lets this one script run without changing your system policy. The script creates `.venv`, installs pinned dependencies, builds the web app and downloads the default models (about 80 MB, checksum-verified). Set `$env:FV_SKIP_MODELS="1"` first to skip the model download.

## 3. Start it

```powershell
powershell -ExecutionPolicy Bypass -File scripts\start.ps1
```

Your browser opens `http://localhost:8600`. Stop the server with Ctrl+C.

The first start may show a Windows Defender Firewall prompt. FaceVision AI listens only on `127.0.0.1`, so it does not need network access; you can choose *Cancel*.

## 4. Allow camera access

1. Open **Settings → Privacy & security → Camera**.
2. Turn on *Camera access*, *Let apps access your camera* and *Let desktop apps access your camera*.
3. In the browser, allow the camera for `localhost`, then reload.

Close other apps that use the camera (Teams, Zoom, OBS) if it does not start.

## CPU and GPU

By default every model runs on the CPU. To use a DirectX 12 GPU for the ONNX models (expression, anti-spoofing, CLIP, research pack), replace ONNX Runtime with its DirectML build:

```powershell
.\.venv\Scripts\python.exe -m pip uninstall -y onnxruntime
.\.venv\Scripts\python.exe -m pip install onnxruntime-directml
```

FaceVision AI detects DirectML automatically and falls back to the CPU for any model it cannot run. YuNet, SFace and MediaPipe stay on the CPU. Check the Dashboard for the engine each model uses, and compare with:

```powershell
.\.venv\Scripts\python.exe -m facevision bench
```

## Uninstalling

Delete the project folder and, to remove your data and models, `%LOCALAPPDATA%\FaceVision AI`.
