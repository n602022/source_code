# -*- coding: utf-8 -*-
"""
ui_pages/review.py — Trang Duyệt vi phạm & Điều khiển khẩn cấp Đội trưởng (Review Queue V2).
Đã áp dụng các đề xuất tinh gọn đúng & tốt:
- Bỏ khung "Điều khiển khẩn cấp · Mã #..." (ca gần nhất) bị trùng ở cột trái khi hết ca chờ duyệt, vì cột phải (`Hồ sơ thẩm định`) luôn hiển thị đầy đủ ảnh bằng chứng và 2 nút `Gửi loa nhắc nhở` / `Dừng khẩn cấp dây chuyền`.
- Thêm hộp thoại xác nhận `@st.dialog` cho nút `Duyệt tất cả (N)` để đảm bảo nguyên tắc Human-in-the-Loop (ngăn bấm nhầm duyệt hàng loạt khi chưa kiểm tra).
- Giữ bảng `Lịch sử sự kiện đã duyệt` gọn gàng trong ngăn kéo ở cuối trang (đã bỏ phần sửa trạng thái trùng lặp).
"""
import datetime
import math
from pathlib import Path
import re
import pandas as pd
import streamlit as st

from chatbot import GIAI_THICH_LOI_VI_PHAM
from core_logic import (
    clean_html,
    image_to_base64_uri,
    record_iot_action,
    render_evidence_img_or_placeholder,
    update_event_status,
)
from ui_components import render_data_table

REV_CARDS_PER_PAGE = 6

_DL_ICON_SVG = (
    '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" '
    'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
    '<path d="M12 3v12m0 0l-4-4m4 4l4-4"></path>'
    '<path d="M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2"></path>'
    "</svg>"
)


def _short_guide(text: str, max_sentences: int = 2) -> str:
    """Rút gọn hướng dẫn duyệt: chỉ giữ tối đa vài câu đầu, gọn trên một khung nhỏ."""
    flat = " ".join(str(text).split())
    parts = re.split(r"(?<=[.!?])\s+", flat)
    return " ".join(parts[:max_sentences])


def _format_card_source(cam_raw: str | None) -> str:
    """
    Rút gọn tên nguồn trên thẻ sự kiện để ngắn gọn, đồng nhất 1 dòng:
    - 'Video tải lên (sample_4_no_hardhat_mask.mp4)' -> 'Video tải lên'
    - 'Ảnh (sample_2.jpg)' -> 'Ảnh tải lên'
    - 'Camera số 1 — Khu vực 1' -> 'Camera khu vực 1'
    """
    if not cam_raw:
        return "Camera khu vực 1"
    txt = str(cam_raw).strip()
    low = txt.lower()
    if low.startswith("video tải lên") or "video tải lên" in low:
        return "Video tải lên"
    if low.startswith("ảnh (") or low.startswith("ảnh tải lên") or "tải lên" in low:
        return "Ảnh tải lên"
    m = re.search(r"khu\s*vực\s*0*(\d+)", txt, flags=re.IGNORECASE)
    if m:
        return f"Camera khu vực {int(m.group(1))}"
    m_cam = re.search(r"camera\s*(?:số\s*)?0*(\d+)", txt, flags=re.IGNORECASE)
    if m_cam:
        return f"Camera khu vực {int(m_cam.group(1))}"
    return txt


def _build_card_download_html(img_path, event_id: int) -> str:
    """
    Tạo nút tải xuống 1-click ở góc phải dưới của thẻ sự kiện (.sg-card-dl-btn):
    - Tự động lấy đúng đuôi file thực tế do thuật toán lưu.
    - Sử dụng độ phân giải gốc (max_width=0) để tệp tải về đạt chất lượng nguyên bản 100%.
    """
    if img_path is None:
        return (
            f'<span class="sg-card-dl-btn disabled" title="Sự kiện #{event_id} chưa có tệp bằng chứng">'
            f"{_DL_ICON_SVG}</span>"
        )
    p = Path(img_path)
    if not p.is_file():
        return (
            f'<span class="sg-card-dl-btn disabled" title="Sự kiện #{event_id} chưa có tệp bằng chứng">'
            f"{_DL_ICON_SVG}</span>"
        )

    ext = p.suffix.lower() or ".jpg"
    dl_filename = f"Bang_chung_su_kien_{event_id}{ext}"
    full_uri = image_to_base64_uri(p, max_width=0)
    if not full_uri:
        return (
            f'<span class="sg-card-dl-btn disabled" title="Không đọc được tệp bằng chứng #{event_id}">'
            f"{_DL_ICON_SVG}</span>"
        )

    return (
        f'<a class="sg-card-dl-btn" href="{full_uri}" download="{dl_filename}" '
        f'title="Tải xuống {dl_filename}">{_DL_ICON_SVG}</a>'
    )


