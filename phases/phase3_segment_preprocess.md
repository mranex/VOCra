# Phase 3: Segment Grouping + Preprocess (1 hr)

## Goal
Gom subtitle trùng lặp thành segments, rồi preprocess ảnh đại diện cho Final OCR.

## Prerequisites
- Phase 2 completed: `ocr_og.json` + `timestamp.json` + cropped images exist

## Files to Create

---

### 1. `vocra_core/segmenter.py`

**Purpose:** So sánh OCR nháp liên tiếp, gom trùng lặp, tạo segments.

```python
import difflib

def build_segments(project_dir: str, similarity_threshold: float = 0.5, callback=None) -> int:
    """
    Logic:
        1. Load ocr_og.json → items list (sorted by image name)
        2. Initialize: current_group = [items[0]]
        3. Iterate items[1:]:
           a. Compare current item text vs last item in current_group
              using difflib.SequenceMatcher.ratio()
           b. Nếu ratio >= threshold AND cả hai text đều non-empty:
              → append to current_group (same subtitle continues)
           c. Nếu text rỗng (blank frame):
              → close current_group → emit segment
              → start new group khi gặp text non-empty tiếp theo
           d. Nếu ratio < threshold:
              → close current_group → emit segment
              → start new group với current item
        4. Close final group
        5. Cho mỗi segment:
           - id: sequential 1-based
           - start_image: first image in group
           - end_image: last image in group
           - represent_image: first image in group (= start_image)
           - source: "ocr_og"
        6. Save segments.json
        7. update_status("segments_done", True)
    
    Returns: segment count
    """

def _pick_representative(group_items: list[dict]) -> str:
    """Lấy frame đầu tiên làm đại diện. Frame đầu ổn định nhất vì nếu blur/noise thì OCR thô đã không match."""
    return group_items[0]["image"]
```

**segments.json output:**
```json
{
  "segments": [
    {
      "id": 1,
      "start_image": "000088.png",
      "end_image": "000094.png",
      "represent_image": "000090.png",
      "source": "ocr_og"
    }
  ]
}
```

**Edge cases to handle:**
- Liên tiếp nhiều blank frames → skip, không tạo segment
- Video bắt đầu bằng blank → skip đến frame có text đầu tiên
- Segment chỉ có 1 frame → vẫn valid
- Text gần giống nhưng có 1-2 ký tự khác (OCR noise) → gom lại

---

### 2. `vocra_core/preprocessor.py`

**Purpose:** Enhance ảnh đại diện để Final OCR đọc tốt hơn.

```python
import cv2
import numpy as np

def preprocess_representatives(project_dir: str, callback=None) -> int:
    """
    Logic:
        1. Load segments.json → lấy danh sách represent_image
        2. Với mỗi represent_image:
           a. Read từ cache/cropped/{represent_image}
           b. Apply preprocessing pipeline:
              - Convert to grayscale
              - CLAHE (clipLimit=2.0, tileGridSize=8x8) → enhance contrast
              - Upscale 2x dùng cv2.INTER_CUBIC
              - Nếu mean pixel value > 128 (text tối trên nền sáng):
                → giữ nguyên
              - Nếu mean pixel value <= 128 (text sáng trên nền tối = phổ biến):
                → cv2.bitwise_not (đảo màu) → text tối trên nền sáng
           c. Save vào cache/preprocessed/{represent_image}
           d. callback(current, total, represent_image)
        3. update_status("preprocessed_done", True)
    
    Returns: preprocessed count
    """

def _preprocess_single(image_path: str) -> np.ndarray:
    """Single image preprocessing pipeline."""
    img = cv2.imread(image_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # CLAHE
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    
    # Upscale 2x
    h, w = enhanced.shape
    upscaled = cv2.resize(enhanced, (w * 2, h * 2), interpolation=cv2.INTER_CUBIC)
    
    # Auto-invert: if mostly dark (white text on dark bg), invert
    if np.mean(upscaled) <= 128:
        upscaled = cv2.bitwise_not(upscaled)
    
    return upscaled
```

## Acceptance Criteria
- `build_segments()`: 1200 OCR items → ~100-300 segments (significant reduction)
- Blank frames don't create segments
- `represent_image` has highest confidence in its group
- `preprocess_representatives()`: creates enhanced images only for represent_images
- Preprocessed images are grayscale, 2x size, contrast-enhanced
- White-on-dark text auto-inverted to dark-on-white
- Both functions resumable and emit progress callbacks
