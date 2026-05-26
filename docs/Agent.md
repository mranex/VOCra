# Agent.md — Rules for AI Coding Agents Building VOCra

## 1. Mission

Build a new app called **VOCra** using the original VideOCR repository as a source of useful algorithms, not as the final architecture.

The target app is a staged, persistent, project-based OCR workbench:

```text
Project
Prepare
OCR
Review
Package
```

The highest-value legacy logic to preserve is:

```text
crop-zone based subtitle detection
frame/timestamp mapping
SSIM duplicate filtering
text-box based duplicate filtering
representative subtitle image selection
SRT timing reconstruction
```

The highest-value new behavior is:

```text
Prepare once.
OCR many times.
Package anytime.
```

---

## 2. Absolute rules

### Rule 1 — Do not recreate the monolith

Do not put GUI, pipeline, OCR backend, config, and packaging logic into one file.

No new file should become a dumping ground.

Recommended max file size:

```text
Soft limit: 500 lines
Hard warning: 800 lines
```

If a file grows too large, split by responsibility.

---

### Rule 2 — Timing belongs to Prepare

OCR output must not determine subtitle timing.

The Prepare stage owns:

```text
segment_id
start_ms
end_ms
zone_idx
representative_image
source_frame_indices
detection_boxes
```

OCR owns only:

```text
segment_id
text
confidence optional
raw output
error/status
```

Packaging joins Prepare and OCR by `segment_id`.

---

### Rule 3 — Prepare artifacts are durable

Never keep critical stage output only in memory.

Prepare must write:

```text
prepare_config.json
crop_zones.json
subtitle_segments.jsonl
representative_images/
detection_boxes.jsonl
logs/prepare.log
```

OCR must write:

```text
ocr_config.json
raw_outputs.jsonl
normalized_text.jsonl
errors.jsonl
run_report.json
```

Package must write:

```text
package_config.json
output.srt
package_report.json
```

---

### Rule 4 — OCR backend must be replaceable

Do not hardcode PaddleOCR, llama.cpp, Ollama, DeepSeekOCR, or any model into the pipeline.

Use backend interfaces.

Bad:

```python
if ocr_engine == "paddleocr":
    ...
elif ocr_engine == "llama":
    ...
elif ocr_engine == "deepseek":
    ...
```

Better:

```python
backend = ocr_backend_registry.create(config)
outputs = backend.run(inputs)
```

Small registry conditionals are allowed. Pipeline conditionals are not.

---

### Rule 5 — Keep legacy prepare logic

Do not replace the original author’s subtitle preparation strategy with naive OCR-every-frame logic.

Preserve:

- crop zone mapped to original video coordinates
- frame skip
- brightness threshold
- SSIM frame filtering
- detection pass
- grid stitching
- unstitching boxes
- tight-box SSIM
- frame-to-timestamp mapping
- dual-zone support if possible
- subtitle merge logic

---

### Rule 6 — GUI is a client, not the brain

The GUI calls services.

The GUI must not:

- parse OCR model output
- own pipeline algorithms
- own project schema
- decide subtitle timing
- directly mutate JSONL artifacts without service layer

GUI should call:

```python
ProjectService
PrepareService
OcrService
ReviewService
PackageService
```

---

### Rule 7 — CLI parity

Every major GUI action must have a CLI equivalent.

If a feature cannot be run from CLI, it is not finished.

Required CLI groups:

```text
vocra project
vocra prepare
vocra ocr
vocra review
vocra package
vocra inspect
```

---

### Rule 8 — Raw output is sacred

Always preserve raw OCR backend output.

Never only store cleaned text.

This allows:

- debugging
- re-normalization
- model comparison
- audit
- future parser improvements

---

### Rule 9 — Rerun creates a new run unless explicitly overwriting

Prepare rerun should create a new prepare run or require explicit overwrite.

OCR rerun should create a new OCR run or resume a run.

Package rerun should create a new package run unless output overwrite is explicit.

Do not silently destroy artifacts.

---

### Rule 10 — No hidden network OCR

Any backend that sends images outside the local machine must be clearly labeled.

Default assumption:

```text
local-first
```

Google Lens, cloud OpenAI, remote endpoints, or any non-local service must be explicit.

---

## 3. Recommended architecture

