# Plan.md — Detailed Implementation Plan for VOCra

## 0. Executive summary

Build a new application, **VOCra**, inspired by VideOCR but architecturally different.

The app must be:

```text
project-based
stage-based
artifact-driven
OCR-backend-agnostic
CLI-controllable
GUI-friendly
```

The key product rule:

```text
Prepare once. OCR many times. Package anytime.
```

The key technical rule:

```text
Prepare owns timing. OCR owns text. Package joins them.
```

---

## 1. Phase overview

```text
Phase 1  — Repo bootstrap and project schema
Phase 2  — Core artifact system
Phase 3  — Package SRT from prepared artifacts
Phase 4  — OCR service with fake backend
Phase 5  — OpenAI-compatible / llama.cpp server backend
Phase 6  — Ollama and local-command backend
Phase 7  — Legacy Prepare extraction
Phase 8  — Prepare artifact generation
Phase 9  — Review/correction layer
Phase 10 — GUI shell
Phase 11 — Full GUI workflow
Phase 12 — Quality tools and compare OCR runs
Phase 13 — Packaging/build/release
```

The plan intentionally starts with contracts and artifacts before GUI.

---

## 2. Phase 1 — Bootstrap new app

### Goal

Create a clean project skeleton for VOCra.

### Tasks

1. Create package layout:

```text
vocra/
  __init__.py
  cli/
  app/
  gui/
  core/
  tests/
```

2. Add tooling:

```text
pyproject.toml
ruff
mypy or pyright
pytest
pre-commit optional
```

3. Add basic command:

```bash
vocra --version
```

4. Add root docs:

```text
Design.md
Product.md
Agent.md
Plan.md
README.md
```

### Acceptance criteria

- `python -m vocra.cli.main --version` works.
- `pytest` runs.
- `ruff check .` runs.
- Package imports without side effects.
- No GUI dependency imported by core modules.

---

## 3. Phase 2 — Project workspace and schema

### Goal

Implement `.vocra` project directories.

### Tasks

1. Create `core/project/schema.py`.

Models:

```python
SourceVideo
ProjectMetadata
ProjectPaths
```

2. Create `core/project/workspace.py`.

Functions:

```python
create_project(video_path: Path, project_root: Path) -> Project
open_project(project_root: Path) -> Project
validate_project(project_root: Path) -> None
resolve_paths(project_root: Path) -> ProjectPaths
```

3. Create `core/video/probe.py`.

Responsibilities:

- probe video duration
- width/height
- fps
- start offset
- fingerprint

4. CLI:

```bash
vocra project create --video input.mkv --project input.vocra
vocra project inspect --project input.vocra
```

### Output files

```text
project.json
source/source_ref.json
logs/app.log
```

### Acceptance criteria

- User can create a project from a video.
- Project can be reopened.
- Project metadata survives app restart.
- Invalid/missing source video gives clear error.
- Test exists for project creation/opening.

---

## 4. Phase 3 — Artifact utilities

### Goal

Build safe read/write primitives for JSON, JSONL, and run folders.

### Tasks

1. Create `core/project/jsonl.py`.

Functions:

```python
read_jsonl(path) -> Iterator[dict]
append_jsonl(path, obj) -> None
write_jsonl_atomic(path, rows) -> None
```

2. Create `core/project/runs.py`.

Functions:

```python
new_run_id(prefix: str) -> str
create_prepare_run(project, name=None) -> Path
create_ocr_run(project, backend_name) -> Path
create_package_run(project, format_name) -> Path
```

3. Create `core/project/manifest.py`.

Responsibilities:

- write schema version
- read config files
- validate required fields

### Acceptance criteria

- JSONL append works.
- Atomic write works.
- Run IDs are unique.
- Tests cover corrupted JSONL, missing fields, and run folder creation.

---

## 5. Phase 4 — Segment and package contracts

### Goal

Define `SubtitleSegment` and package `.srt` from prepared segment + fake OCR text before real prepare exists.

### Tasks

1. Create `core/prepare/models.py`.

```python
CropZone
SubtitleSegment
DetectionBox
PrepareSummary
```

