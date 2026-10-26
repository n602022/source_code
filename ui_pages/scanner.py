# -*- coding: utf-8 -*-
"""
ui_pages/scanner.py — Trang Quét AI & Camera (Live Monitoring V2).
Đã áp dụng các đề xuất tinh gọn đúng & tốt mà không ảnh hưởng đến Báo cáo Word:
1. Giữ hiển thị trực tiếp 2 thanh trượt (`Độ nhạy phát hiện`, `Ngưỡng tự xác nhận`), `Tốc độ quét` và `Quy tắc phân luồng`
   trong khung `Cấu hình AI` để khớp 100% với Chương 2, Chương 3, Chương 4 và Chương 6 của Báo cáo Word.
2. Gộp 3 thẻ Telemetry dưới màn hình quét thành một thanh trạng thái 1 dòng gọn gàng (`02 công nhân · Độ nét ổn định (671.0) · Ánh sáng bình thường (0.0%)`), tự động đổi sang tông vàng cảnh báo khi phát hiện khung hình mờ hoặc chói sáng.
3. Chuyển nút `Làm mới dữ liệu ca trực` xuống góc phải tiêu đề khung `Nhật ký phiên quét` (đúng ngữ cảnh dữ liệu)
   và thêm hộp thoại xác nhận `@st.dialog` để ngăn bấm nhầm xóa mất dữ liệu ca trực.
4. Lược bỏ hộp chọn `10 dòng / trang` trong Nhật ký phiên quét, chỉ giữ thanh chuyển trang `‹ Trước | Trang X / Y | Sau ›`.
"""
import base64
import html as _html
import math
import tempfile
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import streamlit as st

from core_logic import (
    MultiPersonTrackerAndDeduplicator,
    TEN_LOI_TV,
    TRANG_THAI_TV,
    clean_html,
    find_sample_videos,
    fmt_ts_vn,
    get_active_violation_types,
    get_effective_auto_confirm,
    load_event_evidence,
    play_alert_beep,
    reset_shift_data,
    save_new_violations_to_db,
    smart_detect_and_annotate,
)
from ui_components import render_data_table
from video_processor import get_video_info, read_frames

SCAN_LOG_PAGE_SIZE = 8


def _set_scan_source_mode(mode_val: str):
    st.session_state.scan_source_mode = mode_val


def _set_scan_cam_idx(idx: int):
    st.session_state.scan_cam_idx = int(idx)


def _change_scan_log_page(delta: int, max_page: int):
    cur = int(st.session_state.get("scan_log_page", 1))
    st.session_state.scan_log_page = max(1, min(max_page, cur + delta))


@st.dialog("Xác nhận làm mới dữ liệu ca trực")
def _confirm_reset_shift_dialog(total_events: int):
    """Hộp thoại xác nhận trước khi xóa toàn bộ dữ liệu sự kiện và ảnh bằng chứng của ca trực."""
    st.markdown(
        f"Bạn có chắc chắn muốn xóa toàn bộ **{total_events} sự kiện** và ảnh bằng chứng của ca trực hiện tại để bắt đầu ca mới không? "
        f"Thao tác này không thể hoàn tác."
    )
    c_cancel, c_ok = st.columns(2, gap="small")
    with c_cancel:
        if st.button("Hủy", width="stretch", key="dlg_reset_cancel"):
            st.rerun()
    with c_ok:
        with st.container(key="dlg_confirm_wrap"):
            if st.button("Xác nhận làm mới", type="primary", width="stretch", key="dlg_reset_ok"):
                reset_shift_data()
                st.session_state.scan_log_page = 1
                st.rerun()


def _normalize_scan_frame(frame):
    """
    Chuẩn hóa kích thước khung hình cho video dọc (như Camera số 3):
    Nếu khung hình dọc quá cao (h > w và h > 640), thu nhỏ tỷ lệ về chiều cao 640px để nhãn chữ
    và khung bounding box rõ nét, đồng thời tăng tốc độ nhận diện YOLOv8.
    """
    if frame is None:
        return frame
    h, w = frame.shape[:2]
    if h > w and h > 640:
        scale = 640.0 / float(h)
        new_w = max(1, int(round(w * scale)))
        return cv2.resize(frame, (new_w, 640), interpolation=cv2.INTER_AREA)
    return frame