```text
vocra/
  __init__.py

  cli/
    main.py
    project_cmd.py
    prepare_cmd.py
    ocr_cmd.py
    review_cmd.py
    package_cmd.py
    inspect_cmd.py

  app/
    main.py
    state.py
    services.py

  gui/
    main_window.py
    project_tab.py
    prepare_tab.py
    ocr_tab.py
    review_tab.py
    package_tab.py
    logs_tab.py
    widgets/
      video_preview.py
      crop_canvas.py
      segment_table.py
      ocr_config_panel.py

  core/
    project/
      schema.py
      workspace.py
      manifest.py
      jsonl.py
      migrations.py

    video/
      probe.py
      capture.py
      preview.py
      timestamps.py

    prepare/
      config.py
      crop.py
      sampler.py
      frame_filter.py
      stitch.py
      detector.py
      segmenter.py
      writer.py
      service.py

    ocr/
      config.py
      inputs.py
      outputs.py
      registry.py
      service.py
      normalizer.py
      backends/
        base.py
        openai_compatible.py
        llamacpp_cli.py
        ollama.py
        local_command.py
        paddleocr.py
        fake.py

    review/
      service.py
      quality.py

    package/
      srt.py
      ass.py
      service.py

  legacy/
    videocr_notes.md
    extracted_algorithms.md

  tests/
    unit/
    integration/
    fixtures/
```

---

## 4. Core data models

Use dataclasses or Pydantic models. Be consistent.

### Project model

```python
@dataclass(frozen=True)
class SourceVideo:
    path: Path
    fingerprint: str
    duration_ms: int
    width: int
    height: int
    fps: float
    start_time_offset_ms: float = 0.0

@dataclass(frozen=True)
class Project:
    project_id: str
    name: str
    root: Path
    source: SourceVideo
    schema_version: int = 1
```

### Crop model

```python
@dataclass(frozen=True)
class CropZone:
    zone_idx: int
    x: int
    y: int
    width: int
    height: int
```

### Segment model

```python
@dataclass(frozen=True)
class SubtitleSegment:
    segment_id: str
    zone_idx: int
    start_ms: int
    end_ms: int
    start_frame_idx: int
    end_frame_idx: int
    representative_image: Path
    source_frame_indices: tuple[int, ...]
    detection_boxes: tuple[tuple[tuple[float, float], ...], ...]
    status: str = "prepared"
```

### OCR input/output

```python
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
```

---

## 5. Backend interface

All OCR backends must implement:

```python
class OcrBackend(Protocol):
    name: str

    def validate_config(self, config: dict[str, Any]) -> None:
        ...

    def test_connection(self, config: dict[str, Any]) -> BackendTestResult:
        ...

    def run(
        self,
        inputs: Iterable[OcrInput],
        config: dict[str, Any],
        progress: ProgressSink | None = None,
    ) -> Iterable[OcrOutput]:
        ...
```

Backends must not write directly to project artifacts unless explicitly designed as streaming writers. Prefer returning outputs to `OcrService`.

---

## 6. Initial OCR backends

Implement in this order:

1. `fake`
   - returns deterministic text for tests
2. `local-command`
   - generic command template
3. `openai-compatible-vision`
   - supports llama.cpp server and compatible APIs
4. `ollama`
   - local Ollama API
5. `llamacpp-cli`
   - direct llama-cli execution
6. `paddleocr`
   - fallback / legacy compatibility

---

## 7. Prepare detector strategy

Initial Prepare should keep PaddleOCR text detection because the original pipeline relies on detection boxes for filtering.

Do not confuse this with OCR recognition.

Prepare detector:

```text
finds text boxes
helps identify duplicate subtitles
helps select representative images
```

OCR backend:

```text
reads text from representative images
```

Later, detector can also become pluggable:

```python
class TextDetectorBackend(Protocol):
    def detect(self, images: Iterable[DetectionInput]) -> Iterable[DetectionOutput]:
        ...
```

---

## 8. Services

### ProjectService

Responsible for:

- create project
- open project
- validate project schema
- load/save project metadata
- resolve artifact paths

### PrepareService

Responsible for:

- load prepare config
- run prepare pipeline
- resume prepare
- write prepare artifacts
- report summary

### OcrService

Responsible for:

- build OCR inputs from `subtitle_segments.jsonl`
- create OCR run folder
- call backend
- write raw outputs
- write normalized outputs
- resume failed/missing segments

### ReviewService

Responsible for:

- read normalized OCR
- read/write review state
- provide filters and quality flags

### PackageService

Responsible for:

- join segments + OCR/review text
- produce SRT/ASS
- write package report

---

## 9. JSONL rules

Use JSONL for large lists.

Rules:

- one object per line
- append-friendly
- flush often
- write temp file then atomic rename for final outputs where possible
- include `schema_version` in config files
- include `run_id` in run outputs
- validate required fields when reading

---

## 10. Progress events

Use typed progress events.

```python
@dataclass(frozen=True)
class ProgressEvent:
    stage: str
    message: str
    current: int | float | None = None
    total: int | float | None = None
    percent: float | None = None
    segment_id: str | None = None
```

Stages:

