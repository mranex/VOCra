# Design.md — VOCra: Modular Hardcoded Subtitle OCR Workbench

> Working name: **VOCra**  
> Meaning: Video OCR Artifact Workbench  
> Goal: turn a one-click hardcoded subtitle extractor into a persistent, inspectable, modular OCR project system.

---

## 1. Core idea

This app is **not** a cleaner clone of the old VideOCR GUI.

This app is a new workflow built around **persistent project artifacts**.

The old workflow is:

```text
Open video
  -> configure everything
  -> click Run
  -> wait
  -> output SRT or lose everything if interrupted
```

The new workflow is:

```text
Create/open project
  -> Load video
  -> Prepare subtitle evidence
  -> OCR prepared evidence using any backend
  -> Review/fix OCR results
  -> Package SRT
```

Every major step writes files to disk. A user can prepare today, run OCR next month, and package the SRT next year.

---

## 2. Non-negotiable design principle

**Timing belongs to Prepare. Text belongs to OCR. SRT belongs to Packaging.**

OCR must never own the subtitle timeline.

The Prepare stage is responsible for:

- video probing
- crop-zone interpretation
- frame sampling
- subtitle-region cropping
- detection of candidate subtitle frames
- duplicate subtitle filtering
- representative image selection
- preserving timestamp mapping
- generating subtitle segment artifacts

OCR is only responsible for:

- reading text from prepared representative images
- returning raw and normalized text output

Packaging is responsible for:

- combining prepared timeline segments with OCR text
- producing `.srt`, `.ass`, or future export formats

---

## 3. What must be preserved from the original author

The original author’s valuable logic is not the one-click GUI. The valuable logic is the **subtitle preparation engine**.

Keep the spirit and behavior of:

```text
User-drawn crop zone on source video
  -> decode frames
  -> crop subtitle area
  -> filter near-identical frames with SSIM
  -> use text detection to know whether subtitle text exists
  -> group frames with similar subtitle layout
  -> use tight-box SSIM to remove duplicate subtitle frames
  -> choose representative frame(s)
  -> preserve frame index and timestamp mapping
  -> OCR only the minimal useful images
  -> rebuild subtitles with correct start/end timing
```

This is the heart of the app.

Do not replace this with naive “OCR every N frames”.

---

## 4. App mental model

The app is a **workbench**, not a wizard.

A user should feel:

```text
I know what stage I am in.
I can inspect what the app produced.
I can rerun only the broken part.
I can switch OCR model without re-preparing the video.
I can keep multiple OCR runs for the same prepared project.
I can package different SRT outputs from different OCR runs.
```

---

## 5. Project workspace

Every video job lives in a project directory.

Recommended extension:

```text
<project-name>.vocra/
```

Example:

```text
Comedy_Show_EP01.vocra/
  project.json
  app_state.json

  source/
    source_ref.json
    thumbnail.jpg

  prepare/
    prepare_config.json
    crop_zones.json
    timeline.jsonl
    frame_index.jsonl
    detection_boxes.jsonl
    subtitle_segments.jsonl
    representative_images/
      seg_000001_z0.jpg
      seg_000002_z0.jpg
      seg_000003_z0.jpg
    debug/
      contact_sheets/
      rejected_frames/
      detection_grids/

  ocr/
    runs/
      2026-05-24_143522_llamacpp_paddleocr-vl/
        ocr_config.json
        raw_outputs.jsonl
        normalized_text.jsonl
        review_state.jsonl
        errors.jsonl
        run_report.json

      2026-06-10_091011_ollama_other-model/
        ocr_config.json
        raw_outputs.jsonl
        normalized_text.jsonl
        review_state.jsonl
        errors.jsonl
        run_report.json

  package/
    runs/
      2026-05-24_150000_srt/
        package_config.json
        output.srt
        package_report.json

  logs/
    app.log
    prepare.log
    ocr.log
    package.log
```

---

## 6. Project file responsibilities

### `project.json`

Project-level identity and source metadata.

