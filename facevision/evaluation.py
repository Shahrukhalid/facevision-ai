"""Recognition evaluation on a labelled folder: <dataset>/<person>/<image files>.

Reports false match and false non-match rates across thresholds, the equal error rate, the threshold that meets a
target false match rate, rank-1 identification accuracy, and (with a groups CSV) the same error rates per group, so
differences between demographic groups can be measured. Only use data you are allowed to use for this purpose.
"""

from __future__ import annotations

import csv
import itertools
import time
from pathlib import Path

import cv2
import numpy as np

from .engine.pipeline import Options

EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".pgm", ".ppm"}


def _rates(gen: np.ndarray, imp: np.ndarray, thr: float) -> dict:
    return {"threshold": round(thr, 4),
            "false_non_match_rate": round(float(np.mean(gen < thr)), 5) if len(gen) else None,
            "false_match_rate": round(float(np.mean(imp >= thr)), 6) if len(imp) else None}


def evaluate_dataset(state, root: Path, groups_csv: str | None = None, upscale: float = 1.0,
                     recognizer: str = "sface", max_impostor_pairs: int = 2_000_000) -> dict:
    rec = state.hub.recognizer(recognizer)
    if rec is None:
        raise SystemExit("The recognizer is not installed.")
    opts = Options.from_dict({"preset": "fast", "max_side": 1600})
    people = sorted(d for d in root.iterdir() if d.is_dir())
    embs: dict[str, list[np.ndarray]] = {}
    failures, images = 0, 0
    t0 = time.perf_counter()
    for d in people:
        for f in sorted(d.iterdir()):
            if f.suffix.lower() not in EXTS:
                continue
            img = cv2.imread(str(f), cv2.IMREAD_COLOR)
            if img is None:
                continue
            images += 1
            if upscale != 1.0:
                img = cv2.resize(img, None, fx=upscale, fy=upscale, interpolation=cv2.INTER_CUBIC)
            faces = state.analyzer.detect(img, opts)
            if not faces:
                failures += 1
                continue
            e, _ = rec.embed(img, faces[0])
            embs.setdefault(d.name, []).append(e)
    elapsed = time.perf_counter() - t0
    ids = [p for p in embs if len(embs[p]) >= 1]
    gen, imp, imp_pairs = [], [], []
    for p in ids:
        E = np.stack(embs[p])
        s = E @ E.T
        gen += s[np.triu_indices(len(E), 1)].tolist()
    for a, b in itertools.combinations(ids, 2):
        s = (np.stack(embs[a]) @ np.stack(embs[b]).T).ravel()
        imp += s.tolist()
        imp_pairs.append((a, b, len(s)))
        if len(imp) > max_impostor_pairs:
            break
    gen, imp = np.array(gen), np.array(imp)
    thresholds = np.round(np.arange(0.10, 0.80, 0.025), 3)
    curve = [_rates(gen, imp, float(t)) for t in thresholds]
    diffs = [abs(c["false_non_match_rate"] - c["false_match_rate"]) for c in curve]
    eer_point = curve[int(np.argmin(diffs))]
    calib = {}
    for target in (1e-2, 1e-3, 1e-4):
        if len(imp) * target >= 1:
            thr = float(np.quantile(imp, 1 - target))
            calib[f"fmr_{target:g}"] = _rates(gen, imp, thr)
    # rank-1 identification: each image against everyone else's images
    correct = total = 0
    all_e = [(p, e) for p in ids for e in embs[p]]
    if len(all_e) > 1:
        M = np.stack([e for _, e in all_e])
        labels = np.array([p for p, _ in all_e])
        S = M @ M.T
        np.fill_diagonal(S, -2)
        for i in range(len(all_e)):
            if np.sum(labels == labels[i]) < 2:
                continue
            total += 1
            correct += labels[int(np.argmax(S[i]))] == labels[i]
    default_thr = state.analyzer.recognition_threshold(state.context(False), rec.model_id)
    report = {
        "dataset": str(root), "recognizer": rec.model_id, "people": len(people), "images": images,
        "detection_failures": failures, "seconds": round(elapsed, 1),
        "genuine_pairs": int(len(gen)), "impostor_pairs": int(len(imp)),
        "genuine_similarity_mean": round(float(gen.mean()), 4) if len(gen) else None,
        "impostor_similarity_mean": round(float(imp.mean()), 4) if len(imp) else None,
        "at_default_threshold": _rates(gen, imp, default_thr),
        "equal_error_rate_approx": eer_point,
        "calibrated_thresholds": calib,
        "rank1_identification_accuracy": round(correct / total, 4) if total else None,
        "curve": curve,
    }
    if groups_csv:
        groups: dict[str, str] = {}
        with open(groups_csv, newline="") as fh:
            for row in csv.reader(fh):
                if len(row) >= 2 and row[0] != "person":
                    groups[row[0]] = row[1]
        per = {}
        for g in sorted(set(groups.values())):
            members = [p for p in ids if groups.get(p) == g]
            gg, ii = [], []
            for p in members:
                E = np.stack(embs[p])
                gg += (E @ E.T)[np.triu_indices(len(E), 1)].tolist()
            for a, b in itertools.combinations(members, 2):
                ii += (np.stack(embs[a]) @ np.stack(embs[b]).T).ravel().tolist()
            per[g] = {"people": len(members), **_rates(np.array(gg), np.array(ii), default_thr)}
        report["per_group_at_default_threshold"] = per
        report["note"] = ("Group comparisons are only meaningful with enough people per group and comparable image "
                          "conditions across groups.")
    return report
