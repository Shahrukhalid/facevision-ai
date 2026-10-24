# PyInstaller spec: pyinstaller packaging/facevision.spec  (run from the repository root after building the web app)
import os

import sys

from PyInstaller.utils.hooks import collect_all, collect_submodules

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
sys.path.insert(0, ROOT)
if not os.path.isfile(os.path.join(ROOT, "facevision", "web", "index.html")):
    raise SystemExit("Build the web app first: cd frontend && npm ci && npm run build")

datas, binaries, hiddenimports = [], [], []
for pkg in ("mediapipe", "onnxruntime", "cv2"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h
datas += [(os.path.join(ROOT, "facevision", "models", "manifest.json"), "facevision/models"),
          (os.path.join(ROOT, "facevision", "models", "clip_prompts.json"), "facevision/models"),
          (os.path.join(ROOT, "facevision", "web"), "facevision/web")]
hiddenimports += collect_submodules("facevision")
hiddenimports += ["uvicorn.logging", "uvicorn.loops.auto", "uvicorn.protocols.http.auto", "uvicorn.protocols.websockets.auto",
                  "uvicorn.lifespan.on", "multipart", "facevision.api.app"]

a = Analysis([os.path.join(SPECPATH, "launcher.py")], pathex=[ROOT], binaries=binaries, datas=datas, hiddenimports=hiddenimports,
             excludes=["tkinter", "matplotlib.tests", "numpy.tests", "PIL.ImageQt"], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="FaceVisionAI", console=True, upx=False)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="FaceVisionAI")
app = BUNDLE(coll, name="FaceVisionAI.app", bundle_identifier="io.github.shahrukhalid.facevision",
             info_plist={"NSCameraUsageDescription": "FaceVision AI uses the camera only while you have a live view open.",
                         "CFBundleShortVersionString": "0.1.0"}) if sys.platform == "darwin" else None