```json
{
  "schema_version": 1,
  "project_id": "b9c9be26-1c24-48ae-8dd1-5ef87b3a6e10",
  "name": "Comedy_Show_EP01",
  "created_at": "2026-05-24T14:20:00+07:00",
  "updated_at": "2026-05-24T14:25:00+07:00",
  "source": {
    "mode": "external_path",
    "path": "/videos/Comedy_Show_EP01.mkv",
    "fingerprint": "sha256-or-fast-hash",
    "duration_ms": 1485234,
    "width": 1920,
    "height": 1080,
    "fps": 23.976
  }
}
```

### `prepare/prepare_config.json`

The exact settings used during preparation.

```json
{
  "schema_version": 1,
  "time_start_ms": 0,
  "time_end_ms": null,
  "frames_to_skip": 1,
  "ssim_threshold": 0.92,
  "tight_box_ssim_threshold": 0.85,
  "subtitle_position": "center",
  "ocr_image_max_width": 720,
  "brightness_threshold": null,
  "use_fullframe": false,
  "crop_zones": [
    {
      "zone_idx": 0,
      "x": 130,
      "y": 780,
      "width": 1660,
      "height": 220
    }
  ],
  "detector": {
    "name": "paddleocr-text-detection",
    "mode": "local-cli",
    "model_dir": "auto"
  }
}
```

### `prepare/subtitle_segments.jsonl`

This is the most important artifact.

One line per prepared subtitle segment.

```json
{
  "segment_id": "seg_000001",
  "zone_idx": 0,
  "start_ms": 81234,
  "end_ms": 84567,
  "start_frame_idx": 1948,
  "end_frame_idx": 2028,
  "representative_image": "representative_images/seg_000001_z0.jpg",
  "source_frame_indices": [1948, 1949, 1950, 1951],
  "detection_boxes": [
    [[42, 18], [1530, 18], [1530, 104], [42, 104]]
  ],
  "confidence": {
    "detection_score": 0.94,
    "dedupe_score": 0.98
  },
  "status": "prepared"
}
```

### `ocr/runs/<run_id>/ocr_config.json`

The OCR backend and model configuration.

```json
{
  "schema_version": 1,
  "run_id": "2026-05-24_143522_llamacpp_paddleocr-vl",
  "input_prepare_id": "prepare_default",
  "backend": "openai-compatible-vision",
  "provider": "llama.cpp-server",
  "endpoint": "http://127.0.0.1:8080/v1",
  "model": "PaddleOCR-VL-1.5-GGUF",
  "prompt_template": "OCR the subtitle text in this image. Return only the subtitle text.",
  "temperature": 0,
  "max_tokens": 256,
  "batch_size": 1,
  "timeout_sec": 120
}
```

### `ocr/runs/<run_id>/raw_outputs.jsonl`

The raw response from the backend. Never destroy it.

```json
{
  "segment_id": "seg_000001",
  "image": "prepare/representative_images/seg_000001_z0.jpg",
  "backend": "openai-compatible-vision",
  "raw": {
    "id": "chatcmpl-...",
    "choices": [
      {
        "message": {
          "content": "I can't believe you did that!"
        }
      }
    ]
  }
}
```

### `ocr/runs/<run_id>/normalized_text.jsonl`

Backend-independent normalized OCR result.

```json
{
  "segment_id": "seg_000001",
  "zone_idx": 0,
  "text": "I can't believe you did that!",
  "confidence": null,
  "language": "en",
  "status": "ok",
  "source": {
    "backend": "openai-compatible-vision",
    "run_id": "2026-05-24_143522_llamacpp_paddleocr-vl"
  }
}
```

### `ocr/runs/<run_id>/review_state.jsonl`

Manual review/correction state.

```json
{
  "segment_id": "seg_000001",
  "original_text": "I can't believe you did that!",
  "edited_text": "I can't believe you did that!",
  "review_status": "accepted",
  "notes": ""
}
```

### `package/runs/<run_id>/package_config.json`

How SRT was produced.

