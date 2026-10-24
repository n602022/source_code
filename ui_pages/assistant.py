# -*- coding: utf-8 -*-
"""
ui_pages/assistant.py — Trang Trợ lý AI giám sát (AI Assistant V2).
Đã nâng cấp theo 8 nguyên tắc thiết kế UI/UX (đặc biệt là Recognition over Recall & Context):
1. Bố cục 2 cột cân đối (`col_chat, col_context = st.columns([2.32, 1.02])`) có chiều cao bằng nhau tuyệt đối:
   - Cột trái (`panel_assistant`): Khung Chat chuẩn Prototype V2 gồm Header giới thiệu, luồng tin nhắn ở giữa,
     4 nút câu hỏi gợi ý dạng viên thuốc (pill buttons) và thanh nhập câu hỏi hợp nhất ở đáy.
   - Cột phải (`panel_assistant_context`): Thẻ **Ngữ cảnh sự kiện & Ca trực** trực quan hóa ngay ảnh bằng chứng,
     mã công nhân, vị trí camera, độ tin cậy AI của sự kiện đang tham chiếu, kèm hộp chọn chuyển nhanh sang
     bất kỳ sự kiện nào khác và 4 ô thống kê ca trực có khoảng đệm đáy thoáng đãng, cân bằng chiều cao với khung Chat.
"""
import datetime
import html as _html
import streamlit as st
from chatbot import ask_chatbot
from core_logic import clean_html, render_evidence_img_or_placeholder


def _select_chat_context_event():
    chosen_id = st.session_state.get("chat_ctx_ev_picker")
    if chosen_id is not None:
        st.session_state.selected_review_event_id = int(chosen_id)


def _goto_review_from_chat(event_id: int, status_val: str):
    st.session_state.selected_review_event_id = int(event_id)
    st.session_state.rev_locate_selected = True
    st.session_state.review_tab_filter = status_val
    st.session_state.active_page = "review"


def _goto_docs_from_chat(topic_key: str = "all"):
    st.session_state.doc_topic_filter = topic_key
    st.session_state.active_page = "docs"


