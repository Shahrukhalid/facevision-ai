#!/usr/bin/env python3
"""Build the FaceVision AI model pack (run by .github/workflows/model-pack.yml).

The pack contains only permissively licensed models that either need converting to ONNX or are hosted somewhere
that is unreachable from some networks. Every file is rebuilt from its upstream source, validated, and listed with
its SHA-256, source and licence in build-info.json.

    pip install torch onnx onnxruntime transformers huggingface_hub
    python tools/build_model_pack.py dist-models
"""

import hashlib
import json
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "dist-models").resolve()
WORK = OUT.parent / "model-pack-work"

FACE_LANDMARKER_URL = (
    "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task"
)
SILENT_FACE_REPO = "https://github.com/minivision-ai/Silent-Face-Anti-Spoofing.git"
CLIP_REPO_ID = "openai/clip-vit-base-patch32"

info = {"files": {}}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def record(path: Path, **meta):
    info["files"][path.name] = {"sha256": sha256(path), "size": path.stat().st_size, **meta}
    print(f"  {path.name}: {path.stat().st_size} bytes")


def download(url: str, dest: Path):
    req = urllib.request.Request(url, headers={"User-Agent": "facevision-model-pack"})
    with urllib.request.urlopen(req, timeout=300) as r, open(dest, "wb") as f:
        shutil.copyfileobj(r, f)


def face_landmarker():
    print("MediaPipe Face Landmarker")
    dest = OUT / "face_landmarker.task"
    download(FACE_LANDMARKER_URL, dest)
    import zipfile

    with zipfile.ZipFile(dest) as z:
        names = z.namelist()
    assert any("blendshapes" in n for n in names), names
    record(dest, source=FACE_LANDMARKER_URL, license="Apache-2.0", mirrored=True,
           docs="https://ai.google.dev/edge/mediapipe/solutions/vision/face_landmarker", contents=names)


def anti_spoofing():
    print("Silent-Face anti-spoofing (MiniFASNet) -> ONNX")
    import torch
    from collections import OrderedDict

    repo = WORK / "silent-face"
    if not repo.exists():
        subprocess.run(["git", "clone", "--depth", "1", SILENT_FACE_REPO, str(repo)], check=True)
    commit = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True,
                            check=True).stdout.strip()
    sys.path.insert(0, str(repo / "src" / "model_lib"))
    from MiniFASNet import MiniFASNetV1SE, MiniFASNetV2  # noqa: E402

    for weights, cls, out_name in [
        ("2.7_80x80_MiniFASNetV2.pth", MiniFASNetV2, "minifasnet_v2_scale2.7_80x80.onnx"),
        ("4_0_0_80x80_MiniFASNetV1SE.pth", MiniFASNetV1SE, "minifasnet_v1se_scale4.0_80x80.onnx"),
    ]:
        model = cls(conv6_kernel=(5, 5))  # ((80 + 15) // 16, (80 + 15) // 16)
        state = torch.load(repo / "resources" / "anti_spoof_models" / weights, map_location="cpu")
        state = OrderedDict((k[7:] if k.startswith("module.") else k, v) for k, v in state.items())
        model.load_state_dict(state)
        model.eval()
        x = torch.rand(2, 3, 80, 80) * 255  # the upstream model takes un-normalised BGR pixels (0-255)
        dest = OUT / out_name
        torch.onnx.export(model, x, str(dest), input_names=["input"], output_names=["logits"], opset_version=13,
                          dynamic_axes={"input": {0: "batch"}, "logits": {0: "batch"}}, dynamo=False)
        import onnxruntime as ort

        with torch.no_grad():
            ref = model(x).numpy()
        got = ort.InferenceSession(str(dest), providers=["CPUExecutionProvider"]).run(None, {"input": x.numpy()})[0]
        err = float(np.abs(ref - got).max())
        assert err < 1e-3, err
        record(dest, source=f"{SILENT_FACE_REPO} @ {commit} (resources/anti_spoof_models/{weights})",
               license="Apache-2.0", converted=True, max_abs_diff_vs_pytorch=err)


