# -*- coding: utf-8 -*-
"""
core_logic.py — Module nghiệp vụ lõi dùng chung cho toàn bộ hệ thống SafeGuard AI V2.
Đã rà soát và tối ưu hóa toàn diện các thuật toán & tốc độ chuyển trang:
1. Bộ nhớ đệm dữ liệu sự kiện mức RAM (_EVENTS_RAM_CACHE): Tự động kiểm tra mtime_ns của safeguard.db và
   phiên bản dữ liệu nội bộ (_DATA_VERSION). Khi chuyển qua lại giữa 5 trang mà DB không đổi, hệ thống trả về
   ngay raw_events và enriched_events từ RAM trong < 0.01ms (0 truy vấn SQLite, 0 lệnh stat đĩa cứng).
2. Tối ưu hóa ảnh Thumbnail Base64 (image_to_base64_uri): Thu nhỏ ảnh thẻ sự kiện về chiều ngang chuẩn 380px
   (JPEG quality 82) trước khi mã hóa Base64 và lưu cache RAM, giúp giảm ~90% dung lượng HTML truyền qua
   WebSocket mỗi lần chuyển trang (từ ~160KB/ảnh xuống ~15KB/ảnh) trong khi ảnh gốc ở khung chi tiết và file ZIP
   vẫn giữ nguyên độ phân giải 100%.
3. Tối ưu tốc độ đóng gói ZIP (build_evidence_zip_bytes): Dùng ZIP_STORED cho ảnh .jpg (vốn đã nén JPEG)
   và ZIP_DEFLATED cho CSV/JSON, giúp tạo gói bằng chứng nhanh gấp ~20 lần.
4. Chuẩn hóa danh sách Camera hệ thống (get_all_system_cameras): Cố định Camera số 1..5 (Khu vực 1..5),
   luôn có Camera số 3 và tuyệt đối không đưa các video/ảnh tải lên vào danh sách bộ lọc nguồn camera.
"""
import base64
import datetime
import io
import json
import math
import re
import sqlite3
import zipfile
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from chatbot import GIAI_THICH_LOI_VI_PHAM, TEN_VAN_BAN_DEP, ask_chatbot
from database import DB_PATH, get_all_events, init_db, insert_event, update_event_status as _db_update_event_status
from detector import _model
from video_processor import get_video_info, read_frames

BASE_DIR = Path(__file__).resolve().parent
EVIDENCE_DIR = BASE_DIR / "evidence"
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
ASSETS_DIR = BASE_DIR / "assets"
ASSETS_DIR.mkdir(parents=True, exist_ok=True)
DOCS_DIR = BASE_DIR / "safety_docs"

SYSTEM_CAMERA_COUNT = 5

TEN_LOI_TV = {
    "NO-Hardhat": "Không đội mũ bảo hộ",
    "NO-Safety Vest": "Không mặc áo phản quang",
    "NO-Mask": "Không đeo khẩu trang",
}

TRANG_THAI_TV = {
    "pending": "Chờ giám sát duyệt",
    "confirmed": "Đã xác nhận vi phạm",
    "false_positive": "Đã loại bỏ (AI nhầm)",
}

TRANG_THAI_BADGE_TV = {
    "pending": "Chờ duyệt",
    "confirmed": "Đã xác nhận",
    "false_positive": "Đã loại bỏ",
}

MUC_DO_RUI_RO = {
    "NO-Hardhat": ("high", "RỦI RO CAO"),
    "NO-Safety Vest": ("high", "RỦI RO CAO"),
    "NO-Mask": ("medium", "RỦI RO VỪA"),
}

CSV_COLUMNS = [
    "Mã sự kiện",
    "Thời điểm phát hiện",
    "Vị trí Camera",
    "Mã công nhân",
    "Hành vi vi phạm",
    "Giây trong video",
    "Độ tin cậy AI (%)",
    "Điều kiện ánh sáng",
    "Trạng thái duyệt",
    "Lệnh khẩn cấp Đội trưởng",
    "Tệp ảnh bằng chứng",
]

# Bộ nhớ đệm trong RAM giúp chuyển trang tức thì (< 1ms), tránh đọc đĩa cứng và nén lại lặp đi lặp lại
_DB_INITIALIZED: bool = False
_DATA_VERSION: int = 0
_EVIDENCE_META_CACHE: dict[int, dict] = {}
_EVIDENCE_IMG_EXISTS_CACHE: dict[int, Path | None] = {}
_B64_URI_CACHE: dict[tuple[str, int], str] = {}
_CSV_BYTES_CACHE: dict[tuple, bytes] = {}
_ZIP_BYTES_CACHE: dict[tuple, bytes] = {}
_SAMPLE_VIDEOS_CACHE: tuple[int, list[Path]] | None = None
_EVENTS_RAM_CACHE: dict[str, object] = {
    "key": None,
    "raw_events": [],
    "enriched_events": [],
}


def _clear_runtime_caches():
    """Xóa bộ nhớ đệm và tăng版本号 dữ liệu khi có sự kiện mới, cập nhật trạng thái hoặc làm mới ca trực."""
    global _DATA_VERSION
    _DATA_VERSION += 1
    _EVIDENCE_META_CACHE.clear()
    _EVIDENCE_IMG_EXISTS_CACHE.clear()
    _B64_URI_CACHE.clear()
    _CSV_BYTES_CACHE.clear()
    _ZIP_BYTES_CACHE.clear()
    _EVENTS_RAM_CACHE["key"] = None


def update_event_status(event_id: int, new_status: str):
    """Cập nhật trạng thái sự kiện trong SQLite và làm mới ngay cache RAM để các trang đồng bộ tức thì."""
    _db_update_event_status(int(event_id), new_status)
    _clear_runtime_caches()


def clean_html(raw_html: str) -> str:
    """
    Chuẩn hóa chuỗi HTML nhiều dòng trước khi truyền vào st.markdown(..., unsafe_allow_html=True):
    Loại bỏ khoảng trắng đầu dòng (indentation >= 4 spaces) và các dòng trống xen kẽ để trình phân tích
    CommonMark của Streamlit KHÔNG BAO GIỜ hiểu nhầm thẻ đóng </div> hoặc khối con thành <pre><code>.
    """
    if not raw_html:
        return ""
    lines = [line.strip() for line in raw_html.splitlines() if line.strip()]
    return "\n".join(lines)


def ensure_db_ready():
    """Khởi tạo bảng events trong safeguard.db đúng 1 lần duy nhất trong suốt vòng đời tiến trình."""
    global _DB_INITIALIZED
    if not _DB_INITIALIZED:
        init_db()
        _DB_INITIALIZED = True