2. Create `core/ocr/models.py`.

```python
OcrInput
OcrOutput
OcrRunSummary
```

3. Create `core/package/srt.py`.

Functions:

```python
format_srt_timestamp(ms: int) -> str
build_srt(segments, text_by_segment, options) -> str
```

4. Create `core/package/service.py`.

```python
package_srt(project, prepare_run, ocr_run, output_path, options)
```

5. Add fake fixture:

```text
tests/fixtures/prepared/simple/subtitle_segments.jsonl
tests/fixtures/ocr/simple/normalized_text.jsonl
```

6. CLI:

```bash
vocra package srt \
  --project input.vocra \
  --prepare-run prepare_default \
  --ocr-run fake \
  --output output.srt
```

### Acceptance criteria

- SRT can be generated from fixtures.
- Timestamp formatting is correct.
- Empty text policy works.
- Segment ordering is stable.
- Tests cover SRT output exactly.

---

## 6. Phase 5 — OCR service with fake backend

### Goal

Create OCR backend architecture before real model integration.

### Tasks

1. Create `core/ocr/backends/base.py`.

Protocol:

```python
OcrBackend
BackendTestResult
```

2. Create `core/ocr/registry.py`.

```python
register_backend(name, factory)
create_backend(config)
```

3. Create `core/ocr/backends/fake.py`.

Fake backend:

- returns `Text for {segment_id}`
- optionally simulates errors

4. Create `core/ocr/service.py`.

Responsibilities:

- read `subtitle_segments.jsonl`
- build `OcrInput`
- create OCR run folder
- call backend
- write raw output
- write normalized output
- write errors
- write run report

5. CLI:

```bash
vocra ocr run \
  --project input.vocra \
  --prepare-run prepare_default \
  --backend fake
```

### Acceptance criteria

- Fake OCR run creates all expected files.
- Resume skips already completed segments.
- Failed segments can be rerun.
- Package can use fake OCR output.
- Integration test: fixture prepare -> fake OCR -> package SRT.

---

## 7. Phase 6 — OpenAI-compatible vision backend

### Goal

Support llama.cpp server and other OpenAI-compatible local vision endpoints.

### Tasks

1. Create `core/ocr/backends/openai_compatible.py`.

Config:

```python
endpoint: str
api_key: str | None
model: str
prompt_template: str
temperature: float
max_tokens: int
timeout_sec: int
```

2. Implement request builder:

- load image
- base64 encode
- send image + prompt
- receive chat completion
- extract text

3. Implement response normalizer.

4. Implement backend test:

```python
test_connection(config)
```

5. Add CLI options:

```bash
vocra ocr run \
  --backend openai-compatible-vision \
  --endpoint http://127.0.0.1:8080/v1 \
  --model PaddleOCR-VL-1.5-GGUF \
  --prompt-template "OCR this subtitle image. Return only text."
```

6. Add config file support:

```bash
vocra ocr run --config ocr_llamacpp.json
```

### Acceptance criteria

- Backend can run against mocked HTTP server.
- Raw response is preserved.
- Normalized text is written.
- Per-segment errors are recorded.
- Timeout is handled cleanly.
- No package stage changes required.

---

## 8. Phase 7 — Ollama backend

### Goal

Support Ollama as another local OCR backend.

### Tasks

1. Create `core/ocr/backends/ollama.py`.

Config:

```python
endpoint: str = "http://127.0.0.1:11434"
model: str
prompt_template: str
temperature: float
timeout_sec: int
```

2. Implement image request to Ollama API.

3. Normalize response.

4. Add CLI:

```bash
vocra ocr run \
  --backend ollama \
  --endpoint http://127.0.0.1:11434 \
  --model hf.co/PaddlePaddle/PaddleOCR-VL-1.5-GGUF
```

### Acceptance criteria

- Mocked Ollama test passes.
- Raw response is preserved.
- Errors per segment are recorded.
- OCR service does not care whether backend is Ollama or OpenAI-compatible.

---

## 9. Phase 8 — Local command backend

### Goal

Support arbitrary OCR tools.

### Tasks

