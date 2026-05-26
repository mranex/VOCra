# Phase 2: Video Processing Pipeline (1.5 hr)

## Goal
Tách video → frames, crop subtitle region, chạy draft OCR trên toàn bộ crop.

## Prerequisites
- Phase 1 completed (progress.json exists, project dirs created)
- ffmpeg in PATH
- PaddleOCR 3.5.0 installed
- OpenCV installed

## Files to Create

---

### 1. `vocra_core/frame_extractor.py`

**Purpose:** Dùng ffmpeg subprocess để tách frame từ video theo interval.

```python
def extract_frames(project_dir: str, callback=None) -> int:
    """
    Args:
        project_dir: path to project
        callback: optional fn(current, total, message) for progress updates
    
    Logic:
        1. Load progress.json → get video_path, interval_sec, frames_dir
        2. Resolve absolute frames_dir = project_dir / frames_dir
        3. Nếu frames_dir đã có files VÀ status.frames_extracted == True → skip (return count)
        4. Build ffmpeg command:
           ffmpeg -i {video_path} -vf fps=1/{interval_sec} {frames_dir}/%06d.png
        5. Run subprocess, capture stderr for progress
        6. Sau khi xong, build timestamp.json:
           - List tất cả .png files, sort by name
           - Mỗi file: timestamp = (frame_number - 1) * interval_sec
           - Format timestamp: HH:MM:SS.mmm
        7. Save timestamp.json
        8. update_status("frames_extracted", True)
    
    Returns: total frame count
    """

def _build_timestamp(frame_name: str, interval_sec: float) -> str:
    """Convert '000001.png' → '00:00:00.000' based on interval."""
    # frame_number = int(frame_name.split('.')[0])
    # total_seconds = (frame_number - 1) * interval_sec
    # hours, remainder = divmod(total_seconds, 3600)
    # minutes, seconds = divmod(remainder, 60)
    # millis = int((seconds % 1) * 1000)
    # return f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}.{millis:03d}"
```

**timestamp.json output:**
```json
{
  "frames": [
    {"image": "000001.png", "timestamp": "00:00:00.000"},
    {"image": "000002.png", "timestamp": "00:00:00.500"}
  ]
}
```

---

### 2. `vocra_core/cropper.py`

**Purpose:** Crop subtitle region từ mỗi frame.

```python
def crop_frames(project_dir: str, callback=None) -> int:
    """
    Logic:
        1. Load progress.json → subtitle_crop (x, y, w, h), frames_dir, cropped_dir
        2. List tất cả .png trong frames_dir
        3. Với mỗi frame:
           - cv2.imread(frame_path)
           - crop = img[y:y+h, x:x+w]
           - cv2.imwrite(cropped_dir / frame_name, crop)
           - callback(current, total, frame_name)
        4. Skip files đã crop (check exists in cropped_dir)
        5. update_status("cropped_done", True)
    
    Returns: total cropped count
    """
```

**Key:** Resumable — skip nếu cropped file đã tồn tại.

---

### 3. `vocra_core/draft_ocr_providers.py`

**Purpose:** Pluggable draft OCR backend abstraction.

```python
from typing import Protocol

class DraftOCRProvider(Protocol):
    def initialize(self) -> None: ...
    def recognize(self, image_path: str) -> tuple[str, float]: ...  # (text, confidence)
    def close(self) -> None: ...

class PaddleOCRDraftProvider:
    """Default provider using PaddleOCR v5."""
    
    def __init__(self, language: str = "auto"):
        self._engine = None
        self._language = language
    
    def initialize(self):
        # Lazy init — PaddleOCR tốn RAM, chỉ init 1 lần
        from paddleocr import PaddleOCR
        lang = "ch" if self._language == "auto" else self._language
        self._engine = PaddleOCR(use_angle_cls=True, lang=lang)
    
    def recognize(self, image_path: str) -> tuple[str, float]:
        result = self._engine.ocr(image_path, cls=True)
        if not result or not result[0]:
            return ("", 0.0)
        # Gom tất cả text lines, tính avg confidence
        lines = []
        total_conf = 0.0
        count = 0
        for line in result[0]:
            text = line[1][0]  # text content
            conf = line[1][1]  # confidence
            lines.append(text)
            total_conf += conf
            count += 1
        full_text = " ".join(lines)
        avg_conf = total_conf / count if count > 0 else 0.0
        return (full_text, round(avg_conf, 4))
    
    def close(self):
        self._engine = None

def create_draft_provider(config: dict) -> DraftOCRProvider:
    provider = config.get("provider", "paddleocr")
    if provider == "paddleocr":
        return PaddleOCRDraftProvider(language=config.get("language", "auto"))
    raise ValueError(f"Unknown draft OCR provider: {provider}")
```

---

### 4. `vocra_core/draft_ocr.py`

**Purpose:** Orchestrate draft OCR trên toàn bộ cropped images.

```python
def run_draft_ocr(project_dir: str, callback=None) -> int:
    """
    Logic:
        1. Load progress.json → draft_ocr config, cropped_dir
        2. Create draft provider via create_draft_provider()
        3. provider.initialize()
        4. Load existing ocr_og.json nếu có (để resume)
        5. List tất cả .png trong cropped_dir, sort by name
        6. Với mỗi image:
           - Skip nếu đã có trong ocr_og.json
           - text, confidence = provider.recognize(image_path)
           - Append to items list
           - Mỗi 50 items → save ocr_og.json (crash resume)
           - callback(current, total, text_preview)
        7. Final save ocr_og.json
        8. provider.close()
        9. update_status("ocr_origin_done", True)
    
    Returns: total OCR'd count
    """
```

**ocr_og.json output:**
```json
{
  "items": [
    {"image": "000001.png", "text": "hello world", "confidence": 0.71},
    {"image": "000002.png", "text": "", "confidence": 0.0}
  ]
}
```

## Acceptance Criteria
- `extract_frames()`: creates N .png files + valid timestamp.json
- `crop_frames()`: creates N cropped .png files matching crop region
- `run_draft_ocr()`: creates ocr_og.json with entry per cropped image
- All functions are resumable (skip existing work)
- All functions emit progress via callback
- progress.json status updated after each step completes
