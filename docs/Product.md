# Product.md — What VOCra Should Become

## 1. Product identity

**VOCra** is a local-first hardcoded subtitle extraction workbench.

It helps users turn videos with burned-in subtitles into editable subtitle files, while giving power users full control over each processing stage.

It is not a one-click black box. It is a staged workspace.

---

## 2. One-sentence pitch

VOCra lets you prepare subtitle evidence from a video once, run any OCR model on it many times, review the result, and package accurate timestamped subtitles whenever you want.

---

## 3. Product promise

The app should promise:

```text
Your video analysis work is never lost.
Your OCR model is replaceable.
Your subtitle timing is preserved.
Your output is inspectable.
```

---

## 4. Target users

## 4.1 Casual viewer

Wants to watch foreign-language comedy, anime, shows, or videos with subtitles.

Needs:

- simple import
- crop subtitle area
- run prepare
- run recommended OCR
- export SRT
- minimal technical friction

## 4.2 Power user

Wants control over quality and model choice.

Needs:

- inspect prepared frames
- run multiple OCR models
- compare OCR runs
- rerun failed segments only
- manually correct text
- package multiple outputs

## 4.3 Developer / AI tinkerer

Wants to plug in llama.cpp, Ollama, DeepSeekOCR, PaddleOCR-VL GGUF, or custom OCR systems.

Needs:

- clean backend interface
- project artifact format
- CLI-first commands
- logs and raw outputs
- no monolithic GUI trap

---

## 5. Product positioning

VOCra is not:

- a subtitle downloader
- a translation app first
- a fully automatic black box
- a cloud OCR wrapper
- a clone of VideOCR with prettier UI

VOCra is:

- a persistent video OCR project system
- a modular OCR workbench
- a subtitle timing preservation tool
- a GUI + CLI for staged hardcoded subtitle extraction

---

## 6. Core workflow

The product should revolve around five visible stages:

```text
Project
Prepare
OCR
Review
Package
```

Each stage has a clear input and output.

### Stage 1 — Project

User creates or opens a `.vocra` project.

User sees:

- source video path
- video metadata
- project directory
- existing prepare runs
- existing OCR runs
- existing package outputs

### Stage 2 — Prepare

User defines how the video should be analyzed.

User can:

- preview video
- seek through timeline
- draw crop zones
- set time range
- set frame skip
- set SSIM threshold
- run Prepare

Output:

- representative subtitle images
- segment timeline
- detection boxes
- debug artifacts

### Stage 3 — OCR

User chooses which OCR backend to run on prepared segments.

User can:

- select llama.cpp server
- select Ollama
- select OpenAI-compatible endpoint
- select local command
- select PaddleOCR fallback
- test backend
- run OCR
- resume failed/empty segments
- keep multiple OCR runs

Output:

- raw OCR responses
- normalized OCR text
- per-segment errors

### Stage 4 — Review

User fixes quality.

User can:

- view each crop image
- view timestamp
- edit OCR text
- accept/reject
- filter suspicious segments
- compare OCR runs

Output:

- review state
- corrected text

### Stage 5 — Package

User exports final subtitle.

User can:

- choose OCR run
- choose review state
- choose output format
- preview subtitles
- export `.srt`

Output:

- subtitle file
- package report

---

## 7. Main screen concept

The app should feel like a production tool.

Top bar:

```text
[VOCra] [Open Project] [Create Project] [Save] [Settings]
Current project: Comedy_Show_EP01.vocra
```

Left sidebar:

```text
Project
Prepare
OCR
Review
Package
Logs
```

Main panel changes by stage.

Right inspector panel:

```text
Project status
Current config
Warnings
Stage outputs
```

Bottom log/progress bar:

```text
Prepare: 812/1420 frames analyzed | OCR: 103/534 segments | Errors: 2
```

---

## 8. Project dashboard

The Project tab should show:

```text
Source video
  Path: /videos/show.mkv
  Duration: 24:45
  Resolution: 1920x1080
  FPS: 23.976

Prepare
  Status: completed
  Segments: 534
  Representative images: 534
  Last run: 2026-05-24 14:30

OCR
  Runs:
    - llama.cpp / PaddleOCR-VL GGUF / 534 ok / 12 edited
    - Ollama / other model / 511 ok / 23 errors

Package
  Outputs:
    - output.en.srt
    - output.reviewed.en.srt
```

Project dashboard should make it obvious where the project stands.

---

## 9. Prepare tab UX

Prepare tab should be the place where the old author’s magic becomes visible.

Main areas:

### Video preview

- frame preview
- timeline slider
- crop zone overlay
- zoom/pan if possible

### Crop controls

- add crop zone
- clear crop zone
- dual zone mode
- full frame mode
- save crop zone

### Prepare settings

- start time
- end time
- frames to skip
- brightness threshold
- SSIM threshold
- tight-box SSIM threshold
- subtitle position
- detector backend