1. Create `core/ocr/backends/local_command.py`.

Config:

```python
command_template: str
stdout_format: "plain_text" | "json"
timeout_sec: int
working_dir: Path | None
```

Example:

```json
{
  "backend": "local-command",
  "command_template": "my-ocr --image {image} --lang {lang}",
  "stdout_format": "plain_text",
  "timeout_sec": 120
}
```

2. Implement safe command execution:

- no shell by default
- template validation
- timeout
- stdout/stderr capture

3. Normalize output.

### Acceptance criteria

- Local command backend works with test echo script.
- Timeout is handled.
- stderr is logged.
- Command injection risk is minimized.

---

## 10. Phase 9 — Legacy Prepare extraction research

### Goal

Study and extract original VideOCR preparation logic into independent modules.

### Source logic to preserve

From legacy `CLI/videocr/video.py` and utilities:

- video properties
- capture/read frames
- crop/scale with PyAV filter graph
- frame skip
- brightness threshold
- SSIM filtering
- stitch grids
- PaddleOCR text detection pass
- parse detection output
- unstitch polygons
- group similar text boxes
- tight-box SSIM
- representative image selection
- frame timestamp mapping
- subtitle timing

### Tasks

1. Create `legacy/extracted_algorithms.md`.

Document:

- old function/class
- purpose
- new module target
- invariants
- tests needed

2. Create modules:

```text
core/prepare/sampler.py
core/prepare/crop.py
core/prepare/frame_filter.py
core/prepare/stitch.py
core/prepare/detector.py
core/prepare/segmenter.py
core/prepare/writer.py
```

3. Start with pure utilities:

- crop coordinate validation
- scale calculation
- timestamp conversion
- SSIM helpers
- stitch/unstitch mapping

### Acceptance criteria

- Legacy algorithm notes exist.
- Pure utilities have tests.
- No GUI dependency.
- No OCR recognition dependency.

---

## 11. Phase 10 — Prepare detector backend

### Goal

Implement the detection part needed by Prepare.

Initial detector:

```text
PaddleOCR text detection
```

This is not the same as OCR recognition.

### Tasks

1. Create `core/prepare/detectors/base.py`.

```python
class TextDetectorBackend(Protocol):
    def detect_grids(self, image_dir: Path, output_dir: Path, config: dict) -> DetectionResult:
        ...
```

2. Create `core/prepare/detectors/paddle.py`.

Move/adapt old command:

```text
paddleocr text_detection --input ... --model_dir ... --save_path ...
```

3. Parse JSON outputs.

4. Convert boxes back to segmenter-friendly format.

5. Add fake detector for tests.

### Acceptance criteria

- Fake detector works in tests.
- Paddle detector is isolated from Prepare orchestration.
- Detection output parser has fixture tests.
- Detection backend can be swapped later.

---

## 12. Phase 11 — Prepare pipeline implementation

### Goal

Create durable Prepare output.

### Tasks

1. Create `core/prepare/config.py`.

```python
PrepareConfig
```

2. Create `core/prepare/service.py`.

Main function:

```python
run_prepare(project, config, detector_backend, progress) -> PrepareRunSummary
```

3. Implement pipeline:

```text
probe source
load crop zones
decode frames
crop/scale subtitle zones
apply brightness threshold
apply SSIM skip
stitch detection grids
run detector
parse/unstitch boxes
group by text-box layout
tight-box SSIM
select representative images
write subtitle_segments.jsonl
write detection_boxes.jsonl
write frame_index.jsonl
write summary
```

4. Add debug mode:

```text
write contact sheets
write rejected frames
write detection overlays
```

5. CLI:

```bash
vocra prepare run \
  --project input.vocra \
  --crop-zone 130,780,1660,220 \
  --frames-to-skip 1 \
  --ssim-threshold 0.92 \
  --detector paddleocr-text-detection
```

### Acceptance criteria

- Prepare creates project artifacts.
- Prepare can be run without OCR.
- Prepared images can be inspected.
- Segment manifest has stable IDs.
- Timing survives app restart.
- Package with fake OCR works on prepared output.
- Cancellation leaves recoverable partial state if possible.

