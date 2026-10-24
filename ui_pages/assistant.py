# -*- coding: utf-8 -*-
"""
ui_pages/assistant.py — Trang Trợ lý AI giám sát (AI Assistant V2).
Đã áp dụng đề xuất Nhóm 2 (khớp với bản mẫu Prototype V2 ban đầu và Báo cáo Word Chương 4):
- Đưa khung Chat `panel_assistant` về bố cục 1 cột toàn chiều rộng thoáng đãng (bỏ cột phụ bên phải).
- Tích hợp huy hiệu ngữ cảnh `Đang tham chiếu: Mã #ID · Loại lỗi` kèm nút `Đổi / Xem #ID` gọn ngay trên thanh tiêu đề khung Chat.
"""
import datetime
import html as _html
import streamlit as st
from chatbot import ask_chatbot
from core_logic import clean_html


def _select_chat_context_event():
    chosen_id = st.session_state.get("chat_ctx_ev_picker")
    if chosen_id is not None:
        st.session_state.selected_review_event_id = int(chosen_id)


def _goto_review_from_chat(event_id: int, status_val: str):
    st.session_state.selected_review_event_id = int(event_id)
    st.session_state.rev_locate_selected = True
    st.session_state.review_tab_filter = status_val
    st.session_state.active_page = "review"


