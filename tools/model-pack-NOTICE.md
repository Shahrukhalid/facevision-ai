# Model pack notice

This release contains model files redistributed or converted by the FaceVision AI project. They are not covered by
FaceVision AI's MIT licence; each keeps the licence of its upstream source.

| File | Upstream source | Licence | What we did |
| --- | --- | --- | --- |
| `face_landmarker.task` | Google MediaPipe, [Face Landmarker](https://ai.google.dev/edge/mediapipe/solutions/vision/face_landmarker) | Apache-2.0 | Unmodified copy |
| `minifasnet_v2_scale2.7_80x80.onnx` | Minivision [Silent-Face-Anti-Spoofing](https://github.com/minivision-ai/Silent-Face-Anti-Spoofing), `2.7_80x80_MiniFASNetV2.pth` | Apache-2.0 | Converted from PyTorch to ONNX, outputs checked against PyTorch |
| `minifasnet_v1se_scale4.0_80x80.onnx` | Minivision Silent-Face-Anti-Spoofing, `4_0_0_80x80_MiniFASNetV1SE.pth` | Apache-2.0 | Converted from PyTorch to ONNX, outputs checked against PyTorch |
| `clip_vit_b32_image_fp32.onnx` | OpenAI [CLIP ViT-B/32](https://huggingface.co/openai/clip-vit-base-patch32) | MIT | Image encoder exported to ONNX (normalised embeddings) |
| `clip_vit_b32_image_int8.onnx` | OpenAI CLIP ViT-B/32 | MIT | Same export with dynamic int8 weight quantisation |
| `clip_vit_b32_text_embeddings.npz` | OpenAI CLIP ViT-B/32 + `facevision/models/clip_prompts.json` | MIT | Pre-computed text embeddings for the zero-shot prompts |

Exact upstream revisions, sizes and SHA-256 checksums are in `build-info.json` and `SHA256SUMS.txt`.
The Apache License 2.0 text is included as `LICENSE-Apache-2.0.txt`.

Known limitations stated by the upstream projects apply. In particular, the anti-spoofing models were trained by
Minivision on their own data and are not a guarantee against presentation attacks, and CLIP is a general-purpose
model whose zero-shot predictions about people can be biased and wrong.
