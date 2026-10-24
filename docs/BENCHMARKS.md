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
| macOS 14, Apple Silicon (GitHub `macos-14` runner, 3 vCPU) | 9.4 ms (106 fps) | 28.7 ms (35 fps) | 43.7 ms (23 fps) |
| Windows Server 2022, AMD EPYC (GitHub `windows-2022` runner, 4 vCPU) | 8.1 ms (124 fps) | 31.1 ms (32 fps) | 54.0 ms (19 fps) |
| Linux x86-64 (GitHub `ubuntu-24.04` runner, 4 vCPU) | 7.5 ms (133 fps) | 31.0 ms (32 fps) | 56.7 ms (18 fps) |

Each cell is the mean latency per frame, with the matching frame rate if frames are processed back to back. The runner rows come from [CI run #5](https://github.com/Shahrukhalid/facevision-ai/actions/runs/40048661741) (default settings, automatic hardware acceleration; on macOS ONNX Runtime offers Core ML, on the others CPU only). p95 latencies there: macOS 13 / 47 / 59 ms, Windows 9 / 45 / 71 ms, Linux 9 / 41 / 66 ms.

Per-stage means on that machine (Detailed mode): detection 26.6 ms at 960 px, landmarks 10.0 ms, embedding 9.6 ms, expression 7.8 ms, CLIP attributes 65.7 ms (run every 10 frames), InsightFace age 0.7 ms.

Detailed-mode stage means on the CI runners: macOS detection 18.1 ms, landmarks 11.6 ms, embedding 9.2 ms, expression 12.6 ms; Windows detection 27.6 ms, landmarks 12.8 ms, embedding 17.3 ms, expression 10.4 ms.

Every CI run repeats these measurements and shows them in the run summary (and as `measurements-*` artifacts). The runners are shared virtual machines without a GPU, so treat their numbers as indicative.

## What affects speed

- **Frame size sent for analysis**: Fast sends 480 px, Balanced 640 px, Detailed 960 px wide frames.
- **Number of faces**: landmarks, quality and expression run per face.
- **Caching**: recognition, CLIP and age are computed once per track and refreshed every 10–60 frames, so their cost is spread out.
- **The live view** sends a new frame only after the previous result arrives, so the preview stays smooth even when analysis is slower than the camera.
