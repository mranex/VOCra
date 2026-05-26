# Ý tưởng app Video Subtitle Extractor

## Mục tiêu

Làm một công cụ OCR subtitle từ video theo hướng tách từng bước rõ ràng, có thể kiểm soát quá trình xử lý, có thể nâng cấp OCR, có thể export subtitle, và sau này có thể nâng cấp thêm translator ngay trong app.

Ý tưởng chính: không gom toàn bộ workflow vào một file hoặc một nút xử lý mù mờ. Mỗi bước xử lý tạo ra kết quả riêng, lưu tiến trình riêng, để khi cần sửa hoặc chạy lại thì chỉ chạy đúng phần cần chạy.

---

## Quy trình xử lý

### Bước 0: Setup video và vùng subtitle

Người dùng load video vào app.

Người dùng chọn vùng subtitle trên video bằng cách crop subtitle area.

Toàn bộ thông tin setup được lưu vào một file gọi là `process.json`.

File này lưu các thông tin cần thiết để các bước sau biết video nào đang được xử lý, vùng subtitle nằm ở đâu, thư mục project ở đâu, và các kết quả xử lý đang nằm ở đâu.

---

## Bổ sung: Kiến trúc file progress và cache

App nên sử dụng cache dạng file, tuyệt đối không phụ thuộc vào RAM để giữ dữ liệu quan trọng trong quá trình xử lý.

Các dữ liệu quan trọng như timestamp, kết quả OCR thô, kết quả OCR tinh luyện, và kết quả gom nhóm subtitle phải được lưu thành các file riêng biệt. Mục tiêu là mỗi loại dữ liệu có một trách nhiệm rõ ràng, dễ kiểm tra, dễ sửa, dễ chạy lại từng bước, và tránh việc OCR lỗi làm ảnh hưởng đến timestamp hoặc ngược lại.

Bộ file lõi của project gồm:

- `progress.json`
- `timestamp.json`
- `ocr_og.json`
- `segments.json`
- `ocr_fn.json`

### `progress.json`

`progress.json` là file giữ config ban đầu và trạng thái xử lý của project.

File này lưu các thông tin như:

- video đang xử lý
- thư mục project
- vùng crop subtitle chính xác
- nơi lưu frame gốc
- nơi lưu ảnh crop subtitle
- nơi lưu ảnh preprocess
- đường dẫn tới các file cache khác
- trạng thái từng bước đã chạy hay chưa

`progress.json` không nên chứa dữ liệu OCR dài và không nên chứa toàn bộ timestamp chi tiết. Nó chỉ đóng vai trò là bản đồ tổng thể của project.

Ví dụ cấu trúc:

```json
{
  "project_name": "video_001",
  "video_path": "/videos/input.mp4",
  "project_dir": "/projects/video_001",
  "subtitle_crop": {
    "x": 120,
    "y": 820,
    "width": 1680,
    "height": 180
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
    "ocr_final": "cache/ocr_fn.json"
  },
  "status": {
    "setup_done": true,
    "frames_extracted": false,
    "cropped_done": false,
    "ocr_origin_done": false,
    "segments_done": false,
    "ocr_final_done": false,
    "export_done": false
  }
}
```

### `timestamp.json`

`timestamp.json` chỉ lưu quan hệ giữa tên ảnh và timestamp.

File này không chứa OCR text.

Ví dụ:

```json
{
  "frames": [
    {
      "image": "000001.png",
      "timestamp": "00:00:00.000"
    },
    {
      "image": "000002.png",
      "timestamp": "00:00:00.500"
    },
    {
      "image": "000003.png",
      "timestamp": "00:00:01.000"
    }
  ]
}
```

Đây là nguồn dữ liệu chính cho timeline. Nếu OCR sai thì chỉ sửa OCR, không ảnh hưởng tới timestamp.

### `ocr_og.json`

`ocr_og.json` là cache OCR gốc, hay còn gọi là OCR nháp/origin.

File này chỉ lưu tên ảnh và text OCR thô. Nó không lưu timestamp.

Ví dụ:

```json
{
  "items": [
    {
      "image": "000001.png",
      "text": "hello world",
      "confidence": 0.71
    },
    {
      "image": "000002.png",
      "text": "hello wor1d",
      "confidence": 0.66
    }
  ]
}
```

