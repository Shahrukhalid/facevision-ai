# Evaluation

This page reports what has actually been measured, how, and what it does and does not tell you.

## Recognition on the AT&T Database of Faces

**Dataset.** The AT&T ("ORL") Database of Faces: 40 people, 10 greyscale images each (92×112 px), photographed between 1992 and 1994 at the Olivetti Research Laboratory with volunteers who took part in the collection. Images were upscaled 3× before detection. The dataset is not included in this repository.

**Method.** `python -m facevision evaluate DATASET --upscale 3 --recognizer MODEL`. Every image goes through the normal pipeline: YuNet detection, 5-point alignment, embedding. All within-person pairs are genuine (1,800); all cross-person pairs are impostors (78,000). Rank-1 identification compares each image with every other image.

| Recognizer | Detection failures | Genuine mean similarity | Impostor mean | FNMR at default threshold | FMR at default threshold | Threshold for FMR 0.1% | Rank-1 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| SFace (default 0.363) | 0 / 400 | 0.823 | 0.079 | 0.0% | 0.173% | 0.388 (FNMR 0.0%) | 100% |
| ArcFace MobileFaceNet, research pack (default 0.30) | 0 / 400 | 0.797 | 0.043 | 0.0% | 0.023% | 0.272 (FNMR 0.0%) | 100% |

Raw outputs: [`results/att-sface.json`](results/att-sface.json), [`results/att-arcface-mbf.json`](results/att-arcface-mbf.json).

**What this does not show.** AT&T is small, controlled and almost 35 years old: frontal faces, plain background, one camera, 40 people, little demographic variety. It confirms that the pipeline works end to end and that the default thresholds are sensible. It does **not** predict accuracy on phone photos, video, poor lighting, large pose changes, children, ageing over years, or populations unlike the volunteers. Upstream, SFace reports 99.40% accuracy on LFW (OpenCV Zoo).

## Evaluating on your own data

Use only data you are allowed to use for this, ideally collected with the consent of the people in it.

```bash
# dataset/<person>/<images>
python -m facevision evaluate path/to/dataset --output report.json

# with a CSV of "person,group" to compare error rates between groups
python -m facevision evaluate path/to/dataset --groups groups.csv --output report.json
```

The report includes:

- false non-match and false match rates across thresholds (`curve`);
- an approximate equal error rate;
- thresholds that meet target false match rates of 1%, 0.1% and 0.01%;
- rank-1 identification accuracy;
- with `--groups`, error rates per group at the active threshold.

Set the threshold you choose in Settings → Recognition.

### Demographic performance

Face recognition and attribute models are often less accurate for some groups of people. Measuring this needs a dataset with enough people per group, comparable image conditions across groups, and group labels that the people themselves provided. This project has not had access to such a dataset, so **no per-group results are published yet**. The `--groups` option exists so you can run this check before relying on FaceVision AI.

## Other models

| Feature | What was checked |
| --- | --- |
| Detection | Unit tests on a public-domain portrait, blank and noise images, multiple and small faces, and the detection threshold. |
| Head pose | Signs and units checked against image rotation (20° clockwise rotation changes roll by about +20°), mirroring, and 400 AT&T images (sign agreement with an independent 5-point estimate; correlation 0.90 for yaw). Absolute accuracy is not benchmarked. |
| Blink, smile, mouth | MediaPipe blendshape scores. Checked on still images and a smiling portrait; not benchmarked. |
| Expression (FER+) | Checked on a smiling portrait. Upstream training data: FER+ labels on FER2013. |
| Age | Not evaluated. CLIP brackets are zero-shot guesses, and the fp32 and int8 CLIP encoders disagreed on the top bracket for the same test portrait. The InsightFace estimate has no published error figure. |
| Attributes (CLIP) | Not evaluated. Probabilities are zero-shot outputs. |
| Anti-spoofing | Not evaluated beyond smoke tests. See [LIVENESS.md](LIVENESS.md). |

Contributions of evaluations on lawfully obtained, consented data are welcome; see [CONTRIBUTING.md](../CONTRIBUTING.md).
