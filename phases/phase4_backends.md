# Phase 4: Final OCR + Translator + Exporter (2 hr)

## Goal
Build pluggable Final OCR backends, translator backends, và SRT/ASS/TXT exporter.

## Prerequisites
- Phase 3 completed: segments.json + preprocessed images exist
- Reference: `mmt_core/ocr_providers.py`, `mmt_core/deepseek_ocr_client.py`, `mmt_core/llama_server.py`
- Reference: `translator/base.py`, `translator/openai_compatible_translator.py`

---

## Part A: Final OCR Backends

### 1. `vocra_core/final_ocr/base.py`

```python
from typing import Protocol, Any

class FinalOCRProvider(Protocol):
    provider_key: str
    
    def validate(self) -> None:
        """Check server reachable. Raise on failure."""
        ...
    
    def recognize_image(self, image_path: str) -> dict:
        """
        Returns: {
            "text": "recognized text",
            "confidence": None,  # float or None
            "provider": "openai_compatible",
            "raw": {}  # raw response for debugging
        }
        """
        ...
    
    def close(self) -> None: ...
    def metadata(self) -> dict: ...
```

### 2. `vocra_core/final_ocr/openai_compatible.py`

**Reuse pattern from** `deepseek_ocr_client.py`. Key differences: configurable model name, configurable prompt.

```python
class OpenAICompatibleOCRProvider:
    """
    Dùng cho: OpenAI API, llama.cpp local, LM Studio, self-hosted VLM.
    
    Init args (from progress.json final_ocr section):
        server_url, model, timeout, max_tokens, temperature, prompt
    
    Core method: recognize_image(image_path)
        1. Read image → base64 encode
        2. POST {server_url}/v1/chat/completions
           payload: model, messages[{role:user, content:[image_url, text:prompt]}],
                    temperature, max_tokens
        3. Parse response.choices[0].message.content
        4. Clean text via text_cleaner
        5. Return {"text": cleaned, "confidence": None, "provider": "openai_compatible", "raw": response}
    
    validate():
        GET {server_url}/health OR {server_url}/v1/models → check 2xx
    """
```

### 3. `vocra_core/final_ocr/llama_server_manager.py`

**Simplified from** `mmt_core/llama_server.py`. Only these functions:

```python
class LlamaServerManager:
    """
    Init: llama_cpp_dir, model_path, mmproj_path, host, port, gpu_layers, ctx_size, temperature
    
    Methods:
        build_bat_content() -> str     # Generate run_server.bat content
        write_run_server_bat() -> Path # Write to servers/ dir
        check_health() -> (bool, str)  # Probe /health endpoint
        open_server_folder() -> Path   # os.startfile() the folder
        start_external() -> Path       # os.startfile() the bat file
        resolve_binary_path() -> Path  # Find llama-server.exe in tools/
    """
```

### 4. `vocra_core/final_ocr/chrome_lens.py`

```python
class ChromeLensOCRProvider:
    """
    Optional. Wraps chrome-lens-py.
    
    Init: language, headless, chrome_path, user_data_dir, max_retries, timeout
    
    validate(): check chrome-lens-py installed (try import)
    recognize_image(): async call → run in event loop → return same dict format
    
    Graceful fallback: if chrome-lens-py not installed, raise clear error message.
    """
```

### 5. `vocra_core/final_ocr/provider_factory.py`

```python
def create_final_ocr_provider(config: dict) -> FinalOCRProvider:
    provider = config.get("provider", "openai_compatible")
    if provider in ("openai_compatible", "llama_cpp"):
        return OpenAICompatibleOCRProvider(config)  # Same client, different server_url
    if provider == "chrome_lens":
        return ChromeLensOCRProvider(config)
    raise ValueError(f"Unknown final OCR provider: {provider}")
```

### 6. `vocra_core/text_cleaner.py`

**Reuse from** `deepseek_ocr_client._clean_output()`:

```python
def clean_ocr_text(text: str) -> str:
    """
    1. Strip whitespace
    2. Remove markdown code fences (```...```)
    3. Try parse as JSON → extract "text"/"ocr"/"content"/"result" key
    4. Remove prefixes: "OCR:", "Text:", "Recognized text:", "Output:"
    5. Normalize newlines
    """
```

### 7. `vocra_core/run_final_ocr.py`

**Orchestrator function:**

```python
def run_final_ocr(project_dir: str, force: bool = False, callback=None) -> int:
    """
    Logic:
        1. Load progress.json, segments.json
        2. Load existing ocr_fn.json (for resume)
        3. Create provider via factory
        4. provider.validate()
        5. For each segment:
           - Get represent_image
           - Find preprocessed image: cache/preprocessed/{represent_image}
           - If already in ocr_fn.json and not force → skip
           - result = provider.recognize_image(preprocessed_path)
           - Append to ocr_fn items
           - Save ocr_fn.json after EACH item (crash resume)
           - callback(current, total, result["text"][:50])
        6. provider.close()
        7. update_status("ocr_final_done", True)
    """
```