```json
{
  "schema_version": 1,
  "prepare_source": "prepare/subtitle_segments.jsonl",
  "ocr_source": "ocr/runs/2026-05-24_143522_llamacpp_paddleocr-vl/normalized_text.jsonl",
  "review_source": "ocr/runs/2026-05-24_143522_llamacpp_paddleocr-vl/review_state.jsonl",
  "format": "srt",
  "min_subtitle_duration_ms": 200,
  "max_merge_gap_ms": 100,
  "empty_text_policy": "skip",
  "line_break_policy": "preserve"
}
```

---

## 7. Pipeline stages

## 7.1 Load Video

Purpose:

- open a video file
- probe metadata
- show preview frames
- let user create or open a project

Inputs:

- video path
- optional project directory

Outputs:

- `project.json`
- `source/source_ref.json`
- thumbnail/cache

Core operations:

- probe duration, resolution, fps, container start offset
- compute lightweight fingerprint
- initialize project workspace

---

## 7.2 Configure Prepare

Purpose:

- set time range
- define crop zones
- configure frame sampling and filtering
- configure detector for prepare stage

Inputs:

- video preview
- user crop zones
- prepare settings

Outputs:

- `prepare/prepare_config.json`
- `prepare/crop_zones.json`

Important:

The user-drawn crop zone is based on the original video coordinate system, not the scaled preview coordinate system.

Preview coordinates must be converted to original video coordinates.

---

## 7.3 Prepare

Purpose:

Turn video into subtitle evidence.

Inputs:

- source video
- prepare config
- crop zones

Outputs:

- `timeline.jsonl`
- `frame_index.jsonl`
- `detection_boxes.jsonl`
- `subtitle_segments.jsonl`
- `representative_images/`
- debug artifacts

Detailed flow:

```text
1. Open video with PyAV.
2. Seek to time_start.
3. Decode frames.
4. Apply frame skip.
5. Crop subtitle zones.
6. Resize crop images for detection/OCR.
7. Apply brightness filtering if configured.
8. Use SSIM to skip visually redundant frames.
9. Stitch filtered crops into grids.
10. Run text detection pass.
11. Unstitch detection boxes back to original crop coordinates.
12. Identify frames with subtitle text.
13. Group frames by similar text-box layout.
14. Use tight-box SSIM to remove duplicate subtitle appearances.
15. Select representative crop image for each segment.
16. Preserve frame index and timestamp mapping.
17. Write subtitle segment manifest.
```

Key invariant:

```text
Every representative image must map back to:
- segment_id
- frame_idx
- zone_idx
- start_ms
- end_ms
- source crop zone
```

---

## 7.4 OCR

Purpose:

Read text from prepared representative images.

Inputs:

- `prepare/subtitle_segments.jsonl`
- selected OCR backend config
- representative images

Outputs:

- `ocr/runs/<run_id>/ocr_config.json`
- `raw_outputs.jsonl`
- `normalized_text.jsonl`
- `errors.jsonl`
- `run_report.json`

OCR must be rerunnable without rerunning Prepare.

Supported backend types:

```text
openai-compatible-vision
llama.cpp-server
llama.cpp-cli
ollama
local-command
python-plugin
paddleocr-fallback
manual-import
```

The backend layer must normalize every result into:

```json
{
  "segment_id": "seg_000001",
  "text": "...",
  "confidence": null,
  "status": "ok"
}
```

---

## 7.5 Review

Purpose:

Let the user inspect and fix OCR output before packaging.

Inputs:

- prepared representative image
- normalized OCR text
- raw OCR text
- segment timing

Outputs:

- `review_state.jsonl`

UI should show:

```text
[image crop]
segment_id
timestamp start/end
OCR text
editable corrected text
status: pending / accepted / edited / rejected
```

Useful filters:

- empty text
- low confidence
- OCR error
- unreviewed
- edited
- repeated text
- very short segment
- suspicious characters

---

## 7.6 Package SRT

Purpose:

Combine prepared timing with OCR/reviewed text.

Inputs:

- `prepare/subtitle_segments.jsonl`
- `normalized_text.jsonl`
- optional `review_state.jsonl`
- package config

Outputs:

- `.srt`
- package report

Rules:

- Use edited text if present.
- Use normalized OCR text if no edit exists.
- Use `start_ms` and `end_ms` from Prepare.
- Do not let OCR alter timing.
- Skip empty rejected segments unless configured otherwise.
- Preserve dual-zone ordering according to zone position/alignment rules.
- Merge adjacent identical subtitles only if package config allows it.

