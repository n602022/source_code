# -*- coding: utf-8 -*-
"""
ui_pages/dashboard.py — Trang Tổng quan an toàn (Dashboard V2).
Đã cân chỉnh để vừa đảm bảo nguyên tắc thiết kế gọn gàng, vừa khớp 100% với Báo cáo Word 6 chương của nhóm:
- Bảo toàn khối biểu đồ tròn `Tiến độ thẩm định` (`sg-score-panel`) vì Chương 3, Chương 4 và Chương 6 đều trích dẫn trực tiếp.
- Giữ 2 nút `Xuất báo cáo (.CSV)` và `Tải bằng chứng (.ZIP)` trực tiếp trên thanh công cụ để khớp kịch bản Demo Bước 6.
- Bỏ huy hiệu cố định "5 / 5 trực tuyến" gây hiểu sai ở khung `Camera trong hệ thống` (theo đề xuất Nhóm 1).
- Bỏ ô lọc "Mức độ rủi ro" ít dùng trong khung Bộ lọc nâng cao (theo đề xuất Nhóm 2).
- Bỏ nút "Mở trang duyệt vi phạm →" dư thừa ở đáy khung `Vi phạm gần đây`.
"""
import datetime
import re
import streamlit as st
from core_logic import (
    build_evidence_zip_bytes,
    build_shift_csv_bytes,
    clean_html,
    get_all_system_cameras,
    render_evidence_img_or_placeholder,
)


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


def _set_dash_range(range_val: str):
    st.session_state.dash_range = range_val


def _toggle_dash_filter():
    st.session_state.dash_filter_open = not bool(st.session_state.get("dash_filter_open", False))


def _reset_dash_filters():
    st.session_state.dash_cam_filter = "all"
    st.session_state.dash_status_filter = "all"
    st.session_state.dash_sev_filter = "all"
    st.session_state.dash_range = "all"
    st.session_state.dash_custom_date = None


def _goto_review_page(event_id: int | None = None, status_tab: str | None = None):
    if event_id is not None:
        st.session_state.selected_review_event_id = int(event_id)
        st.session_state.rev_locate_selected = True
    if status_tab is not None:
        st.session_state.review_tab_filter = status_tab
    st.session_state.active_page = "review"


def _goto_scanner_camera(cam_idx: int):
    """Chuyển thẳng sang trang Quét AI & Camera và chọn đúng camera khu vực tương ứng."""
    st.session_state.scan_source_mode = "Hệ thống Camera công trường"
    st.session_state.scan_cam_idx = int(cam_idx)
    st.session_state.active_page = "scan"


def _filter_events_by_toolbar(enriched_events: list) -> list:
    """Lọc danh sách sự kiện thực tế theo khoảng thời gian, ngày chọn, camera và trạng thái."""
    range_mode = st.session_state.get("dash_range", "all")
    custom_date = st.session_state.get("dash_custom_date")
    cam_filter = st.session_state.get("dash_cam_filter", "all")
    status_filter = st.session_state.get("dash_status_filter", "all")

    today = datetime.date.today()

    filtered = []
    for ev in enriched_events:
        ev_date = None
        try:
            ev_date = datetime.date.fromisoformat(ev["timestamp"].split()[0])
        except Exception:
            pass

        if range_mode == "today" and ev_date is not None:
            if ev_date != today:
                continue
        elif range_mode == "7d" and ev_date is not None:
            if not (0 <= (today - ev_date).days <= 7):
                continue
        elif range_mode == "30d" and ev_date is not None:
            if not (0 <= (today - ev_date).days <= 30):
                continue
        elif range_mode == "custom" and custom_date is not None and ev_date is not None:
            if ev_date != custom_date:
                continue

        if cam_filter != "all" and ev["camera"] != cam_filter:
            continue

        if status_filter != "all" and ev["status"] != status_filter:
            continue

        filtered.append(ev)

    return filtered


