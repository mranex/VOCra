# Phase 5: PySide6 GUI (2.5 hr)

## Goal
Build 5-scene desktop GUI: Setup → Process → Translator → Export → Config.

## Prerequisites
- Phase 1–4 completed (all vocra_core modules working)
- PySide6 6.11.1 installed

## Design Principles
- Dark theme, teal/cyan accent (#00BCD4)
- All processing runs in QThread (never block GUI)
- Scene navigation via sidebar buttons (vertical, icon + text)
- Single QStackedWidget swaps between 5 scenes

---

## 1. `vocra_gui/main_window.py`

```python
class VoCRAMainWindow(QMainWindow):
    """
    Layout: 
        [Sidebar 200px] | [Content QStackedWidget]
    
    Sidebar buttons:
        📁 Setup     → scene_setup (index 0)
        ⚙️ Process   → scene_process (index 1)
        🌐 Translate → scene_translator (index 2)
        📄 Export    → scene_export (index 3)
        🔧 Config    → scene_config (index 4)
    
    State management:
        self.project_dir: str | None  — current loaded project
        self.progress: dict | None    — loaded progress.json
    
    Methods:
        load_project(project_dir)  — loads progress, enables scenes
        create_project(...)        — calls project_manager, then load_project
        refresh_all_scenes()       — notify each scene to reload data
    
    Startup behavior:
        Show dialog: "Open Video (new project)" | "Open Project Folder (existing)"
    """

def run_app(argv):
    app = QApplication(argv)
    app.setStyleSheet(load_qss())
    window = VoCRAMainWindow()
    window.show()
    sys.exit(app.exec())
```

---

## 2. `vocra_gui/scene_setup.py` — Scene 1: Setup

```
┌─────────────────────────────────────────────────┐
│  [Load Video]  [Browse Project Dir]             │
│                                                 │
│  ┌─────────────────────────────────────┐        │
│  │                                     │        │
│  │     QMediaPlayer Video Preview      │        │
│  │     (with play/pause/seek bar)      │        │
│  │                                     │        │
│  │     [CROP OVERLAY when paused]      │        │
│  │                                     │        │
│  └─────────────────────────────────────┘        │
│                                                 │
│  Frame Interval: [___0.5___] sec  (QDoubleSpinBox)
│  Crop Region: x=120 y=820 w=1680 h=180 (read-only display)
│                                                 │
│  [✓ Create Project]                             │
└─────────────────────────────────────────────────┘
```

**Key widgets:**
- `video_preview.py`: QMediaPlayer + QVideoWidget for smooth playback
- `crop_overlay.py`: Transparent QWidget overlay, only active when paused
  - Mouse press → start drag
  - Mouse move → draw rectangle
  - Mouse release → store crop region (x, y, w, h)
  - Draw rectangle with dashed cyan border

**Behavior:**
- Load Video → set QMediaPlayer source → play
- User clicks pause → crop overlay becomes active
- User drags rectangle on paused frame → crop region saved
- Frame Interval: QDoubleSpinBox, range 0.1–5.0, step 0.1
- Create Project: validate (video loaded, crop set, project dir set) → create_project()

---

## 3. `vocra_gui/scene_process.py` — Scene 2: Process

```
┌─────────────────────────────────────────────────┐
│  Step Pipeline Indicator:                       │
│  [1.Extract ✅] → [2.Crop ✅] → [3.Draft OCR ⏳] → [4.Segment ⬜] → [5.Preprocess ⬜] → [6.Final OCR ⬜]
│                                                 │
│  ┌──── Buttons ──────────────────────┐          │
│  │ [▶ Prepare]  [▶ Draft OCR]       │          │
│  │ [▶ Final OCR]                     │          │
│  └───────────────────────────────────┘          │
│                                                 │
│  ┌──── Current Preview ──────────────┐          │
│  │ Image: [crop thumbnail]           │          │
│  │ OCR:   "detected text here..."    │          │
│  └───────────────────────────────────┘          │
│                                                 │
│  ┌──── Log Panel ────────────────────┐          │
│  │ [14:32:01] Extracting frame 142/600...       │
│  │ [14:32:02] Extracting frame 143/600...       │
│  │ ...                               │          │
│  └───────────────────────────────────┘          │
└─────────────────────────────────────────────────┘
```

**Button mapping:**
- **Prepare**: runs `extract_frames()` + `crop_frames()` sequentially in QThread
- **Draft OCR**: runs `run_draft_ocr()` + `build_segments()` + `preprocess_representatives()` in QThread
- **Final OCR**: runs `run_final_ocr()` in QThread

**QThread worker pattern:**
```python
class ProcessWorker(QThread):
    progress = Signal(int, int, str)   # current, total, message
    log_message = Signal(str)          # for log panel
    finished = Signal(bool, str)       # success, error_message
    preview_update = Signal(str, str)  # image_path, ocr_text
    
    def run(self):
        try:
            self.task_fn(callback=self._emit_progress)
            self.finished.emit(True, "")
        except Exception as e:
            self.finished.emit(False, str(e))
```

**Step indicator**: Custom widget with 6 circles connected by lines. Colors: ✅green=done, ⏳yellow=running, ⬜gray=pending.

---

## 4. `vocra_gui/scene_translator.py` — Scene 3: Translator (Optional)

```
┌─────────────────────────────────────────────────┐
│  Translation is OPTIONAL                        │
│                                                 │
│  Source: [auto ▼]  Target: [vi ▼]               │
│  Batch size: [300]                              │
│                                                 │
│  Total segments: 245                            │
│  Translated: 0 / 245                            │
│                                                 │
│  [▶ Start Translation]  [⏹ Stop]                │
│                                                 │
│  ┌──── Progress ─────────────────────┐          │
│  │ ████████░░░░░░░░░░ 34%           │          │
│  │ Batch 2/3 processing...           │          │
│  └───────────────────────────────────┘          │
│                                                 │
│  ┌──── Log Panel ────────────────────┐          │
│  │ [14:45:01] Translating batch 1 (300 items)   │
│  │ [14:45:30] Batch 1 done. Saved.              │
│  │ ...                               │          │
│  └───────────────────────────────────┘          │
└─────────────────────────────────────────────────┘
```

**Behavior:**
- Only enabled when `ocr_final_done == True`
- Source/Target: QComboBox with language codes
- Start Translation: runs `run_translation()` in QThread
- Resumable: shows already-translated count on load
- Stop button: sets cancel flag on worker thread

---

## 5. `vocra_gui/scene_export.py` — Scene 4: Export

```
┌─────────────────────────────────────────────────┐
│  Export Source: (●) Original OCR  (○) Translation│
│                                                 │
│  ┌──── Subtitle Table (QTableWidget) ──────────┐│
│  │ #  │ Start      │ End        │ Text         ││
│  │ 1  │ 00:00:01.0 │ 00:00:03.5 │ Hello world  ││
│  │ 2  │ 00:00:04.0 │ 00:00:06.0 │ How are you  ││
│  │ ... │           │            │              ││
│  └─────────────────────────────────────────────┘│
│                                                 │
│  Double-click text cell to edit inline          │
│  [Save Edits]                                   │
│                                                 │
│  [Export SRT]  [Export ASS]  [Export TXT]        │
└─────────────────────────────────────────────────┘
```

**Behavior:**
- Radio buttons switch between OCR text and translated text
- Table loads from: segments.json + timestamp.json + (ocr_fn.json | translation.json)
- Text column is editable (double-click)
- Save Edits: writes back to ocr_fn.json/translation.json with `edited: true`
- Export buttons: open file save dialog → call exporter functions

---

## 6. `vocra_gui/scene_config.py` — Scene 5: Config

```
┌─────────────────────────────────────────────────┐
│  ═══ Draft OCR ═══                              │
│  Language: [auto ▼]                             │
│                                                 │
│  ═══ Final OCR ═══                              │
│  Provider: [llama.cpp local ▼]                  │
│  Server URL: [http://127.0.0.1:8080]            │
│  Model: [_____________]                         │
│  Prompt: [OCR this subtitle...]                 │
│  Timeout: [120] Max tokens: [512] Temp: [0.0]   │
│                                                 │
│  ── llama.cpp Server ──                         │
│  Model path: [Browse...]                        │
│  mmproj path: [Browse...]                       │
│  GPU layers: [99]  Context: [8192]              │
│  [Create .bat] [Open folder] [Start] [Check ✓]  │
│                                                 │
│  ═══ Translator ═══                             │
│  Provider: [OpenAI-compatible ▼]                │
│  Base URL: [https://api.openai.com/v1]          │
│  API Key: [●●●●●●●●]                           │
│  Model: [gpt-4o-mini]                           │
│  Source: [auto]  Target: [vi]                   │
│  Batch size: [300]  Timeout: [120]              │
│  Style: [default ▼]                             │
│                                                 │
│  [Save Config]                                  │
└─────────────────────────────────────────────────┘
```

**Behavior:**
- All fields read from / write to progress.json (per-project config)
- Provider dropdown changes which fields are visible
- llama.cpp section: calls LlamaServerManager methods
- Save Config: update progress.json immediately
- Chrome Lens fields shown only when provider == chrome_lens

---

## 7. `vocra_gui/styles/theme.qss`

Dark theme key tokens:
- Background: `#1a1a2e`
- Surface: `#16213e`
- Card: `#0f3460`
- Accent: `#00bcd4`
- Text: `#e0e0e0`
- Text dim: `#888888`
- Success: `#4caf50`
- Warning: `#ff9800`
- Error: `#f44336`

---

## 8. Widgets

### `video_preview.py`
- QMediaPlayer + QVideoWidget
- Play/pause button, seek slider, time label
- Method: `capture_current_frame() -> QImage` (pause + grab frame via OpenCV)

### `crop_overlay.py`
- Transparent QWidget overlaid on video widget
- Only active when video is paused
- Mouse events: press/move/release → draw dashed cyan rectangle
- Emits signal: `crop_changed(x, y, w, h)`
- Scale-aware: maps widget coords to actual video resolution

### `log_panel.py`
- QPlainTextEdit, read-only
- Auto-scroll to bottom
- Timestamp prefix on each line
- Method: `append_log(message: str)`

### `subtitle_table.py`
- QTableWidget wrapper
- Load from combined cache data
- Editable text column
- Method: `get_edited_items() -> list[dict]`

### `progress_bar.py`
- Custom painted widget: 6 circles + connecting lines
- Each step: label + status color (gray/yellow/green)
- Method: `set_step_status(step_index, status)`

## Acceptance Criteria
- App launches with dark theme, 5 scenes navigable
- Scene 1: video plays smoothly, pause → crop works, project created
- Scene 2: all 3 buttons trigger correct pipeline steps, log shows progress
- Scene 3: translation runs in batches, resumable
- Scene 4: table shows subtitles, editable, export produces valid files
- Scene 5: config changes persist to progress.json
- No GUI freezing during processing (all QThread)