**ocr_fn.json output:**
```json
{
  "items": [
    {
      "image": "000088.png",
      "segment_id": 1,
      "text": "Hello world.",
      "confidence": null,
      "status": "done",
      "error": "",
      "raw_ocr_text": "",
      "provider": "openai_compatible",
      "edited": false
    }
  ]
}
```

---

## Part B: Translator Backends

### 8. `vocra_core/translator/base.py`

**Copy pattern from** `translator/base.py` with subtitle-specific style presets:

```python
class BaseTranslator:
    LANG_NAMES = {"ja": "Japanese", "zh": "Chinese", "ko": "Korean",
                  "en": "English", "vi": "Vietnamese", ...}
    STYLE_PRESETS = {
        "default": "",
        "formal": "Use formal, polite language.",
        "casual": "Use casual, natural everyday language.",
        "keep_honorifics": "Keep honorifics untranslated.",
        "literal": "Translate meaning accurately.",
    }
```

### 9. `vocra_core/translator/openai_compatible.py`

**Reuse from** `translator/openai_compatible_translator.py`. Key adaptation for subtitles:

```python
class OpenAICompatibleTranslator(BaseTranslator):
    """
    translate_batch(texts: list[str], source, target) -> list[str]
    
    Prompt pattern:
        System: "You are a subtitle translator. Translate from {source} to {target}."
        User: JSON {"items": [{"index": 0, "text": "..."}]}
        Expected: JSON {"items": [{"index": 0, "translation": "..."}]}
    
    Structured output:
        - json_mode=True (default) → sends response_format: {"type": "json_object"}
        - Forces model to output valid JSON
        - Config field in progress.json: translator.json_mode
    
    Fallback khi JSON parse fail (theo thứ tự):
        1. Strip markdown code fences (```json...```)
        2. Extract first JSON object/array from response text
        3. Nếu vẫn fail → retry (max_retries lần, default 2)
        4. Nếu hết retry → raise error, log raw response để debug
    
    Config: base_url, api_key, model, temperature, max_tokens, timeout, json_mode, max_retries
    """
```

### 10. `vocra_core/translator/llama_local.py`

```python
class LlamaLocalTranslator(BaseTranslator):
    """Same as OpenAICompatibleTranslator but server_url points to local llama.cpp.
    No api_key needed. Inherits or wraps OpenAICompatibleTranslator."""
```

### 11. `vocra_core/translator/provider_factory.py`

```python
def create_translator(config: dict) -> BaseTranslator:
    provider = config.get("provider", "openai_compatible")
    if provider == "openai_compatible":
        return OpenAICompatibleTranslator(...)
    if provider == "llama_local":
        return LlamaLocalTranslator(...)
    raise ValueError(...)
```

### 12. `vocra_core/run_translator.py`

```python
def run_translation(project_dir: str, force: bool = False, callback=None) -> int:
    """
    Logic:
        1. Load ocr_fn.json → get all segment texts
        2. Load existing translation.json (resume)
        3. Create translator via factory
        4. Split untranslated items into batches of batch_size (default 300)
        5. For each batch:
           - texts = [item["text"] for item in batch]
           - translations = translator.translate_batch(texts, source, target)
           - Merge into translation.json
           - Save translation.json after each batch
           - callback(batch_num, total_batches, "Batch N done")
        6. update_status("translation_done", True)
    """
```

**translation.json output:**
```json
{
  "source_lang": "ja",
  "target_lang": "vi",
  "items": [
    {
      "segment_id": 1,
      "image": "000088.png",
      "original": "こんにちは世界",
      "translation": "Xin chào thế giới",
      "status": "done",
      "edited": false
    }
  ]
}
```

---

## Part C: Exporter

### 13. `vocra_core/exporter.py`

```python
def export_srt(project_dir: str, output_path: str, use_translation: bool = False) -> str:
    """
    Combine: segments.json + timestamp.json + (ocr_fn.json OR translation.json)
    
    For each segment:
        start_time = timestamp_lookup[segment.start_image]
        end_time   = timestamp_lookup[segment.end_image]
        text       = ocr_fn[segment.represent_image] or translation[segment_id]
    
    SRT format:
        1
        00:00:01,000 --> 00:00:03,500
        Hello world.
    """

def export_ass(project_dir, output_path, use_translation=False) -> str:
    """ASS format with basic [V4+ Styles] section."""

def export_txt(project_dir, output_path, use_translation=False) -> str:
    """Plain text: [timestamp] text per line."""
```

**Timestamp conversion:** `"00:00:01.500"` → SRT `"00:00:01,500"` (dot→comma)

## Acceptance Criteria
- OpenAI-compatible provider: validate + recognize works against any /v1/chat/completions server
- LlamaServerManager: generates valid run_server.bat, health check works
- ChromeLens: graceful error if not installed
- run_final_ocr: resumable, saves after each item
- Translator: batch 300, resumable, saves after each batch
- Exporter: valid SRT/ASS/TXT output with correct timestamps