---

## 8. OCR backend architecture

## 8.1 Backend interface

```python
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, Iterable, Any

@dataclass(frozen=True)
class OcrInput:
    segment_id: str
    image_path: Path
    zone_idx: int
    start_ms: int
    end_ms: int
    metadata: dict[str, Any]

@dataclass(frozen=True)
class OcrOutput:
    segment_id: str
    text: str
    confidence: float | None
    raw: Any
    status: str
    error: str | None = None

class OcrBackend(Protocol):
    name: str

    def run(
        self,
        inputs: Iterable[OcrInput],
        config: dict[str, Any],
    ) -> Iterable[OcrOutput]:
        ...
```

## 8.2 Backend responsibilities

A backend may:

- call llama.cpp server
- call llama.cpp CLI
- call Ollama
- call any OpenAI-compatible vision endpoint
- call a local Python model
- call a custom command
- call PaddleOCR as fallback

A backend must:

- never modify prepare artifacts
- write raw output
- return normalized text
- report per-segment error without killing the whole project unless configured
- be deterministic when temperature/config says deterministic
- include enough metadata for replay/debugging

---

## 9. Llama.cpp / Ollama / GGUF design

The app should support GGUF vision OCR models through flexible adapters.

Target model example:

```text
PaddlePaddle/PaddleOCR-VL-1.5-GGUF
```

Possible execution modes:

### Mode A — llama.cpp server / OpenAI-compatible endpoint

```text
User starts llama-server externally
App sends image + prompt to http://127.0.0.1:8080/v1/chat/completions
App receives text
```

Config:

```json
{
  "backend": "openai-compatible-vision",
  "endpoint": "http://127.0.0.1:8080/v1",
  "api_key": "not-needed-or-local",
  "model": "PaddleOCR-VL-1.5-GGUF",
  "prompt_template": "OCR this subtitle image. Return only the subtitle text.",
  "temperature": 0
}
```

### Mode B — llama.cpp CLI

```text
App calls llama-cli with image path and prompt
App captures stdout
App normalizes text
```

Config:

```json
{
  "backend": "llama.cpp-cli",
  "llama_cli_path": "/path/to/llama-cli",
  "model_path": "/models/PaddleOCR-VL-1.5.gguf",
  "mmproj_path": "/models/mmproj.gguf",
  "prompt_template": "OCR:",
  "timeout_sec": 120
}
```

### Mode C — Ollama

```text
App sends image to Ollama API
App receives text
```

Config:

```json
{
  "backend": "ollama",
  "endpoint": "http://127.0.0.1:11434",
  "model": "hf.co/PaddlePaddle/PaddleOCR-VL-1.5-GGUF",
  "prompt_template": "OCR this subtitle image. Return only the text.",
  "temperature": 0
}
```

### Mode D — Local command

For any custom OCR tool.

```json
{
  "backend": "local-command",
  "command": "my-ocr --image {image} --lang {lang}",
  "stdout_format": "plain_text"
}
```

---

## 10. Detector architecture

Prepare still needs a way to detect text boxes for filtering and de-duplication.

Initial detector options:

```text
paddleocr-text-detection
simple-visual-diff-only
external-detector-command
manual-segment-import
```

Recommended first version:

```text
Keep PaddleOCR text detection for Prepare.
Replace only OCR recognition first.
```

Reason:

The original author’s high-value logic depends on detection boxes for tight-box grouping and de-duplication. Replacing recognition is easy. Replacing detection should be a later plugin step.

Eventually:

```text
DetectorBackend
  - PaddleTextDetector
  - LlamaVisionDetector
  - CustomCommandDetector
  - ManualDetector
```

---

## 11. GUI design model

The GUI should be stage-based.

Main navigation:

```text
Project
Prepare
OCR
Review
Package
Logs
Settings
```

### Project tab

Contains:

- create project
- open project
- load source video
- project path
- video metadata
- thumbnail
- artifact status summary

Status summary example:

