# -*- coding: utf-8 -*-
"""
ui_components.py — Các thành phần giao diện dùng chung chuẩn Prototype V2:
- Đã tối ưu hóa điều hướng bằng cơ chế callback `on_click` chuẩn của Streamlit (1-pass execution).
- Gộp hai hàng đầu trang thành một hàng Header duy nhất (`render_topbar`):
  + Bên trái: Tiêu đề trang (`<h1>`) rõ ràng, căn thẳng hàng với khối thương hiệu ở Sidebar (bỏ nhãn phụ phía trên và chữ lặp).
  + Bên phải: Huy hiệu trạng thái hệ thống + Nút Chuông thông báo + Khung hồ sơ "Minh An / Giám sát viên" nằm gọn trên cùng 1 hàng, tiết kiệm ~90px chiều dọc.
"""
import html as _html

import streamlit as st
from core_logic import (
    TRANG_THAI_TV,
    clean_html,
    play_emergency_siren,
    play_speaker_chime,
    update_event_status,
)

PAGE_META = {
    "dashboard": (
        "Tổng quan an toàn",
        "Theo dõi sự cố, mức độ tuân thủ và các bằng chứng vi phạm gần đây từ cơ sở dữ liệu.",
        "AN TOÀN & TUÂN THỦ",
    ),
    "scan": (
        "Quét AI & Camera",
        "Chọn nguồn hình ảnh, kiểm tra khung hình trực tiếp và cấu hình phiên quét.",
        "GIÁM SÁT TRỰC TIẾP",
    ),
    "review": (
        "Duyệt vi phạm",
        "Thẩm định bằng chứng (Human-in-the-loop), hoàn tác khi bấm nhầm và điều khiển hiện trường.",
        "HÀNG ĐỢI DUYỆT",
    ),
    "chat": (
        "Trợ lý AI",
        "Tra cứu nhanh về ca trực, hướng dẫn duyệt vi phạm và quy định an toàn lao động.",
        "TRỢ LÝ THÔNG MINH",
    ),
    "docs": (
        "Tài liệu an toàn",
        "Tìm kiếm và đọc nguyên văn các quy định an toàn lao động trong hệ thống.",
        "THƯ VIỆN NỘI QUY",
    ),
}


def _set_active_page(page_key: str):
    """Callback đổi trang tức thì trong 1 chu kỳ duy nhất."""
    st.session_state.active_page = page_key


def _set_theme_mode(mode: str):
    """Callback đổi giao diện Sáng / Tối / Theo hệ thống tức thì trong 1 chu kỳ duy nhất."""
    st.session_state.theme_mode = mode


def _toggle_sidebar():
    """Callback thu gọn / mở rộng sidebar tức thì trong 1 chu kỳ duy nhất."""
    st.session_state.sidebar_collapsed = not bool(st.session_state.get("sidebar_collapsed", False))


def _clear_estop():
    """Callback khôi phục dây chuyền sau khi dừng khẩn cấp."""
    st.session_state.emergency_stop_active = None


def _flip_last_reviewed(event_id: int, flipped_status: str):
    """Callback đổi nhanh trạng thái sự kiện vừa duyệt."""
    update_event_status(event_id, flipped_status)
    st.session_state.last_reviewed_action = {"event_id": event_id, "new_status": flipped_status}


def _restore_last_reviewed_pending(event_id: int):
    """Callback hoàn tác sự kiện vừa duyệt về trạng thái chờ duyệt."""
    update_event_status(event_id, "pending")
    st.session_state.last_reviewed_action = None