@st.cache_data(show_spinner=False)
def _camera_thumb_uri(path_str: str, v_tag: int = 2) -> str:
    """Ảnh xem trước 16:10 lấy từ một khung hình của video; nếu là video dọc thì đặt giữa nền mờ để không bị cắt ngang."""
    try:
        cap = cv2.VideoCapture(path_str)
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        if total > 30:
            cap.set(cv2.CAP_PROP_POS_FRAMES, min(total // 5, 150))
        ok, frame = cap.read()
        cap.release()
        if not ok or frame is None:
            return ""
        h, w = frame.shape[:2]
        target = 16 / 10
        if h > w:
            bg = cv2.resize(frame, (160, 100), interpolation=cv2.INTER_LINEAR)
            bg = cv2.GaussianBlur(bg, (25, 25), 0)
            bg = (bg.astype(np.float32) * 0.42).astype(np.uint8)
            fg_w = max(1, min(160, int(round(w * (100.0 / float(h))))))
            fg = cv2.resize(frame, (fg_w, 100), interpolation=cv2.INTER_AREA)
            x0 = (160 - fg_w) // 2
            bg[:, x0:x0 + fg_w] = fg
            frame = bg
        elif w / h > target:
            new_w = int(h * target)
            x0 = (w - new_w) // 2
            frame = cv2.resize(frame[:, x0:x0 + new_w], (160, 100), interpolation=cv2.INTER_AREA)
        else:
            new_h = int(w / target)
            y0 = (h - new_h) // 2
            frame = cv2.resize(frame[y0:y0 + new_h, :], (160, 100), interpolation=cv2.INTER_AREA)
        ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 74])
        return "data:image/jpeg;base64," + base64.b64encode(buf.tobytes()).decode() if ok else ""
    except Exception:
        return ""


@st.cache_data(show_spinner=False, max_entries=24)
def _cached_first_frame_preview(
    video_path_str: str,
    conf_threshold: float,
    active_violations_tuple: tuple[str, ...],
    v_tag: int = 2,
):
    """
    Lưu cache kết quả nhận diện YOLOv8 của khung hình đầu tiên theo (video, độ nhạy, loại lỗi):
    Giúp mở trang Quét AI & Camera hoặc bấm chuyển đổi giữa Camera 01..05 mượt tức thì (< 2ms).
    """
    preview_tracker = MultiPersonTrackerAndDeduplicator()
    for _, frame in read_frames(video_path_str, frame_step=1, max_width=720):
        frame = _normalize_scan_frame(frame)
        annotated_bgr, _, worker_cnt, env_info = smart_detect_and_annotate(
            frame,
            conf_threshold=conf_threshold,
            active_violation_types=active_violations_tuple,
            tracker=preview_tracker,
            frame_idx=1,
        )
        ok, jpg_buf = cv2.imencode(".jpg", annotated_bgr, [cv2.IMWRITE_JPEG_QUALITY, 86])
        b64_uri = (
            "data:image/jpeg;base64," + base64.b64encode(jpg_buf.tobytes()).decode("ascii")
            if ok
            else ""
        )
        return b64_uri, int(worker_cnt), {
            "blur_score": env_info["blur_score"],
            "glare_pct": env_info["glare_pct"],
            "is_glare": env_info.get("is_glare", False),
            "is_blur": env_info.get("is_blur", False),
            "status_text": env_info["status_text"],
        }
    return "", 0, {
        "blur_score": 0.0,
        "glare_pct": 0.0,
        "is_glare": False,
        "is_blur": False,
        "status_text": "Chưa có khung hình",
    }


def _build_monitor_frame_html(
    img_uri: str,
    top_left_text: str,
    top_right_text: str,
    bottom_left_text: str,
) -> str:
    """Dựng khung hình 16:9 kèm 3 nhãn overlay góc ảnh theo đúng thiết kế Prototype V2."""
    if not img_uri:
        return clean_html(
            """
            <div class="sg-monitor-frame" style="display:flex;align-items:center;justify-content:center;color:#9BAEC7;font-size:12px;">
                Chưa có tín hiệu khung hình
            </div>
            """
        )
    return clean_html(
        f"""
        <div class="sg-monitor-frame">
            <div class="sg-monitor-blur-bg" style="background-image:url('{img_uri}');"></div>
            <img alt="Khung hình giám sát AI" src="{img_uri}" />
            <div class="sg-monitor-overlay top-left">{top_left_text}</div>
            <div class="sg-monitor-overlay top-right">{top_right_text}</div>
            <div class="sg-monitor-overlay bottom-left">{bottom_left_text}</div>
        </div>
        """
    )