def render_assistant_page(raw_events: list, enriched_events: list):
    """Hiển thị trang Trợ lý AI giám sát dạng khung Chat toàn chiều rộng kèm chip ngữ cảnh sự kiện."""
    pending_raw = [e for e in raw_events if e.get("status") == "pending"]
    selected_id = st.session_state.get("selected_review_event_id")

    active_context_ev = None
    if selected_id is not None:
        for ev in raw_events:
            if int(ev["event_id"]) == int(selected_id):
                active_context_ev = ev
                break
    if active_context_ev is None:
        active_context_ev = pending_raw[0] if pending_raw else (raw_events[0] if raw_events else None)
        if active_context_ev is not None:
            st.session_state.selected_review_event_id = int(active_context_ev["event_id"])

    active_enriched_ev = None
    if active_context_ev is not None:
        target_eid = int(active_context_ev["event_id"])
        for e_item in enriched_events:
            if int(e_item["event_id"]) == target_eid:
                active_enriched_ev = e_item
                break

    ctx_note = (
        f" · Đang tham chiếu sự kiện Mã #{active_context_ev['event_id']} ({active_context_ev['violation_type']})"
        if active_context_ev
        else ""
    )
    chip_html = (
        f'<span class="sg-chat-ctx-chip">'
        f'Đang tham chiếu: <b>Mã #{active_enriched_ev["event_id"]}</b> · {_html.escape(active_enriched_ev["title_tv"])}'
        f"</span>"
        if active_enriched_ev
        else ""
    )

    with st.container(key="panel_assistant"):
        # 1. HEADER KHUNG CHAT (.sg-chat-intro) KÈM CHIP NGỮ CẢNH SỰ KIỆN
        st.markdown(
            clean_html(
                f"""
                <div class="sg-chat-intro">
                    <div style="display:flex;align-items:center;gap:12px;min-width:0;">
                        <div class="sg-chat-mark">
                            <svg aria-hidden="true" viewBox="0 0 24 24" width="19" height="19" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                                <path d="M4 5.5A2.5 2.5 0 0 1 6.5 3h11A2.5 2.5 0 0 1 20 5.5v8a2.5 2.5 0 0 1-2.5 2.5h-6l-4.5 4v-4H6.5A2.5 2.5 0 0 1 4 13.5z"></path>
                            </svg>
                        </div>
                        <div class="sg-chat-intro-text">
                            <h2>Trợ lý AI giám sát</h2>
                            <p>Tra cứu quy trình, nội quy và hướng xử lý sự kiện{ctx_note}.</p>
                        </div>
                    </div>
                    {chip_html}
                </div>
                """
            ),
            unsafe_allow_html=True,
        )

        # 2. VÙNG LUỒNG TIN NHẮN Ở GIỮA
        chat_stream_container = st.container(key="chat_stream_area")

        # 3. VÙNG GỢI Ý & THANH NHẬP CÂU HỎI Ở ĐÁY KHUNG CHAT (.st-key-chat_bottom_dock)
        with st.container(key="chat_bottom_dock"):
            if st.session_state.qa_history:
                lbl_col, clr_col = st.columns([4.5, 1.0], gap="small", vertical_alignment="center")
                with lbl_col:
                    st.markdown('<div class="sg-chat-suggest-label">Câu hỏi gợi ý</div>', unsafe_allow_html=True)
                with clr_col:
                    if st.button("Xóa hội thoại", key="clear_qa_hist", width="stretch"):
                        st.session_state.qa_history = []
                        st.rerun()
            else:
                st.markdown('<div class="sg-chat-suggest-label">Câu hỏi gợi ý</div>', unsafe_allow_html=True)

            quick_prompt = None
            with st.container(key="chat_suggest_row"):
                q1, q2, q3, q4 = st.columns([1.15, 1.35, 1.15, 1.05], gap="small")
                with q1:
                    if st.button("Tóm tắt vi phạm trong ca hôm nay", key="qa_btn_1", width="stretch"):
                        quick_prompt = "Báo cáo thống kê tình hình vi phạm trong ca làm việc hiện tại?"
                with q2:
                    if st.button("Ngưỡng tự xác nhận hoạt động thế nào?", key="qa_btn_2", width="stretch"):
                        quick_prompt = "Ý nghĩa 2 thanh trượt độ nhạy phát hiện tối thiểu và ngưỡng tự động xác nhận cấu hình AI là gì?"
                with q3:
                    if st.button("Quy định về áo phản quang là gì?", key="qa_btn_3", width="stretch"):
                        quick_prompt = "Quy định mặc áo phản quang tại công trường và phân xưởng như thế nào?"
                with q4:
                    if st.button("Cần làm gì khi AI báo nhầm?", key="qa_btn_4", width="stretch"):
                        quick_prompt = "Nhân viên bấm nhầm nút duyệt sai thành đúng hoặc đúng thành sai thì sửa lại như thế nào?"

            with st.form("top_chat_form", clear_on_submit=True):
                in_c1, in_c2 = st.columns([5.3, 0.95], gap="small", vertical_alignment="center")
                with in_c1:
                    user_typed_q = st.text_input(
                        "Nhập câu hỏi về an toàn lao động:",
                        placeholder="Nhập câu hỏi về an toàn lao động...",
                        label_visibility="collapsed",
                    )
                with in_c2:
                    send_btn = st.form_submit_button("Gửi câu hỏi", type="primary", width="stretch")

        # Xử lý câu hỏi khi người dùng bấm nút gợi ý hoặc gửi từ thanh chat
        active_prompt = quick_prompt or (user_typed_q.strip() if send_btn and user_typed_q.strip() else None)
        if active_prompt:
            error_msg = None
            with st.spinner("Trợ lý AI đang tra cứu cơ sở tri thức và dữ liệu ca trực..."):
                try:
                    reply_text = ask_chatbot(active_prompt, selected_event=active_context_ev)
                except Exception as exc:
                    error_msg = str(exc)
                    reply_text = "Chưa đủ tài liệu để trả lời."

            if error_msg:
                st.error(f"Đã xảy ra lỗi khi gọi chatbot backend: {error_msg}")

            st.session_state.qa_history.append(
                {
                    "question": active_prompt,
                    "answer": reply_text,
                    "time": datetime.datetime.now().strftime("%H:%M:%S"),
                }
            )

        # Đổ toàn bộ luồng hội thoại vào vùng chat ở giữa (tin nhắn chào mừng + lịch sử hội thoại)
        with chat_stream_container:
            st.markdown(
                clean_html(
                    """
                    <div class="sg-chat-msg-ai">
                        <b>Trợ lý AI</b>
                        <p>
                            Xin chào. Tôi có thể hỗ trợ tra cứu quy định an toàn, giải thích trạng thái duyệt và gợi ý các bước xử lý sự cố. Hãy chọn một chủ đề hoặc nhập câu hỏi của bạn.
                        </p>
                    </div>
                    """
                ),
                unsafe_allow_html=True,
            )

            for idx, item in enumerate(st.session_state.qa_history):
                q_safe = _html.escape(str(item.get("question", "")))
                t_safe = _html.escape(str(item.get("time", "")))
                st.markdown(
                    clean_html(
                        f"""
                        <div class="sg-chat-msg-user">
                            <div class="sg-chat-msg-meta">Giám sát viên · {t_safe}</div>
                            <div class="sg-chat-msg-text">{q_safe}</div>
                        </div>
                        """
                    ),
                    unsafe_allow_html=True,
                )
                with st.container(key=f"subpanel_chat_{idx}"):
                    st.markdown(
                        clean_html(f'<div class="sg-chat-ai-head"><b>Trợ lý AI</b><span>{t_safe}</span></div>'),
                        unsafe_allow_html=True,
                    )
                    st.markdown(item.get("answer", ""))