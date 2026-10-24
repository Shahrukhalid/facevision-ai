# Models, licences and compatibility

FaceVision AI uses a separate model for each task, so each one can be replaced or upgraded without touching the others. No model is used for something it was not built to do. The registry lives in [`facevision/models/manifest.json`](../facevision/models/manifest.json); the Model Manager reads it.

## How models are installed

1. The Model Manager (or `python -m facevision models install`) downloads each file from the URLs in the manifest.
2. Every file is hashed while it downloads. A file whose SHA-256 does not match the manifest is deleted and the next mirror is tried.
3. Files are written to a staging folder and moved into place only when everything is verified.
4. After that, no network access is needed. `FV_OFFLINE=1` disables downloads entirely.

For an offline machine, copy the files from another computer and run `python -m facevision models install --defaults --from-dir FOLDER`. Checksums are still verified.

## Licensing matrix

| Model | Task | Licence | Commercial use | Redistributed by this project | Source |
| --- | --- | --- | --- | --- | --- |
| YuNet 2023mar | Detection, 5 key points | MIT | Yes | No (downloaded from OpenCV Zoo) | [opencv_zoo](https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet) |
| SFace 2021dec | 128-d face embeddings | Apache-2.0 | Yes | No (OpenCV Zoo) | [opencv_zoo](https://github.com/opencv/opencv_zoo/tree/main/models/face_recognition_sface) |
| MediaPipe Face Landmarker (float16/1) | 478 landmarks, 52 blendshapes, pose matrix | Apache-2.0 | Yes | Mirrored unmodified as a fallback | [Google](https://ai.google.dev/edge/mediapipe/solutions/vision/face_landmarker) |
| FER+ (opset 8) | 8 expression classes | MIT | Yes | No (ONNX Model Zoo) | [onnx/models](https://github.com/onnx/models/tree/main/validated/vision/body_analysis/emotion_ferplus) |
| MiniFASNetV2 (2.7×) + MiniFASNetV1SE (4.0×) | Passive anti-spoofing | Apache-2.0 | Yes | Converted PyTorch → ONNX | [Silent-Face-Anti-Spoofing](https://github.com/minivision-ai/Silent-Face-Anti-Spoofing) |
| CLIP ViT-B/32 image encoder + prompt embeddings | Zero-shot attributes and age brackets | MIT | Yes | Converted PyTorch → ONNX, text embeddings pre-computed | [openai/clip-vit-base-patch32](https://huggingface.co/openai/clip-vit-base-patch32) |
| InsightFace buffalo_s: genderage, w600k_mbf | Age, appearance label, ArcFace embeddings | Non-commercial research only | **No** | **No.** Downloaded from InsightFace after the user accepts its licence | [InsightFace v0.7](https://github.com/deepinsight/insightface/releases/tag/v0.7) |

Converted and mirrored files are published in the [`model-pack-v1` release](https://github.com/Shahrukhalid/facevision-ai/releases/tag/model-pack-v1). They are rebuilt from upstream by [`tools/build_model_pack.py`](../tools/build_model_pack.py), which records the upstream revision of each file and checks every converted model against the original PyTorch output (maximum difference about 1e-6). The release includes the Apache-2.0 licence text and a NOTICE file.

### Training data

Model licences cover the weights. Some training datasets carry their own terms:

- FER+ was trained on FER+ labels for the FER2013 images.
- CLIP was trained by OpenAI on internet image-text pairs; its model card documents demographic biases.
- InsightFace's models are trained on research datasets, which is one reason they are licensed for non-commercial research only.

No permissively licensed age model trained on permissively licensed data was found, so FaceVision AI offers only experimental CLIP age brackets by default and the InsightFace estimate as an opt-in research option. A permissively licensed age model on Hugging Face (`onnx-community/age-gender-prediction-ONNX`) was evaluated and not included: it is trained on UTKFace (non-commercial) and its model card is inconsistent about inputs and outputs.

## Compatibility

| Model | Runs through | Apple Silicon | Windows x64 | Linux x64 / arm64 | Accelerator |
| --- | --- | --- | --- | --- | --- |
| YuNet | OpenCV `FaceDetectorYN` | CPU | CPU | CPU | – |
| SFace | OpenCV `FaceRecognizerSF` | CPU | CPU | CPU | – |
| Face Landmarker | MediaPipe Tasks | CPU | CPU | CPU | – |
| FER+, MiniFASNet, CLIP, InsightFace | ONNX Runtime | CPU or Core ML | CPU or DirectML\* | CPU or CUDA\* | Automatic with CPU fallback |

\* DirectML needs the `onnxruntime-directml` package and CUDA needs `onnxruntime-gpu` in place of `onnxruntime`. If an accelerator cannot load a model, FaceVision AI falls back to the CPU and the Dashboard shows which engine each model uses. Settings → *Run models on* forces CPU only.

Tested versions: OpenCV 5.0, MediaPipe 0.10.32–0.10.35 (pinned below 0.11), ONNX Runtime 1.24–1.31, Python 3.10–3.13. See `requirements.lock`.

## Published evaluation figures

| Model | Upstream figure |
| --- | --- |
| YuNet | WIDER Face validation AP 0.884 easy, 0.866 medium, 0.750 hard (OpenCV Zoo) |
| SFace | LFW accuracy 0.9940 (OpenCV Zoo) |
| Others | No benchmark that maps to how FaceVision AI uses them; see [EVALUATION.md](EVALUATION.md) for this project's own measurements |

## Adding or replacing a model

1. Add an entry to `manifest.json` with the file names, download URLs, SHA-256, size, licence and an honest `evaluation` note.
2. Write a small wrapper in `facevision/engine/` (see `classifiers.py`) and a loader in `engine/hub.py`.
3. Call it from `engine/pipeline.py`, reporting `unavailable` with a reason when it is not installed.
4. Add tests that run it on a real image, and document its licence here.