Mục đích của file này là phục vụ bước so sánh nhanh, gom dòng trùng lặp, và chọn ảnh đại diện cho subtitle.

### `segments.json`

`segments.json` lưu kết quả gom nhóm subtitle sau khi so sánh OCR nháp.

File này là cầu nối giữa ảnh đại diện, ảnh bắt đầu, ảnh kết thúc, timestamp và OCR final.

Ví dụ:

```json
{
  "segments": [
    {
      "id": 1,
      "start_image": "000088.png",
      "end_image": "000094.png",
      "represent_image": "000088.png",
      "source": "ocr_og"
    },
    {
      "id": 2,
      "start_image": "000095.png",
      "end_image": "000104.png",
      "represent_image": "000095.png",
      "source": "ocr_og"
    }
  ]
}
```

Khi cần tính thời gian bắt đầu và kết thúc của subtitle, app sẽ lấy `start_image` và `end_image` từ `segments.json`, sau đó tra timestamp tương ứng trong `timestamp.json`.

### `ocr_fn.json`

`ocr_fn.json` là cache OCR tinh luyện/final.

File này chỉ lưu tên ảnh và text OCR cuối cùng. Nó không lưu timestamp.

Ví dụ:

```json
{
  "items": [
    {
      "image": "000088.png",
      "text": "Hello world.",
      "confidence": 0.94,
      "edited": false
    },
    {
      "image": "000095.png",
      "text": "This is the final subtitle text.",
      "confidence": 0.91,
      "edited": true
    }
  ]
}
```

File này là nguồn subtitle text cuối cùng để review và export.

### Nguyên tắc tách cache

Các file cache phải được tách trách nhiệm rõ ràng:

- `progress.json`: config project và trạng thái xử lý
- `timestamp.json`: tên ảnh và timestamp
- `ocr_og.json`: tên ảnh và OCR thô
- `segments.json`: nhóm subtitle, ảnh bắt đầu, ảnh kết thúc, ảnh đại diện
- `ocr_fn.json`: tên ảnh và OCR final

Không lưu cache quan trọng trong RAM.

Không trộn timestamp vào OCR.

Không trộn OCR thô và OCR final.

Không để `progress.json` phình to thành nơi chứa mọi dữ liệu xử lý.

### Review và export cuối cùng

Ở bước review and export, app sẽ không lấy dữ liệu từ một file duy nhất.

App sẽ kết hợp dữ liệu theo logic:

```text
segments.json + timestamp.json + ocr_fn.json => subtitle hoàn chỉnh
```

Cách lấy dữ liệu:

- `segments.json` xác định subtitle bắt đầu ở ảnh nào, kết thúc ở ảnh nào, và ảnh đại diện là ảnh nào.
- `timestamp.json` cung cấp thời gian bắt đầu và kết thúc dựa trên tên ảnh.
- `ocr_fn.json` cung cấp nội dung subtitle final dựa trên ảnh đại diện.

Ví dụ:

```text
segment.start_image -> timestamp bắt đầu
segment.end_image -> timestamp kết thúc
segment.represent_image -> text trong ocr_fn.json
```

Kết quả cuối cùng được dùng để export ra các định dạng như SRT, ASS hoặc TXT.

---

### Bước 1: Tách video thành nhiều frame theo cấp độ giây

Tách video thành các frame theo khoảng thời gian cố định.

Mức cơ bản:

- 1 giây 1 ảnh.

Mức ngon hơn:

- 0.5 giây 1 ảnh.

Ví dụ:

- Video 10 phút = 600 giây.
- Nếu lấy 1 giây 1 ảnh thì có khoảng 600 ảnh.
- Nếu lấy 0.5 giây 1 ảnh thì có khoảng 1200 ảnh.

Mục tiêu của bước này là tạo ra một tập ảnh đại diện cho timeline của video.

---

### Bước 2: Crop vùng subtitle từ các frame

Dựa vào vùng subtitle đã thiết lập ở Bước 0 trong `process.json`.

Crop toàn bộ các frame đã tách ở Bước 1.

Kết quả là một tập ảnh chỉ chứa vùng subtitle.

Ví dụ:

- Input: 1200 ảnh frame gốc.
- Output: 1200 ảnh đã được crop vùng subtitle.