def _set_review_tab(tab_key: str):
    st.session_state.review_tab_filter = tab_key
    st.session_state.selected_review_event_id = None
    st.session_state.rev_card_page = 1


def _select_review_card(event_id: int):
    st.session_state.selected_review_event_id = int(event_id)


def _set_rev_card_page(page_num: int):
    st.session_state.rev_card_page = int(page_num)


def _decide_event(event_id: int, new_status: str):
    eid = int(event_id)
    update_event_status(eid, new_status)
    if new_status == "pending":
        st.session_state.last_reviewed_action = None
    else:
        st.session_state.last_reviewed_action = {"event_id": eid, "new_status": new_status}


def _ask_ai_about_event(event_id: int):
    """Chuyển sang trang Trợ lý AI với ngữ cảnh được ghim sẵn vào sự kiện đang thẩm định."""
    st.session_state.selected_review_event_id = int(event_id)
    st.session_state.active_page = "chat"


@st.dialog("Xác nhận duyệt hàng loạt")
def _confirm_bulk_approve_dialog(pending_ids: list[int]):
    """Hộp thoại xác nhận trước khi xác nhận hàng loạt toàn bộ sự kiện đang chờ duyệt."""
    st.markdown(
        f"Bạn có chắc chắn muốn xác nhận toàn bộ **{len(pending_ids)} sự kiện** đang chờ duyệt là **Vi phạm thật** không? "
        f"Hãy đảm bảo bạn đã rà soát các ảnh bằng chứng trên danh sách."
    )
    c_cancel, c_ok = st.columns(2, gap="small")
    with c_cancel:
        if st.button("Hủy", width="stretch", key="dlg_bulk_cancel"):
            st.rerun()
    with c_ok:
        if st.button("Xác nhận duyệt tất cả", type="primary", width="stretch", key="dlg_bulk_ok"):
            for eid in pending_ids:
                update_event_status(int(eid), "confirmed")
            if pending_ids:
                st.session_state.last_reviewed_action = {"event_id": int(pending_ids[0]), "new_status": "confirmed"}
            st.rerun()


@st.dialog("Xác nhận dừng khẩn cấp")
def _confirm_estop_dialog(event_id: int, cam: str, worker: str, mark_confirmed: bool):
    """Hộp thoại xác nhận: ngăn bấm nhầm thao tác dừng dây chuyền (không thể hoàn tác ngoài hiện trường)."""
    st.markdown(
        f"Gửi tín hiệu **DỪNG KHẨN CẤP DÂY CHUYỀN** tại **{cam}** "
        f"(Mã sự kiện #{event_id} · {worker})? Máy móc sẽ ngắt ngay lập tức."
    )
    c_cancel, c_ok = st.columns(2, gap="small")
    with c_cancel:
        if st.button("Hủy", width="stretch", key=f"dlg_cancel_{event_id}"):
            st.rerun()
    with c_ok:
        with st.container(key="dlg_confirm_wrap"):
            confirmed = st.button("Xác nhận dừng", type="primary", width="stretch", key=f"dlg_ok_{event_id}")
        if confirmed:
            if mark_confirmed:
                update_event_status(event_id, "confirmed")
                st.session_state.last_reviewed_action = {"event_id": event_id, "new_status": "confirmed"}
            record_iot_action(event_id, "Đã dừng khẩn cấp dây chuyền")
            st.session_state.emergency_stop_active = {
                "event_id": event_id,
                "camera": cam,
                "worker_id": worker,
                "time": datetime.datetime.now().strftime("%H:%M:%S"),
            }
            st.session_state.iot_action_banner = {
                "type": "estop",
                "msg": f"Đã gửi tín hiệu DỪNG KHẨN CẤP DÂY CHUYỀN tại {cam} (Mã sự kiện #{event_id}).",
            }
            st.rerun()


