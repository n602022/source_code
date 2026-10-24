# -*- coding: utf-8 -*-
"""
app.py — Entry point và điều phối trung tâm của hệ thống SAFEGUARD AI (Giao diện Prototype V2).
Đã tối ưu tốc độ chuyển trang: sử dụng bộ nhớ đệm RAM (get_cached_events_bundle) và pre-compiled CSS
giúp chuyển đổi giữa 5 trang mượt mà tức thì mà không phải đọc lại SQLite hay đĩa cứng.
"""
import os
import threading
import time

import streamlit as st

from core_logic import (
    BASE_DIR,
    EVIDENCE_DIR,
    MultiPersonTrackerAndDeduplicator,
    TEN_LOI_TV,
    TRANG_THAI_TV,
    box_overlap_ratio,
    build_evidence_zip_bytes,
    build_shift_csv_bytes,
    clean_html,
    ensure_db_ready,
    evaluate_lighting_and_glare,
    find_sample_videos,
    get_cached_events_bundle,
    image_to_base64_uri,
    get_enriched_events,
    init_app_session_state,
    load_event_evidence,
    play_alert_beep,
    play_emergency_siren,
    play_speaker_chime,
    record_iot_action,
    reset_shift_data,
    save_new_violations_to_db,
    smart_detect_and_annotate,
)
from ui_components import (
    render_global_banners,
    render_sidebar,
    render_topbar,
    render_utility_bar,
)
from ui_pages.assistant import render_assistant_page
from ui_pages.dashboard import render_dashboard_page
from ui_pages.documents import render_documents_page
from ui_pages.review import render_review_page
from ui_pages.scanner import render_scanner_page
from ui_theme import apply_ui_theme


@st.cache_resource(show_spinner=False)
def _warm_up_once() -> bool:
    """
    Làm nóng bộ nhớ đệm ở luồng nền ngay lần mở đầu tiên của tiến trình (không chặn giao diện):
    tài liệu nội quy, danh sách video, ảnh bằng chứng gần nhất. Lần đầu bấm sang từng trang sẽ không phải chờ đọc đĩa.
    """

    def _job():
        try:
            from ui_pages.documents import _get_cached_docs

            _get_cached_docs()
        except Exception:
            pass
        try:
            find_sample_videos()
        except Exception:
            pass
        try:
            _, enriched, _ = get_cached_events_bundle()
            for ev in enriched[:16]:
                if ev.get("img_path"):
                    image_to_base64_uri(ev["img_path"])
        except Exception:
            pass

    threading.Thread(target=_job, daemon=True).start()
    return True


def main():
    st.set_page_config(
        page_title="SafeGuard AI — Hệ Thống Giám Sát An Toàn Lao Động",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # 1. Khởi tạo cơ sở dữ liệu (1 lần duy nhất mỗi tiến trình) và các khóa session_state
    _t0 = time.perf_counter()
    perf_on = os.environ.get("SAFEGUARD_PERF") == "1" or st.query_params.get("perf") == "1"
    ensure_db_ready()
    init_app_session_state()
    _warm_up_once()

    # 2. Áp dụng Design System & Theme từ bộ nhớ đệm pre-compiled (< 0.01ms, 0 đọc đĩa)
    apply_ui_theme()

    # 3. Lấy dữ liệu sự kiện từ bộ nhớ đệm RAM (chỉ đọc lại SQLite khi file safeguard.db thay đổi)
    raw_events, enriched_events, db_connected = get_cached_events_bundle()
    pending_events = [e for e in enriched_events if e.get("status") == "pending"]
    pending_count = len(pending_events) if db_connected else None

    # 4. Dựng Sidebar điều hướng 5 trang chuẩn Prototype V2 (dùng on_click chuyển trang 1-pass)
    _t1 = time.perf_counter()
    render_sidebar(pending_count=pending_count, total_events=len(raw_events))

    # 5. Dựng Header hợp nhất 1 hàng (Tiêu đề trang bên trái | Trạng thái, Chuông, Minh An bên phải)
    active_page = st.session_state.get("active_page", "dashboard")
    render_topbar(
        page_key=active_page,
        db_connected=db_connected,
        enriched_events=enriched_events,
        pending_events=pending_events,
    )
    render_global_banners()

    # 6. Điều phối hiển thị trang chức năng đang chọn
    _t2 = time.perf_counter()
    if active_page == "dashboard":
        render_dashboard_page(raw_events=raw_events, enriched_events=enriched_events)
    elif active_page == "scan":
        render_scanner_page(raw_events=raw_events)
    elif active_page == "review":
        render_review_page(raw_events=raw_events, enriched_events=enriched_events)
    elif active_page == "chat":
        render_assistant_page(raw_events=raw_events, enriched_events=enriched_events)
    elif active_page == "docs":
        render_documents_page()
    else:
        render_dashboard_page(raw_events=raw_events, enriched_events=enriched_events)

    if perf_on:
        # Chế độ đo hiệu năng: mở trang với ?perf=1 để biết phần nào chậm
        _t3 = time.perf_counter()
        st.caption(
            f"Thời gian dựng (ms) — dữ liệu & giao diện nền: {(_t1 - _t0) * 1000:.0f} · "
            f"thanh điều hướng & tiêu đề: {(_t2 - _t1) * 1000:.0f} · nội dung trang '{active_page}': {(_t3 - _t2) * 1000:.0f}"
        )


if __name__ == "__main__":
    main()