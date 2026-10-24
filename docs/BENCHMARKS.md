# Benchmarks

All numbers come from `python -m facevision bench`, which runs each performance mode for several seconds on a 1280×720 frame containing one face (scikit-image's public-domain portrait) and reports per-frame latency. Recognition is timed against an empty gallery; matching against a gallery of a few hundred people adds well under a millisecond.

Run it yourself:

```bash
python -m facevision bench --seconds 10
```

## Results

| Machine | Fast | Balanced | Detailed |
| --- | --- | --- | --- |
| Linux x86-64, 2 vCPU, CPU only (development container) | 5.3 ms mean (189 fps) | 23.3 ms (43 fps) | 52.0 ms (19 fps) |

Per-stage means on that machine (Detailed mode): detection 26.6 ms at 960 px, landmarks 10.0 ms, embedding 9.6 ms, expression 7.8 ms, CLIP attributes 65.7 ms (run every 10 frames), InsightFace age 0.7 ms.

CI runners (macOS Apple Silicon, Windows, Linux) upload their benchmark results as workflow artifacts on every run. They are shared virtual machines, so treat their numbers as indicative.

## What affects speed

- **Frame size sent for analysis**: Fast sends 480 px, Balanced 640 px, Detailed 960 px wide frames.
- **Number of faces**: landmarks, quality and expression run per face.
- **Caching**: recognition, CLIP and age are computed once per track and refreshed every 10–60 frames, so their cost is spread out.
- **The live view** sends a new frame only after the previous result arrives, so the preview stays smooth even when analysis is slower than the camera.