def render_review_page(raw_events: list, enriched_events: list):
    """Hiển thị trang Duyệt vi phạm & Trạm điều khiển khẩn cấp Đội trưởng."""
    pending_events = [e for e in enriched_events if e["status"] == "pending"]
    confirmed_events = [e for e in enriched_events if e["status"] == "confirmed"]
    rejected_events = [e for e in enriched_events if e["status"] == "false_positive"]

    pending_count = len(pending_events)
    confirmed_count = len(confirmed_events)
    rejected_count = len(rejected_events)

    # --- THANH CÔNG CỤ LỌC TRẠNG THÁI (NHÓM 4 TAB BÊN TRÁI | NÚT HÀNH ĐỘNG HÀNG LOẠT BÊN PHẢI) ---
    rt_left, rt_spacer, rt_bulk = st.columns([3.85, 0.45, 1.35], gap="small", vertical_alignment="center")
    cur_tab = st.session_state.get("review_tab_filter", "pending")

    with rt_left:
        with st.container(key="rev_tab_group"):
            rt1, rt2, rt3, rt4 = st.columns([1.15, 1.15, 1.15, 0.95], gap="small")
            with rt1:
                st.button(
                    f"Chờ duyệt ({pending_count})",
                    key="rev_tab_pending",
                    type="primary" if cur_tab == "pending" else "secondary",
                    width="stretch",
                    on_click=_set_review_tab,
                    args=("pending",),
                )
            with rt2:
                st.button(
                    f"Đã xác nhận ({confirmed_count})",
                    key="rev_tab_confirmed",
                    type="primary" if cur_tab == "confirmed" else "secondary",
                    width="stretch",
                    on_click=_set_review_tab,
                    args=("confirmed",),
                )
            with rt3:
                st.button(
                    f"Đã loại bỏ ({rejected_count})",
                    key="rev_tab_rejected",
                    type="primary" if cur_tab == "false_positive" else "secondary",
                    width="stretch",
                    on_click=_set_review_tab,
                    args=("false_positive",),
                )
            with rt4:
                st.button(
                    f"Tất cả ({len(enriched_events)})",
                    key="rev_tab_all",
                    type="primary" if cur_tab == "all" else "secondary",
                    width="stretch",
                    on_click=_set_review_tab,
                    args=("all",),
                )
    with rt_bulk:
        if pending_events:
            if st.button(f"Duyệt tất cả ({pending_count})", type="primary", width="stretch", key="rev_bulk_confirm_btn"):
                _confirm_bulk_approve_dialog([int(ev["event_id"]) for ev in pending_events])

    if cur_tab == "pending":
        visible_events = pending_events
    elif cur_tab == "confirmed":
        visible_events = confirmed_events
    elif cur_tab == "false_positive":
        visible_events = rejected_events
    else:
        visible_events = enriched_events

    # --- TÍNH TOÁN PHÂN TRANG CỐ ĐỊNH 6 VIDEO MỖI TRANG ---
    cur_page_size = REV_CARDS_PER_PAGE
    total_visible = len(visible_events)
    max_page = max(1, math.ceil(total_visible / cur_page_size)) if total_visible > 0 else 1

    selected_id = st.session_state.get("selected_review_event_id")
    selected_ev = None
    selected_idx = None
    if selected_id is not None:
        for idx_ev, ev in enumerate(visible_events):
            if ev["event_id"] == selected_id:
                selected_ev = ev
                selected_idx = idx_ev
                break

    if st.session_state.get("rev_locate_selected", False) and selected_idx is not None:
        st.session_state.rev_card_page = (selected_idx // cur_page_size) + 1
        st.session_state.rev_locate_selected = False

    cur_page = int(st.session_state.get("rev_card_page", 1))
    cur_page = max(1, min(max_page, cur_page))
    st.session_state.rev_card_page = cur_page

    start_idx = (cur_page - 1) * cur_page_size
    end_idx = min(total_visible, start_idx + cur_page_size)
    paged_events = visible_events[start_idx:end_idx]

    if selected_ev is None and paged_events:
        selected_ev = paged_events[0]
        st.session_state.selected_review_event_id = selected_ev["event_id"]
    elif selected_ev is None and visible_events:
        selected_ev = visible_events[0]
        st.session_state.selected_review_event_id = selected_ev["event_id"]

    # --- BỐ CỤC 2 CỘT CHUẨN PROTOTYPE V2: DANH SÁCH THẺ BÊN TRÁI | HỒ SƠ THẨM ĐỊNH GHIM CỐ ĐỊNH BÊN PHẢI ---
    col_list, col_detail = st.columns([1.35, 1.1], gap="medium")

    with col_list:
        if visible_events:
            for row_start in range(0, len(paged_events), 2):
                row_items = paged_events[row_start:row_start + 2]
                grid_cols = st.columns(2, gap="small")
                for col_idx, ev in enumerate(row_items):
                    eid = int(ev["event_id"])
                    is_selected = selected_ev is not None and selected_ev["event_id"] == eid
                    card_cls = "sg-incident-card selected" if is_selected else "sg-incident-card"
                    src_label = _format_card_source(ev.get("camera"))
                    media_html = render_evidence_img_or_placeholder(ev["img_path"], eid, height_px=135)
                    dl_btn_html = _build_card_download_html(ev.get("img_path"), eid)

                    with grid_cols[col_idx]:
                        st.markdown(
                            clean_html(
                                f"""
                                <div class="{card_cls}">
                                    {media_html}
                                    <div class="sg-incident-body">
                                        <div class="sg-incident-badges">
                                            <span class="sg-badge {ev['severity']}">{ev['severity_label']}</span>
                                            <span class="sg-badge {ev['status']}" style="margin-left:auto;">{ev['status_badge_tv']}</span>
                                        </div>
                                        <div class="sg-incident-title" title="#{eid} · {ev['title_tv']}">#{eid} · {ev['title_tv']}</div>
                                        <div class="sg-incident-foot">
                                            <div class="sg-incident-meta-group">
                                                <div class="sg-incident-meta">{src_label}</div>
                                                <div class="sg-incident-meta">{ev['timestamp_vn']} · AI: {ev['confidence_pct']}</div>
                                            </div>
                                            {dl_btn_html}
                                        </div>
                                    </div>
                                </div>
                                """
                            ),
                            unsafe_allow_html=True,
                        )
                        st.button(
                            f"Đang xem #{eid}" if is_selected else f"Xem hồ sơ #{eid}",
                            key=f"select_rev_card_{eid}",
                            type="primary" if is_selected else "secondary",
                            width="stretch",
                            on_click=_select_review_card,
                            args=(eid,),
                        )

            # --- THANH ĐIỀU HƯỚNG PHÂN TRANG GỌN GÀNG, CĂN GIỮA NGANG HÀNG (6 VIDEO / TRANG) ---
            with st.container(key="rev_card_footer"):
                ft_info, ft_pager = st.columns([1.45, 1.35], gap="small", vertical_alignment="center")
                with ft_info:
                    st.markdown(
                        clean_html(
                            f'<div class="sg-rev-page-meta">Hiển thị <b>{start_idx + 1}–{end_idx}</b> / <b>{total_visible}</b> video</div>'
                        ),
                        unsafe_allow_html=True,
                    )
                with ft_pager:
                    with st.container(key="rev_card_pager"):
                        win_size = min(4, max_page)
                        win_start = max(1, min(cur_page - 1, max_page - win_size + 1))
                        page_nums = list(range(win_start, win_start + win_size))

                        col_weights = [0.85] + [0.85] * len(page_nums) + [0.85]
                        p_cols = st.columns(col_weights, gap="small", vertical_alignment="center")

                        with p_cols[0]:
                            st.button(
                                "‹",
                                key="rev_page_prev",
                                disabled=(cur_page <= 1),
                                width="stretch",
                                on_click=_set_rev_card_page,
                                args=(max(1, cur_page - 1),),
                            )
                        for idx_p, p_num in enumerate(page_nums):
                            with p_cols[idx_p + 1]:
                                st.button(
                                    f"{p_num}",
                                    key=f"rev_page_num_{p_num}",
                                    type="primary" if p_num == cur_page else "secondary",
                                    width="stretch",
                                    on_click=_set_rev_card_page,
                                    args=(p_num,),
                                )
                        with p_cols[-1]:
                            st.button(
                                "›",
                                key="rev_page_next",
                                disabled=(cur_page >= max_page),
                                width="stretch",
                                on_click=_set_rev_card_page,
                                args=(min(max_page, cur_page + 1),),
                            )
        else:
            st.markdown(
                clean_html(
                    """
                    <div class="sg-panel" style="text-align:center;padding:34px 18px;">
                        <div class="sg-panel-title">Không có sự kiện trong nhóm trạng thái này</div>
                        <div class="sg-panel-sub" style="margin-top:6px;">Bạn có thể chuyển sang tab Đã xác nhận / Tất cả hoặc điều khiển trực tiếp hồ sơ bên phải.</div>
                    </div>
                    """
                ),
                unsafe_allow_html=True,
            )

    # ==========================================================================
    # CỘT PHẢI: HỒ SƠ THẨM ĐỊNH CHI TIẾT (STICKY) & LỆNH KHẨN CẤP ĐỘI TRƯỞNG
    # ==========================================================================
    with col_detail:
        with st.container(key="panel_review_detail"):
            target_ev = selected_ev or (enriched_events[0] if enriched_events else None)
            if target_ev is not None:
                cur_id = int(target_ev["event_id"])
                cur_code = target_ev["violation_type"]
                cur_time = target_ev["timestamp_vn"]
                info_loi = GIAI_THICH_LOI_VI_PHAM.get(cur_code, GIAI_THICH_LOI_VI_PHAM["NO-Hardhat"])
                ev_img_path = target_ev.get("img_path")
                video_sec = target_ev.get("video_sec")

                with st.container(key="rev_detail_head_row"):
                    dh_left, dh_right = st.columns([1.5, 1.15], gap="small", vertical_alignment="center")
                    with dh_left:
                        st.markdown('<div class="sg-panel-title">Hồ sơ thẩm định</div>', unsafe_allow_html=True)
                    with dh_right:
                        st.button(
                            f"Hỏi Trợ lý AI về #{cur_id} →",
                            key=f"textlink_ask_ai_{cur_id}",
                            width="stretch",
                            on_click=_ask_ai_about_event,
                            args=(cur_id,),
                        )

                if ev_img_path is not None:
                    sec_str = f" — Giây thứ {video_sec}s trong video" if video_sec is not None else ""
                    st.image(
                        str(ev_img_path),
                        caption=f"Ảnh chụp màn hình Mã #{cur_id}{sec_str}",
                        width="stretch",
                    )
                else:
                    st.markdown(
                        clean_html(render_evidence_img_or_placeholder(None, cur_id, height_px=180)),
                        unsafe_allow_html=True,
                    )

                conf_val = target_ev["confidence"]
                conf_pct_num = int(round(conf_val * 100)) if conf_val is not None else 0
                conf_display = f"{conf_pct_num}%" if conf_val is not None else "Chưa có trong metadata"
                sec_info = f" (Giây {video_sec}s)" if video_sec is not None else ""

                st.markdown(
                    clean_html(
                        f"""
                        <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-top:8px;">
                            <div>
                                <div class="sg-eyebrow" style="margin:0;">SỰ KIỆN #{cur_id}</div>
                                <h3 style="margin:3px 0 0;font-size:17px;color:var(--text);">{info_loi['ten_tv']}</h3>
                            </div>
                            <span class="sg-badge {target_ev['status']}">{target_ev['status_badge_tv']}</span>
                        </div>
                        <div class="sg-detail-list">
                            <span class="sg-label">Công nhân</span><b>{target_ev['worker_id']}</b>
                            <span class="sg-label">Vị trí camera</span><b>{target_ev['camera']}</b>
                            <span class="sg-label">Thời điểm</span><b>{cur_time}{sec_info}</b>
                            <span class="sg-label">Môi trường</span><b>{target_ev['env_status']}</b>
                            <span class="sg-label">Mức độ rủi ro</span><b>{info_loi['muc_do']}</b>
                            <span class="sg-label">Lệnh IoT</span><b>{target_ev['iot_action']}</b>
                            <span class="sg-label">Độ tin cậy AI</span><b>{conf_display}</b>
                        </div>
                        <div class="sg-confidence-track">
                            <span style="width:{conf_pct_num}%"></span>
                        </div>
                        <div class="sg-guide-box">
                            <strong>Gợi ý duyệt:</strong> {_short_guide(info_loi['cach_duyet'])}
                        </div>
                        """
                    ),
                    unsafe_allow_html=True,
                )

                st.markdown("**Quyết định thẩm định**")
                if target_ev["status"] == "pending":
                    btn_c1, btn_c2 = st.columns(2, gap="small")
                    with btn_c1:
                        st.button(
                            "Xác nhận vi phạm",
                            type="primary",
                            width="stretch",
                            key=f"confirm_{cur_id}",
                            on_click=_decide_event,
                            args=(cur_id, "confirmed"),
                        )
                    with btn_c2:
                        st.button(
                            "Đánh dấu báo nhầm",
                            width="stretch",
                            key=f"reject_{cur_id}",
                            on_click=_decide_event,
                            args=(cur_id, "false_positive"),
                        )
                else:
                    btn_c1, btn_c2, btn_c3 = st.columns([1.05, 1.05, 0.95], gap="small")
                    with btn_c1:
                        st.button(
                            "Xác nhận vi phạm",
                            type="primary" if target_ev["status"] == "confirmed" else "secondary",
                            width="stretch",
                            key=f"confirm_{cur_id}",
                            on_click=_decide_event,
                            args=(cur_id, "confirmed"),
                        )
                    with btn_c2:
                        st.button(
                            "Đánh dấu báo nhầm",
                            type="primary" if target_ev["status"] == "false_positive" else "secondary",
                            width="stretch",
                            key=f"reject_{cur_id}",
                            on_click=_decide_event,
                            args=(cur_id, "false_positive"),
                        )
                    with btn_c3:
                        st.button(
                            "Về Chờ duyệt",
                            width="stretch",
                            key=f"reset_pend_{cur_id}",
                            on_click=_decide_event,
                            args=(cur_id, "pending"),
                        )

                st.markdown("**Điều khiển hiện trường**")
                iot_c1, iot_c2 = st.columns(2, gap="small")
                cam_loc = target_ev["camera"]
                wk_code = target_ev["worker_id"]
                with iot_c1:
                    if st.button(
                        "Gửi loa nhắc nhở",
                        width="stretch",
                        key=f"speaker_{cur_id}",
                        help="Phát thông báo nhắc nhở trực tiếp qua hệ thống loa truyền thanh tại khu vực Camera và xác nhận vi phạm.",
                    ):
                        update_event_status(cur_id, "confirmed")
                        record_iot_action(cur_id, "Đã gửi loa nhắc nhở")
                        st.session_state.last_reviewed_action = {"event_id": cur_id, "new_status": "confirmed"}
                        st.session_state.iot_action_banner = {
                            "type": "speaker",
                            "msg": f"Đã phát loa nhắc nhở tại {cam_loc} đối với {wk_code} (Mã sự kiện #{cur_id} — {info_loi['ten_tv']}).",
                        }
                        st.rerun()
                with iot_c2:
                    if st.button(
                        "Dừng khẩn cấp dây chuyền",
                        width="stretch",
                        key=f"estop_{cur_id}",
                        help="Ngắt tín hiệu vận hành dây chuyền máy móc ngay lập tức khi phát hiện nguy cơ tai nạn nghiêm trọng.",
                    ):
                        _confirm_estop_dialog(cur_id, cam_loc, wk_code, True)
            else:
                st.markdown('<div class="sg-panel-title">Hồ sơ thẩm định</div>', unsafe_allow_html=True)
                st.info("Chưa có sự kiện nào.")

    # ==========================================================================
    # NGĂN KÉO LỊCH SỬ SỰ KIỆN ĐÃ DUYỆT (CHỈ GIỮ BẢNG TRA CỨU GỌN GÀNG)
    # ==========================================================================
    reviewed_enriched = [e for e in enriched_events if e.get("status") != "pending"]
    with st.expander(f"Lịch sử sự kiện đã duyệt ({len(reviewed_enriched)} sự kiện)", expanded=False):
        if reviewed_enriched:
            df_hist = pd.DataFrame([
                {
                    "Mã số": e["event_id"],
                    "Thời điểm": e["timestamp_vn"],
                    "Khu vực Camera": e["camera"],
                    "Mã công nhân": e["worker_id"],
                    "Hành vi vi phạm": e["title_tv"],
                    "Trạng thái hiện tại": e["status_tv"],
                    "Lệnh khẩn cấp IoT": e["iot_action"],
                }
                for e in reviewed_enriched
            ])
            render_data_table(
                df_hist,
                id_cols=("Mã số",),
                status_cols=("Trạng thái hiện tại",),
                iot_cols=("Lệnh khẩn cấp IoT",),
                muted_cols=("Thời điểm",),
                max_height=340,
            )
        else:
            st.caption("Chưa có sự kiện đã duyệt.")