def render_sidebar(pending_count: int | None, total_events: int):
    """
    Dựng thanh điều hướng bên trái chuẩn Prototype V2:
    - Sử dụng `on_click` cho toàn bộ nút điều hướng, nút chọn giao diện và nút thu gọn để phản hồi tức thì.
    """
    with st.sidebar:
        st.markdown(
            clean_html(
                """
                <div class="sg-brand">
                    <div class="sg-logo">
                        <svg aria-hidden="true" viewBox="0 0 24 24">
                            <path d="M12 2.8l8.8 5.1v8.2L12 21.2l-8.8-5.1V7.9z"></path>
                            <path d="M12 7v10"></path>
                        </svg>
                    </div>
                    <div>
                        <div class="sg-brand-title">SAFEGUARD AI</div>
                        <small class="sg-brand-sub">Giám sát an toàn lao động</small>
                    </div>
                </div>
                <div class="sg-side-label">Không gian làm việc</div>
                """
            ),
            unsafe_allow_html=True,
        )

        cur_page = st.session_state.get("active_page", "dashboard")
        collapsed = bool(st.session_state.get("sidebar_collapsed", False))

        # Badge số lượng chờ duyệt: vẽ bằng CSS ::after (tròn, cam)
        if isinstance(pending_count, int) and pending_count > 0:
            st.markdown(
                "<style>.st-key-nav_btn_review button::after{content:\"%d\";margin-left:auto;"
                "min-width:20px;height:20px;padding:0 6px;border-radius:999px;background:#B9770E;"
                "color:#fff;font-size:10px;font-weight:800;display:inline-flex;align-items:center;"
                "justify-content:center;}</style>" % pending_count,
                unsafe_allow_html=True,
            )

        nav_items = [
            ("dashboard", "Tổng quan", ":material/grid_view:"),
            ("scan", "Quét AI & Camera", ":material/smart_display:"),
            ("review", "Duyệt vi phạm", ":material/check:"),
            ("chat", "Trợ lý AI", ":material/chat_bubble_outline:"),
            ("docs", "Tài liệu an toàn", ":material/description:"),
        ]

        for page_key, label, icon in nav_items:
            is_active = cur_page == page_key
            st.button(
                label,
                key=f"nav_btn_{page_key}",
                help=label if collapsed else None,
                type="primary" if is_active else "secondary",
                width="stretch",
                on_click=_set_active_page,
                args=(page_key,),
            )

        # Nhóm chân sidebar: ghim sát đáy như prototype (CSS: .st-key-sb_bottom { margin-top: auto })
        with st.container(key="sb_bottom"):
            with st.container(key="sb_footer"):
                st.markdown('<div class="sg-side-label">Giao diện</div>', unsafe_allow_html=True)
                cur_theme = st.session_state.get("theme_mode", "light")

                # Thanh phân đoạn 1 hàng: Sáng | Tối | Theo hệ thống (CSS: .st-key-theme_switch)
                with st.container(key="theme_switch"):
                    t_col1, t_col2, t_col3 = st.columns([0.85, 0.7, 1.5], gap="small")
                    for col, mode, label in (
                        (t_col1, "light", "Sáng"),
                        (t_col2, "dark", "Tối"),
                        (t_col3, "system", "Theo hệ thống"),
                    ):
                        with col:
                            st.button(
                                label,
                                key=f"theme_btn_{mode}",
                                type="primary" if cur_theme == mode else "secondary",
                                width="stretch",
                                on_click=_set_theme_mode,
                                args=(mode,),
                            )

            st.button(
                "Mở rộng" if collapsed else "Thu gọn",
                key="sb_toggle_btn",
                icon=":material/keyboard_double_arrow_right:" if collapsed else ":material/keyboard_double_arrow_left:",
                help="Mở rộng thanh bên" if collapsed else "Thu gọn thanh bên",
                width="stretch",
                on_click=_toggle_sidebar,
            )


def render_utility_bar(enriched_events: list, pending_events: list):
    """Giữ hàm tương thích API (đã gộp trực tiếp vào render_topbar để tiết kiệm chiều dọc)."""
    return None


