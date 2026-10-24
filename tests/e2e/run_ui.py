"""Browser end-to-end test: drives the real web app in headless Chromium with a fake camera.

The fake camera plays a generated video of scikit-image's public-domain NASA portrait moving across the frame.
Enrolment uses mirrored and rescaled copies of the same portrait; recognition is checked on a held-out variant.

    python tests/e2e/run_ui.py http://localhost:8600  [--chromium /path/to/chrome]

Needs: playwright (pip), a Chromium build, scikit-image, and a running server with the default models installed.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np
from skimage import data

PAGES = ["/", "/live", "/analysis", "/recognition", "/enrolled", "/compare", "/image", "/video", "/batch", "/tracking",
         "/liveness", "/privacy", "/reports", "/models", "/settings", "/help"]


def make_assets(d: Path) -> dict:
    portrait = cv2.cvtColor(data.astronaut(), cv2.COLOR_RGB2BGR)
    w, h = 1280, 720
    with open(d / "camera.y4m", "wb") as out:
        out.write(f"YUV4MPEG2 W{w} H{h} F15:1 Ip A1:1 C420jpeg\n".encode())
        for i in range(90):
            f = np.full((h, w, 3), 35, np.uint8)
            x = 384 + int(300 * np.sin(i / 90 * 2 * np.pi))
            f[100:612, x:x + 512] = portrait
            out.write(b"FRAME\n")
            out.write(cv2.cvtColor(f, cv2.COLOR_BGR2YUV_I420).tobytes())
    files = {}
    variants = {"enrol1": portrait, "enrol2": cv2.flip(portrait, 1), "enrol3": cv2.resize(portrait, (600, 600)),
                "query": cv2.convertScaleAbs(cv2.resize(portrait, (448, 448)), alpha=1.1, beta=8)}
    for name, img in variants.items():
        p = d / f"{name}.jpg"
        cv2.imwrite(str(p), img)
        files[name] = str(p)
    return files


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("base", nargs="?", default="http://localhost:8600")
    ap.add_argument("--chromium")
    ap.add_argument("--shots", default="e2e-screenshots")
    args = ap.parse_args()
    from playwright.sync_api import sync_playwright

    tmp = Path(tempfile.mkdtemp())
    files = make_assets(tmp)
    shots = Path(args.shots)
    shots.mkdir(exist_ok=True)
    errors: list[str] = []
    checks: dict[str, object] = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=args.chromium, args=[
            "--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream",
            f"--use-file-for-fake-video-capture={tmp / 'camera.y4m'}"])
        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, permissions=["camera"])
        page = ctx.new_page()
        page.on("console", lambda m: m.type == "error" and errors.append(f"{page.url}: {m.text}"))
        page.on("pageerror", lambda e: errors.append(f"{page.url}: {e}"))
        B = args.base.rstrip("/")

        for path in PAGES:
            page.goto(B + path)
            page.wait_for_timeout(600)
            checks[f"page {path}"] = page.locator("h1").first.inner_text()
            page.screenshot(path=str(shots / f"page{path.replace('/', '_') or '_'}.png"))

        page.goto(B + "/live")
        page.get_by_role("button", name="Start camera").first.click()
        page.wait_for_selector("text=/^1 face$/", timeout=30000)
        checks["live: one face detected"] = True
        page.get_by_role("button", name="Detailed").click()
        page.wait_for_selector("text=Head pose", timeout=30000)
        checks["live: analysis panel shown"] = True
        page.screenshot(path=str(shots / "live.png"))
        page.get_by_role("button", name="Stop camera").click()

        page.goto(B + "/settings")
        page.get_by_label("New passphrase (10+ characters)").fill("e2e test passphrase")
        page.get_by_label("Repeat passphrase").fill("e2e test passphrase")
        page.get_by_role("button", name="Set passphrase").click()
        page.wait_for_selector("text=Your API key", timeout=15000)
        checks["settings: passphrase set"] = True

        page.goto(B + "/enrolled")
        page.get_by_role("button", name="Enrol a person").click()
        page.get_by_label("Name or identifier").fill("E2E Volunteer")
        page.get_by_role("checkbox").first.check()
        page.get_by_role("button", name="Create and add photos").click()
        page.wait_for_selector("text=Face templates", timeout=15000)
        page.locator("input[type=file][multiple]").first.set_input_files([files["enrol1"], files["enrol2"], files["enrol3"]])
        page.wait_for_selector("text=/3 of 3 photos added/", timeout=60000)
        checks["enrolment: 3 of 3 photos added"] = True

        page.goto(B + "/recognition")
        page.locator("input[type=file]").first.set_input_files(files["query"])
        page.wait_for_timeout(3000)
        res = page.evaluate("""async () => {
            const r = await fetch('/api/data/summary'); return await r.json(); }""")
        checks["recognition: enrolled count"] = res["persons"]
        page.screenshot(path=str(shots / "recognition.png"))

        page.goto(B + "/compare")
        page.locator("input[type=file]").nth(0).set_input_files(files["enrol1"])
        page.locator("input[type=file]").nth(1).set_input_files(files["query"])
        page.wait_for_selector("text=/Same person likely/", timeout=30000)
        checks["compare: same person"] = True

        page.goto(B + "/privacy")
        page.locator("input[type=file]").first.set_input_files(files["query"])
        page.wait_for_selector("text=/1 of 1 hidden/i", timeout=30000)
        checks["privacy: face hidden"] = True

        page.goto(B + "/tracking")
        page.get_by_role("button", name="Start camera").first.click()
        page.wait_for_selector("text=/→ enter #\\d+/", timeout=30000)
        checks["tracking: enter event"] = True
        page.get_by_role("button", name="Stop camera").click()
        browser.close()

    print(json.dumps(checks, indent=1))
    print(f"console errors: {len(errors)}")
    for e in errors:
        print("  ", e)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