def _build_real_trend_or_timeline_html(events_list: list) -> str:
    """
    Biểu diễn diễn biến sự kiện theo thời gian thực từ safeguard.db:
    - Nếu 0 sự kiện: hiển thị Empty State.
    - Nếu chỉ có 1 hoặc 2 mốc thời gian: hiển thị Dòng thời gian sự kiện (Event Timeline) chi tiết.
    - Nếu có từ 3 mốc thời gian trở lên: vẽ biểu đồ xu hướng SVG với nhãn thời gian và số lượng thật.
    """
    if not events_list:
        return clean_html(
            """
            <div class="sg-timeline-box" style="text-align:center;padding:24px 16px;color:var(--muted);font-size:12px;">
                Chưa có sự kiện nào khớp với bộ lọc thời gian hiện tại để hiển thị diễn biến.
            </div>
            """
        )

    dates_map = {}
    hours_map = {}
    for ev in events_list:
        ts = ev.get("timestamp", "")
        parts = ts.split()
        d_key = parts[0] if parts else "N/A"
        h_key = parts[1][:5] if len(parts) > 1 else ts
        dates_map[d_key] = dates_map.get(d_key, 0) + 1
        hours_map[h_key] = hours_map.get(h_key, 0) + 1

    items = sorted(dates_map.items())[-7:] if len(dates_map) >= 3 else sorted(hours_map.items())[-7:]

    if len(items) < 3:
        rows_html = []
        for ev in events_list[:5]:
            eid = int(ev["event_id"])
            src_short = _format_card_source(ev.get("camera"))
            rows_html.append(
                f'<div class="sg-timeline-row">'
                f'<div style="display:flex;align-items:center;gap:10px;min-width:0;">'
                f'<span class="sg-timeline-time">{ev.get("timestamp_vn", ev["timestamp"])}</span>'
                f'<strong style="color:var(--text);">#{eid} · {ev["title_tv"]}</strong>'
                f'<span style="color:var(--muted);font-size:11px;">({src_short} · AI: {ev["confidence_pct"]})</span>'
                f"</div>"
                f'<span class="sg-badge {ev["status"]}">{ev["status_badge_tv"]}</span>'
                f"</div>"
            )
        rows_joined = "".join(rows_html)
        return clean_html(
            f"""
            <div class="sg-timeline-box">
                <div class="sg-timeline-head">
                    <span><b>Dòng thời gian sự kiện</b> ({len(events_list)} sự kiện)</span>
                </div>
                {rows_joined}
            </div>
            """
        )

    max_v = max(max(v for _, v in items), 1)
    n = len(items)
    xs = [int(round(36 + i * (628 / max(1, n - 1)))) for i in range(n)]
    ys = [int(round(130 - (v / max_v) * 85)) for _, v in items]

    pts = " L ".join(f"{x} {y}" for x, y in zip(xs, ys))
    line_path = f"M {pts}"
    area_path = f"M {pts} L {xs[-1]} 145 L {xs[0]} 145 Z"

    circles_svg = "".join(
        f'<circle cx="{x}" cy="{y}" r="4.5" fill="var(--primary)" />'
        for x, y in zip(xs, ys)
    )
    labels_svg = "".join(
        f'<text x="{x}" y="166" text-anchor="middle">{lbl} ({val})</text>'
        for (lbl, val), x in zip(items, xs)
    )

    return clean_html(
        f"""
        <svg aria-label="Biểu đồ xu hướng sự cố thực tế" class="sg-spark" preserveAspectRatio="none" viewBox="0 0 700 175">
            <defs>
                <linearGradient id="sgAreaGrad" x1="0" x2="0" y1="0" y2="1">
                    <stop offset="0" stop-color="#3157D5" stop-opacity="0.26"></stop>
                    <stop offset="1" stop-color="#3157D5" stop-opacity="0.01"></stop>
                </linearGradient>
            </defs>
            <g stroke="var(--border)" stroke-width="1">
                <line x1="20" x2="680" y1="25" y2="25"></line>
                <line x1="20" x2="680" y1="65" y2="65"></line>
                <line x1="20" x2="680" y1="105" y2="105"></line>
                <line x1="20" x2="680" y1="145" y2="145"></line>
            </g>
            <path d="{area_path}" fill="url(#sgAreaGrad)"></path>
            <path d="{line_path}" fill="none" stroke="var(--primary)" stroke-linecap="round" stroke-linejoin="round" stroke-width="3"></path>
            {circles_svg}
            <g fill="var(--muted)" font-size="10" font-weight="600">
                {labels_svg}
            </g>
        </svg>
        """
    )