def clip():
    print("CLIP ViT-B/32 image encoder -> ONNX, text prompts -> embeddings")
    import torch
    from huggingface_hub import HfApi
    from transformers import CLIPModel, CLIPTokenizer

    revision = HfApi().model_info(CLIP_REPO_ID).sha
    model = CLIPModel.from_pretrained(CLIP_REPO_ID, revision=revision).eval()
    tok = CLIPTokenizer.from_pretrained(CLIP_REPO_ID, revision=revision)

    class ImageEncoder(torch.nn.Module):
        def __init__(self, m):
            super().__init__()
            self.m = m

        def forward(self, pixel_values):
            pooled = self.m.vision_model(pixel_values=pixel_values)[1]  # pooler output
            out = self.m.visual_projection(pooled)
            return out / out.norm(dim=-1, keepdim=True)

    enc = ImageEncoder(model).eval()
    fp32 = OUT / "clip_vit_b32_image_fp32.onnx"
    x = torch.randn(2, 3, 224, 224)
    torch.onnx.export(enc, x, str(fp32), input_names=["pixel_values"], output_names=["image_embeds"],
                      opset_version=17, dynamic_axes={"pixel_values": {0: "batch"}, "image_embeds": {0: "batch"}},
                      dynamo=False)
    import onnxruntime as ort
    from onnxruntime.quantization import QuantType, quantize_dynamic

    with torch.no_grad():
        ref = enc(x).numpy()
    got = ort.InferenceSession(str(fp32), providers=["CPUExecutionProvider"]).run(None, {"pixel_values": x.numpy()})[0]
    assert ref.shape == (2, model.config.projection_dim), ref.shape
    err = float(np.abs(ref - got).max())
    assert err < 1e-3, err
    src = f"https://huggingface.co/{CLIP_REPO_ID} @ {revision}"
    record(fp32, source=src, license="MIT", converted=True, max_abs_diff_vs_pytorch=err)
    int8 = OUT / "clip_vit_b32_image_int8.onnx"
    quantize_dynamic(str(fp32), str(int8), weight_type=QuantType.QUInt8)
    q = ort.InferenceSession(str(int8), providers=["CPUExecutionProvider"]).run(None, {"pixel_values": x.numpy()})[0]
    cos = float(np.min(np.sum(ref * q, axis=1)))
    print(f"  int8 vs fp32 cosine similarity (min over batch): {cos:.4f}")
    if cos >= 0.98:
        record(int8, source=src, license="MIT", converted=True, quantized="dynamic uint8 weights",
               min_cosine_vs_fp32_on_random_input=cos)
    else:
        print("  int8 model is not close enough to fp32; not publishing it")
        int8.unlink()

    prompts = json.loads((ROOT / "facevision" / "models" / "clip_prompts.json").read_text())
    templates = prompts["templates"]

    def embed(phrases):
        texts = [t.format(p) for p in phrases for t in templates]
        with torch.no_grad():
            t = tok(texts, padding=True, return_tensors="pt")
            pooled = model.text_model(input_ids=t["input_ids"], attention_mask=t["attention_mask"])[1]
            e = model.text_projection(pooled)
        assert e.shape == (len(texts), model.config.projection_dim), e.shape
        e = e / e.norm(dim=-1, keepdim=True)
        e = e.mean(dim=0)
        return (e / e.norm()).numpy().astype(np.float32)

    arrays = {}
    for name, sets in prompts["attributes"].items():
        arrays[f"attr:{name}"] = np.stack([embed(sets["present"]), embed(sets["absent"])])
    labels = list(prompts["age_brackets"])
    arrays["age:labels"] = np.array(labels)
    arrays["age:embeds"] = np.stack([embed(prompts["age_brackets"][k]) for k in labels])
    arrays["logit_scale"] = np.array(float(model.logit_scale.exp().item()), dtype=np.float32)
    dest = OUT / "clip_vit_b32_text_embeddings.npz"
    np.savez(dest, **arrays)
    record(dest, source=f"{src}; prompts: facevision/models/clip_prompts.json", license="MIT", derived=True,
           prompts_sha256=hashlib.sha256((ROOT / "facevision/models/clip_prompts.json").read_bytes()).hexdigest())


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    WORK.mkdir(parents=True, exist_ok=True)
    face_landmarker()
    anti_spoofing()
    clip()
    (OUT / "build-info.json").write_text(json.dumps(info, indent=2))
    with open(OUT / "SHA256SUMS.txt", "w") as f:
        for name, meta in sorted(info["files"].items()):
            f.write(f"{meta['sha256']}  {name}\n")
    print((OUT / "SHA256SUMS.txt").read_text())


if __name__ == "__main__":
    main()