### Actions

```text
[Run Prepare]
[Resume Prepare]
[Open Prepared Images]
[Open Segment Manifest]
[View Debug Contact Sheet]
```

### Result summary

After Prepare:

```text
Frames scanned: 35200
Candidate subtitle frames: 1800
Segments prepared: 534
Duplicate frames removed: 1266
Representative images: 534
```

---

## 10. OCR tab UX

OCR tab should be model/backend focused.

Backend presets:

```text
llama.cpp server
llama.cpp CLI
Ollama
OpenAI-compatible vision endpoint
Local command
PaddleOCR fallback
```

For llama.cpp server:

```text
Endpoint: http://127.0.0.1:8080/v1
Model: PaddleOCR-VL-1.5-GGUF
Prompt: OCR this subtitle image. Return only the subtitle text.
Temperature: 0
Max tokens: 256
Timeout: 120 sec
```

Actions:

```text
[Test Backend]
[Run OCR]
[Stop]
[Resume Failed Only]
[Rerun Empty Only]
[Open Raw Outputs]
[Open Normalized Outputs]
```

OCR run list:

```text
Run ID | Backend | Model | OK | Empty | Error | Edited | Created
```

---

## 11. Review tab UX

Review should be fast.

Layout:

```text
Left: segment list
Center: crop image
Right: text editor + metadata
Bottom: shortcuts
```

Segment list should support filters:

```text
All
Unreviewed
Empty
Errors
Low confidence
Edited
Rejected
Suspicious
```

Keyboard shortcuts:

```text
Enter: accept
E: edit
R: reject
N: next
P: previous
Ctrl+S: save
```

Each segment view:

```text
Segment: seg_000123
Time: 00:01:21,234 --> 00:01:24,567
Zone: 0
Image: representative crop
OCR text: editable box
Raw output: expandable
Status: pending / accepted / edited / rejected
```

---

## 12. Package tab UX

Package tab should be simple.

Inputs:

- Prepare run
- OCR run
- Review state
- Output path
- Format

Options:

- skip empty text
- preserve line breaks
- merge adjacent identical text
- minimum subtitle duration
- dual-zone ordering
- include ASS alignment tags if applicable

Actions:

```text
[Preview SRT]
[Export SRT]
[Open Output Folder]
```

Preview should show:

```text
1
00:00:01,200 --> 00:00:03,500
Hello world.
```

---

## 13. Settings

Global settings:

- default project directory
- default OCR backend
- default llama.cpp endpoint
- default Ollama endpoint
- default prompt templates
- theme
- logging verbosity
- temp/cache directory
- max parallel OCR jobs
- auto-save interval

Project settings should override global settings.

---

## 14. Quality control features

The app should actively help users find bad OCR.

Suspicious conditions:

- empty OCR text
- very long text
- text with many replacement characters
- text with mostly punctuation
- repeated OCR text across many unrelated segments
- OCR backend error
- text confidence below threshold
- segment image likely contains text but OCR is empty

Future optional scoring:

```text
quality_score = detection_confidence + OCR_confidence + text_sanity_score
```

---

## 15. Multiple OCR runs

Multiple OCR runs are first-class.

A user can run:

```text
Run A: llama.cpp + PaddleOCR-VL GGUF
Run B: Ollama + another OCR VLM
Run C: DeepSeekOCR
Run D: PaddleOCR fallback
```

Then compare them.

Possible compare view:

```text
Segment image
Run A text
Run B text
Run C text
Choose winner
```

---

## 16. Translation is future, not core

Translation can be added later as another stage:

```text
Prepare
OCR
Review OCR
Translate
Review Translation
Package
```

Do not mix translation into the first version of OCR.

The first product must get extraction architecture right.

---

## 17. Product success criteria

The product is successful when:

- user can prepare once and close app
- user can reopen project and see prepared segments
- user can run OCR with llama.cpp/Ollama/custom backend
- user can switch OCR backend without re-preparing video
- user can package SRT from any OCR run
- timing remains stable across OCR runs
- failed OCR segments can be resumed
- raw outputs are preserved
- edited corrections are preserved
- app does not depend on one giant file

---

## 18. Product anti-goals

Do not build:

- a one-click-only app
- a workflow that stores critical state only in RAM
- an OCR-specific timeline generator
- a GUI that hides all intermediate artifacts
- a system where changing OCR model requires editing core pipeline
- a system where Prepare output is overwritten silently
- a system that cannot be used from CLI

---

## 19. Product personality

The app should feel:

```text
technical but clear
powerful but not chaotic
local-first
artifact-driven
recoverable
inspectable
model-agnostic
```

Not cute. Not magical. Not “trust me bro”.

---

## 20. Final product sentence

VOCra is a staged, persistent, model-agnostic hardcoded subtitle extraction workbench that preserves the original video timing logic while letting users run any OCR backend they want.
