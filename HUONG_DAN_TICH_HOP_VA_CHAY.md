# HƯỚNG DẪN TÍCH HỢP VÀ CHẠY SAFEGUARD AI (GIAO DIỆN V2) TRONG VS CODE

Tài liệu này hướng dẫn chi tiết cách sao lưu, tích hợp bộ mã nguồn Giao diện V2 (xây dựng từ `preview.html`) vào dự án **SafeGuard AI** hiện tại của bạn và chạy kiểm thử trên Windows + VS Code.

---

## 1. Danh sách các file được giữ nguyên (Không thay đổi)

Các module nghiệp vụ, cơ sở dữ liệu, mô hình AI và tài liệu an toàn của bạn được **giữ nguyên 100%**, không cần sửa đổi:
- `database.py` — Quản lý SQLite database (`safeguard.db`), bảng `events`.
- `detector.py` — Nạp mô hình YOLO (`models/best.pt`) và hàm `detect_frame()`.
- `video_processor.py` — Đọc luồng video MP4, cắt frame và bắt lỗi file hỏng.
- `chatbot.py` — Engine trợ lý AI giám sát và tra cứu văn bản nội quy.
- `models/best.pt` — Trọng số mô hình YOLO nhận diện PPE.
- `safeguard.db` — Cơ sở dữ liệu SQLite hiện có.
- `evidence/` — Thư mục chứa ảnh bằng chứng (`event_*.jpg`) và metadata (`event_*.json`).
- `safety_docs/` — Thư mục chứa 5 văn bản quy định an toàn lao động (`.txt` / `.docx`):
  - `Quy_dinh_trang_thiet_bi_bao_ho.txt`
  - `Quy_dinh_vung_nguy_hiem_DangerZone.txt`
  - `Quyen_va_nghia_vu_nguoi_lao_dong.txt`
  - `Xu_ly_vi_pham_qua_camera_AI.txt`
  - `An_toan_han_cat_va_lam_viec_tren_cao.txt`
- `sample_data/` — Thư mục chứa các video mẫu (`.mp4`, `.avi`, `.mov`).

---

## 2. Danh sách các file cần sao lưu trước khi thay thế

Chỉ có **01 file duy nhất** bị thay thế là `app.py`. Trước khi giải nén gói giao diện V2 vào thư mục dự án, hãy sao lưu `app.py` cũ bằng lệnh sau trong Terminal của VS Code (PowerShell hoặc CMD):

```powershell
copy app.py app_legacy_backup.py
```

Nếu bất kỳ lúc nào bạn muốn quay lại giao diện cũ, chỉ cần chạy:
```powershell
copy app_legacy_backup.py app.py
```

---

## 3. Cấu trúc các file mới trong gói Giao diện V2

Khi giải nén `SafeGuard_AI_UI_V2_Rebuild.zip` vào thư mục gốc của dự án, bạn sẽ có thêm các file sau:

```text
safeguard_ai_project/
├── app.py                      # [THAY THẾ] Entry point mới điều phối 5 trang V2
├── core_logic.py               # [MỚI] Tách toàn bộ hàm/class nghiệp vụ từ app.py cũ
├── ui_theme.py                 # [MỚI] Quản lý chế độ Sáng / Tối / Theo hệ thống
├── ui_components.py            # [MỚI] Sidebar V2, Utility Bar, Topbar, Banner E-Stop & Undo
├── ui_pages/                   # [MỚI] Package chứa 5 trang chức năng chuẩn Prototype V2
│   ├── __init__.py
│   ├── dashboard.py            # Trang 1: Tổng quan an toàn
│   ├── scanner.py              # Trang 2: Quét AI & Camera
│   ├── review.py               # Trang 3: Duyệt vi phạm & Điều khiển IoT
│   ├── assistant.py            # Trang 4: Trợ lý AI giám sát
│   └── documents.py            # Trang 5: Tài liệu an toàn lao động
├── assets/
│   └── style.css               # [MỚI] Stylesheet tập trung theo Design System V2
├── requirements.txt            # [MỚI] Danh sách thư viện chuẩn
└── HUONG_DAN_TICH_HOP_VA_CHAY.md
```