def _build_telemetry_html(worker_cnt: int, env_info: dict) -> str:
    """
    Gộp thông số Telemetry dưới màn hình quét thành 1 thanh trạng thái ngang gọn gàng:
    - Bình thường: hiển thị số công nhân + 'Hình ảnh & ánh sáng ổn định' kèm chỉ số độ nét/độ lóa.
    - Khi bị mờ hoặc lóa sáng: đổi sang tông vàng cảnh báo và nêu rõ lý do.
    """
    blur_val = float(env_info.get("blur_score", 0.0))
    glare_val = float(env_info.get("glare_pct", 0.0))
    is_blur = bool(env_info.get("is_blur", False))
    is_glare = bool(env_info.get("is_glare", False))
    status_txt = str(env_info.get("status_text", "Ánh sáng và độ nét ổn định"))

    is_warn = is_blur or is_glare
    bar_cls = "sg-telemetry-line warn" if is_warn else "sg-telemetry-line"
    dot_cls = "sg-tele-dot warn" if is_warn else "sg-tele-dot"

    return clean_html(
        f"""
        <div class="{bar_cls}">
            <div class="sg-tele-main">
                <span class="{dot_cls}"></span>
                <strong>{worker_cnt:02d} công nhân trong khung</strong>
                <span class="sg-tele-sep">·</span>
                <span>{status_txt}</span>
            </div>
            <div class="sg-tele-metrics">
                Độ nét: <b>{blur_val:.0f}</b> · Độ lóa: <b>{glare_val:.1f}%</b>
            </div>
        </div>
        """
    )


