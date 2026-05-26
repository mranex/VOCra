# Phase 1: Scaffold + Cache Architecture (30 min)

## Goal
Tạo skeleton project, entry point, và module quản lý `progress.json`.

## Prerequisites
- Python 3.11, PySide6 installed
- `c:\Nghich\vocra\` là workspace root

## Files to Create

### 1. `main.py`
Entry point duy nhất.

```python
# Behavior:
# - No args → launch PySide6 GUI (Phase 5)
# - Phase 1 chỉ cần stub: print("VoCRA starting...") rồi sys.exit()

import sys

def main():
    from vocra_gui.main_window import run_app
    run_app(sys.argv)

if __name__ == "__main__":
    main()
```

### 2. `vocra_core/__init__.py`
Empty init.

### 3. `vocra_core/project_manager.py`

**Functions required:**

```python
def create_project(video_path: str, project_dir: str, subtitle_crop: dict, frame_interval: float) -> dict:
    """
    Tạo project mới.
    
    Args:
        video_path: absolute path to video file (mp4/mkv)
        project_dir: absolute path to project output folder
        subtitle_crop: {"x": int, "y": int, "width": int, "height": int}
        frame_interval: seconds between frames (user-configurable)
    
    Actions:
        1. Tạo project_dir nếu chưa có
        2. Tạo subdirs: cache/frames, cache/cropped, cache/preprocessed
        3. Tạo progress.json với full structure
        4. Copy app-level default config (final_ocr, translator) vào progress.json
    
    Returns: loaded progress dict
    """

def load_project(project_dir: str) -> dict:
    """Load progress.json từ project_dir. Raise nếu không tìm thấy."""

def update_status(project_dir: str, step: str, value: bool) -> None:
    """Update 1 field trong progress.status. Save file ngay."""

def get_cache_path(project_dir: str, cache_key: str) -> str:
    """Resolve absolute path cho cache file (timestamp, ocr_origin, segments, ocr_final, translation)."""

def save_progress(project_dir: str, progress: dict) -> None:
    """Write progress dict to progress.json with indent=2."""
```

**progress.json full schema:**

```json
{
  "project_name": "video_001",
  "video_path": "C:/videos/input.mp4",
  "project_dir": "C:/projects/video_001",
  "subtitle_crop": {
    "x": 120, "y": 820, "width": 1680, "height": 180
  },
  "frame_extract": {
    "interval_sec": 0.5,
    "frames_dir": "cache/frames",
    "cropped_dir": "cache/cropped",
    "preprocessed_dir": "cache/preprocessed"
  },
  "cache_files": {
    "timestamp": "cache/timestamp.json",
    "ocr_origin": "cache/ocr_og.json",
    "segments": "cache/segments.json",
    "ocr_final": "cache/ocr_fn.json",
    "translation": "cache/translation.json"
  },
  "status": {
    "setup_done": true,
    "frames_extracted": false,
    "cropped_done": false,
    "ocr_origin_done": false,
    "segments_done": false,
    "preprocessed_done": false,
    "ocr_final_done": false,
    "translation_done": false,
    "export_done": false
  },
  "draft_ocr": {
    "provider": "paddleocr",
    "language": "auto"
  },
  "final_ocr": {
    "provider": "openai_compatible",
    "server_url": "http://127.0.0.1:8080",
    "model": "",
    "timeout": 120,
    "temperature": 0,
    "max_tokens": 512,
    "prompt": "OCR this subtitle image. Return only the subtitle text.",
    "llama_cpp_dir": "tools/",
    "model_path": "",
    "mmproj_path": "",
    "gpu_layers": 99,
    "ctx_size": 8192,
    "chrome_lens_language": "auto",
    "chrome_lens_headless": true,
    "chrome_lens_max_retries": 3
  },
  "translator": {
    "enabled": false,
    "provider": "openai_compatible",
    "base_url": "",
    "api_key": "",
    "model": "",
    "source_lang": "auto",
    "target_lang": "vi",
    "batch_size": 300,
    "timeout": 120,
    "temperature": 0.3,
    "max_tokens": 4096,
    "style": "default",
    "custom_prompt": "",
    "json_mode": true,
    "max_retries": 2
  }
}
```

### 4. `vocra_core/default_config.json`
App-level template config. `create_project()` reads this as defaults for `final_ocr` and `translator` sections.

### 5. Directory stubs
- `vocra_gui/__init__.py`
- `vocra_gui/main_window.py` (stub: `def run_app(argv): print("GUI stub")`)
- `vocra_core/final_ocr/__init__.py`
- `vocra_core/translator/__init__.py`
- `tools/` (empty dir, README.md saying "Put llama.cpp binary here")

## Acceptance Criteria
- [x] `python main.py` runs without crash
- [x] `create_project()` creates dirs + writes valid `progress.json`
- [x] `load_project()` reads it back correctly
- [x] `update_status()` modifies single field and saves
- [x] All paths in progress.json are relative to project_dir (except video_path)