---

## 13. Phase 12 — Review layer

### Goal

Allow corrections independent of OCR run.

### Tasks

1. Create `core/review/service.py`.

Functions:

```python
load_review_items(project, ocr_run)
save_review_edit(project, ocr_run, segment_id, edited_text, status)
filter_review_items(...)
```

2. Create `core/review/quality.py`.

Quality flags:

- empty text
- OCR error
- suspicious punctuation
- repeated text
- too long
- too short
- unreviewed

3. CLI:

```bash
vocra review list --project input.vocra --ocr-run run_id --filter errors
vocra review set --project input.vocra --ocr-run run_id --segment seg_001 --text "..."
```

### Acceptance criteria

- Review edits are stored in `review_state.jsonl`.
- Package uses edited text.
- Package can ignore rejected segments.
- Tests cover edited/rejected/accepted behavior.

---

## 14. Phase 13 — GUI shell

### Goal

Create GUI skeleton after CLI/core works.

Recommended GUI tech:

- PySide6 if starting fresh and wanting stronger long-term UI
- PySimpleGUI only if speed matters and dependency constraints are acceptable

Given this is a new app, prefer **PySide6** unless there is a strong reason not to.

### Tasks

1. Create `gui/main_window.py`.

Layout:

```text
Top project bar
Left sidebar tabs
Main stage panel
Right inspector
Bottom log/progress
```

2. Create tabs:

```text
project_tab.py
prepare_tab.py
ocr_tab.py
review_tab.py
package_tab.py
logs_tab.py
```

3. Create app state:

```python
AppState
```

4. GUI calls services only.

### Acceptance criteria

- GUI opens.
- User can open project.
- Project dashboard displays status.
- No pipeline code in GUI files.
- No OCR backend parsing in GUI files.

---

## 15. Phase 14 — GUI Project tab

### Goal

Project creation/opening in GUI.

### Tasks

- create project dialog
- open project dialog
- source video display
- artifact status summary
- recent projects
- open project folder button

### Acceptance criteria

- User can create project from GUI.
- User can reopen project.
- Dashboard reflects existing artifacts.
- Missing source video warning is clear.

---

## 16. Phase 15 — GUI Prepare tab

### Goal

Visual prepare workflow.

### Tasks

1. Video preview widget:

- seek slider
- frame display
- original coordinate mapping

2. Crop canvas:

- draw zone
- move/resize zone
- dual-zone support
- clear zone

3. Prepare config panel:

- time start/end
- frames to skip
- SSIM threshold
- detector backend
- debug mode

4. Actions:

- run prepare
- stop prepare
- open prepared images
- open manifest

5. Results summary.

### Acceptance criteria

- User can draw crop.
- Crop is saved in original video coordinates.
- User can run Prepare from GUI.
- GUI remains responsive.
- Progress/logs appear.
- Result summary appears after completion.

---

## 17. Phase 16 — GUI OCR tab

### Goal

Run OCR backends from GUI.

### Tasks

1. Prepare run selector.
2. Backend selector.
3. Dynamic backend config panel.
4. Test backend button.
5. Run OCR button.
6. Resume failed button.
7. OCR runs table.

Backend presets:

```text
OpenAI-compatible / llama.cpp server
Ollama
llama.cpp CLI
Local command
Fake
```

### Acceptance criteria

- User can configure local llama.cpp endpoint.
- User can test backend.
- User can run OCR.
- User can resume failed/empty segments.
- OCR run artifacts appear in table.

---

## 18. Phase 17 — GUI Review tab

### Goal

Fast correction workflow.

### Tasks

- segment list
- image preview
- text editor
- raw output viewer
- filters
- accept/edit/reject
- keyboard shortcuts
- save review state

### Acceptance criteria

- User can edit OCR text.
- Edits persist after restart.
- Filters work.
- Package uses edited text.

---

## 19. Phase 18 — GUI Package tab

### Goal

Export SRT.

### Tasks

- select prepare run
- select OCR run
- select review state
- package config
- preview SRT
- export SRT
- open output folder

### Acceptance criteria