def render_assistant_page(raw_events: list, enriched_events: list):
    """Hiển thị trang Trợ lý AI giám sát với khung Chat bên trái và Bảng ngữ cảnh sự kiện bên phải."""
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
        f" · Đang tham chiếu sự kiện Mã #{active_enriched_ev['event_id']} ({active_enriched_ev['title_tv']})"
        if active_enriched_ev
        else ""
    )

    with st.container(key="assistant_workspace_row"):
        col_chat, col_context = st.columns([2.32, 1.02], gap="medium")

        # ==========================================================================
        # CỘT PHẢI: THẺ NGỮ CẢNH SỰ KIỆN ĐANG THAM CHIẾU & THỐNG KÊ NHANH CA TRỰC
        # ==========================================================================
        with col_context:
            with st.container(key="panel_assistant_context"):
                st.markdown(
                    clean_html(
                        """
                        <div>
                            <div class="sg-panel-title">Ngữ cảnh sự kiện đang chọn</div>
                            <div class="sg-panel-sub" style="margin-bottom:4px;">Trợ lý AI tự động phân tích sự kiện này khi bạn đặt câu hỏi</div>
                        </div>
                        """
                    ),
                    unsafe_allow_html=True,
                )

                if enriched_events:
                    ev_id_options = [int(e["event_id"]) for e in enriched_events[:30]]
                    cur_ctx_id = int(active_enriched_ev["event_id"]) if active_enriched_ev else ev_id_options[0]
                    if cur_ctx_id not in ev_id_options:
                        ev_id_options.insert(0, cur_ctx_id)
                    ev_label_map = {
                        int(e["event_id"]): f"#{e['event_id']} · {e['title_tv']} ({e['status_badge_tv']})"
                        for e in enriched_events
                    }
                    st.selectbox(
                        "Đổi sự kiện tham chiếu",
                        options=ev_id_options,
                        index=ev_id_options.index(cur_ctx_id),
                        format_func=lambda eid: ev_label_map.get(eid, f"Sự kiện #{eid}"),
                        label_visibility="collapsed",
                        key="chat_ctx_ev_picker",
                        on_change=_select_chat_context_event,
                    )

                if active_enriched_ev is not None:
                    eid = int(active_enriched_ev["event_id"])
                    media_html = render_evidence_img_or_placeholder(active_enriched_ev.get("img_path"), eid, height_px=130)
                    st.markdown(
                        clean_html(
                            f"""
                            <div class="sg-incident-card" style="margin-top:2px;margin-bottom:4px;">
                                {media_html}
                                <div class="sg-incident-body">
                                    <div class="sg-incident-badges">
                                        <span class="sg-badge {active_enriched_ev['severity']}">{active_enriched_ev['severity_label']}</span>
                                        <span class="sg-badge {active_enriched_ev['status']}" style="margin-left:auto;">{active_enriched_ev['status_badge_tv']}</span>
                                    </div>
                                    <div class="sg-incident-title">#{eid} · {active_enriched_ev['title_tv']}</div>
                                    <div class="sg-incident-meta">{active_enriched_ev['camera']} · {active_enriched_ev['worker_id']}</div>
                                    <div class="sg-incident-meta">{active_enriched_ev['timestamp_vn']} · Tin cậy AI: {active_enriched_ev['confidence_pct']}</div>
                                </div>
                            </div>
                            """
                        ),
                        unsafe_allow_html=True,
                    )

                    ctx_b1, ctx_b2 = st.columns(2, gap="small")
                    with ctx_b1:
                        st.button(
                            f"Thẩm định #{eid}",
                            key=f"chat_goto_rev_{eid}",
                            type="primary",
                            width="stretch",
                            on_click=_goto_review_from_chat,
                            args=(eid, active_enriched_ev["status"]),
                        )
                    with ctx_b2:
                        st.button(
                            "Mở Nội quy PPE",
                            key="chat_goto_docs_ppe",
                            width="stretch",
                            on_click=_goto_docs_from_chat,
                            args=("ppe",),
                        )
                else:
                    st.info("Chưa có sự kiện nào trong ca trực.")

                # Tóm tắt nhanh số liệu ca trực ngay bên dưới để người dùng không cần nhớ số liệu
                tot_cnt = len(enriched_events)
                pend_cnt = sum(1 for e in enriched_events if e.get("status") == "pending")
                conf_cnt = sum(1 for e in enriched_events if e.get("status") == "confirmed")
                rej_cnt = sum(1 for e in enriched_events if e.get("status") == "false_positive")

                st.markdown(
                    clean_html(
                        f"""
                        <div class="sg-chat-ctx-summary">
                            <div class="sg-chat-ctx-summary-title">Tóm tắt dữ liệu ca trực hiện tại</div>
                            <div class="sg-chat-ctx-grid">
                                <div class="sg-chat-ctx-stat">
                                    <span>Tổng sự kiện</span>
                                    <strong>{tot_cnt:02d}</strong>
                                </div>
                                <div class="sg-chat-ctx-stat warn">
                                    <span>Chờ duyệt</span>
                                    <strong>{pend_cnt:02d}</strong>
                                </div>
                                <div class="sg-chat-ctx-stat ok">
                                    <span>Đã xác nhận</span>
                                    <strong>{conf_cnt:02d}</strong>
                                </div>
                                <div class="sg-chat-ctx-stat">
                                    <span>Đã loại bỏ</span>
                                    <strong>{rej_cnt:02d}</strong>
                                </div>
                            </div>
                        </div>
                        """
                    ),
                    unsafe_allow_html=True,
                )

        # ==========================================================================
        # CỘT TRÁI: KHUNG CHAT TRỢ LÝ AI GIÁM SÁT (.st-key-panel_assistant)
        # ==========================================================================
        with col_chat:
            with st.container(key="panel_assistant"):
                # 1. HEADER KHUNG CHAT (.sg-chat-intro)
                st.markdown(
                    clean_html(
                        f"""
                        <div class="sg-chat-intro">
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