---

### Bước 3: OCR nháp bằng model nhẹ và nhanh

Dùng một model OCR siêu nhẹ, tốc độ nhanh.

OCR thô có thể sử dụng PaddleOCR v5.

Khi code, phần OCR thô nên được thiết kế như một backend có thể thay thế, để sau này có thể đổi PaddleOCR v5 sang model khác như EasyOCR hoặc Tesseract mà không ảnh hưởng tới các bước còn lại.

Chạy OCR trên toàn bộ ảnh crop subtitle.

Kết quả là bản thảo OCR nháp của toàn bộ các frame.

Ví dụ:

- 1200 ảnh crop.
- Output: 1200 dòng OCR nháp.

Mục tiêu của bước này không phải là OCR thật chính xác, mà là tạo dữ liệu nháp để so sánh và gom các subtitle trùng lặp.

---

### Bước 4: So sánh nhanh và gom các dòng trùng lặp

Dùng cách so sánh nhanh như regex hoặc phương pháp tương tự.

Không cần dùng AI ở bước này.

So sánh các dòng OCR nháp với nhau.

Nếu các dòng có mức trùng lặp ký tự khoảng 50% hoặc theo một ngưỡng được đặt trước, coi như chúng thuộc cùng một subtitle.

Khi gặp một nhóm trùng lặp, lấy frame đầu tiên của nhóm đó làm đại diện.

Ghi lại timestamp tương ứng.

Ví dụ:

- Từ 1200 ảnh ban đầu.
- Sau khi gom trùng lặp, còn khoảng 200 ảnh đại diện.

Kết quả của bước này là danh sách các subtitle nháp kèm timestamp.

---

### Bước 5: Preprocess các ảnh đại diện

Dựa vào timestamp và danh sách ảnh đại diện đã có ở Bước 4.

Lấy khoảng 200 ảnh crop đại diện.

Preprocess các ảnh này để chuẩn bị cho OCR xịn.

Các thao tác có thể là:

- upscale
- đảo màu
- tăng chất lượng ảnh
- xử lý ảnh để chữ dễ đọc hơn

Mục tiêu là làm cho ảnh đủ chất lượng để OCR xịn đọc tốt hơn.

---

### Bước 6: OCR xịn bằng model mạnh

Đẩy toàn bộ ảnh đã preprocess ở Bước 5 qua OCR xịn.

OCR xịn có thể là VLM hoặc một model OCR mạnh khác.

Kết quả là bản OCR xịn hơn, sạch hơn, chính xác hơn so với bản nháp.

Ví dụ:

- Input: khoảng 200 ảnh đã preprocess.
- Output: khoảng 200 dòng subtitle OCR chất lượng cao.

#### Ghi chú triển khai OCR xịn

OCR xịn chỉ chạy sau khi đã có `segments.json` và ảnh đại diện đã preprocess.

Không chạy OCR xịn trên toàn bộ frame.

Luồng dữ liệu chính:

```text
segments.json
+ cache/preprocessed/ảnh đại diện
        ↓
final OCR backend
        ↓
ocr_fn.json
```

OCR xịn nên được thiết kế theo dạng backend có thể thay thế.

Các hướng backend chính:

- OpenAI-compatible API
- llama.cpp thông qua API local
- Chrome Lens thông qua `chrome-lens-py`

Phần này có thể lấy lại ý tưởng từ repo `my_manga_translator`, nhưng chỉ lấy phần core backend OCR, không lấy workflow manga.

Các phần nên lấy lại ý tưởng:

- Provider abstraction giống `mmt_core/ocr_providers.py`
- Config provider giống `mmt_core/ocr_models.py`
- Llama server manager giống `mmt_core/llama_server.py`
- OpenAI-compatible image client giống `mmt_core/deepseek_ocr_client.py`
- Chrome Lens wrapper giống `mmt_core/chrome_lens_client.py` và `ocr/chrome_lens_ocr.py`
- Cách lưu kết quả OCR từng item giống `mmt_core/ocr_stage.py`
- Một phần text cleaning/filtering giống `mmt_core/ocr_text_filter.py`

Các phần không lấy nguyên từ repo `my_manga_translator`:

- `canon_state`
- detection cache
- bubble bbox
- manga page workflow
- reading order cho manga
- detector stage
- translation stage của manga

Lý do: app subtitle đã có vùng subtitle cố định từ video, không cần detect bubble hoặc xử lý layout manga.

Interface backend OCR xịn nên có dạng chung:

```python
class FinalOCRProvider:
    def validate(self) -> None:
        ...

    def recognize_image(self, image_path: str) -> dict:
        ...

    def close(self) -> None:
        ...

    def metadata(self) -> dict:
        ...
```

Output chuẩn từ backend OCR xịn:

```json
{
  "text": "recognized subtitle text",
  "confidence": null,
  "provider": "openai_compatible",
  "raw": {}
}
```

Cấu trúc module đề xuất:

```text
backend/
  final_ocr/
    base.py
    provider_factory.py
    openai_compatible.py
    llama_server_manager.py
    chrome_lens.py
    text_cleaner.py
```

`provider_factory.py` chịu trách nhiệm nhận config và tạo backend tương ứng.

Ví dụ:

```python
def create_final_ocr_provider(config):
    if config["provider"] == "openai_compatible":
        return OpenAICompatibleOCRProvider(config)
    if config["provider"] == "llama_cpp":
        return OpenAICompatibleOCRProvider(config)
    if config["provider"] == "chrome_lens":
        return ChromeLensOCRProvider(config)
```

`openai_compatible.py` chịu trách nhiệm:

- đọc ảnh
- encode base64
- gửi vào `/v1/chat/completions`
- parse response
- clean text
- trả về OCR result

Backend này dùng được cho:

- OpenAI-compatible cloud API
- llama.cpp local server
- LM Studio
- server VLM tự host
- các API khác nếu tương thích OpenAI format

`llama_server_manager.py` chịu trách nhiệm:

- build `run_server.bat`
- check health server
- open server folder
- start server bên ngoài app

Không bắt buộc app phải tự giữ process llama.cpp trong RAM.

`chrome_lens.py` chịu trách nhiệm:

- gọi `chrome-lens-py`
- retry
- timeout
- language config
- trả text về cùng format với các backend khác

Chrome Lens nên là backend tuỳ chọn, không phải backend bắt buộc.

`text_cleaner.py` chịu trách nhiệm xử lý output OCR xịn:

- bỏ markdown fence
- bỏ JSON wrapper nếu model trả về JSON
- bỏ prefix như `OCR:`, `Text:`, `Recognized text:`
- giữ lại `raw_ocr_text` nếu text đã bị clean
- đánh dấu lỗi nếu output rỗng

Config OCR xịn có thể lưu trong `progress.json` hoặc file config riêng.

Ví dụ:

```json
{
  "final_ocr": {
    "provider": "openai_compatible",
    "server_url": "http://127.0.0.1:8080",
    "model": "deepseek-ocr",
    "timeout": 120,
    "temperature": 0,
    "max_tokens": 512,
    "prompt": "OCR this subtitle image. Return only the subtitle text."
  }
}
```

Hàm xử lý OCR xịn đề xuất:

```python
def run_final_ocr_for_segments(project_dir, force=False):
    ...
```

Logic xử lý:

1. Load `progress.json`.
2. Load `segments.json`.
3. Load config OCR xịn.
4. Tạo final OCR provider.
5. Validate provider.
6. Với mỗi segment:
   - lấy `represent_image`
   - tìm ảnh đã preprocess tương ứng
   - nếu đã OCR rồi và `force=false` thì skip
   - gọi `provider.recognize_image(image_path)`
   - ghi text vào `ocr_fn.json`
   - lưu file sau mỗi item
7. Close provider.

`ocr_fn.json` nên lưu tiến trình từng item để có thể resume nếu app crash.

Ví dụ cấu trúc mở rộng:

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

Nguyên tắc:

- OCR xịn chạy tới đâu lưu tới đó.
- Nếu app crash, lần sau resume được.
- Nếu một ảnh lỗi, không làm mất toàn bộ batch.
- OCR xịn chỉ tạo text final, không tự sửa timestamp.
- Timestamp vẫn lấy từ `segments.json` và `timestamp.json`.

Thứ tự ưu tiên backend cho MVP:

1. OpenAI-compatible API
2. llama.cpp local server qua OpenAI-compatible endpoint
3. Chrome Lens