- SRT exports from GUI.
- Output matches CLI package result.
- Empty/rejected policies work.
- Package report is written.

---

## 20. Phase 19 — OCR run comparison

### Goal

Enable model experimentation.

### Tasks

- select multiple OCR runs
- compare text per segment
- choose preferred text
- save chosen text to review state

Comparison view:

```text
Image
Timing
Run A text
Run B text
Run C text
Chosen text
```

### Acceptance criteria

- User can compare at least two OCR runs.
- User can choose winner per segment.
- Chosen text packages correctly.

---

## 21. Phase 20 — Polish and packaging

### Goal

Make app usable outside dev environment.

### Tasks

- app icon
- settings page
- default backend presets
- project migration checks
- crash logs
- build script
- README quickstart
- troubleshooting docs

### Acceptance criteria

- Fresh user can create project and run fake OCR demo.
- Power user can configure llama.cpp/Ollama backend.
- Logs are findable.
- Errors are understandable.

---

## 22. Suggested first milestone

Milestone 1 should not include real video processing.

Milestone 1:

```text
Project create/open
Fake prepared segments fixture
Fake OCR backend
Package SRT
CLI end-to-end
```

Command demo:

```bash
vocra project create --video sample.mp4 --project sample.vocra
vocra dev seed-prepare --project sample.vocra
vocra ocr run --project sample.vocra --prepare-run seeded --backend fake
vocra package srt --project sample.vocra --ocr-run fake --output sample.srt
```

Why:

This proves the artifact architecture before touching hard video logic.

---

## 23. Suggested second milestone

Milestone 2:

```text
OpenAI-compatible OCR backend
Ollama backend
Local command backend
OCR resume
Raw + normalized output
```

This proves the replaceable OCR idea.

---

## 24. Suggested third milestone

Milestone 3:

```text
Legacy Prepare extraction
Real video -> subtitle_segments.jsonl
Prepared images -> OCR backend
Package SRT
```

This brings back the original author’s magic.

---

## 25. Suggested fourth milestone

Milestone 4:

```text
GUI shell
Project tab
Prepare tab
OCR tab
Package tab
```

Review tab can follow after basic GUI workflow works.

---

## 26. Risks and mitigations

### Risk: Prepare extraction becomes too hard

Mitigation:

- extract in small pure modules
- keep a legacy adapter temporarily
- test with synthetic frames
- compare output against old CLI on same video

### Risk: OCR model APIs vary wildly

Mitigation:

- raw output preservation
- backend-specific normalizers
- local-command generic fallback
- OpenAI-compatible first

### Risk: GUI becomes another monolith

Mitigation:

- service layer first
- one tab per file
- no algorithm in GUI
- enforce file size limits

### Risk: artifact schema changes

Mitigation:

- schema_version
- migrations
- manifest validation
- no silent reinterpretation

### Risk: users accidentally overwrite work

Mitigation:

- run IDs
- explicit overwrite
- archive old runs
- project status dashboard

---

## 27. Final target checklist

VOCra v1 is complete when:

```text
[ ] User can create/open .vocra project.
[ ] User can prepare video into persistent subtitle segments.
[ ] Prepare uses crop-zone + detection + de-dup + timestamp logic.
[ ] User can run at least one local OCR backend.
[ ] User can use llama.cpp/OpenAI-compatible endpoint.
[ ] User can use Ollama or local-command backend.
[ ] OCR raw outputs are preserved.
[ ] OCR normalized outputs are preserved.
[ ] User can review/edit text.
[ ] User can export SRT from selected OCR run.
[ ] User can close app after Prepare and resume later.
[ ] User can switch OCR model without rerunning Prepare.
[ ] CLI supports every major stage.
[ ] GUI supports the normal workflow.
[ ] Core has tests.
```

---

## 28. Final implementation principle

Do not chase “one-click complete app” first.

Build the durable chain:

```text
Project schema
  -> Prepare artifacts
  -> OCR artifacts
  -> Review artifacts
  -> Package output
```

Once this chain is correct, the GUI can become pleasant.

If the chain is wrong, no GUI can save the product.