def render_topbar(
    page_key: str,
    db_connected: bool = True,
    enriched_events: list | None = None,
    pending_events: list | None = None,
):
    """
    Dựng Header hợp nhất trên 1 hàng duy nhất:
    - Cột trái: Tiêu đề trang (`<h1>`) gọn gàng (bỏ nhãn nhỏ phía trên và dòng chữ lặp với Sidebar).
    - Cột phải: Huy hiệu trạng thái hệ thống + Chuông thông báo + Khung hồ sơ "Minh An / Giám sát viên".
    """
    enriched_events = enriched_events or []
    pending_events = pending_events or []
    title, _, _ = PAGE_META.get(page_key, PAGE_META["dashboard"])
    estop = st.session_state.get("emergency_stop_active")

    if estop:
        status_html = (
            f'<div class="sg-top-status danger">'
            f'<span class="sg-dot-danger"></span> DỪNG KHẨN CẤP: {estop["camera"]}'
            f"</div>"
        )
    elif not db_connected:
        status_html = (
            '<div class="sg-top-status warn">'
            '<span class="sg-dot"></span> MẤT KẾT NỐI DỮ LIỆU'
            "</div>"
        )
    elif st.session_state.get("scan_is_running"):
        status_html = (
            '<div class="sg-top-status busy">'
            '<span class="sg-dot"></span> ĐANG QUÉT'
            "</div>"
        )
    else:
        status_html = (
            '<div class="sg-top-status">'
            '<span class="sg-dot"></span> HỆ THỐNG SẴN SÀNG'
            "</div>"
        )

    if pending_events:
        st.markdown(
            "<style>.st-key-util_bell button::after{content:\"\";position:absolute;top:7px;right:9px;"
            "width:9px;height:9px;border-radius:50%;background:#EF4444;border:2px solid var(--surface);z-index:2;}</style>",
            unsafe_allow_html=True,
        )

    with st.container(key="util_bar_row"):
        h_title, h_status, h_bell, h_user = st.columns([4.5, 1.55, 0.42, 1.38], vertical_alignment="center", gap="small")
        with h_title:
            st.markdown(
                clean_html(f'<div class="sg-unified-title"><h1>{title}</h1></div>'),
                unsafe_allow_html=True,
            )
        with h_status:
            st.markdown(
                clean_html(f'<div class="sg-unified-status-wrap">{status_html}</div>'),
                unsafe_allow_html=True,
            )
        with h_bell:
            with st.container(key="util_bell"):
                with st.popover("Thông báo", icon=":material/notifications:", help="Thông báo sự kiện"):
                    st.markdown("**Thông báo sự kiện**")
                    if pending_events:
                        st.caption(f"**{len(pending_events)} sự kiện** đang chờ duyệt:")
                        for pev in pending_events[:4]:
                            st.markdown(
                                f"- **#{pev['event_id']} · {pev['title_tv']}**  \n"
                                f"  <small>{pev['camera']} · {pev['worker_id']} · `{pev.get('timestamp_vn', pev['timestamp'])}`</small>",
                                unsafe_allow_html=True,
                            )
                    elif enriched_events:
                        latest = enriched_events[0]
                        st.caption("Không có sự kiện chờ duyệt.")
                        st.markdown(
                            f"Sự kiện gần nhất: **#{latest['event_id']} — {latest['title_tv']}** "
                            f"({latest['status_badge_tv']}) lúc `{latest.get('timestamp_vn', latest['timestamp'])}`."
                        )
                    else:
                        st.caption("Chưa có sự kiện nào.")

                    st.button(
                        "Mở trang duyệt vi phạm",
                        key="util_goto_review",
                        type="primary",
                        width="stretch",
                        on_click=_set_active_page,
                        args=("review",),
                    )
        with h_user:
            with st.container(key="util_user"):
                with st.popover("**Minh An**  \nGiám sát viên"):
                    st.markdown("**Minh An — Giám sát viên An toàn**")
                    _n_done = sum(1 for e in enriched_events if e.get("status") in ("confirmed", "false_positive"))
                    st.caption(f"Chờ duyệt: **{len(pending_events)}** · Đã xử lý: **{_n_done}**")

    st.markdown('<div class="sg-utility-divider"></div>', unsafe_allow_html=True)


