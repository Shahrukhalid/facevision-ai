# Liveness checks and their limits

Liveness detection tries to tell a live person in front of the camera from a presentation attack such as a printed photo, a phone screen or a video replay. FaceVision AI combines two techniques. Neither, alone or together, proves that a live person is present.

## Active challenge

1. The server picks three random actions from: blink both eyes, turn your head left, turn your head right, smile.
2. Each frame is analysed with the landmark model:
   - blinks come from the `eyeBlinkLeft/Right` blendshapes (closed, then open again);
   - turns come from head yaw (more than 20 degrees);
   - smiles come from the `mouthSmileLeft/Right` blendshapes.
3. The check fails if it times out (25 seconds), if more than one face appears, or if the face jumps between frames.

**What it stops:** still photos, photos on a screen, and simple pre-recorded videos that do not follow the random prompts.

**What it does not stop:** 3D masks, a person holding up a video that happens to follow the prompts, puppeteered or real-time deepfakes, and virtual camera software feeding synthetic video.

## Passive check

Two MiniFASNet models from Minivision's Silent-Face-Anti-Spoofing project look at the face at two context sizes and score real versus spoof. During the active challenge their scores are averaged across frames, and a challenge that ends with an average below 0.5 is marked as failed.

In development testing, a fake-camera video made from a still photograph scored 0.37 (flagged as a spoof) and could not complete the head-turn prompt. That is one observation, not an evaluation. The models were trained by their authors on their own data, and this project has not independently measured their error rates. Lighting, camera quality and screen type all change the scores.

## Guidance

- Treat a pass as one signal, never as proof.
- Do not use FaceVision AI's liveness check to protect anything valuable on its own. Pair it with something the person has or knows.
- Keep the camera close and well lit, with one face in view.
