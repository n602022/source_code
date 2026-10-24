# -*- coding: utf-8 -*-
"""
ui_pages/review.py — Trang Duyệt vi phạm & Điều khiển khẩn cấp Đội trưởng (Review Queue V2).
Đã nâng cấp theo 8 nguyên tắc thiết kế UI/UX:
- Đồng bộ chiều cao các thẻ video vi phạm: rút gọn dòng thông tin nguồn thành "Camera khu vực X" /
  "Video tải lên" / "Ảnh tải lên" kèm ngày giờ và % AI nhận diện; dựng theo từng hàng 2 cột để không bị lệch.
- Bổ sung nút tải xuống bằng chứng (`.sg-card-dl-btn`) ngay ở góc dưới bên phải mỗi thẻ sự kiện (ngang hàng
  với thông tin nguồn và ngày giờ), tự động lấy đúng đuôi file thực tế từ thuật toán (`ev["img_path"].suffix`).
- Thanh điều hướng phân trang hiện đại ở dưới danh sách thẻ: cố định 6 video / trang, căn giữa hoàn hảo
  dòng chữ "Hiển thị X–Y / N video" ngang hàng với cụm nút chuyển trang (‹, 1, 2, ... ›).
- Bối cảnh điều khiển & Giảm tải nhận thức:
  + Khung `Hồ sơ thẩm định` bên phải được ghim cố định (`position: sticky; top: 18px`) khi cuộn danh sách thẻ,
    kèm liên kết chuyển nhanh sang hỏi Trợ lý AI về đúng sự kiện đang xem.
  + Khi xem một sự kiện đã duyệt (`confirmed` / `false_positive`), nút "Đưa lại về Chờ duyệt" đặt ngay trong
    khung `Hồ sơ thẩm định` (đúng ngữ cảnh đối tượng).
  + Bảng `Lịch sử sự kiện đã duyệt` ở cuối trang được thu gọn gọn gàng trong một ngăn kéo (`st.expander`),
    giúp màn hình làm việc chính luôn thoáng đãng và tập trung.
"""
import datetime
import math
from pathlib import Path
import re
import pandas as pd
import streamlit as st

from chatbot import GIAI_THICH_LOI_VI_PHAM
from core_logic import (
    TEN_LOI_TV,
    TRANG_THAI_TV,
    clean_html,
    image_to_base64_uri,
    load_event_evidence,
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
    - Tự động lấy đúng đuôi file thực tế do thuật toán lưu (ví dụ: .jpg từ save_new_violations_to_db
      hoặc bất kỳ định dạng ảnh/video nào của tệp bằng chứng).
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
                for ev in pending_events:
                    update_event_status(int(ev["event_id"]), "confirmed")
                st.rerun()

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

    # Nếu vừa chuyển từ trang Dashboard sang ("Thẩm định #ID"), tự động nhảy tới trang chứa thẻ đó
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
                    <div class="sg-panel" style="text-align:center;padding:28px 18px;">
                        <div class="sg-panel-title">Không có sự kiện trong nhóm trạng thái này</div>
                    </div>
                    """
                ),
                unsafe_allow_html=True,
            )

            # Bảo toàn Bảng Điều Khiển Khẩn Cấp Đội Trưởng cho ca xác nhận gần nhất khi hết ca chờ duyệt
            if cur_tab == "pending" and confirmed_events:
                latest_conf = confirmed_events[0]
                lc_id = int(latest_conf["event_id"])
                lc_img, lc_meta = load_event_evidence(lc_id)
                lc_cam = lc_meta.get("camera", "Camera số 1")
                lc_wk = lc_meta.get("worker_id", "CN #01")
                lc_name = TEN_LOI_TV.get(latest_conf["violation_type"], latest_conf["violation_type"])
                with st.container(key="panel_review_emergency"):
                    st.markdown(f"#### Điều khiển khẩn cấp · Mã #{lc_id} — {lc_name}")
                    if lc_img is not None:
                        st.image(str(lc_img), caption=f"Ảnh bằng chứng Mã #{lc_id} tại {lc_cam}", width="stretch")
                    else:
                        st.info("Chưa có ảnh bằng chứng cho ca này.")
                    st.markdown(
                        f"- **Vị trí phát hiện:** `{lc_cam}` | **Công nhân:** `{lc_wk}`\n"
                        f"- **Thời điểm:** `{latest_conf['timestamp_vn']}`\n"
                        f"- **Lệnh IoT đã gửi:** `{lc_meta.get('iot_action', 'Chưa kích hoạt')}`"
                    )
                    em_b1, em_b2 = st.columns(2, gap="small")
                    with em_b1:
                        if st.button("Gửi loa nhắc nhở", type="primary", width="stretch", key=f"em_spk_{lc_id}"):
                            record_iot_action(lc_id, "Đã gửi loa nhắc nhở")
                            st.session_state.iot_action_banner = {
                                "type": "speaker",
                                "msg": f"Đã phát loa nhắc nhở tại {lc_cam} đối với {lc_wk} (Mã sự kiện #{lc_id}).",
                            }
                            st.rerun()
                    with em_b2:
                        if st.button("Dừng khẩn cấp dây chuyền", width="stretch", key=f"em_stop_{lc_id}"):
                            _confirm_estop_dialog(lc_id, lc_cam, lc_wk, False)

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
    # NGĂN KÉO LỊCH SỬ SỰ KIỆN ĐÃ DUYỆT & CHỈNH SỬA TRẠNG THÁI NHANH (GIẢM TẢI NHẬN THỨC)
    # ==========================================================================
    reviewed_enriched = [e for e in enriched_events if e.get("status") != "pending"]
    with st.expander(f"Lịch sử sự kiện đã duyệt & Đổi lại trạng thái ({len(reviewed_enriched)} sự kiện)", expanded=False):
        if reviewed_enriched:
            fix_c1, fix_c2, fix_c3, fix_c4 = st.columns([2.1, 1.0, 1.0, 1.0], gap="small")
            rev_map = {
                f"Mã #{e['event_id']} — {e['title_tv']} | Hiện tại: {e['status_tv']} ({e['timestamp_vn']})": e
                for e in reviewed_enriched
            }
            with fix_c1:
                chosen_fix_label = st.selectbox("Chọn sự kiện cần đổi lại trạng thái:", list(rev_map.keys()))
                target_fix_ev = rev_map[chosen_fix_label]
                target_fix_id = int(target_fix_ev["event_id"])
            with fix_c2:
                st.write("")
                st.button(
                    "Sửa thành: Vi phạm thật",
                    width="stretch",
                    key="btn_fix_to_true",
                    on_click=_decide_event,
                    args=(target_fix_id, "confirmed"),
                )
            with fix_c3:
                st.write("")
                st.button(
                    "Sửa thành: Báo nhầm",
                    width="stretch",
                    key="btn_fix_to_false",
                    on_click=_decide_event,
                    args=(target_fix_id, "false_positive"),
                )
            with fix_c4:
                st.write("")
                st.button(
                    "Đưa về: Chờ duyệt",
                    width="stretch",
                    key="btn_fix_to_pending",
                    on_click=_decide_event,
                    args=(target_fix_id, "pending"),
                )

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