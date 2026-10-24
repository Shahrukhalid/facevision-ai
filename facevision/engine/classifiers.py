"""Appearance classifiers. Every output is a model estimate with its probability, never a fact about the person."""

from __future__ import annotations

import math

import cv2
import numpy as np

from .runtime import make_session

FER_LABELS = ["neutral", "happiness", "surprise", "sadness", "anger", "disgust", "fear", "contempt"]
CLIP_MEAN = np.array([0.48145466, 0.4578275, 0.40821073], np.float32)
CLIP_STD = np.array([0.26862954, 0.26130258, 0.27577711], np.float32)


def _softmax(x: np.ndarray) -> np.ndarray:
    e = np.exp(x - x.max())
    return e / e.sum()


def _square_crop(image: np.ndarray, box: list[float], scale: float, size: int) -> np.ndarray:
    x, y, w, h = box
    side = max(w, h) * scale
    cx, cy = x + w / 2, y + h / 2
    k = size / side
    m = np.array([[k, 0, size / 2 - cx * k], [0, k, size / 2 - cy * k]], np.float32)
    return cv2.warpAffine(image, m, (size, size), flags=cv2.INTER_CUBIC, borderValue=0)


class ExpressionModel:
    """FER+ (MIT). Classifies the visible expression; it cannot tell what someone feels."""

    def __init__(self, path: str):
        self.sess, self.provider = make_session(path)
        self.inp = self.sess.get_inputs()[0].name

    def predict(self, image: np.ndarray, box: list[float]) -> dict:
        crop = _square_crop(image, box, 1.0, 64)
        g = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY).astype(np.float32)[None, None]
        p = _softmax(self.sess.run(None, {self.inp: g})[0].ravel())
        order = np.argsort(-p)
        entropy = float(-(p * np.log(p + 1e-12)).sum() / math.log(len(p)))
        top = FER_LABELS[order[0]]
        return {
            "label": top,
            "probability": round(float(p[order[0]]), 3),
            "uncertain": bool(p[order[0]] < 0.5),
            "normalized_entropy": round(entropy, 3),
            "probabilities": {FER_LABELS[i]: round(float(p[i]), 3) for i in order},
        }


class GenderAgeModel:
    """InsightFace genderage.onnx (non-commercial research licence, opt-in)."""

    def __init__(self, path: str):
        self.sess, self.provider = make_session(path)
        self.inp = self.sess.get_inputs()[0].name

    def predict(self, image: np.ndarray, box: list[float]) -> dict:
        crop = _square_crop(image, box, 1.5, 96)
        blob = cv2.dnn.blobFromImage(crop, 1.0, (96, 96), (0, 0, 0), swapRB=True)
        out = self.sess.run(None, {self.inp: blob})[0].ravel()
        p = _softmax(out[:2])
        return {"age": float(out[2] * 100), "appearance": {"female": round(float(p[0]), 3), "male": round(float(p[1]), 3)}}


class ClipAttributeModel:
    """CLIP ViT-B/32 zero-shot scoring (MIT). Experimental: prompts are not evaluated and CLIP has known biases."""

    def __init__(self, image_model: str, text_npz: str):
        self.sess, self.provider = make_session(image_model)
        self.inp = self.sess.get_inputs()[0].name
        data = np.load(text_npz, allow_pickle=False)
        self.scale = float(data["logit_scale"])
        self.attrs = {k.split(":", 1)[1]: data[k] for k in data.files if k.startswith("attr:")}
        self.age_labels = [str(x) for x in data["age:labels"]]
        self.age_embeds = data["age:embeds"]

    def embed(self, image: np.ndarray, box: list[float]) -> np.ndarray:
        crop = _square_crop(image, box, 1.4, 224)
        rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        x = ((rgb - CLIP_MEAN) / CLIP_STD).transpose(2, 0, 1)[None]
        return self.sess.run(None, {self.inp: x.astype(np.float32)})[0][0]

    def predict(self, image: np.ndarray, box: list[float]) -> dict:
        e = self.embed(image, box)
        attrs = {}
        for name, pair in self.attrs.items():
            p = _softmax(self.scale * pair @ e)
            attrs[name] = round(float(p[0]), 3)
        pa = _softmax(self.scale * self.age_embeds @ e)
        order = np.argsort(-pa)
        return {
            "attributes": attrs,
            "age_brackets": {self.age_labels[i]: round(float(pa[i]), 3) for i in order},
            "age_top": self.age_labels[order[0]],
            "age_top_probability": round(float(pa[order[0]]), 3),
        }
