# `vocra_translator` V1 Plan

## Summary
Xây một app desktop mini trong `vocra_translator/` chuyên dịch subtitle file, tách khỏi pipeline OCR/video của VoCRA nhưng tái sử dụng lõi translator hiện có. V1 hỗ trợ import `SRT/ASS/VTT`, hiển thị subtitle theo dạng editor bảng `time + source + translation`, nhập bối cảnh và translator config, chạy dịch theo batch, cho phép sửa bản dịch, rồi export lại file cùng format gốc hoặc convert sang format khác.

Các quyết định đã chốt:
- Dùng `PySide6`, cùng stack desktop với VoCRA.
- `vocra_translator` có config/secrets global riêng, không dùng chung namespace với VoCRA.
- Mỗi job là một `project folder`, có thể resume.
- `ASS` preserve theo hướng best-effort.
- Editor chính là bảng side-by-side, `source` readonly, `translation` editable.
- Export hỗ trợ `same format` và `convert`.

## Key Changes
### App structure
- App riêng trong `vocra_translator/` với entrypoint riêng.
- Reuse provider/prompt translator từ `vocra_core.translator.*`.
- Có `settings.json` và `secrets.json` riêng cho app mới.

### Project model
- Mỗi project folder có:
  - `project.json`
  - `source/`
  - `cache/document.json`
  - `cache/translation.json`
  - `exports/`
- `project.json` lưu source file, format, translator snapshot, context và status.
- Translation cache có signature dựa trên provider/model/language/style/context + hash của source entries.

### Neutral subtitle interfaces
- `SubtitleEntry`
- `SubtitleDocument`
- `TranslationCacheRow`
- Registry/adapter cho `SRT`, `VTT`, `ASS`

### Format behavior
- `SRT`: parse cue index, time range, multiline text; export regenerate numbering.
- `VTT`: preserve `WEBVTT`, cue settings, `NOTE/STYLE/REGION` blocks khi export cùng format.
- `ASS`: preserve raw sections, event order, override tags và `\N` theo best-effort.
- Convert `ASS -> SRT/VTT` flatten style thành plain text.
- Convert `SRT/VTT -> ASS` dùng template ASS chuẩn hóa.

### Translation flow
- Batch unit là `1 subtitle entry = 1 translation item`.
- Batch requests giữ thứ tự entries.
- UI translation có provider/model/base URL/API key, source/target, style/custom prompt, context, batch size, timeout, progress, log, cancel.
- Cache row lưu `entry_id`, `source_snapshot`, `translation`, `status`, `edited`.

### UI shape
- `Project`: import subtitle file hoặc mở project folder.
- `Translate`: bảng side-by-side + translator controls + log/progress.
- `Export`: review translation, chọn source text và target format, export file.
- `Config`: global defaults cho translator app.

## Public Interfaces / Types
- `SubtitleEntry`
- `SubtitleDocument`
- `SubtitleFormatAdapter`
- `TranslationCacheRow`
- `project.json` manifest
- `translation signature`

## Test Plan
- Parse/export round-trip cho `SRT`, `VTT`, `ASS`.
- Signature đổi khi context/source đổi.
- Cache reuse và stale marking.
- ASS preserve tags và line breaks.
- Convert `SRT -> ASS`.

## Assumptions and Defaults
- V1 không sửa app `vocra` hiện tại.
- Source text mặc định readonly.
- `Dialogue` là unit chính để dịch trong ASS.
- Export source mặc định là `translation`.
- Cross-format export là best-effort.