```text
Source video: loaded
Prepare: completed, 1234 segments
OCR runs: 3
Reviewed: 822/1234 accepted
Package outputs: 2
```

### Prepare tab

Contains:

- video preview
- timeline slider
- crop-zone drawing
- time range
- frames to skip
- SSIM threshold
- detector selection
- Prepare button
- Resume Prepare button
- Open prepare folder button
- prepare result summary

Important buttons:

```text
Save Crop Zone
Run Prepare
Rerun Prepare
Open Prepared Images
Open Segment Manifest
```

### OCR tab

Contains:

- choose prepare run
- choose OCR backend
- backend config panel
- test backend connection
- run OCR
- resume OCR
- compare OCR runs
- OCR run list

Important buttons:

```text
Test Backend
Run OCR
Stop OCR
Resume Failed Only
Open Raw Output
Open Normalized Output
```

### Review tab

Contains:

- segment image
- timestamp
- OCR text
- editable text
- accept/edit/reject
- filters
- next suspicious
- bulk accept

### Package tab

Contains:

- choose prepare run
- choose OCR run
- choose review state
- output format
- packaging options
- preview SRT
- export button

---

## 12. CLI design

Every GUI action must map to a CLI command.

This makes the app scriptable and testable.

Suggested commands:

```bash
vocra project create --video input.mkv --project Comedy_Show_EP01.vocra

vocra prepare run \
  --project Comedy_Show_EP01.vocra \
  --time-start 0:00 \
  --crop-zone 130,780,1660,220 \
  --frames-to-skip 1 \
  --detector paddleocr-text-detection

vocra ocr run \
  --project Comedy_Show_EP01.vocra \
  --backend openai-compatible-vision \
  --endpoint http://127.0.0.1:8080/v1 \
  --model PaddleOCR-VL-1.5-GGUF \
  --prompt-template "OCR this subtitle image. Return only text."

vocra package srt \
  --project Comedy_Show_EP01.vocra \
  --ocr-run 2026-05-24_143522_llamacpp_paddleocr-vl \
  --output output.srt
```

---

## 13. Data contracts

## 13.1 Segment contract

A segment is a subtitle timing unit prepared before OCR.

Required fields:

```text
segment_id
zone_idx
start_ms
end_ms
representative_image
source_frame_indices
detection_boxes
status
```

OCR output must reference `segment_id`.

Packaging joins on `segment_id`.

## 13.2 OCR contract

OCR output must not create new timing.

Required fields:

```text
segment_id
text
status
confidence optional
error optional
```

## 13.3 Review contract

Review output must reference original OCR output.

Required fields:

```text
segment_id
edited_text
review_status
```

---

## 14. Error and resume design

Every stage should be resumable.

### Prepare resume

Prepare can resume if:

- source video fingerprint matches
- prepare config matches
- partial segment files exist

If config changed, create a new prepare run instead of mutating old artifacts.

### OCR resume

OCR can resume per segment.

If `normalized_text.jsonl` already has `segment_id`, skip it unless `--force`.

### Package resume

Packaging is fast and can be rerun anytime.

---

## 15. Versioning

All artifact files need `schema_version`.

When schema changes:

- write migration if simple
- otherwise reject with readable error
- never silently reinterpret old data

---

## 16. Logging

Each stage writes its own logs:

```text
logs/app.log
logs/prepare.log
logs/ocr.log
logs/package.log
```

Errors should include:

- project path
- stage
- segment_id if applicable
- backend config name
- short message
- traceback in log only

---

## 17. Testing philosophy

The app must be testable without real OCR model.

Use fake backends:

```text
FakeDetector
FakeOcrBackend
FakeVideoSource
```

The core Prepare pipeline should be testable with synthetic frames.

The OCR pipeline should be testable with static prepared images and fake responses.

The Package pipeline should be testable with small JSONL fixtures.

---

## 18. Summary

VOCra is built around one idea:

```text
Prepare once.
OCR many times.
Package anytime.
```

The original VideOCR author’s detection, filtering, de-duplication, and timestamp-preserving logic is the foundation. The new app changes the workflow and architecture so that OCR becomes replaceable, progress becomes durable, and the user controls every stage.