def render_global_banners():
    """
    Hiển thị các thanh trạng thái nghiệp vụ quan trọng:
    1. Trạng thái khẩn cấp khi Đội trưởng kích hoạt Dừng khẩn cấp dây chuyền (kèm nút Khôi phục dây chuyền).
    2. Thông báo và phát âm thanh chuông loa / còi báo động khi vừa bấm nút IoT.
    3. Thanh hoàn tác / đổi nhanh trạng thái (Đúng <-> Sai) khi vừa duyệt sự kiện.
    """
    enable_audio = st.session_state.get("enable_audio", True)

    if st.session_state.get("emergency_stop_active") is not None:
        es_info = st.session_state.emergency_stop_active
        es_c1, es_c2 = st.columns([3.3, 1.0])
        with es_c1:
            st.error(
                f"TRẠNG THÁI KHẨN CẤP: Đã kích hoạt lệnh **DỪNG KHẨN CẤP DÂY CHUYỀN** tại **{es_info['camera']}** "
                f"(Sự kiện Mã #{es_info['event_id']} — {es_info['worker_id']} lúc {es_info['time']})."
            )
        with es_c2:
            st.button(
                "Khôi phục dây chuyền",
                width="stretch",
                key="btn_reset_estop",
                on_click=_clear_estop,
            )

    if st.session_state.get("iot_action_banner") is not None:
        ib = st.session_state.iot_action_banner
        if ib["type"] == "speaker":
            st.success(ib["msg"])
            if enable_audio:
                play_speaker_chime()
        elif ib["type"] == "estop":
            st.warning(ib["msg"])
            if enable_audio:
                play_emergency_siren()
        st.session_state.iot_action_banner = None

    if st.session_state.get("last_reviewed_action") is not None:
        last_act = st.session_state.last_reviewed_action
        l_id = int(last_act["event_id"])
        l_status = last_act["new_status"]
        l_status_tv = TRANG_THAI_TV.get(l_status, l_status)

        u1, u2, u3 = st.columns([2.2, 1.15, 1.05])
        with u1:
            st.info(f"Vừa duyệt **Mã #{l_id}**: **{l_status_tv}**.")
        with u2:
            flipped_status = "false_positive" if l_status == "confirmed" else "confirmed"
            flipped_btn_text = (
                "Đổi sang: Báo nhầm (Sai)"
                if flipped_status == "false_positive"
                else "Đổi sang: Vi phạm thật (Đúng)"
            )
            st.button(
                flipped_btn_text,
                width="stretch",
                key="btn_flip_immediate",
                on_click=_flip_last_reviewed,
                args=(l_id, flipped_status),
            )
        with u3:
            st.button(
                "Đưa lại về Chờ duyệt",
                width="stretch",
                key="btn_restore_pending",
                on_click=_restore_last_reviewed_pending,
                args=(l_id,),
            )


# Màu huy hiệu theo nội dung trạng thái (so khớp không phân biệt hoa thường)
_STATUS_TONES = (
    ("loại bỏ", "mute"),
    ("báo nhầm", "mute"),
    ("xác nhận", "ok"),
    ("chờ duyệt", "warn"),
    ("khẩn cấp", "bad"),
    ("dừng", "bad"),
    ("đã gửi", "info"),
    ("loa", "info"),
)


def _status_tone(text: str) -> str:
    low = str(text).lower()
    for key, tone in _STATUS_TONES:
        if key in low:
            return tone
    return "mute"


def render_data_table(df, id_cols=(), status_cols=(), iot_cols=(), muted_cols=(), max_height: int = 340):
    """
    Bảng dữ liệu hiện đại thay cho st.dataframe: tiêu đề cố định, hàng sọc nhẹ, hover, huy hiệu trạng thái,
    cuộn trong khung, tự đổi màu theo giao diện Sáng/Tối (CSS .sg-table trong ui_theme.py).
    """
    esc = lambda v: _html.escape(str(v), quote=True)
    if df is None or len(df) == 0:
        st.markdown('<div class="sg-table-empty">Chưa có dữ liệu.</div>', unsafe_allow_html=True)
        return

    head = "".join(f"<th>{esc(c)}</th>" for c in df.columns)
    rows = []
    for rec in df.itertuples(index=False):
        cells = []
        for col, val in zip(df.columns, rec):
            v = esc(val)
            if col in id_cols:
                cells.append(f'<td class="sg-id">#{v}</td>')
            elif col in status_cols:
                cells.append(f'<td><span class="sg-pill {_status_tone(val)}">{v}</span></td>')
            elif col in iot_cols:
                if "chưa" in str(val).lower() or not str(val).strip():
                    cells.append('<td class="sg-muted">—</td>')
                else:
                    cells.append(f'<td><span class="sg-pill {_status_tone(val)}">{v}</span></td>')
            elif col in muted_cols:
                cells.append(f'<td class="sg-muted">{v}</td>')
            else:
                cells.append(f'<td class="sg-ellipsis" title="{v}">{v}</td>')
        rows.append("<tr>" + "".join(cells) + "</tr>")

    st.markdown(
        f'<div class="sg-table-wrap" style="max-height:{int(max_height)}px">'
        f'<table class="sg-table"><thead><tr>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>',
        unsafe_allow_html=True,
    )