<p align="center">
  <a href="https://github.com/your-username/vocra">
    <img src="https://raw.githubusercontent.com/your-username/vocra/main/vocra_gui/icon.png" alt="VoCRA Logo" width="160" height="160" style="border-radius: 24px; box-shadow: 0 0 20px rgba(0, 240, 255, 0.4); border: 2px solid #00f0ff;" />
  </a>
</p>

<h1 align="center">🌌 VoCRA & VoCRA TRANSLATOR 🌌</h1>

<p align="center">
  <pre align="center">
██╗   ██╗ ██████╗  ██████╗██████╗  █████╗ 
██║   ██║██╔═══██╗██╔════╝██╔══██╗██╔══██╗
██║   ██║██║   ██║██║     ██████╔╝███████║
╚██╗ ██╔╝██║   ██║██║     ██╔══██╗██╔══██║
 ╚████╔╝ ╚██████╔╝╚██████╗██║  ██║██║  ██║
  ╚═══╝   ╚═════╝  ╚═════╝╚═╝  ╚═╝╚═╝  ╚═╝
  </pre>
</p>

<p align="center">
  <strong>Hệ Thống Trích Xuất & Dịch Thuật Phụ Đề Visual-OCR Hybrid Siêu Cấp Tối Tân</strong>
</p>

<p align="center">
  <a href="#architecture"><img src="https://img.shields.io/badge/Architecture-Python%20%7C%20PySide6%20%7C%20llama.cpp-00f0ff?style=for-the-badge&logo=python&logoColor=white" alt="Arch"></a>
  <a href="#vibe"><img src="https://img.shields.io/badge/Style-Wibu%20High--Tech-a800ff?style=for-the-badge" alt="Style"></a>
  <a href="#subtool"><img src="https://img.shields.io/badge/Subtool-VoCRA%20Translator-ff9f00?style=for-the-badge" alt="Subtool"></a>
</p>

---

## 🔮 TỔNG QUAN DỰ ÁN (Project Overview)

**VoCRA** (Visual Optical Character Recognition Assistant) là một hệ sinh thái mã nguồn mở đột phá giúp giải quyết trọn gói bài toán **Trích xuất phụ đề cứng (Hardsub) từ Video và Dịch thuật AI tự động**. 

Được xây dựng trên nền tảng **Python 3.10+**, giao diện Mecha viễn tưởng cực ngầu của **PySide6 (Qt)**, kết hợp cùng sức mạnh xử lý ảnh nâng cao **SSIM** và công cụ chạy mô hình ngôn ngữ lớn cục bộ **llama.cpp** thần tốc ở tầng lõi. Dự án cung cấp hai ứng dụng Workspace chuyên nghiệp:
1. **VoCRA Main App:** Pipeline toàn diện từ Đọc Video -> Cắt vùng thông minh -> Lọc frame cấu trúc -> Chạy VLM OCR (local/cloud) -> Xuất phụ đề.
2. **VoCRA Translator:** Phân khu dịch thuật phụ đề tách rời cao cấp, chuyên trị các định dạng `SRT`, `ASS`, `VTT` với cơ chế tối ưu hóa cache thông minh và bảo toàn cấu trúc tags tối đa.

---

## 🌌 CÁC ĐẶC TÍNH SIÊU VIỆT (Core Features)

### 1. 🚀 VoCRA Extractor (Cỗ Máy Trích Xuất Visual-OCR Hybrid)
*   **Interactive Region Cropper:** Công cụ quét chuột tọa độ trực quan trên màn hình để định hình khu vực chứa phụ đề, triệt tiêu 100% nhiễu từ các hoạt cảnh xung quanh.
*   **SSIM Structural Frame Filtering:** Thuật toán so sánh độ tương đồng cấu trúc hình ảnh (SSIM với ngưỡng `0.95`). Tự động phát hiện và loại bỏ tới **90%+ số lượng frame tĩnh trùng lặp**, giảm thiểu tối đa gánh nặng xử lý AI ở các bước sau.
*   **Visual-OCR Segmentation Engine:**
    *   *Blank-frame tolerance:* Kháng nhiễu chớp tắt khung hình đen cực tốt, ngăn ngừa việc phân chia sub vụn vặt không mong muốn.
    *   *Sharpness-based representative selection:* Tự động tính toán độ sắc nét (Laplacian variance) giữa các frame liên quan để chỉ chọn ra ảnh chất lượng cao nhất gửi lên AI.
    *   *Text Voting System:* Thuật toán bầu chọn ký tự từ các kết quả OCR nháp để tìm ra phiên bản chuẩn xác nhất.
*   **Local Llama.cpp Integration:** Tự động hóa và quản lý trơn tru tiến trình `llama-server.exe` nội bộ, hỗ trợ nạp trực tiếp các Vision-Language Models (VLM) dạng GGUF (như `paddleocr-vl`, `minicpm-v`, `qwen2-vl`, `llava`) với khả năng gán tải GPU layers linh hoạt (`gpu_layers: 99`).
*   **Cloud OCR Fallback:** Tích hợp sẵn Chrome Lens OCR dịch vụ dự phòng chạy chế độ không đầu (headless) siêu tốc độ.