---

### Bước 7: So sánh lại bản OCR xịn và lấy timestamp chuẩn

Dựa trên kết quả OCR xịn ở Bước 6.

So sánh lại các dòng subtitle.

Lấy ra các timestamp chuẩn hơn.

Mục tiêu là tạo ra danh sách subtitle cuối cùng, gồm:

- thời gian bắt đầu
- thời gian kết thúc
- nội dung subtitle OCR cuối cùng

---

### Bước 8: Export subtitle

Dựa vào `process.json` và toàn bộ kết quả đã ghi lại từ các bước trước.

Tạo file export subtitle.

Các định dạng export có thể là:

- SRT
- ASS
- TXT

Kết quả cuối cùng là file subtitle có timestamp và nội dung đã OCR.

---

## UI của app

UI được tách thành 4 scene chính.

---

## Scene 1: Project Manager + Preview + Config

Đây là nơi bắt đầu project.

Chức năng chính:

- Load video vào app.
- Preview video.
- Chọn vùng crop subtitle.
- Chọn nơi lưu project.
- Lưu setup ban đầu vào `process.json`.

Scene này chủ yếu để chuẩn bị dữ liệu đầu vào cho toàn bộ pipeline.

---

## Scene 2: Process

Đây là nơi chạy các bước xử lý.

Chức năng chính:

- Nút Prepare.
- Nút xử lý lần 1.
- Nút xử lý lần 2.
- Hiện log quá trình xử lý.
- Hiện subtitle realtime cho người dùng xem.

Scene này là trung tâm xử lý của app.

Người dùng có thể nhìn thấy app đang chạy đến bước nào và kết quả đang ra sao.

---

## Scene 3: Export

Đây là nơi người dùng xử lý file subtitle cuối cùng.

Chức năng chính:

- Xem danh sách subtitle đã tạo.
- Edit subtitle ngay trong app.
- Export file subtitle.
- Xuất ra các định dạng cần thiết.

Scene này là nơi người dùng kiểm tra kết quả cuối cùng trước khi dùng subtitle.

---

## Scene 4: Config

Đây là nơi setup backend và các cấu hình xử lý.

Chức năng chính:

- Setup llama.cpp.
- Setup API.
- Setup model OCR nhẹ.
- Setup model OCR xịn.
- Chọn backend OCR xịn: OpenAI-compatible API, llama.cpp local API, hoặc Chrome Lens.
- Tạo, mở, chạy và kiểm tra health `run_server.bat` cho llama.cpp nếu dùng local server.
- Setup `server_url`, model name, model path, mmproj path, timeout, max tokens, temperature và prompt OCR.
- Setup Chrome Lens nếu dùng backend Chrome Lens: language, headless, Chrome path, user data dir và retry.
- Setup các thông số cần thiết cho quá trình xử lý.

Scene này tách riêng cấu hình khỏi quá trình xử lý, để app dễ nâng cấp và dễ thay backend.

---

## Nâng cấp translator

App hoàn toàn có thể nâng cấp thêm translator ngay trong workflow này.

Sau khi đã có subtitle OCR cuối cùng, có thể thêm bước dịch.

Quy trình mở rộng:

1. OCR ra subtitle gốc.
2. Đưa subtitle gốc qua translator.
3. Nhận subtitle đã dịch.
4. Export subtitle đã dịch.
5. Có thể export song ngữ nếu cần.

Translator có thể được đặt trong phần Config giống như OCR backend.

Người dùng có thể chọn backend dịch phù hợp.

---

## Tinh thần thiết kế

App này không nên là một script gom tất cả vào một file.

App này nên đi theo hướng:

- tách từng bước xử lý
- mỗi bước có dữ liệu đầu ra riêng
- có file lưu tiến trình
- có UI rõ ràng
- có thể thay OCR backend
- OCR thô và OCR xịn đều phải được thiết kế theo backend có thể thay thế
- OCR xịn không phụ thuộc cố định vào một model hoặc một API
- có thể thêm translator
- có thể export subtitle cuối cùng

Mục tiêu là tạo một công cụ dễ nâng cấp, dễ sửa lỗi, dễ debug, và người dùng có thể kiểm soát được toàn bộ workflow.