### Lưu ý quan trọng về vị trí thư mục tài nguyên
Hãy đảm bảo các tệp hiện có của bạn được đặt đúng thư mục con như sau (nếu trước đó bạn đang để chung ở thư mục gốc):
1. File `best.pt` phải nằm tại: `models/best.pt`
2. 5 file `.txt` nội quy an toàn phải nằm tại: `safety_docs/`
3. Các file `event_184.jpg`, `event_184.json`, `event_185.jpg`, `event_185.json` phải nằm tại: `evidence/`
4. Các file video `.mp4` (nếu có) đặt tại: `sample_data/`

Lệnh PowerShell nhanh để sắp xếp tự động nếu các file đang nằm ở thư mục gốc:
```powershell
mkdir models, safety_docs, evidence, sample_data -Force
if (Test-Path best.pt) { Move-Item best.pt models\best.pt -Force }
if (Test-Path event_184.jpg) { Move-Item event_*.jpg, event_*.json evidence\ -Force }
Move-Item Quy_dinh_*.txt, Quyen_va_*.txt, Xu_ly_*.txt, An_toan_*.txt safety_docs\ -ErrorAction SilentlyContinue
```

---

## 4. Hướng dẫn cài đặt môi trường và chạy trên Windows + VS Code

### Bước 1: Mở thư mục dự án trong VS Code
1. Mở **VS Code** → **File** → **Open Folder...** → Chọn thư mục dự án của bạn.
2. Mở Terminal tích hợp trong VS Code bằng tổ hợp phím `` Ctrl + ` `` (chọn cấu hình **PowerShell** hoặc **Command Prompt**).

### Bước 2: Tạo và kích hoạt môi trường ảo (Virtual Environment)
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```
*(Nếu PowerShell báo lỗi ExecutionPolicy khi chạy `Activate.ps1`, hãy chạy lệnh: `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser` rồi kích hoạt lại, hoặc dùng CMD: `.venv\Scripts\activate.bat`).*

### Bước 3: Cài đặt thư viện
```powershell
pip install --upgrade pip
pip install -r requirements.txt
```

### Bước 4: Chạy ứng dụng Streamlit
```powershell
streamlit run app.py
```
Ứng dụng sẽ tự động mở trên trình duyệt tại địa chỉ `http://localhost:8501`.

---

## 5. Xử lý các lỗi thường gặp (Troubleshooting)

1. **`FileNotFoundError: Khong tim thay mo hinh: .../models/best.pt`**
   - **Nguyên nhân:** File `detector.py` kiểm tra đường dẫn cứng `models/best.pt` ngay khi import.
   - **Cách khắc phục:** Tạo thư mục `models` ở cùng cấp với `app.py` và chép file `best.pt` vào `models/best.pt`.

2. **Trang Tài liệu an toàn hoặc Chatbot báo `"Chưa tìm thấy thư mục văn bản nội quy"`**
   - **Nguyên nhân:** 5 file `.txt` nội quy chưa được đặt trong thư mục `safety_docs/`.
   - **Cách khắc phục:** Tạo thư mục `safety_docs/` cùng cấp với `app.py` và di chuyển 5 file `.txt` vào đó.

3. **Trang Quét AI báo `"Chưa tìm thấy video mẫu (.mp4, .avi, .mov) trong thư mục sample_data"`**
   - **Nguyên nhân:** Thư mục `sample_data/` hiện chưa có file video `.mp4`.
   - **Cách khắc phục:** Chép các file video `.mp4` của bạn vào `sample_data/`, hoặc chuyển công tắc nguồn sang **"Tải video hoặc ảnh từ máy tính"** để tải trực tiếp ảnh (`sample_2_hd_003_result.jpg`, `sample_4_no_hardhat_mask_027_result.jpg`, v.v.) hoặc video bất kỳ từ máy tính lên kiểm thử.

4. **Lỗi thiếu `DLL` của OpenCV trên Windows (`ImportError: DLL load failed while importing cv2`)**
   - **Cách khắc phục:** Chạy `pip uninstall opencv-python -y` và cài đặt `pip install opencv-python-headless` hoặc cài đặt gói *Microsoft Visual C++ Redistributable 2015–2022*.