```text
project
prepare.probe
prepare.sample
prepare.detect
prepare.filter
prepare.segment
prepare.write
ocr.start
ocr.segment
ocr.write
review.save
package.srt
error
```

Do not parse human log text for internal progress unless temporarily wrapping legacy code.

---

## 11. Testing rules

### Must-have tests

Before large refactors:

```text
tests/unit/test_project_workspace.py
tests/unit/test_jsonl.py
tests/unit/test_time_utils.py
tests/unit/test_crop_coordinate_mapping.py
tests/unit/test_segment_contract.py
tests/unit/test_srt_packager.py
tests/unit/test_fake_ocr_backend.py
```

Before OCR backend work:

```text
tests/unit/test_openai_compatible_backend.py
tests/unit/test_ollama_backend.py
tests/unit/test_local_command_backend.py
```

Before prepare pipeline changes:

```text
tests/integration/test_prepare_with_synthetic_frames.py
tests/integration/test_prepare_to_package_fake_ocr.py
```

### Golden test

Create a tiny fixture project:

```text
tests/fixtures/projects/simple.vocra/
```

Expected:

```text
prepare/subtitle_segments.jsonl
ocr/runs/fake/normalized_text.jsonl
package/runs/fake/output.srt
```

---

## 12. Migration from legacy VideOCR

Use legacy code as an algorithm source.

Suggested extraction map:

| Legacy file | Keep | New location |
|---|---|---|
| `VideOCR.py` crop drawing | concept only | `gui/widgets/crop_canvas.py` |
| `VideOCR.py` video preview | yes | `gui/widgets/video_preview.py`, `core/video/preview.py` |
| `CLI/videocr/video.py` frame decode | yes | `core/prepare/sampler.py` |
| `CLI/videocr/video.py` crop/scale | yes | `core/prepare/crop.py` |
| `CLI/videocr/video.py` SSIM filter | yes | `core/prepare/frame_filter.py` |
| `CLI/videocr/video.py` stitch/unstitch | yes | `core/prepare/stitch.py` |
| `CLI/videocr/video.py` text detection pass | yes | `core/prepare/detector.py` |
| `CLI/videocr/video.py` subtitle generation | yes | `core/package/srt.py` and `core/prepare/segmenter.py` |
| `CLI/videocr/models.py` text models | adapt | `core/prepare/models.py`, `core/package/models.py` |
| `CLI/videocr/utils.py` time helpers | yes | `core/video/timestamps.py` |
| `VideOCR.py` one-click orchestration | no | replace with stage services |

---

## 13. Implementation order for agents

Do not start with GUI.

Start with core contracts and CLI.

Recommended order:

1. project workspace
2. JSONL utilities
3. segment model
4. fake prepare fixture
5. fake OCR backend
6. SRT packager
7. CLI package command
8. OCR service
9. OpenAI-compatible backend
10. Prepare pipeline extraction
11. GUI shell
12. GUI project tab
13. GUI prepare tab
14. GUI OCR tab
15. GUI review tab
16. GUI package tab

---

## 14. Coding style

Use:

- Python 3.11+ if starting fresh
- type hints
- dataclasses or Pydantic
- pathlib
- structured logging
- small modules
- explicit config objects

Avoid:

- global mutable state
- giant event loops
- magic strings scattered everywhere
- hidden side effects
- swallowing exceptions
- mixing UI and core

---

## 15. Safety around external commands

External command execution must:

- log command safely
- avoid shell=True unless absolutely required
- support timeout
- capture stdout/stderr
- write error logs
- handle cancellation
- stream progress if possible

For local command backend, templates must be validated.

---

## 16. Review checklist for every PR

Before claiming completion:

```text
[ ] Does this preserve project artifacts?
[ ] Does this avoid GUI-core coupling?
[ ] Does this preserve timing ownership in Prepare?
[ ] Can this be called from CLI?
[ ] Are raw outputs preserved?
[ ] Is the module under size limits?
[ ] Is there a test?
[ ] Are errors visible and logged?
[ ] Can the stage be resumed or rerun safely?
```

---

## 17. Forbidden shortcuts

Never do these:

```text
- Add a new OCR model directly inside the Prepare pipeline.
- Make OCR rerun require re-decoding the whole video.
- Store prepared segments only in memory.
- Let package stage infer timing from OCR text.
- Build a one-click-only GUI.
- Hide intermediate artifacts from the user.
- Overwrite prepare/OCR/package runs silently.
- Require a specific OCR model as the only path.
- Remove the author’s filtering/timestamp logic.
```

---

## 18. Final instruction to AI agents

When uncertain, preserve artifacts and split responsibility.

The correct architecture is not “fastest to demo”. The correct architecture is:

```text
stable prepare artifacts
replaceable OCR backends
reviewable text
deterministic packaging
```

Build for that.