### 2. ⚡ VoCRA Translator (Phi Thuyền Dịch Thuật Phụ Đề Độc Lập)
*   **Chuyên Biệt Hóa Không Gian Làm Việc:** Tách rời hoàn toàn khỏi pipeline xử lý video, tối ưu hóa tài nguyên chỉ để dịch và biên tập tệp phụ đề.
*   **Dual-Panel Grid Editor:** Giao diện dịch thuật bảng trực quan hiển thị song hành Source text (Readonly) và Target text (Editable) theo thời gian thực.
*   **Smart Stale-Signature Cache:**
    *   Tính toán mã định danh Hash chữ ký độc nhất dựa trên tập hợp cấu hình: *Provider + Model + Source/Target Languages + Style + Context Prompt + Hash danh sách dòng nguồn*.
    *   Chỉ biên dịch các dòng phụ đề mới hoặc có sự thay đổi. Hoàn toàn không tốn tài nguyên GPU/CPU hay chi phí token API cho những dòng phụ đề đã có sẵn bản dịch tương thích.
*   **Advanced ASS Style Preserver:** Thuật toán phân tích cú pháp best-effort bảo vệ nguyên vẹn các thẻ ghi đè phong cách của ASS (như `\N`, `{\fad(200,200)}`, v.v.), đảm bảo phụ đề sau dịch vẫn giữ nguyên hiệu ứng đồ họa gốc.
*   **Cross-Format Converter:** Chuyển đổi linh hoạt qua lại giữa `SRT`, `ASS`, `VTT`.

---

## 🎨 HƯỚNG DẪN MÀU SẮC GIAO DIỆN (Visual Design System)

Giao diện của dự án tuân thủ nghiêm ngặt phong cách thiết kế Mecha-Spacecraft được cấu hình qua tệp `theme.qss` nghệ thuật:

*   🌌 **Deep Space Background (#08080a - #0b0b0e):** Tông màu tối sâu thẳm, dịu mắt, tăng độ tập trung tối đa cho người dùng.
*   🔮 **Spaceship Purple-Cyan Gradient:** Các thành phần nút bấm và khu vực tương tác chủ đạo sở hữu dải màu chuyển sắc Purple-to-Cyan (`#1a0c30` -> `#061e2b`).
*   ⚡ **Neon Laser Hover Borders:** Khi di chuột, viền nút phát sáng hào quang neon rực rỡ (`#a800ff` -> `#00f0ff`). Khi nhấn giữ, viền nút chuyển sang sắc màu vàng hổ phách cháy bỏng (Amber Gold).
*   🔋 **Progressive Neon Loading:** Thanh trạng thái trượt gradient từ Cyan sang Violet hiển thị tốc độ xử lý luồng công việc thời gian thực.

---

## 🗂️ SƠ ĐỒ CẤU TRÚC MÃ NGUỒN (Repository Structure)

```yaml
vocra/
├── main.py                     # Entry point chính của VoCRA (Subtitle Video OCR)
├── vocra_translator_main.py    # Entry point phân khu dịch thuật vocra_translator
│
├── vocra_core/                 # LÕI NGHIỆP VỤ & THUẬT TOÁN (Business Logic)
│   ├── app_config.py           # Quản lý cấu hình toàn cục & nạp mặc định
│   ├── default_config.json     # Cấu hình tham số mặc định của hệ thống
│   ├── cropper.py              # Xử lý tọa độ cắt cúp khung hình phụ đề
│   ├── frame_extractor.py      # Trích xuất khung hình từ video qua OpenCV
│   ├── ssim_filter.py          # Bộ lọc cấu trúc tương đồng hình ảnh (SSIM)
│   ├── segmenter.py            # Logic phân mảnh, đo độ nét & bầu chọn văn bản
│   ├── text_cleaner.py         # Hậu xử lý chuẩn hóa chuỗi ký tự OCR
│   ├── final_ocr/              # Giao thức OCR cuối cùng (llama.cpp / Chrome Lens)
│   │   ├── llama_server_manager.py  # Điều khiển & tham số hóa cho llama-server.exe
│   │   ├── paddleocr_vl.py     # Tương tác mô hình Vision PaddleOCR GGUF
│   │   └── chrome_lens.py      # Module dự phòng Chrome Lens OCR
│   └── translator/             # Bộ máy dịch thuật lõi AI
│       └── openai_compatible.py # Trình dịch tương thích chuẩn RESTful APIs
│
├── vocra_gui/                  # THÀNH PHẦN GIAO DIỆN VOCRA
│   ├── main_window.py          # Điều khiển tổng quan, quản lý 5 scene chính
│   ├── styles/theme.qss        # Visual mecha của app chính
│   ├── widgets/                # Các UI widgets tùy biến
│   └── scene_setup.py / scene_process.py / scene_translator.py / scene_export.py / scene_config.py
│
├── vocra_translator/           # GIAO DIỆN PHÂN KHU VOCRA TRANSLATOR
│   ├── main_window.py          # Bộ não điều phối GUI Translator độc lập
│   ├── core/                   # Xử lý định dạng SRT/ASS/VTT & cache dịch thuật
│   ├── scenes/                 # 4 Scene chính: Project, Translate, Export, Config
│   ├── styles/theme.qss        # Visual mecha tối ưu riêng cho translator
│   └── widgets/                # Các widget chuyên dụng
│
├── tools/                      # THƯ MỤC CHỨA BINARY COMPILATION CỦA LLAMA.CPP (Windows native)
│   ├── llama-server.exe        # Server chạy cục bộ GGUF models
│   ├── ggml-cuda.dll           # Driver tăng tốc GPU Nvidia cực hạn
│   └── ...                     # Các thư viện liên kết động (.dll) hỗ trợ
└── models/                     # Thư mục chứa các mô hình AI VLM GGUF (Đã gitignored)
```

---

## 🛠️ HƯỚNG DẪN CÀI ĐẶT (Installation)

### 1. Điều Kiện Cần (Prerequisites)
*   **Hệ điều hành:** Windows 10 / 11 (Khuyến khích trang bị GPU NVIDIA hỗ trợ CUDA để tận dụng tối đa `ggml-cuda.dll`).
*   **Môi trường:** Python `3.10` trở lên.

### 2. Cài Đặt Các Phụ Thuộc (Dependencies)
Mở cửa sổ dòng lệnh (Terminal/Command Prompt) tại thư mục dự án và tiến hành cài đặt:
```bash
pip install PySide6 numpy opencv-python Pillow pillow_heif requests scikit-image
```

*(Lưu ý: Thư viện `scikit-image` sẽ tối ưu hóa hiệu năng tính toán SSIM lên cực hạn. Hệ thống tích hợp sẵn module SSIM thuần túy bằng NumPy làm phương án dự phòng an toàn).*

### 3. Thiết Lập Mô Hình Trí Tuệ Nhân Tạo (VLM Models)
1. Tạo thư mục theo cấu trúc: `models/paddleocr_vl/` trong thư mục gốc.
2. Tải và sao chép các mô hình Vision-Language GGUF tương ứng vào thư mục:
    *   File mô hình chính: `models/paddleocr_vl/model.gguf`
    *   File máy chiếu hình ảnh: `models/paddleocr_vl/mmproj.gguf`
3. Ba có thể thay đổi tùy ý đường dẫn nạp mô hình tại tab **Config** trên GUI.

---

## 🎮 QUY TRÌNH HÀNH QUÂN (Quick Start Guide)

### 🚀 Sử Dụng VoCRA Extractor (Video to Subtitle OCR Pipeline)
```bash
python main.py
```
*   **Bước 1 (Setup):** Nhập tệp video đầu vào. Kéo thả vùng quét phụ đề mong muốn trên trình phát trực quan. Xác định khoảng thời gian quét. Bấm **Create Project**.
*   **Bước 2 (Process):** Bấm **Extract & Process**. Tiến trình tự động cắt ảnh -> Lọc SSIM loại bỏ frame trùng -> Trích xuất văn bản qua local VLM GGUF / Chrome Lens -> Tự động ghép nối mốc thời gian (timestamps).
*   **Bước 3 (Translate):** Chọn cấu hình dịch thuật, bổ sung bối cảnh văn cảnh phim (Context), định hình ngôn ngữ đích (`vi`), chọn số lượng dòng xử lý song song (batch size). Bấm nút dịch.
*   **Bước 4 (Export):** Kiểm duyệt bản dịch, chọn định dạng phụ đề (`SRT`, `ASS`, `VTT`) và tiến hành kết xuất sản phẩm.

---

### ⚡ Sử Dụng Độc Lập VoCRA Translator
```bash
python vocra_translator_main.py
```
*   **Bước 1 (Project):** Bấm **Import Subtitle File** để mở tệp phụ đề sẵn có (`SRT`, `VTT`, `ASS`). Dự án dịch thuật độc lập sẽ được kiến tạo cùng cơ chế khôi phục trạng thái làm việc dở dang thông minh.
*   **Bước 2 (Translate):** Cấu hình Endpoint AI của bạn (OpenAI, Gemini, DeepSeek, Local LLM,...), khai báo Context chủ đề để AI dịch tự nhiên và đúng vai vế nhân vật. Bấm **Start Translation**.
*   **Bước 3 (Interactive Edit):** Xem xét bảng đối chiếu song ngữ, click trực tiếp vào dòng chữ dịch để hiệu chỉnh thủ công câu từ theo ý muốn.
*   **Bước 4 (Export):** Xuất phụ đề mới cùng định dạng hoặc hoán chuyển sang định dạng khác tùy nhu cầu.

---

## 📝 GIẤY PHÉP & BẢN QUYỀN (License)

Dự án được phân phối dưới giấy phép mã nguồn mở MIT License. Mọi đóng góp cải tiến kỹ thuật, tối ưu hóa thuật toán hoặc phát triển giao diện đều được chào đón nồng nhiệt tại mục Pull Requests.
