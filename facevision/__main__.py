"""Command line: python -m facevision [serve|models|bench|evaluate|doctor]."""

from __future__ import annotations

import argparse
import json
import sys
import threading
import time
import webbrowser
from pathlib import Path

from . import __version__
from .config import Config, setup_logging


def _state(cfg: Config):
    from .state import AppState
    return AppState(cfg)


def cmd_serve(args, cfg: Config):
    import uvicorn

    from .api.app import create_app

    if args.host:
        cfg.host = args.host
    if args.port:
        cfg.port = args.port
    cfg.validate()
    state = _state(cfg)
    app = create_app(state)
    missing = [m for m in ("yunet",) if not state.registry.installed(m)]
    url = f"http://{'localhost' if cfg.host in {'127.0.0.1', '::1', 'localhost'} else cfg.host}:{cfg.port}"
    print(f"FaceVision AI {__version__} on {url}  (data: {cfg.data_dir})")
    if missing:
        print("The face detector is not installed yet. Open the Model Manager in the app, or run:\n"
              "  python -m facevision models install --defaults")
    if args.open:
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    uvicorn.run(app, host=cfg.host, port=cfg.port, log_level=cfg.log_level.lower(), ws_max_size=16 * 1024 * 1024)


def cmd_models(args, cfg: Config):
    state = _state(cfg)
    reg = state.registry
    if args.action == "list":
        for m in reg.list():
            flag = "installed" if m["installed"] else "not installed"
            on = "on" if m["enabled"] else "off"
            print(f"{m['id']:24} {m['task']:12} {m['license']:30} {flag:14} {on}")
        return 0
    ids = args.ids or []
    if args.defaults:
        ids = [m["id"] for m in reg.list() if m.get("default")]
    if args.action == "install":
        if args.from_dir:
            for mid in ids:
                if reg.models[mid].get("research_only") and not args.accept_research_license:
                    print(f"{mid}: licensed for non-commercial research only. Re-run with --accept-research-license")
                    continue
                reg.install_local(mid, Path(args.from_dir))
                if reg.models[mid].get("research_only"):
                    reg.set_enabled({**reg.get_enabled(), f"license:{mid}": True})
                print(f"installed {mid} from {args.from_dir}")
            return 0
        for mid in ids:
            if reg.installed(mid) and not args.force:
                print(f"{mid}: already installed")
                continue
            m = reg.models[mid]
            if m.get("research_only") and not args.accept_research_license:
                print(f"{mid}: licensed for non-commercial research only. Re-run with --accept-research-license "
                      f"after reading {m['license_url']}")
                continue
            print(f"{mid}: downloading {m['name']} ...", flush=True)
            reg.install_blocking(mid, accept_license=args.accept_research_license)
            print(f"{mid}: installed and verified")
        return 0
    if args.action == "verify":
        bad = 0
        for mid in ids or list(reg.models):
            if not reg.installed(mid):
                continue
            res = reg.verify(mid)
            bad += sum(v != "ok" for v in res.values())
            print(mid, res)
        return 1 if bad else 0
    return 0


def cmd_bench(args, cfg: Config):
    from .tools_bench import run_benchmark
    print(json.dumps(run_benchmark(_state(cfg), args.image, args.seconds), indent=2))
    return 0


def cmd_evaluate(args, cfg: Config):
    from .evaluation import evaluate_dataset
    report = evaluate_dataset(_state(cfg), Path(args.dataset), groups_csv=args.groups, upscale=args.upscale,
                              recognizer=args.recognizer)
    out = json.dumps(report, indent=2)
    if args.output:
        Path(args.output).write_text(out)
        print(f"wrote {args.output}")
    else:
        print(out)
    return 0


def cmd_doctor(args, cfg: Config):
    import cv2
    import numpy as np

    from .engine import runtime

    state = _state(cfg)
    print(f"FaceVision AI {__version__}, Python {sys.version.split()[0]}, OpenCV {cv2.__version__}, numpy {np.__version__}")
    print("hardware:", json.dumps(runtime.hardware_summary()))
    for m in state.registry.list():
        print(f"  {m['id']:24} installed={m['installed']} enabled={m['enabled']}")
    t = time.perf_counter()
    print("warm-up (ms):", state.hub.warmup(), f"total {round((time.perf_counter() - t) * 1000)} ms")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="facevision", description="FaceVision AI")
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="cmd")
    s = sub.add_parser("serve", help="start the web app and API (default)")
    s.add_argument("--host")
    s.add_argument("--port", type=int)
    s.add_argument("--open", action="store_true", help="open the browser")
    m = sub.add_parser("models", help="list, install or verify models")
    m.add_argument("action", choices=["list", "install", "verify"])
    m.add_argument("ids", nargs="*")
    m.add_argument("--defaults", action="store_true", help="all models marked as default")
    m.add_argument("--from-dir", help="install from a folder of already-downloaded files (checksums verified)")
    m.add_argument("--force", action="store_true")
    m.add_argument("--accept-research-license", action="store_true")
    b = sub.add_parser("bench", help="measure each performance preset on this machine")
    b.add_argument("--image", help="test image (default: a public-domain NASA portrait from scikit-image, if installed)")
    b.add_argument("--seconds", type=float, default=5.0)
    e = sub.add_parser("evaluate", help="recognition accuracy on a folder of <person>/<image> files")
    e.add_argument("dataset")
    e.add_argument("--groups", help="optional CSV person,group for per-group error rates")
    e.add_argument("--upscale", type=float, default=1.0)
    e.add_argument("--recognizer", default="sface")
    e.add_argument("--output")
    sub.add_parser("doctor", help="check installation, hardware and models")
    args = p.parse_args(argv)
    cfg = Config.from_env()
    setup_logging(cfg.log_level)
    cmd = args.cmd or "serve"
    if cmd == "serve" and not args.cmd:
        args = p.parse_args(["serve", *(argv or sys.argv[1:])])
    return {"serve": cmd_serve, "models": cmd_models, "bench": cmd_bench, "evaluate": cmd_evaluate,
            "doctor": cmd_doctor}[cmd](args, cfg) or 0


if __name__ == "__main__":
    sys.exit(main())