def render_scanner_page(raw_events: list):
    """
    Hiển thị trang Quét AI & Camera theo bố cục 2 cột cân bằng chiều cao:
    - Cột chính bên trái (`col_main`): Trên là Màn hình Giám sát AI 16:9 cỡ lớn, dưới là dải Nguồn Camera nằm ngang.
    - Cột điều khiển bên phải (`col_controls`): Cấu hình AI + Hành vi giám sát.
    """
    sample_videos = find_sample_videos()

    col_main, col_controls = st.columns([2.32, 1.02], gap="medium")

    # ==========================================================================
    # CỘT PHẢI: CẤU HÌNH AI & HÀNH VI GIÁM SÁT
    # ==========================================================================
    with col_controls:
        with st.container(key="panel_scan_controls"):
            st.markdown(
                clean_html('<div class="sg-panel-title" style="margin-bottom:2px;">Cấu hình AI</div>'),
                unsafe_allow_html=True,
            )

            cur_sens = float(
                st.session_state.get("scan_slider_sens", st.session_state.get("ai_sensitivity", 0.50))
            )
            st.markdown(
                clean_html(
                    f'<div class="sg-ctrl-label"><span>Độ nhạy phát hiện</span><b>{int(round(cur_sens * 100))}%</b></div>'
                ),
                unsafe_allow_html=True,
            )
            ai_sensitivity = st.slider(
                "Độ nhạy phát hiện",
                min_value=0.30,
                max_value=0.85,
                value=cur_sens,
                step=0.05,
                label_visibility="collapsed",
                key="scan_slider_sens",
            )
            st.session_state.ai_sensitivity = ai_sensitivity

            cur_auto = float(
                st.session_state.get("scan_slider_thresh", st.session_state.get("auto_confirm_level", 0.75))
            )
            st.markdown(
                clean_html(
                    f'<div class="sg-ctrl-label"><span>Ngưỡng tự xác nhận</span><b>{int(round(cur_auto * 100))}%</b></div>'
                ),
                unsafe_allow_html=True,
            )
            auto_confirm_level = st.slider(
                "Ngưỡng tự xác nhận",
                min_value=0.55,
                max_value=0.95,
                value=cur_auto,
                step=0.05,
                label_visibility="collapsed",
                key="scan_slider_thresh",
            )
            st.session_state.auto_confirm_level = auto_confirm_level
            effective_auto_confirm = get_effective_auto_confirm()

            speed_options = {
                5: "Nhanh (5x)",
                3: "Bình thường (3x)",
                1: "Chậm (1x)",
                8: "Rất nhanh (8x)",
                12: "Tối đa (12x)",
            }
            cur_speed = int(st.session_state.get("scan_speed_step", 5))
            if cur_speed not in speed_options:
                cur_speed = 5
            st.markdown(
                clean_html('<div class="sg-ctrl-label"><span>Tốc độ quét</span></div>'),
                unsafe_allow_html=True,
            )
            speed_step = st.selectbox(
                "Tốc độ quét",
                options=list(speed_options.keys()),
                format_func=lambda k: speed_options[k],
                index=list(speed_options.keys()).index(cur_speed),
                label_visibility="collapsed",
                key="scan_speed_select",
            )
            st.session_state.scan_speed_step = int(speed_step)

            st.markdown(
                clean_html(
                    f"""
                    <div class="sg-threshold-note">
                        <b>Quy tắc phân luồng</b>
                        <p>
                            ≥{effective_auto_confirm:.0%}: AI tự xác nhận<br/>
                            {ai_sensitivity:.0%}–{max(ai_sensitivity, effective_auto_confirm - 0.01):.0%}: chờ giám sát duyệt
                        </p>
                    </div>
                    """
                ),
                unsafe_allow_html=True,
            )

            st.markdown(
                clean_html('<div class="sg-panel-title sg-behavior-heading">Hành vi giám sát</div>'),
                unsafe_allow_html=True,
            )
            check_hardhat = st.toggle(
                "Mũ bảo hộ",
                value=bool(st.session_state.get("check_hardhat", True)),
                key="scan_tgl_hardhat",
            )
            check_vest = st.toggle(
                "Áo phản quang",
                value=bool(st.session_state.get("check_vest", True)),
                key="scan_tgl_vest",
            )
            check_mask = st.toggle(
                "Khẩu trang",
                value=bool(st.session_state.get("check_mask", False)),
                key="scan_tgl_mask",
            )
            enable_audio = st.toggle(
                "Âm thanh cảnh báo",
                value=bool(st.session_state.get("enable_audio", True)),
                key="scan_tgl_audio",
            )

            st.session_state.check_hardhat = check_hardhat
            st.session_state.check_vest = check_vest
            st.session_state.check_mask = check_mask
            st.session_state.enable_audio = enable_audio
            active_violations = get_active_violation_types()

    # ==========================================================================
    # CỘT TRÁI (CHÍNH): TRÊN LÀ MÀN HÌNH QUÉT AI 16:9, DƯỚI LÀ KHUNG NGUỒN CAMERA NẰM NGANG
    # ==========================================================================
    with col_main:
        center_box = st.container(key="panel_scan_center")
        sources_box = st.container(key="panel_scan_sources")

    # 1. XỬ LÝ KHUNG NGUỒN CAMERA Ở DƯỚI TRƯỚC ĐỂ LẤY NGUỒN VIDEO / TỆP ĐANG CHỌN
    with sources_box:
        SRC_CAM = "Hệ thống Camera công trường"
        SRC_UP = "Tải video hoặc ảnh từ máy tính"
        if st.session_state.get("scan_source_mode") not in (SRC_CAM, SRC_UP):
            st.session_state.scan_source_mode = SRC_CAM

        with st.container(key="scan_sources_top_bar"):
            sh_title_col, sh_switch_col = st.columns([1.85, 1.05], gap="small", vertical_alignment="center")
            with sh_title_col:
                st.markdown(
                    clean_html('<div class="sg-panel-title" style="margin:0;">Nguồn camera</div>'),
                    unsafe_allow_html=True,
                )
            with sh_switch_col:
                with st.container(key="source_switch"):
                    sw1, sw2 = st.columns(2, gap="small")
                    for col, mode_val, mode_label, mode_key in (
                        (sw1, SRC_CAM, "Hệ thống", "src_mode_cam"),
                        (sw2, SRC_UP, "Tải tệp", "src_mode_up"),
                    ):
                        with col:
                            st.button(
                                mode_label,
                                key=mode_key,
                                type="primary" if st.session_state.scan_source_mode == mode_val else "secondary",
                                width="stretch",
                                on_click=_set_scan_source_mode,
                                args=(mode_val,),
                            )

        source_mode = st.session_state.scan_source_mode
        selected_video_path = None
        selected_cam_label = "Camera 01 — Khu vực 1"
        selected_cam_short = "CAMERA 01 · KHU VỰC 1"
        uploaded = None

        if source_mode == SRC_CAM:
            if sample_videos:
                cur_idx = int(st.session_state.get("scan_cam_idx", 0))
                if cur_idx >= len(sample_videos):
                    cur_idx = 0
                thumb_css = []
                cam_cols = st.columns(len(sample_videos), gap="small")
                for i, vp in enumerate(sample_videos):
                    thumb = _camera_thumb_uri(str(vp))
                    if thumb:
                        thumb_css.append(
                            f'.st-key-camopt_{i} button::before{{background-image:url("{thumb}") !important;}}'
                        )
                    with cam_cols[i]:
                        st.button(
                            f"**Camera {i + 1:02d}**  \nKhu vực {i + 1}  \n:green[●] Sẵn sàng",
                            key=f"camopt_{i}",
                            type="primary" if i == cur_idx else "secondary",
                            width="stretch",
                            on_click=_set_scan_cam_idx,
                            args=(i,),
                        )
                if thumb_css:
                    st.markdown("<style>" + "".join(thumb_css) + "</style>", unsafe_allow_html=True)
                selected_video_path = sample_videos[cur_idx]
                selected_cam_label = f"Camera số {cur_idx + 1} — Khu vực {cur_idx + 1}"
                selected_cam_short = f"CAMERA {cur_idx + 1:02d} · KHU VỰC {cur_idx + 1}"
            else:
                st.warning("Chưa có camera nào được kết nối.")
        else:
            up_col_drop, up_col_info = st.columns([1.45, 1.15], gap="medium", vertical_alignment="center")
            with up_col_drop:
                uploaded = st.file_uploader(
                    "Chọn video từ máy tính",
                    type=["mp4", "avi", "mov", "jpg", "jpeg", "png", "webp"],
                    label_visibility="collapsed",
                    key="scan_file_uploader",
                )
            with up_col_info:
                if uploaded is not None:
                    up_name_safe = _html.escape(uploaded.name)
                    up_kb = max(1, int(round(len(uploaded.getvalue()) / 1024)))
                    ext_upper = Path(uploaded.name).suffix.lstrip(".").upper() or "FILE"
                    st.markdown(
                        clean_html(
                            f"""
                            <div class="sg-upload-status-card active">
                                <span class="sg-upload-pill">ĐÃ NẠP TỆP · {ext_upper}</span>
                                <strong>{up_name_safe}</strong>
                                <p>Dung lượng {up_kb:,} KB · Nhấn <b>Bắt đầu quét</b> trên màn hình chính để phân tích AI.</p>
                            </div>
                            """
                        ),
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(
                        clean_html(
                            """
                            <div class="sg-upload-status-card">
                                <span class="sg-upload-pill">CHẾ ĐỘ KIỂM TRA TỆP</span>
                                <strong>Chưa chọn tệp kiểm tra</strong>
                                <p>Kéo thả hoặc nhấn vào khung bên trái để tải video (MP4, MOV, AVI) hoặc ảnh hiện trường lên kiểm tra AI.</p>
                            </div>
                            """
                        ),
                        unsafe_allow_html=True,
                    )

    # 2. DỰNG KHUNG MÀN HÌNH QUÉT AI 16:9 Ở PHÍA TRÊN (`center_box`)
    with center_box:
        header_placeholder = st.empty()
        video_placeholder = st.empty()
        progress_bar = st.empty()

        def _render_monitor_header(title_text: str, is_running: bool = False):
            badge_cls = "sg-monitor-badge live" if is_running else "sg-monitor-badge"
            badge_txt = "ĐANG QUÉT AI" if is_running else "BẢN XEM TRƯỚC"
            header_placeholder.markdown(
                clean_html(
                    f"""
                    <div class="sg-monitor-heading" style="align-items:center;">
                        <div class="sg-panel-title" style="margin:0;">{title_text}</div>
                        <span class="{badge_cls}">{badge_txt}</span>
                    </div>
                    """
                ),
                unsafe_allow_html=True,
            )

        def run_video_scanner(video_path_str: str, cam_name: str, cam_short_tag: str):
            info = get_video_info(video_path_str)
            total_fr = info["total_frames"] if info and info["total_frames"] > 0 else 100
            fps_val = info["fps"] if info and info["fps"] > 0 else 30.0

            act_c1, act_c2, act_c3 = st.columns([1.05, 0.95, 2.1], gap="small", vertical_alignment="center")
            with act_c1:
                start_btn = st.button(
                    "Bắt đầu quét",
                    type="primary",
                    width="stretch",
                    key=f"btn_scan_{cam_name}",
                )
            with act_c2:
                stop_btn = st.button(
                    "Dừng quét",
                    width="stretch",
                    key=f"btn_stop_{cam_name}",
                )
            with act_c3:
                state_placeholder = st.empty()

            telemetry_placeholder = st.empty()

            if stop_btn:
                st.session_state.scan_is_running = False

            if start_btn:
                st.session_state.scan_is_running = True
                _render_monitor_header(cam_name, is_running=True)
                tracker = MultiPersonTrackerAndDeduplicator()
                auto_cnt = 0
                human_cnt = 0

                for frame_idx, frame in read_frames(video_path_str, frame_step=speed_step, max_width=720):
                    frame = _normalize_scan_frame(frame)
                    annotated_bgr, new_viols, worker_cnt, env_info = smart_detect_and_annotate(
                        frame,
                        conf_threshold=ai_sensitivity,
                        active_violation_types=active_violations,
                        tracker=tracker,
                        frame_idx=frame_idx,
                    )
                    st.session_state.last_scan_telemetry = {
                        "worker_cnt": worker_cnt,
                        "blur_score": env_info["blur_score"],
                        "glare_pct": env_info["glare_pct"],
                        "status_text": env_info["status_text"],
                    }
                    if new_viols:
                        auto_list, human_list = save_new_violations_to_db(
                            new_viols,
                            annotated_bgr,
                            auto_confirm_threshold=effective_auto_confirm,
                            camera_name=cam_name,
                            frame_idx=frame_idx,
                            fps=fps_val,
                        )
                        auto_cnt += len(auto_list)
                        human_cnt += len(human_list)
                        if enable_audio:
                            play_alert_beep()

                    ok_enc, jpg_buf = cv2.imencode(".jpg", annotated_bgr, [cv2.IMWRITE_JPEG_QUALITY, 84])
                    frame_uri = (
                        "data:image/jpeg;base64," + base64.b64encode(jpg_buf.tobytes()).decode("ascii")
                        if ok_enc
                        else ""
                    )
                    video_placeholder.markdown(
                        _build_monitor_frame_html(
                            img_uri=frame_uri,
                            top_left_text=f"ĐANG QUÉT · FRAME #{frame_idx}",
                            top_right_text=cam_short_tag,
                            bottom_left_text=f"Tự xác nhận: {auto_cnt} · Chờ duyệt: {human_cnt} · {env_info['status_text']}",
                        ),
                        unsafe_allow_html=True,
                    )
                    state_placeholder.markdown(
                        clean_html(
                            f'<div class="sg-scan-state-text">Đang phân tích luồng video ({int(round(min(1.0, frame_idx / max(1, total_fr)) * 100))}%)</div>'
                        ),
                        unsafe_allow_html=True,
                    )
                    telemetry_placeholder.markdown(
                        _build_telemetry_html(worker_cnt, env_info),
                        unsafe_allow_html=True,
                    )
                    progress_bar.progress(min(1.0, frame_idx / max(1, total_fr)))

                st.session_state.scan_is_running = False
                st.toast(
                    f"Đã quét xong {cam_name}: {auto_cnt} lỗi tự xác nhận, {human_cnt} ảnh nghi ngờ chuyển sang trang Duyệt vi phạm."
                )
                st.rerun()
            else:
                _render_monitor_header(cam_name, is_running=False)
                b64_uri, worker_cnt, env_info = _cached_first_frame_preview(
                    video_path_str,
                    float(ai_sensitivity),
                    tuple(active_violations),
                )
                video_placeholder.markdown(
                    _build_monitor_frame_html(
                        img_uri=b64_uri,
                        top_left_text="CHƯA CHẠY PHIÊN QUÉT",
                        top_right_text=cam_short_tag,
                        bottom_left_text=f"Khung hình xem trước · {env_info['status_text']}",
                    ),
                    unsafe_allow_html=True,
                )
                state_placeholder.markdown(
                    clean_html('<div class="sg-scan-state-text">Sẵn sàng bắt đầu phiên quét</div>'),
                    unsafe_allow_html=True,
                )
                telemetry_placeholder.markdown(
                    _build_telemetry_html(worker_cnt, env_info),
                    unsafe_allow_html=True,
                )

        if source_mode == SRC_CAM:
            if selected_video_path is not None:
                run_video_scanner(str(selected_video_path), selected_cam_label, selected_cam_short)
            else:
                _render_monitor_header("Chưa kết nối Camera", is_running=False)
                st.info("Chưa có camera nào được kết nối. Hãy chuyển sang **Tải tệp** để kiểm tra.")
        else:
            if uploaded is not None:
                ext = Path(uploaded.name).suffix.lower()
                if ext in (".mp4", ".avi", ".mov"):
                    tmp_dir = Path(tempfile.gettempdir()) / "safeguard_v6"
                    tmp_dir.mkdir(parents=True, exist_ok=True)
                    tmp_path = tmp_dir / uploaded.name
                    tmp_path.write_bytes(uploaded.getvalue())
                    run_video_scanner(
                        str(tmp_path),
                        f"Video tải lên ({uploaded.name})",
                        "VIDEO TẢI LÊN",
                    )
                else:
                    _render_monitor_header(f"Ảnh kiểm tra ({uploaded.name})", is_running=False)
                    raw_bytes = np.asarray(bytearray(uploaded.getvalue()), dtype=np.uint8)
                    img_bgr = cv2.imdecode(raw_bytes, cv2.IMREAD_COLOR)
                    if img_bgr is not None:
                        img_bgr = _normalize_scan_frame(img_bgr)
                        img_tracker = MultiPersonTrackerAndDeduplicator()
                        annotated_bgr, new_viols, worker_cnt, env_info = smart_detect_and_annotate(
                            img_bgr,
                            conf_threshold=ai_sensitivity,
                            active_violation_types=active_violations,
                            tracker=img_tracker,
                            frame_idx=1,
                        )
                        ok_enc, jpg_buf = cv2.imencode(".jpg", annotated_bgr, [cv2.IMWRITE_JPEG_QUALITY, 88])
                        img_uri = (
                            "data:image/jpeg;base64," + base64.b64encode(jpg_buf.tobytes()).decode("ascii")
                            if ok_enc
                            else ""
                        )
                        video_placeholder.markdown(
                            _build_monitor_frame_html(
                                img_uri=img_uri,
                                top_left_text=f"PHÁT HIỆN {len(new_viols)} VI PHẠM",
                                top_right_text="ẢNH TẢI LÊN",
                                bottom_left_text=env_info["status_text"],
                            ),
                            unsafe_allow_html=True,
                        )
                        act_c1, act_c2 = st.columns([1.4, 2.6], gap="small", vertical_alignment="center")
                        with act_c1:
                            if st.button("Lưu kết quả kiểm tra ảnh này", type="primary", width="stretch"):
                                save_new_violations_to_db(
                                    new_viols,
                                    annotated_bgr,
                                    auto_confirm_threshold=effective_auto_confirm,
                                    camera_name=f"Ảnh ({uploaded.name})",
                                    frame_idx=1,
                                    fps=1.0,
                                )
                                st.rerun()
                        with act_c2:
                            st.markdown(
                                clean_html(
                                    f'<div class="sg-scan-state-text">Đã phân tích ảnh `{uploaded.name}` ({len(new_viols)} lỗi phát hiện)</div>'
                                ),
                                unsafe_allow_html=True,
                            )
                        st.markdown(
                            _build_telemetry_html(worker_cnt, env_info),
                            unsafe_allow_html=True,
                        )
            else:
                _render_monitor_header("Tải tệp kiểm tra", is_running=False)
                video_placeholder.markdown(
                    _build_monitor_frame_html(
                        img_uri="",
                        top_left_text="CHỜ TẢI TỆP",
                        top_right_text="CHẾ ĐỘ TẢI TỆP",
                        bottom_left_text="Hãy chọn một tệp video hoặc ảnh ở khung Nguồn camera phía dưới",
                    ),
                    unsafe_allow_html=True,
                )
                st.markdown(
                    _build_telemetry_html(
                        0,
                        {"blur_score": 0.0, "glare_pct": 0.0, "is_blur": False, "is_glare": False, "status_text": "Chưa có tín hiệu khung hình"},
                    ),
                    unsafe_allow_html=True,
                )

    # ==========================================================================
    # NHẬT KÝ PHIÊN QUÉT: ĐƯA NÚT LÀM MỚI DỮ LIỆU CA TRỰC (KÈM XÁC NHẬN) VỀ ĐÚNG NGỮ CẢNH
    # ==========================================================================
    with st.container(key="panel_scan_log"):
        total_logs = len(raw_events)

        if total_logs > 0:
            cur_page_size = SCAN_LOG_PAGE_SIZE
            max_page = max(1, math.ceil(total_logs / cur_page_size))
            cur_page = int(st.session_state.get("scan_log_page", 1))
            cur_page = max(1, min(max_page, cur_page))
            st.session_state.scan_log_page = cur_page

            start_idx = (cur_page - 1) * cur_page_size
            end_idx = min(total_logs, start_idx + cur_page_size)

            hdr_left, hdr_pager, hdr_reset = st.columns(
                [3.0, 1.35, 1.15],
                gap="small",
                vertical_alignment="center",
            )
            with hdr_left:
                st.markdown(
                    clean_html(
                        f"""
                        <div>
                            <div class="sg-panel-title">Nhật ký phiên quét</div>
                            <div class="sg-panel-sub" style="margin-bottom:2px;">
                                Hiển thị <b>{start_idx + 1}–{end_idx}</b> / <b>{total_logs}</b> sự kiện ghi nhận
                            </div>
                        </div>
                        """
                    ),
                    unsafe_allow_html=True,
                )
            with hdr_pager:
                with st.container(key="scan_log_pager"):
                    p_prev, p_info, p_next = st.columns([0.9, 1.15, 0.9], gap="small", vertical_alignment="center")
                    with p_prev:
                        st.button(
                            "‹ Trước",
                            key="scan_log_prev_btn",
                            disabled=(cur_page <= 1),
                            width="stretch",
                            on_click=_change_scan_log_page,
                            args=(-1, max_page),
                        )
                    with p_info:
                        st.markdown(
                            clean_html(
                                f'<div class="sg-page-indicator">Trang <b>{cur_page}</b> / {max_page}</div>'
                            ),
                            unsafe_allow_html=True,
                        )
                    with p_next:
                        st.button(
                            "Sau ›",
                            key="scan_log_next_btn",
                            disabled=(cur_page >= max_page),
                            width="stretch",
                            on_click=_change_scan_log_page,
                            args=(1, max_page),
                        )
            with hdr_reset:
                if st.button("Làm mới dữ liệu ca trực", width="stretch", key="scan_btn_reset_shift"):
                    _confirm_reset_shift_dialog(total_logs)

            page_slice = raw_events[start_idx:end_idx]
            rows_page = []
            for e in page_slice:
                eid = int(e["event_id"])
                _, meta = load_event_evidence(eid)
                rows_page.append({
                    "Mã số": eid,
                    "Thời điểm phát hiện": fmt_ts_vn(e.get("timestamp", "")),
                    "Mã công nhân": meta.get("worker_id", "CN #01"),
                    "Hành vi vi phạm": TEN_LOI_TV.get(e.get("violation_type", ""), e.get("violation_type", "")),
                    "Trạng thái": TRANG_THAI_TV.get(e.get("status", ""), e.get("status", "")),
                })
            df_show = pd.DataFrame(rows_page)
            render_data_table(
                df_show,
                id_cols=("Mã số",),
                status_cols=("Trạng thái",),
                muted_cols=("Thời điểm phát hiện",),
                max_height=340,
            )
        else:
            st.markdown('<div class="sg-panel-title">Nhật ký phiên quét</div>', unsafe_allow_html=True)
            st.info("Chưa có dữ liệu vi phạm.")