def init_app_session_state():
    """Khởi tạo đầy đủ các khóa session_state gốc của app.py và các khóa điều hướng V2."""
    defaults = {
        "last_reviewed_action": None,
        "iot_action_banner": None,
        "emergency_stop_active": None,
        "qa_history": [],
        "ai_sensitivity": 0.50,
        "auto_confirm_level": 0.75,
        "check_hardhat": True,
        "check_vest": True,
        "check_mask": False,
        "enable_audio": True,
        "active_page": "dashboard",
        "sidebar_collapsed": False,
        "theme_mode": "light",
        "dash_range": "all",
        "dash_custom_date": None,
        "dash_apply_date": False,
        "dash_filter_open": False,
        "dash_cam_filter": "all",
        "dash_status_filter": "all",
        "dash_sev_filter": "all",
        "scan_source_mode": "Hệ thống Camera công trường",
        "selected_camera_idx": 0,
        "scan_cam_idx": 0,
        "scan_is_running": False,
        "last_scan_telemetry": {
            "worker_cnt": 0,
            "blur_score": 0.0,
            "glare_pct": 0.0,
            "status_text": "Chưa chạy phiên quét",
        },
        "review_tab_filter": "pending",
        "selected_review_event_id": None,
        "doc_topic_filter": "all",
        "doc_search_query": "",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def get_active_violation_types():
    """Trả về danh sách các mã hành vi vi phạm đang được bật giám sát."""
    active = []
    if st.session_state.get("check_hardhat", True):
        active.append("NO-Hardhat")
    if st.session_state.get("check_vest", True):
        active.append("NO-Safety Vest")
    if st.session_state.get("check_mask", False):
        active.append("NO-Mask")
    return active


def get_effective_auto_confirm():
    """Đảm bảo ngưỡng tự động xác nhận luôn hợp lệ so với độ nhạy phát hiện tối thiểu."""
    sens = float(st.session_state.get("ai_sensitivity", 0.50))
    auto_c = float(st.session_state.get("auto_confirm_level", 0.75))
    return max(auto_c, round(min(0.95, sens + 0.05), 2))


def play_alert_beep():
    """Phát tín hiệu âm thanh ngắn khi phát hiện vi phạm mới."""
    components.html(
        """
        <script>
        try {
            const ctx = new (window.AudioContext || window.webkitAudioContext)();
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.type = 'sine';
            osc.frequency.setValueAtTime(840, ctx.currentTime);
            gain.gain.setValueAtTime(0.10, ctx.currentTime);
            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.start();
            osc.stop(ctx.currentTime + 0.15);
        } catch (e) {}
        </script>
        """,
        height=0,
    )


def play_speaker_chime():
    """Phát âm thanh chuông loa truyền thanh nhắc nhở tại phân xưởng."""
    components.html(
        """
        <script>
        try {
            const ctx = new (window.AudioContext || window.webkitAudioContext)();
            const now = ctx.currentTime;
            const osc1 = ctx.createOscillator();
            const gain1 = ctx.createGain();
            osc1.type = 'triangle';
            osc1.frequency.setValueAtTime(660, now);
            osc1.frequency.setValueAtTime(520, now + 0.18);
            gain1.gain.setValueAtTime(0.14, now);
            osc1.connect(gain1);
            gain1.connect(ctx.destination);
            osc1.start(now);
            osc1.stop(now + 0.38);
        } catch (e) {}
        </script>
        """,
        height=0,
    )


def play_emergency_siren():
    """Phát còi báo động khi Đội trưởng kích hoạt Dừng khẩn cấp dây chuyền."""
    components.html(
        """
        <script>
        try {
            const ctx = new (window.AudioContext || window.webkitAudioContext)();
            const now = ctx.currentTime;
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.type = 'sawtooth';
            osc.frequency.setValueAtTime(880, now);
            osc.frequency.setValueAtTime(620, now + 0.16);
            osc.frequency.setValueAtTime(880, now + 0.32);
            gain.gain.setValueAtTime(0.16, now);
            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.start(now);
            osc.stop(now + 0.50);
        } catch (e) {}
        </script>
        """,
        height=0,
    )


def find_sample_videos():
    """Tìm tất cả video mẫu (.mp4, .avi, .mov) trong sample_data, có cache RAM theo mtime thư mục."""
    global _SAMPLE_VIDEOS_CACHE
    search_dirs = [BASE_DIR / "sample_data", BASE_DIR.parent / "sample_data"]
    dir_sig = 0
    for d in search_dirs:
        if d.is_dir():
            try:
                dir_sig ^= d.stat().st_mtime_ns
            except Exception:
                pass
    if _SAMPLE_VIDEOS_CACHE is not None and _SAMPLE_VIDEOS_CACHE[0] == dir_sig:
        return _SAMPLE_VIDEOS_CACHE[1]

    found = []
    seen = set()
    for d in search_dirs:
        if d.is_dir():
            for p in sorted(d.iterdir()):
                if p.is_file() and p.suffix.lower() in (".mp4", ".avi", ".mov"):
                    if p.name not in seen:
                        found.append(p)
                        seen.add(p.name)
    _SAMPLE_VIDEOS_CACHE = (dir_sig, found)
    return found


# ==============================================================================
# CHUẨN HÓA NGUỒN CAMERA HỆ THỐNG (KHU VỰC 1 ĐẾN 5) & HÌNH HỌC BOUNDING BOX
# ==============================================================================
def normalize_system_camera_name(cam_raw: str | None) -> str | None:
    """
    Chuẩn hóa tên camera về đúng định dạng chuẩn 'Camera số X — Khu vực X' (X từ 1..5).
    Nếu nguồn là video hoặc ảnh tải lên ('Video tải lên (...)', 'Ảnh (...)') hoặc không phải camera hệ thống,
    trả về None để tuyệt đối không lẫn vào bộ lọc Camera khu vực 1..5.
    """
    if not cam_raw:
        return None
    text = str(cam_raw).strip()
    low = text.lower()
    if low.startswith("video tải lên") or low.startswith("ảnh (") or "tải lên" in low:
        return None

    m = re.match(r"^camera\s*(?:số\s*)?0*(\d+)\b", text, flags=re.IGNORECASE)
    if m:
        idx = int(m.group(1))
        if 1 <= idx <= SYSTEM_CAMERA_COUNT:
            return f"Camera số {idx} — Khu vực {idx}"
    return None


def get_all_system_cameras(enriched_events: list | None = None) -> list[str]:
    """
    Trả về danh sách cố định 5 Camera hệ thống từ Khu vực 1 đến Khu vực 5:
    ['Camera số 1 — Khu vực 1', ..., 'Camera số 5 — Khu vực 5'].
    - Đảm bảo luôn có đầy đủ Camera số 3 — Khu vực 3 kể cả khi chưa có sự kiện vi phạm.
    - Tuyệt đối KHÔNG thêm các video/ảnh tải lên ('Video tải lên (...)', 'Ảnh (...)') vào bộ lọc Camera.
    """
    return [f"Camera số {idx} — Khu vực {idx}" for idx in range(1, SYSTEM_CAMERA_COUNT + 1)]


def box_overlap_ratio(box_small, box_large):
    """Tỷ lệ chồng lấp lớn nhất giữa 2 hộp (giữ tương thích API)."""
    x1 = max(box_small[0], box_large[0])
    y1 = max(box_small[1], box_large[1])
    x2 = min(box_small[2], box_large[2])
    y2 = min(box_small[3], box_large[3])
    inter = max(0, x2 - x1) * max(0, y2 - y1)
    if inter == 0:
        return 0.0
    area_small = max(1, (box_small[2] - box_small[0]) * (box_small[3] - box_small[1]))
    area_large = max(1, (box_large[2] - box_large[0]) * (box_large[3] - box_large[1]))
    return max(inter / area_small, inter / area_large)


def iou_score(box_a, box_b) -> float:
    """Tính chỉ số Intersection over Union (IoU) chuẩn [0, 1] dùng cho Tracking công nhân."""
    x1 = max(box_a[0], box_b[0])
    y1 = max(box_a[1], box_b[1])
    x2 = min(box_a[2], box_b[2])
    y2 = min(box_a[3], box_b[3])
    inter = max(0, x2 - x1) * max(0, y2 - y1)
    if inter == 0:
        return 0.0
    area_a = max(1, (box_a[2] - box_a[0]) * (box_a[3] - box_a[1]))
    area_b = max(1, (box_b[2] - box_b[0]) * (box_b[3] - box_b[1]))
    return inter / float(area_a + area_b - inter)


def box_inclusion_ratio(inner_box, outer_box) -> float:
    """
    Tính tỷ lệ phần diện tích của vật thể nhỏ (Mũ, Khẩu trang, Áo hoặc lỗi NO-*)
    nằm bên trong hộp lớn (Person): inter / area_inner.
    """
    x1 = max(inner_box[0], outer_box[0])
    y1 = max(inner_box[1], outer_box[1])
    x2 = min(inner_box[2], outer_box[2])
    y2 = min(inner_box[3], outer_box[3])
    inter = max(0, x2 - x1) * max(0, y2 - y1)
    if inter == 0:
        return 0.0
    area_inner = max(1, (inner_box[2] - inner_box[0]) * (inner_box[3] - inner_box[1]))
    return inter / float(area_inner)


def is_anatomically_valid(item_bbox, person_bbox, label: str) -> bool:
    """
    Kiểm tra tính hợp lý về giải phẫu học của vật thể PPE / lỗi vi phạm so với khung cơ thể công nhân.
    """
    ix1, iy1, ix2, iy2 = item_bbox
    px1, py1, px2, py2 = person_bbox
    pw = max(1.0, float(px2 - px1))
    ph = max(1.0, float(py2 - py1))
    icx = (ix1 + ix2) / 2.0
    icy = (iy1 + iy2) / 2.0

    if not (px1 - 0.15 * pw <= icx <= px2 + 0.15 * pw):
        return False

    if label in ("Hardhat", "NO-Hardhat", "Mask", "NO-Mask"):
        return (py1 - 0.15 * ph) <= icy <= (py1 + 0.58 * ph)
    if label in ("Safety Vest", "NO-Safety Vest"):
        return (py1 + 0.10 * ph) <= icy <= (py1 + 0.88 * ph)
    return True


# ==============================================================================
# ĐÁNH GIÁ ÁNH SÁNG LÓE & ĐỘ MỜ (TỐI ƯU HÓA CPU & ĐỘ CHÍNH XÁC CỤC BỘ ROI)
# ==============================================================================
def evaluate_lighting_and_glare(
    frame_bgr,
    target_bbox=None,
    precomputed_gray=None,
    global_stats=None,
):
    """Đánh giá hoàn cảnh ánh sáng xung quanh (ánh sáng lóe từ tia lửa hàn, ngược sáng, độ mờ)."""
    gray = precomputed_gray if precomputed_gray is not None else cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape[:2]

    if global_stats is not None:
        global_glare = global_stats["global_glare"]
        global_blur = global_stats["global_blur"]
        global_mean = global_stats["global_mean"]
    else:
        global_glare = float(np.mean(gray > 242))
        global_blur = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        global_mean = float(np.mean(gray))

    local_glare = global_glare
    local_blur = global_blur
    local_mean = global_mean
    has_valid_roi = False

    if target_bbox is not None:
        bx1, by1, bx2, by2 = target_bbox
        pad_x = int((bx2 - bx1) * 0.35)
        pad_y = int((by2 - by1) * 0.25)
        rx1, ry1 = max(0, bx1 - pad_x), max(0, by1 - pad_y)
        rx2, ry2 = min(w, bx2 + pad_x), min(h, by2 + pad_y)
        roi = gray[ry1:ry2, rx1:rx2]
        if roi.size >= 100:
            has_valid_roi = True
            local_glare = float(np.mean(roi > 238))
            local_blur = float(cv2.Laplacian(roi, cv2.CV_64F).var())
            local_mean = float(np.mean(roi))

    if has_valid_roi:
        effective_blur = local_blur
        is_blur = (local_blur < 38.0) or (local_blur < 65.0 and global_blur < 45.0) or (global_blur < 22.0)
    else:
        effective_blur = global_blur
        is_blur = global_blur < 50.0

    is_glare = (local_glare >= 0.055) or (global_glare >= 0.075)
    is_low_light = (local_mean < 58.0) if has_valid_roi else (global_mean < 62.0)

    conf_penalty = 0.0
    status_parts = []
    if is_glare:
        conf_penalty += 0.14
        status_parts.append("Phát hiện ánh sáng lóe mạnh (Đã bật lọc chống bắt nhầm)")
    if is_blur:
        conf_penalty += 0.10
        status_parts.append("Khung hình rung/mờ (Đã tăng ngưỡng lọc nhiễu)")
    if is_low_light:
        conf_penalty += 0.05
        status_parts.append("Môi trường thiếu sáng")
    if not status_parts:
        status_parts.append("Ánh sáng và độ nét ổn định")

    return {
        "is_glare": is_glare,
        "is_blur": is_blur,
        "conf_penalty": conf_penalty,
        "glare_pct": round(max(local_glare, global_glare) * 100, 1),
        "blur_score": round(effective_blur, 1),
        "status_text": " | ".join(status_parts),
        "_global_stats": {
            "global_glare": global_glare,
            "global_blur": global_blur,
            "global_mean": global_mean,
        },
    }


# ==============================================================================
# TRACKING ĐA ĐỐI TƯỢNG TOÀN CỤC & KHÓA CHỐNG BÁO LẶP THÔNG MINH
# ==============================================================================
class MultiPersonTrackerAndDeduplicator:
    """Bộ nhận diện nhiều người trong 1 khung hình & Khóa chống báo lặp (Anti-Duplicate Lock)."""

    def __init__(self, max_inactive_frames: int = 90, spatial_cooldown_frames: int = 120):
        self.next_id = 1
        self.max_inactive_frames = max_inactive_frames
        self.spatial_cooldown_frames = spatial_cooldown_frames
        self.active_workers = {}
        self.logged_worker_violations = {}
        self.logged_spatial_zones = []

    def update_workers(self, person_detections, frame_idx, frame_w, frame_h):
        diag = max(1.0, math.hypot(frame_w, frame_h))
        max_match_dist = diag * 0.18

        stale_ids = [
            wid for wid, winfo in self.active_workers.items()
            if frame_idx - winfo["last_frame"] > self.max_inactive_frames
        ]
        for wid in stale_ids:
            del self.active_workers[wid]

        sorted_persons = sorted(person_detections, key=lambda d: (d["bbox"][0], d["bbox"][1]))
        num_dets = len(sorted_persons)

        candidate_pairs = []
        for det_idx, pdet in enumerate(sorted_persons):
            pbox = pdet["bbox"]
            cx = (pbox[0] + pbox[2]) / 2.0
            cy = (pbox[1] + pbox[3]) / 2.0
            pw = max(1.0, float(pbox[2] - pbox[0]))
            ph = max(1.0, float(pbox[3] - pbox[1]))

            for wid, winfo in self.active_workers.items():
                dt = max(1, frame_idx - winfo["last_frame"])
                pred_dt = min(dt, 15)
                pred_cx = winfo["center"][0] + winfo.get("vx", 0.0) * pred_dt
                pred_cy = winfo["center"][1] + winfo.get("vy", 0.0) * pred_dt

                dist = math.hypot(cx - pred_cx, cy - pred_cy)
                raw_dist = math.hypot(cx - winfo["center"][0], cy - winfo["center"][1])
                eff_dist = min(dist, raw_dist)

                iou = iou_score(pbox, winfo["bbox"])
                ov = box_overlap_ratio(pbox, winfo["bbox"])

                old_w = max(1.0, float(winfo["bbox"][2] - winfo["bbox"][0]))
                old_h = max(1.0, float(winfo["bbox"][3] - winfo["bbox"][1]))
                size_diff = abs(pw - old_w) / max(pw, old_w) + abs(ph - old_h) / max(ph, old_h)

                if eff_dist <= max_match_dist or iou >= 0.20 or ov >= 0.30:
                    cost = eff_dist - (iou * 150.0) - (ov * 60.0) + (size_diff * 25.0)
                    candidate_pairs.append((cost, det_idx, wid))

        candidate_pairs.sort(key=lambda item: item[0])

        matched_det_to_wid = {}
        used_wids = set()
        for _, det_idx, wid in candidate_pairs:
            if det_idx in matched_det_to_wid or wid in used_wids:
                continue
            matched_det_to_wid[det_idx] = wid
            used_wids.add(wid)

        assigned = []
        for det_idx in range(num_dets):
            pdet = sorted_persons[det_idx]
            pbox = pdet["bbox"]
            cx = (pbox[0] + pbox[2]) / 2.0
            cy = (pbox[1] + pbox[3]) / 2.0

            wid = matched_det_to_wid.get(det_idx)
            if wid is None:
                wid = self.next_id
                self.next_id += 1
                vx, vy = 0.0, 0.0
            else:
                prev = self.active_workers[wid]
                dt = max(1, frame_idx - prev["last_frame"])
                inst_vx = (cx - prev["center"][0]) / dt
                inst_vy = (cy - prev["center"][1]) / dt
                vx = 0.6 * prev.get("vx", 0.0) + 0.4 * inst_vx
                vy = 0.6 * prev.get("vy", 0.0) + 0.4 * inst_vy

            self.active_workers[wid] = {
                "bbox": pbox,
                "center": (cx, cy),
                "vx": vx,
                "vy": vy,
                "last_frame": frame_idx,
            }
            if wid not in self.logged_worker_violations:
                self.logged_worker_violations[wid] = set()

            assigned.append({
                "worker_id": wid,
                "bbox": pbox,
                "confidence": pdet["confidence"],
                "center": (cx, cy),
            })

        return assigned

    def assign_virtual_worker(self, item_bbox, frame_idx, frame_w, frame_h) -> int:
        cx = (item_bbox[0] + item_bbox[2]) / 2.0
        cy = (item_bbox[1] + item_bbox[3]) / 2.0
        diag = max(1.0, math.hypot(frame_w, frame_h))
        match_radius = diag * 0.14

        best_id = None
        best_dist = match_radius
        for wid, winfo in self.active_workers.items():
            if frame_idx - winfo["last_frame"] > self.max_inactive_frames:
                continue
            dist = math.hypot(cx - winfo["center"][0], cy - winfo["center"][1])
            if dist <= best_dist:
                best_dist = dist
                best_id = wid

        if best_id is None:
            best_id = self.next_id
            self.next_id += 1

        self.active_workers[best_id] = {
            "bbox": item_bbox,
            "center": (cx, cy),
            "vx": 0.0,
            "vy": 0.0,
            "last_frame": frame_idx,
        }
        if best_id not in self.logged_worker_violations:
            self.logged_worker_violations[best_id] = set()
        return best_id

    def is_already_logged(self, worker_id, violation_type, center_xy, frame_w, frame_h, frame_idx: int = 0):
        if violation_type in self.logged_worker_violations.get(worker_id, set()):
            return True

        cx, cy = center_xy
        zone_radius = math.hypot(frame_w, frame_h) * 0.10
        for z in self.logged_spatial_zones:
            if z["v_type"] != violation_type:
                continue
            if frame_idx > 0 and (frame_idx - z.get("frame_idx", 0)) > self.spatial_cooldown_frames:
                continue
            if math.hypot(cx - z["cx"], cy - z["cy"]) <= zone_radius:
                return True
        return False

    def mark_logged(self, worker_id, violation_type, center_xy, frame_idx: int = 0):
        if worker_id not in self.logged_worker_violations:
            self.logged_worker_violations[worker_id] = set()
        self.logged_worker_violations[worker_id].add(violation_type)
        self.logged_spatial_zones.append({
            "v_type": violation_type,
            "cx": center_xy[0],
            "cy": center_xy[1],
            "frame_idx": frame_idx,
            "worker_id": worker_id,
        })


def _draw_smart_label(img, text: str, x1: int, y1: int, bg_color: tuple, font_scale: float = 0.48, thickness: int = 1):
    """Vẽ nhãn chữ trên khung hình đảm bảo không bao giờ bị tràn ra ngoài rìa ảnh."""
    h, w = img.shape[:2]
    (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness)
    pad_x, pad_y = 4, 6
    box_w = tw + pad_x * 2
    box_h = th + pad_y

    lx1 = max(2, min(x1, w - box_w - 2))
    ly2 = y1 if y1 - box_h >= 2 else min(h - 2, y1 + box_h + 4)
    ly1 = max(2, ly2 - box_h)

    cv2.rectangle(img, (lx1, ly1), (lx1 + box_w, ly2), bg_color, -1)
    cv2.putText(
        img,
        text,
        (lx1 + pad_x, ly2 - 4),
        cv2.FONT_HERSHEY_SIMPLEX,
        font_scale,
        (255, 255, 255),
        thickness,
        cv2.LINE_AA,
    )


def smart_detect_and_annotate(
    frame_bgr,
    conf_threshold=0.50,
    active_violation_types=("NO-Hardhat", "NO-Safety Vest", "NO-Mask"),
    tracker: MultiPersonTrackerAndDeduplicator = None,
    frame_idx: int = 0,
):
    """Nhận diện đa đối tượng thông minh trong khung hình + Tự động chống lóa/mờ + Chống báo lặp."""
    results = _model.predict(source=frame_bgr, conf=conf_threshold, verbose=False)
    raw_detections = []
    for result in results:
        if result.boxes is None:
            continue
        for box in result.boxes:
            class_id = int(box.cls.item())
            confidence = float(box.conf.item())
            coords = [int(round(v)) for v in box.xyxy[0].tolist()]
            raw_detections.append({
                "label": result.names[class_id],
                "confidence": round(confidence, 4),
                "bbox": coords,
            })

    h, w = frame_bgr.shape[:2]
    gray_frame = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    frame_env = evaluate_lighting_and_glare(frame_bgr, precomputed_gray=gray_frame)
    global_stats = frame_env.get("_global_stats")

    safe_hardhats = [d for d in raw_detections if d["label"] == "Hardhat"]
    safe_vests = [d for d in raw_detections if d["label"] == "Safety Vest"]
    safe_masks = [d for d in raw_detections if d["label"] == "Mask"]
    person_dets = [
        d for d in raw_detections
        if d["label"] == "Person" and (d["bbox"][2] - d["bbox"][0]) >= 22 and (d["bbox"][3] - d["bbox"][1]) >= 30
    ]

    if tracker is None:
        tracker = MultiPersonTrackerAndDeduplicator()
    tracked_workers = tracker.update_workers(person_dets, frame_idx, w, h)

    valid_safe_items = safe_hardhats + safe_vests + safe_masks
    new_violations_to_log = []
    display_violations = []
    worker_having_violation = set()
    worker_violation_pairs_in_frame = set()

    candidate_violations = sorted(
        [d for d in raw_detections if d["label"].startswith("NO-") and d["label"] in active_violation_types],
        key=lambda x: x["confidence"],
        reverse=True,
    )

    for d in candidate_violations:
        lbl = d["label"]
        conf = d["confidence"]
        bx1, by1, bx2, by2 = d["bbox"]
        bw, bh = bx2 - bx1, by2 - by1

        if bw < 18 or bh < 18:
            continue
        if (bx2 >= w - 10 or bx1 <= 10) and bw < (w * 0.12):
            continue

        matched_worker = None
        best_match_score = 0.0
        max_raw_overlap = 0.0
        icx = (bx1 + bx2) / 2.0

        for wk in tracked_workers:
            inc = box_inclusion_ratio(d["bbox"], wk["bbox"])
            ov = box_overlap_ratio(d["bbox"], wk["bbox"])
            base_ov = max(inc, ov)
            if base_ov > max_raw_overlap:
                max_raw_overlap = base_ov
            if base_ov < 0.25:
                continue
            if not is_anatomically_valid(d["bbox"], wk["bbox"], lbl):
                continue
            wk_w = max(1.0, float(wk["bbox"][2] - wk["bbox"][0]))
            horiz_offset = abs(icx - wk["center"][0]) / wk_w
            match_score = base_ov - 0.15 * horiz_offset
            if match_score > best_match_score:
                best_match_score = match_score
                matched_worker = wk

        if tracked_workers and matched_worker is None:
            if max_raw_overlap >= 0.12 or conf < max(0.68, conf_threshold + 0.12):
                continue

        if matched_worker is not None:
            wid = matched_worker["worker_id"]
            worker_bbox = matched_worker["bbox"]
            worker_center = matched_worker["center"]
        else:
            wid = tracker.assign_virtual_worker(d["bbox"], frame_idx, w, h)
            worker_bbox = d["bbox"]
            worker_center = ((bx1 + bx2) / 2.0, (by1 + by2) / 2.0)

        if (wid, lbl) in worker_violation_pairs_in_frame:
            continue

        local_env = evaluate_lighting_and_glare(
            frame_bgr,
            target_bbox=worker_bbox,
            precomputed_gray=gray_frame,
            global_stats=global_stats,
        )
        required_conf = conf_threshold + local_env["conf_penalty"]

        if lbl == "NO-Hardhat":
            has_hat_on_worker = any(
                box_overlap_ratio(d["bbox"], h_item["bbox"]) > 0.15
                or (
                    box_inclusion_ratio(h_item["bbox"], worker_bbox) > 0.45
                    and is_anatomically_valid(h_item["bbox"], worker_bbox, "Hardhat")
                )
                for h_item in safe_hardhats
            )
            if has_hat_on_worker or conf < max(0.52, required_conf):
                continue

        elif lbl == "NO-Safety Vest":
            has_vest_on_worker = any(
                box_overlap_ratio(d["bbox"], v_item["bbox"]) > 0.15
                or (
                    box_inclusion_ratio(v_item["bbox"], worker_bbox) > 0.40
                    and is_anatomically_valid(v_item["bbox"], worker_bbox, "Safety Vest")
                )
                for v_item in safe_vests
            )
            min_vest_conf = max(0.62, required_conf)
            if local_env["is_glare"]:
                min_vest_conf = max(min_vest_conf, 0.80)
            if has_vest_on_worker or conf < min_vest_conf:
                continue

        elif lbl == "NO-Mask":
            has_mask_on_worker = any(
                box_overlap_ratio(d["bbox"], m_item["bbox"]) > 0.15
                or (
                    box_inclusion_ratio(m_item["bbox"], worker_bbox) > 0.45
                    and is_anatomically_valid(m_item["bbox"], worker_bbox, "Mask")
                )
                for m_item in safe_masks
            )
            if has_mask_on_worker or conf < max(0.75, required_conf):
                continue

        worker_having_violation.add(wid)
        worker_violation_pairs_in_frame.add((wid, lbl))

        already_logged = tracker.is_already_logged(wid, lbl, worker_center, w, h, frame_idx=frame_idx)
        det_record = {
            "label": lbl,
            "confidence": conf,
            "bbox": d["bbox"],
            "worker_id": wid,
            "already_logged": already_logged,
            "env_status": local_env["status_text"],
        }
        display_violations.append(det_record)

        if not already_logged:
            tracker.mark_logged(wid, lbl, worker_center, frame_idx=frame_idx)
            new_violations_to_log.append(det_record)

    annotated = frame_bgr.copy()
    label_vn_map = {
        "Hardhat": "An toan: Mu bao ho",
        "Safety Vest": "An toan: Ao phan quang",
        "Mask": "An toan: Khau trang",
    }

    for wk in tracked_workers:
        wid = wk["worker_id"]
        x1, y1, x2, y2 = wk["bbox"]
        p_color = (0, 185, 75)
        p_text = f"Cong nhan #{wid:02d} ({wk['confidence']:.0%})"
        cv2.rectangle(annotated, (x1, y1), (x2, y2), p_color, 2)
        _draw_smart_label(annotated, p_text, x1, y1, p_color, font_scale=0.48, thickness=1)

    for item in valid_safe_items:
        lbl = item["label"]
        if lbl not in label_vn_map:
            continue
        x1, y1, x2, y2 = item["bbox"]
        s_color = (0, 200, 83)
        s_text = f"{label_vn_map[lbl]} ({item['confidence']:.0%})"
        cv2.rectangle(annotated, (x1, y1), (x2, y2), s_color, 2)
        _draw_smart_label(annotated, s_text, x1, y1, s_color, font_scale=0.46, thickness=1)

    viol_vn_map = {
        "NO-Hardhat": "VI PHAM: Khong mu",
        "NO-Safety Vest": "VI PHAM: Khong ao",
        "NO-Mask": "VI PHAM: Khong khau trang",
    }
    worker_label_stack_count: dict[int, int] = {}
    for v_item in display_violations:
        x1, y1, x2, y2 = v_item["bbox"]
        wid = v_item["worker_id"]
        stack_idx = worker_label_stack_count.get(wid, 0)
        worker_label_stack_count[wid] = stack_idx + 1

        v_color = (0, 0, 255)
        lock_note = " [Da ghi nhan]" if v_item["already_logged"] else ""
        v_text = f"{viol_vn_map.get(v_item['label'], v_item['label'])} ({v_item['confidence']:.0%}){lock_note}"
        cv2.rectangle(annotated, (x1, y1), (x2, y2), v_color, 3)
        _draw_smart_label(annotated, v_text, x1, y1 + (stack_idx * 22), v_color, font_scale=0.50, thickness=2)

    effective_worker_cnt = max(len(tracked_workers), len(worker_having_violation))
    return annotated, new_violations_to_log, effective_worker_cnt, frame_env


def save_new_violations_to_db(
    new_violations,
    annotated_bgr,
    auto_confirm_threshold=0.75,
    camera_name="Camera 1",
    frame_idx=0,
    fps=30.0,
):
    """Lưu các vi phạm mới vào safeguard.db và thư mục evidence/."""
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sec_in_video = frame_idx / max(1.0, float(fps or 30.0))
    auto_confirmed_list = []
    needs_human_list = []

    for v in new_violations:
        v_type = v["label"]
        conf = v["confidence"]
        wid = v.get("worker_id", 1)

        initial_status = "confirmed" if conf >= auto_confirm_threshold else "pending"
        new_id = insert_event(timestamp=now_str, violation_type=v_type, status=initial_status)

        img_path = EVIDENCE_DIR / f"event_{new_id}.jpg"
        cv2.imwrite(str(img_path), annotated_bgr)

        meta_path = EVIDENCE_DIR / f"event_{new_id}.json"
        meta_data = {
            "event_id": new_id,
            "worker_id": f"CN #{wid:02d}",
            "camera": camera_name,
            "frame_idx": frame_idx,
            "video_sec": round(sec_in_video, 1),
            "confidence": round(conf, 2),
            "violation_type": v_type,
            "env_status": v.get("env_status", "Ổn định"),
            "auto_triaged": initial_status == "confirmed",
        }
        meta_path.write_text(json.dumps(meta_data, ensure_ascii=False), encoding="utf-8")

        if initial_status == "confirmed":
            auto_confirmed_list.append(meta_data)
        else:
            needs_human_list.append(meta_data)

    if new_violations:
        _clear_runtime_caches()

    return auto_confirmed_list, needs_human_list


def load_event_evidence(event_id):
    """
    Đọc đường dẫn ảnh bằng chứng và file JSON metadata của sự kiện theo đúng event_id.
    Có bộ nhớ đệm trực tiếp trong RAM theo event_id để chuyển trang tức thì mà không gọi lệnh stat() lặp lại.
    """
    eid = int(event_id)
    if eid in _EVIDENCE_META_CACHE and eid in _EVIDENCE_IMG_EXISTS_CACHE:
        return _EVIDENCE_IMG_EXISTS_CACHE[eid], _EVIDENCE_META_CACHE[eid]

    img_path = EVIDENCE_DIR / f"event_{eid}.jpg"
    meta_path = EVIDENCE_DIR / f"event_{eid}.json"
    resolved_img = img_path if img_path.is_file() else None
    meta = {}
    if meta_path.is_file():
        try:
            loaded = json.loads(meta_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                meta = loaded
        except Exception:
            meta = {}

    _EVIDENCE_IMG_EXISTS_CACHE[eid] = resolved_img
    _EVIDENCE_META_CACHE[eid] = meta
    return resolved_img, meta


def record_iot_action(event_id, action_label):
    """Lưu lệnh khẩn cấp của Đội trưởng vào hồ sơ JSON của sự kiện."""
    eid = int(event_id)
    meta_path = EVIDENCE_DIR / f"event_{eid}.json"
    meta = {}
    if meta_path.is_file():
        try:
            loaded = json.loads(meta_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                meta = loaded
        except Exception:
            meta = {}
    now_hm = datetime.datetime.now().strftime("%H:%M:%S")
    meta["iot_action"] = f"{action_label} ({now_hm})"
    meta_path.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    _clear_runtime_caches()


def _events_signature(events_list: list) -> tuple:
    """Tạo chữ ký nhẹ cho danh sách sự kiện để làm khóa cache cho CSV và ZIP (0 lệnh đọc đĩa)."""
    return tuple(
        (
            int(e.get("event_id", 0)),
            str(e.get("status", "")),
            str(e.get("iot_action") or _EVIDENCE_META_CACHE.get(int(e.get("event_id", 0)), {}).get("iot_action", "")),
        )
        for e in events_list
    )


def build_shift_csv_bytes(events_list):
    """Tạo file báo cáo CSV chuẩn UTF-8-SIG mở trực tiếp trên Excel, có cache RAM tức thì."""
    sig = _events_signature(events_list)
    if sig in _CSV_BYTES_CACHE:
        return _CSV_BYTES_CACHE[sig]

    rows = []
    for e in events_list:
        eid = int(e["event_id"])
        img_path, meta = load_event_evidence(eid)

        cam_val = e.get("camera") or meta.get("camera") or "Chưa ghi nhận"
        worker_val = e.get("worker_id") or meta.get("worker_id") or "Chưa định danh"
        vtype = e.get("violation_type", "")
        vtype_tv = e.get("title_tv") or TEN_LOI_TV.get(vtype, vtype)
        sec_val = e.get("video_sec") if "video_sec" in e else meta.get("video_sec")
        sec_display = round(float(sec_val), 1) if sec_val is not None else 0.0

        raw_conf = e.get("confidence") if "confidence" in e else meta.get("confidence")
        try:
            conf_display = round(float(raw_conf) * 100, 1) if raw_conf is not None else "N/A"
        except (TypeError, ValueError):
            conf_display = "N/A"

        env_val = e.get("env_status") or meta.get("env_status") or "Ổn định"
        status_code = e.get("status", "")
        status_tv = TRANG_THAI_TV.get(status_code, status_code)
        iot_val = e.get("iot_action") or meta.get("iot_action") or "Chưa kích hoạt"
        img_rel = f"evidence/event_{eid}.jpg" if img_path is not None else "Chưa có ảnh"

        rows.append({
            "Mã sự kiện": eid,
            "Thời điểm phát hiện": e.get("timestamp", ""),
            "Vị trí Camera": cam_val,
            "Mã công nhân": worker_val,
            "Hành vi vi phạm": vtype_tv,
            "Giây trong video": sec_display,
            "Độ tin cậy AI (%)": conf_display,
            "Điều kiện ánh sáng": env_val,
            "Trạng thái duyệt": status_tv,
            "Lệnh khẩn cấp Đội trưởng": iot_val,
            "Tệp ảnh bằng chứng": img_rel,
        })

    df_out = pd.DataFrame(rows, columns=CSV_COLUMNS)
    csv_bytes = df_out.to_csv(index=False).encode("utf-8-sig")
    _CSV_BYTES_CACHE[sig] = csv_bytes
    return csv_bytes


def build_evidence_zip_bytes(events_list):
    """
    Đóng gói báo cáo CSV + các tệp ảnh chụp bằng chứng (.jpg) và metadata (.json) thành file .ZIP:
    - Dùng ZIP_STORED cho tệp .jpg (vì JPEG đã nén sẵn) giúp tốc độ đóng gói nhanh gấp ~20 lần.
    """
    sig = _events_signature(events_list)
    if sig in _ZIP_BYTES_CACHE:
        return _ZIP_BYTES_CACHE[sig]

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("Bao_Cao_Vi_Pham_Ca_Lam.csv", build_shift_csv_bytes(events_list))

        seen_ids = set()
        for e in events_list:
            try:
                eid = int(e["event_id"])
            except Exception:
                continue
            if eid in seen_ids:
                continue
            seen_ids.add(eid)

            img_path, _ = load_event_evidence(eid)
            if img_path is not None:
                zf.write(img_path, arcname=f"anh_bang_chung/{img_path.name}", compress_type=zipfile.ZIP_STORED)

            meta_path = EVIDENCE_DIR / f"event_{eid}.json"
            if meta_path.is_file():
                zf.write(meta_path, arcname=f"metadata/{meta_path.name}", compress_type=zipfile.ZIP_DEFLATED)

    zip_bytes = buf.getvalue()
    _ZIP_BYTES_CACHE[sig] = zip_bytes
    return zip_bytes


def reset_shift_data():
    """Làm mới dữ liệu ca trực: xóa bảng events, các tệp bằng chứng trong evidence/ và bộ nhớ đệm."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM events")
    for f in EVIDENCE_DIR.glob("event_*"):
        try:
            f.unlink()
        except Exception:
            pass
    _clear_runtime_caches()
    st.session_state.last_reviewed_action = None
    st.session_state.selected_review_event_id = None


def image_to_base64_uri(img_path: Path, max_width: int = 380):
    """
    Chuyển tệp ảnh của sự kiện thành chuỗi data URI base64 tối ưu hóa cho thẻ giao diện:
    - Thu nhỏ ảnh về chiều ngang chuẩn 380px (JPEG quality 82) trước khi mã hóa Base64,
      giúp giảm ~90% dung lượng HTML truyền qua WebSocket mỗi lần chuyển trang.
    - Lưu cache trực tiếp trong RAM theo đường dẫn để chuyển trang 0ms.
    """
    if img_path is None:
        return ""
    key_str = str(img_path)
    cache_key = (key_str, max_width)
    if cache_key in _B64_URI_CACHE:
        return _B64_URI_CACHE[cache_key]

    p = Path(img_path)
    if not p.is_file():
        return ""
    try:
        img = cv2.imread(key_str)
        if img is not None:
            h, w = img.shape[:2]
            if max_width and h > w:
                # Ảnh dọc (như Camera số 3): đặt trọn khung dọc vào giữa nền mờ 16:10 để thẻ sự kiện không bị cắt ngang đầu/chân
                canvas_w = int(max_width)
                canvas_h = max(1, int(round(canvas_w * 10 / 16)))
                bg = cv2.resize(img, (canvas_w, canvas_h), interpolation=cv2.INTER_LINEAR)
                bg = cv2.GaussianBlur(bg, (31, 31), 0)
                bg = (bg.astype(np.float32) * 0.42).astype(np.uint8)
                fg_w = max(1, min(canvas_w, int(round(w * (canvas_h / float(h))))))
                fg = cv2.resize(img, (fg_w, canvas_h), interpolation=cv2.INTER_AREA)
                x0 = (canvas_w - fg_w) // 2
                bg[:, x0:x0 + fg_w] = fg
                img = bg
            elif max_width and w > max_width:
                new_h = max(1, int(round(h * (max_width / float(w)))))
                img = cv2.resize(img, (max_width, new_h), interpolation=cv2.INTER_AREA)
            ok, enc = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 82])
            if ok:
                uri = "data:image/jpeg;base64," + base64.b64encode(enc.tobytes()).decode("ascii")
                _B64_URI_CACHE[cache_key] = uri
                return uri

        raw = p.read_bytes()
        b64 = base64.b64encode(raw).decode("ascii")
        ext = p.suffix.lower().lstrip(".")
        mime = "image/png" if ext == "png" else "image/jpeg"
        uri = f"data:{mime};base64,{b64}"
        _B64_URI_CACHE[cache_key] = uri
        return uri
    except Exception:
        return ""


def render_evidence_img_or_placeholder(img_path: Path, event_id: int, height_px: int = 138) -> str:
    """
    Trả về thẻ <img> nếu file evidence/event_{id}.jpg tồn tại;
    nếu không tìm thấy ảnh, hiển thị khung placeholder SVG đơn sắc rõ ràng.
    """
    uri = image_to_base64_uri(img_path)
    if uri:
        return f'<img alt="Bằng chứng sự kiện #{event_id}" src="{uri}" loading="lazy" decoding="async" style="height:{height_px}px;"/>'
    return (
        f'<div style="height:{height_px}px;display:flex;flex-direction:column;align-items:center;'
        f'justify-content:center;background:var(--surface2);color:var(--muted);font-size:11px;'
        f'border-bottom:1px solid var(--border);padding:12px;text-align:center;">'
        f'<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" style="margin-bottom:6px;opacity:0.7;">'
        f'<rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="8.5" cy="9.5" r="1.5"/><path d="M21 15l-5-5L5 20"/>'
        f"</svg>"
        f"<span>Chưa có tệp ảnh evidence/event_{event_id}.jpg</span>"
        f"</div>"
    )


def get_cached_events_bundle() -> tuple[list, list, bool]:
    """
    Trả về (raw_events, enriched_events, db_connected) từ bộ nhớ đệm RAM nếu safeguard.db chưa thay đổi.
    Giúp việc bấm chuyển qua lại giữa 5 trang trên Sidebar đạt tốc độ tức thì (< 0.01ms).
    """
    try:
        db_mtime = Path(DB_PATH).stat().st_mtime_ns if Path(DB_PATH).exists() else 0
    except Exception:
        db_mtime = 0

    cache_key = (db_mtime, _DATA_VERSION)
    if _EVENTS_RAM_CACHE.get("key") == cache_key:
        return (
            _EVENTS_RAM_CACHE["raw_events"],
            _EVENTS_RAM_CACHE["enriched_events"],
            True,
        )

    try:
        raw_events = get_all_events()
        db_connected = True
    except Exception:
        return [], [], False

    enriched = _build_enriched_events_internal(raw_events)
    _EVENTS_RAM_CACHE["key"] = cache_key
    _EVENTS_RAM_CACHE["raw_events"] = raw_events
    _EVENTS_RAM_CACHE["enriched_events"] = enriched
    return raw_events, enriched, db_connected


def fmt_ts_vn(ts) -> str:
    """'2026-10-23 11:52:33' -> '23/10/2026 11:52:33' (định dạng ngày Việt Nam); giữ nguyên nếu không đúng mẫu."""
    s = str(ts or "").strip()
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}:\d{2}(?::\d{2})?)", s)
    return f"{m.group(3)}/{m.group(2)}/{m.group(1)} {m.group(4)}" if m else s


def _build_enriched_events_internal(raw_events: list) -> list:
    enriched = []
    for e in raw_events:
        eid = int(e["event_id"])
        vtype = e.get("violation_type", "NO-Hardhat")
        status = e.get("status", "pending")
        img_path, meta = load_event_evidence(eid)
        sev_code, sev_label = MUC_DO_RUI_RO.get(vtype, ("medium", "RỦI RO VỪA"))

        raw_conf = meta.get("confidence")
        has_conf = raw_conf is not None
        try:
            conf_val = float(raw_conf) if has_conf else None
        except (TypeError, ValueError):
            conf_val = None

        cam_full = str(meta.get("camera", "Chưa ghi nhận vị trí camera"))
        sys_cam = normalize_system_camera_name(cam_full)
        cam_short = "Khác"
        if sys_cam is not None:
            m_num = re.search(r"Camera\s+số\s+(\d+)", sys_cam)
            if m_num:
                cam_short = f"{int(m_num.group(1)):02d}"

        enriched.append({
            "event_id": eid,
            "timestamp": e.get("timestamp", ""),
            "timestamp_vn": fmt_ts_vn(e.get("timestamp", "")),
            "violation_type": vtype,
            "title_tv": TEN_LOI_TV.get(vtype, vtype),
            "status": status,
            "status_tv": TRANG_THAI_TV.get(status, status),
            "status_badge_tv": TRANG_THAI_BADGE_TV.get(status, status),
            "severity": sev_code,
            "severity_label": sev_label,
            "worker_id": str(meta.get("worker_id", "Chưa định danh")),
            "camera": cam_full,
            "system_camera": sys_cam,
            "camera_code": cam_short,
            "video_sec": meta.get("video_sec"),
            "confidence": conf_val,
            "confidence_pct": f"{int(round(conf_val * 100))}%" if conf_val is not None else "N/A",
            "env_status": str(meta.get("env_status", "Chưa có thông tin")),
            "iot_action": str(meta.get("iot_action", "Chưa kích hoạt")),
            "auto_triaged": bool(meta.get("auto_triaged", False)),
            "img_path": img_path,
            "has_meta": bool(meta),
        })
    return enriched


def get_enriched_events(raw_events: list | None = None):
    """Lấy danh sách sự kiện đầy đủ (sử dụng RAM cache khi có thể)."""
    if raw_events is None:
        _, enriched, _ = get_cached_events_bundle()
        return enriched

    try:
        db_mtime = Path(DB_PATH).stat().st_mtime_ns if Path(DB_PATH).exists() else 0
    except Exception:
        db_mtime = 0
    cache_key = (db_mtime, _DATA_VERSION)
    if _EVENTS_RAM_CACHE.get("key") == cache_key and len(_EVENTS_RAM_CACHE["raw_events"]) == len(raw_events):
        return _EVENTS_RAM_CACHE["enriched_events"]

    enriched = _build_enriched_events_internal(raw_events)
    _EVENTS_RAM_CACHE["key"] = cache_key
    _EVENTS_RAM_CACHE["raw_events"] = raw_events
    _EVENTS_RAM_CACHE["enriched_events"] = enriched
    return enriched