def render_dashboard_page(raw_events: list, enriched_events: list):
    """Hiển thị trang Tổng quan an toàn (Dashboard V2) với dữ liệu thực tế từ safeguard.db."""
    system_cams = get_all_system_cameras()
    cur_range = st.session_state.get("dash_range", "all")
    filter_open = st.session_state.get("dash_filter_open", False)

    active_filter_count = sum([
        1 if st.session_state.get("dash_cam_filter", "all") != "all" else 0,
        1 if st.session_state.get("dash_status_filter", "all") != "all" else 0,
        1 if cur_range == "custom" else 0,
    ])
    filter_btn_label = f"Bộ lọc ({active_filter_count})" if active_filter_count > 0 else "Bộ lọc"

    # --- THANH CÔNG CỤ: NHÓM THỜI GIAN BÊN TRÁI | BỘ LỌC, XUẤT BÁO CÁO (.CSV) & TẢI BẰNG CHỨNG (.ZIP) BÊN PHẢI ---
    with st.container(key="dash_toolbar_wrap"):
        tb_left, tb_filter, tb_csv, tb_zip = st.columns([3.55, 0.85, 1.25, 1.35], gap="small", vertical_alignment="center")
        with tb_left:
            with st.container(key="dash_range_group"):
                r1, r2, r3, r4 = st.columns([0.9, 1.25, 1.25, 0.85], gap="small")
                with r1:
                    st.button(
                        "Hôm nay",
                        key="range_today",
                        type="primary" if cur_range == "today" else "secondary",
                        width="stretch",
                        on_click=_set_dash_range,
                        args=("today",),
                    )
                with r2:
                    st.button(
                        "7 ngày gần nhất",
                        key="range_7d",
                        type="primary" if cur_range == "7d" else "secondary",
                        width="stretch",
                        on_click=_set_dash_range,
                        args=("7d",),
                    )
                with r3:
                    st.button(
                        "30 ngày gần nhất",
                        key="range_30d",
                        type="primary" if cur_range == "30d" else "secondary",
                        width="stretch",
                        on_click=_set_dash_range,
                        args=("30d",),
                    )
                with r4:
                    st.button(
                        "Tất cả",
                        key="range_all",
                        type="primary" if cur_range == "all" else "secondary",
                        width="stretch",
                        on_click=_set_dash_range,
                        args=("all",),
                    )
        with tb_filter:
            st.button(
                filter_btn_label,
                key="toggle_dash_filter",
                type="primary" if (filter_open or active_filter_count > 0) else "secondary",
                width="stretch",
                on_click=_toggle_dash_filter,
            )

    if filter_open:
        with st.container(key="panel_dash_filter"):
            # Đã bỏ ô lọc "Mức độ rủi ro" theo đề xuất Nhóm 2, chỉ giữ Camera, Trạng thái, Ngày báo cáo
            fc1, fc2, fc3, fc4 = st.columns([1.4, 1.3, 1.3, 0.95], gap="small")
            cam_map = {"all": "Tất cả camera"}
            for c in system_cams:
                cam_map[c] = c

            with fc1:
                cur_cam_f = st.session_state.get("dash_cam_filter", "all")
                if cur_cam_f not in cam_map:
                    cur_cam_f = "all"
                chosen_cam = st.selectbox(
                    "Camera",
                    options=list(cam_map.keys()),
                    format_func=lambda k: cam_map[k],
                    index=list(cam_map.keys()).index(cur_cam_f),
                    key="dash_cam_select",
                )
                st.session_state.dash_cam_filter = chosen_cam

            with fc2:
                status_map = {
                    "all": "Tất cả trạng thái",
                    "pending": "Chờ duyệt",
                    "confirmed": "Đã xác nhận",
                    "false_positive": "Đã loại bỏ (AI nhầm)",
                }
                chosen_st = st.selectbox(
                    "Trạng thái xử lý",
                    options=list(status_map.keys()),
                    format_func=lambda k: status_map[k],
                    index=list(status_map.keys()).index(st.session_state.get("dash_status_filter", "all")),
                    key="dash_status_select",
                )
                st.session_state.dash_status_filter = chosen_st

            with fc3:
                picked_date = st.date_input(
                    "Chọn ngày báo cáo",
                    value=st.session_state.get("dash_custom_date") or datetime.date.today(),
                    key="dash_date_picker",
                )
                if st.checkbox("Lọc theo ngày này", value=(cur_range == "custom"), key="dash_apply_date"):
                    st.session_state.dash_range = "custom"
                    st.session_state.dash_custom_date = picked_date

            with fc4:
                st.write("")
                st.button(
                    "Đặt lại mặc định",
                    key="dash_reset_filter",
                    width="stretch",
                    on_click=_reset_dash_filters,
                )

    filtered_events = _filter_events_by_toolbar(enriched_events)

    with tb_csv:
        st.download_button(
            label="Xuất báo cáo (.CSV)",
            data=build_shift_csv_bytes(filtered_events),
            file_name=f"Bao_Cao_Vi_Pham_Ca_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv",
            width="stretch",
            key="dash_dl_csv",
        )
    with tb_zip:
        st.download_button(
            label="Tải bằng chứng (.ZIP)",
            data=build_evidence_zip_bytes(filtered_events),
            file_name=f"Bang_Chung_Vi_Pham_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.zip",
            mime="application/zip",
            width="stretch",
            key="dash_dl_zip",
        )

    total_events = len(filtered_events)
    pending_list = [e for e in filtered_events if e["status"] == "pending"]
    confirmed_list = [e for e in filtered_events if e["status"] == "confirmed"]
    false_pos_list = [e for e in filtered_events if e["status"] == "false_positive"]

    pending_count = len(pending_list)
    confirmed_count = len(confirmed_list)
    false_pos_count = len(false_pos_list)

    # --- 4 THẺ KPI TỔNG QUAN TỪ DATABASE ---
    k1, k2, k3, k4 = st.columns(4, gap="medium")
    with k1:
        st.markdown(
            clean_html(
                f"""
                <div class="sg-kpi-card" style="border-left-color: #3574C5;">
                    <div class="sg-kpi-label">Tổng cảnh báo trong bộ lọc</div>
                    <div class="sg-kpi-val">{total_events:02d}</div>
                </div>
                """
            ),
            unsafe_allow_html=True,
        )
    with k2:
        st.markdown(
            clean_html(
                f"""
                <div class="sg-kpi-card" style="border-left-color: #16856B;">
                    <div class="sg-kpi-label">Vi phạm đã xác nhận</div>
                    <div class="sg-kpi-val" style="color: var(--success);">{confirmed_count:02d}</div>
                </div>
                """
            ),
            unsafe_allow_html=True,
        )
    with k3:
        st.markdown(
            clean_html(
                f"""
                <div class="sg-kpi-card{' needs-action' if pending_count else ''}" style="border-left-color: #B9770E;">
                    <div class="sg-kpi-label">Cần giám sát duyệt lại</div>
                    <div class="sg-kpi-val" style="color: var(--warning);">{pending_count:02d}</div>
                </div>
                """
            ),
            unsafe_allow_html=True,
        )
    with k4:
        st.markdown(
            clean_html(
                f"""
                <div class="sg-kpi-card" style="border-left-color: #D64545;">
                    <div class="sg-kpi-label">Đã loại bỏ (AI nhầm)</div>
                    <div class="sg-kpi-val" style="color: var(--danger);">{false_pos_count:02d}</div>
                </div>
                """
            ),
            unsafe_allow_html=True,
        )

    range_labels = {
        "today": "Hôm nay",
        "7d": "7 ngày gần nhất",
        "30d": "30 ngày gần nhất",
        "all": "Tất cả thời gian",
        "custom": f"Ngày {st.session_state.get('dash_custom_date')}",
    }
    active_range_label = range_labels.get(st.session_state.get("dash_range", "all"), "Tất cả thời gian")
    reviewed_ratio = int(round(((confirmed_count + false_pos_count) / max(1, total_events)) * 100)) if total_events > 0 else 100

    # --- BỐ CỤC 2 CỘT CHÍNH (LEFT STACK & RIGHT STACK) ---
    col_left, col_right = st.columns([1.45, 1.05], gap="medium")

    with col_left:
        # 1. PANEL DIỄN BIẾN SỰ CỐ THEO THỜI GIAN (Không lặp lại con số của 4 thẻ KPI phía trên)
        trend_or_timeline_html = _build_real_trend_or_timeline_html(filtered_events)
        st.markdown(
            clean_html(
                f"""
                <div class="sg-panel">
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
                        <div>
                            <div class="sg-panel-title" style="color:var(--primary)">Diễn biến sự cố theo thời gian</div>
                            <div class="sg-panel-sub" style="margin-top:2px;">Phạm vi: {active_range_label}</div>
                        </div>
                    </div>
                    {trend_or_timeline_html}
                </div>
                """
            ),
            unsafe_allow_html=True,
        )

        # 2. HAI THẺ PHÂN TÍCH SONG SONG: SỰ CỐ THEO HÀNH VI & KHU VỰC GHI NHẬN NHIỀU NHẤT
        sub_c1, sub_c2 = st.columns(2, gap="medium")
        valid_ev = [e for e in filtered_events if e["status"] != "false_positive"]
        cnt_vest = sum(1 for e in valid_ev if e["violation_type"] == "NO-Safety Vest")
        cnt_hat = sum(1 for e in valid_ev if e["violation_type"] == "NO-Hardhat")
        cnt_mask = sum(1 for e in valid_ev if e["violation_type"] == "NO-Mask")
        tot_valid = max(1, cnt_vest + cnt_hat + cnt_mask)

        w_vest = int(round((cnt_vest / tot_valid) * 100)) if (cnt_vest + cnt_hat + cnt_mask) > 0 else 0
        w_hat = int(round((cnt_hat / tot_valid) * 100)) if (cnt_vest + cnt_hat + cnt_mask) > 0 else 0
        w_mask = int(round((cnt_mask / tot_valid) * 100)) if (cnt_vest + cnt_hat + cnt_mask) > 0 else 0

        with sub_c1:
            st.markdown(
                clean_html(
                    f"""
                    <div class="sg-panel">
                        <div class="sg-panel-title">Sự cố theo hành vi</div>
                        <div class="sg-bar-row">
                            <span>Không mặc áo phản quang</span>
                            <b>{cnt_vest}</b>
                            <div class="sg-track"><div class="sg-fill" style="width:{max(4, w_vest) if cnt_vest else 0}%;background:#D68B1E"></div></div>
                        </div>
                        <div class="sg-bar-row">
                            <span>Không đội mũ bảo hộ</span>
                            <b>{cnt_hat}</b>
                            <div class="sg-track"><div class="sg-fill" style="width:{max(4, w_hat) if cnt_hat else 0}%;background:#D64545"></div></div>
                        </div>
                        <div class="sg-bar-row">
                            <span>Không đeo khẩu trang</span>
                            <b>{cnt_mask}</b>
                            <div class="sg-track"><div class="sg-fill" style="width:{max(4, w_mask) if cnt_mask else 0}%;background:#3574C5"></div></div>
                        </div>
                    </div>
                    """
                ),
                unsafe_allow_html=True,
            )

        with sub_c2:
            src_counts = {}
            for ev in valid_ev:
                lbl_s = _format_card_source(ev.get("camera"))
                src_counts[lbl_s] = src_counts.get(lbl_s, 0) + 1
            top_sources = sorted(src_counts.items(), key=lambda x: x[1], reverse=True)[:3]
            while len(top_sources) < 3:
                fallback_lbl = f"Camera khu vực {len(top_sources) + 1}"
                if all(k != fallback_lbl for k, _ in top_sources):
                    top_sources.append((fallback_lbl, 0))
                else:
                    top_sources.append((f"Khu vực {len(top_sources) + 2}", 0))

            bar_colors = ("#3157D5", "#16856B", "#B9770E")
            src_rows_html = []
            for idx_s, (s_lbl, s_cnt) in enumerate(top_sources):
                s_pct = int(round((s_cnt / tot_valid) * 100)) if len(valid_ev) > 0 else 0
                src_rows_html.append(
                    f'<div class="sg-bar-row">'
                    f"<span>{s_lbl}</span>"
                    f"<b>{s_cnt}</b>"
                    f'<div class="sg-track"><div class="sg-fill" style="width:{max(4, s_pct) if s_cnt else 0}%;background:{bar_colors[idx_s % 3]}"></div></div>'
                    f"</div>"
                )
            st.markdown(
                clean_html(
                    f"""
                    <div class="sg-panel">
                        <div class="sg-panel-title">Khu vực ghi nhận nhiều nhất</div>
                        {"".join(src_rows_html)}
                    </div>
                    """
                ),
                unsafe_allow_html=True,
            )

        # 3. PANEL BIỂU ĐỒ TRÒN TIẾN ĐỘ THẨM ĐỊNH (Giữ nguyên khớp Chương 3, 4, 6 trong Báo cáo Word)
        vest_status = f"{cnt_vest} vi phạm" if cnt_vest > 0 else "0 vi phạm"
        hat_status = f"{cnt_hat} vi phạm" if cnt_hat > 0 else "0 vi phạm"
        mask_status = f"{cnt_mask} vi phạm" if cnt_mask > 0 else "0 vi phạm"
        queue_status = f"{pending_count} chờ duyệt" if pending_count > 0 else "Đã duyệt hết"

        st.markdown(
            clean_html(
                f"""
                <div class="sg-score-panel">
                    <div>
                        <div style="font-size:14px;font-weight:700;color:#F5F8FF;margin-bottom:14px;">Tiến độ thẩm định</div>
                        <div class="sg-score-ring">
                            <div class="sg-score-ring-inner">
                                <strong>{reviewed_ratio}%</strong>
                                <small>đã thẩm định</small>
                            </div>
                        </div>
                    </div>
                    <div>
                        <div style="font-size:14px;font-weight:700;color:#F5F8FF;margin-bottom:14px;">Trạng thái theo nhóm nghiệp vụ</div>
                        <div class="sg-score-list">
                            <div class="sg-score-item">
                                <span><i class="sg-score-dot" style="background:#45D6A5"></i>Mũ bảo hộ</span>
                                <b>{hat_status}</b>
                            </div>
                            <div class="sg-score-item">
                                <span><i class="sg-score-dot" style="background:#F7A51A"></i>Áo phản quang</span>
                                <b>{vest_status}</b>
                            </div>
                            <div class="sg-score-item">
                                <span><i class="sg-score-dot" style="background:#7895FF"></i>Khẩu trang</span>
                                <b>{mask_status}</b>
                            </div>
                            <div class="sg-score-item">
                                <span><i class="sg-score-dot" style="background:#7B91AE"></i>Hàng đợi duyệt</span>
                                <b>{queue_status}</b>
                            </div>
                        </div>
                    </div>
                </div>
                """
            ),
            unsafe_allow_html=True,
        )

        # 4. DẢI 5 CAMERA TRONG HỆ THỐNG (Đã bỏ huy hiệu cố định "5 / 5 trực tuyến" gây hiểu sai)
        with st.container(key="panel_dash_cameras"):
            st.markdown(
                clean_html('<div class="sg-panel-title" style="margin-bottom:6px;">Camera trong hệ thống</div>'),
                unsafe_allow_html=True,
            )
            cam_cols = st.columns(len(system_cams), gap="small")
            for idx_c, cam_name in enumerate(system_cams):
                cam_ev_cnt = sum(1 for e in filtered_events if e.get("system_camera") == cam_name and e.get("status") != "false_positive")
                sub_txt = f"{cam_ev_cnt} cảnh báo" if cam_ev_cnt > 0 else "An toàn"
                with cam_cols[idx_c]:
                    st.button(
                        f"**Cam {idx_c + 1:02d}**  \nKhu vực {idx_c + 1}  \n:green[●] {sub_txt}",
                        key=f"dash_cam_jump_{idx_c}",
                        width="stretch",
                        on_click=_goto_scanner_camera,
                        args=(idx_c,),
                    )

    with col_right:
        # PANEL VI PHẠM GẦN ĐÂY (Tiêu đề ngang hàng nút Xem tất cả →, đã bỏ nút trùng ở đáy)
        with st.container(key="panel_dash_evidence"):
            with st.container(key="dash_recent_header"):
                hd_c1, hd_c2 = st.columns([2.1, 1.0], vertical_alignment="center")
                with hd_c1:
                    st.markdown(
                        clean_html('<div class="sg-panel-title">Vi phạm gần đây</div>'),
                        unsafe_allow_html=True,
                    )
                with hd_c2:
                    st.button(
                        "Xem tất cả →",
                        key="dash_top_goto_review",
                        width="stretch",
                        on_click=_goto_review_page,
                    )

            recent_slice = filtered_events[:4]
            if recent_slice:
                for row_start in range(0, len(recent_slice), 2):
                    row_items = recent_slice[row_start:row_start + 2]
                    grid_cols = st.columns(2, gap="small")
                    for col_idx, ev in enumerate(row_items):
                        eid = int(ev["event_id"])
                        src_label = _format_card_source(ev.get("camera"))
                        media_html = render_evidence_img_or_placeholder(ev["img_path"], eid, height_px=136)
                        with grid_cols[col_idx]:
                            st.markdown(
                                clean_html(
                                    f"""
                                    <div class="sg-incident-card">
                                        {media_html}
                                        <div class="sg-incident-body">
                                            <div class="sg-incident-badges">
                                                <span class="sg-badge {ev['severity']}">{ev['severity_label']}</span>
                                                <span class="sg-badge {ev['status']}" style="margin-left:auto;">{ev['status_badge_tv']}</span>
                                            </div>
                                            <div class="sg-incident-title" title="#{eid} · {ev['title_tv']}">#{eid} · {ev['title_tv']}</div>
                                            <div class="sg-incident-meta">{src_label}</div>
                                            <div class="sg-incident-meta">{ev['timestamp_vn']} · AI: {ev['confidence_pct']}</div>
                                        </div>
                                    </div>
                                    """
                                ),
                                unsafe_allow_html=True,
                            )
                            st.button(
                                f"Thẩm định #{eid}",
                                key=f"dash_inspect_{eid}",
                                width="stretch",
                                on_click=_goto_review_page,
                                args=(eid, ev["status"]),
                            )
            else:
                st.info("Không có sự kiện nào phù hợp với bộ lọc đã chọn.")