# -*- coding: utf-8 -*-
"""
ui_pages/documents.py — Trang Tài liệu an toàn lao động (Safety Knowledge Base V2).
Đã áp dụng đề xuất Nhóm 1:
- Giữ ô tìm kiếm (tô vàng từ khóa khớp với Bước 5 Kịch bản Demo) và 6 nút lọc chủ đề có ích (căn giữa chữ hoàn hảo).
- Bỏ huy hiệu trang trí "5 TÀI LIỆU" và bỏ cột Mục lục trùng lặp bên phải để danh sách văn bản rộng thoáng.
"""
import html as _html
import re
import streamlit as st
from chatbot import TEN_VAN_BAN_DEP, chuan_hoa, doc_file_docx
from core_logic import DOCS_DIR, clean_html

DOC_METADATA = {
    "Quy_dinh_trang_thiet_bi_bao_ho.txt": {
        "order": 1,
        "code": "01 / 05",
        "category": "ppe",
        "sub": "Mũ bảo hộ, áo phản quang, khẩu trang, găng tay",
    },
    "Quy_dinh_vung_nguy_hiem_DangerZone.txt": {
        "order": 2,
        "code": "02 / 05",
        "category": "danger",
        "sub": "Máy móc, khu vực hạn chế, quy trình dừng khẩn cấp",
    },
    "Quyen_va_nghia_vu_nguoi_lao_dong.txt": {
        "order": 3,
        "code": "03 / 05",
        "category": "roles",
        "sub": "Trách nhiệm của người lao động và báo cáo thiết bị hư hỏng",
    },
    "Xu_ly_vi_pham_qua_camera_AI.txt": {
        "order": 4,
        "code": "04 / 05",
        "category": "camera",
        "sub": "Phát hiện, giám sát viên xác nhận, nhắc loa và kỷ luật",
    },
    "An_toan_han_cat_va_lam_viec_tren_cao.txt": {
        "order": 5,
        "code": "05 / 05",
        "category": "height",
        "sub": "Tia lửa hàn, dây đai an toàn trên giàn giáo, trang bị chống cháy",
    },
}

TOPIC_FILTERS = [
    ("all", "Tất cả"),
    ("ppe", "Trang bị bảo hộ"),
    ("danger", "Vùng nguy hiểm"),
    ("roles", "Trách nhiệm"),
    ("camera", "Camera AI"),
    ("height", "Hàn cắt & làm việc trên cao"),
]

_DOCS_RAM_CACHE: list[dict] | None = None


def _set_doc_topic(topic_key: str):
    st.session_state.doc_topic_filter = topic_key


def _highlight_text_html(text: str, raw_query: str) -> str:
    """Làm nổi bật (highlight) từ khóa tìm kiếm trong nội dung văn bản để quét mắt nhanh."""
    escaped = _html.escape(text)
    q = raw_query.strip()
    if not q:
        return f'<div class="sg-doc-body-text">{escaped}</div>'
    try:
        pattern = re.compile(re.escape(_html.escape(q)), flags=re.IGNORECASE)
        highlighted = pattern.sub(lambda m: f'<mark class="sg-doc-mark">{m.group(0)}</mark>', escaped)
        return f'<div class="sg-doc-body-text">{highlighted}</div>'
    except Exception:
        return f'<div class="sg-doc-body-text">{escaped}</div>'


def _get_cached_docs() -> list[dict]:
    """Đọc và chuẩn hóa 5 tệp văn bản nội quy đúng 1 lần duy nhất vào RAM."""
    global _DOCS_RAM_CACHE
    if _DOCS_RAM_CACHE is not None:
        return _DOCS_RAM_CACHE

    if not DOCS_DIR.is_dir():
        return []

    all_files = sorted(
        [
            p for p in DOCS_DIR.iterdir()
            if p.is_file() and not p.name.startswith("~$") and p.suffix.lower() in (".txt", ".docx")
        ],
        key=lambda p: DOC_METADATA.get(p.name, {}).get("order", 99),
    )

    items = []
    for doc_path in all_files:
        meta = DOC_METADATA.get(
            doc_path.name,
            {"order": 99, "code": f"{len(all_files):02d}", "category": "all", "sub": doc_path.name},
        )
        tieu_de_dep = TEN_VAN_BAN_DEP.get(doc_path.name, doc_path.stem.replace("_", " "))
        try:
            if doc_path.suffix.lower() == ".docx":
                content_text = doc_file_docx(str(doc_path)).strip()
            else:
                content_text = doc_path.read_text(encoding="utf-8").strip()
        except Exception as exc:
            content_text = f"[Không đọc được tệp {doc_path.name}: {exc}]"

        items.append({
            "name": doc_path.name,
            "title": tieu_de_dep,
            "code": meta["code"],
            "category": meta["category"],
            "sub": meta["sub"],
            "content": content_text,
            "haystack": chuan_hoa(f"{tieu_de_dep} {meta['sub']} {content_text}"),
        })

    _DOCS_RAM_CACHE = items
    return items


def render_documents_page():
    """Hiển thị nguyên văn các tệp văn bản quy định từ bộ nhớ đệm RAM trên 1 cột rộng thoáng đãng."""
    docs_list = _get_cached_docs()
    if not docs_list:
        st.warning("Chưa có tài liệu nội quy nào.")
        return

    # --- THANH TÌM KIẾM TÀI LIỆU (.doc-toolbar) ---
    with st.container(key="doc_toolbar_row"):
        search_q = st.text_input(
            "Tìm quy định, từ khóa hoặc chủ đề:",
            value=st.session_state.get("doc_search_query", ""),
            placeholder="Tìm quy định, từ khóa hoặc chủ đề…",
            label_visibility="collapsed",
            key="doc_search_input",
        )
        st.session_state.doc_search_query = search_q

    # --- BỘ LỌC CHỦ ĐỀ (.doc-topic-filters) ---
    cur_topic = st.session_state.get("doc_topic_filter", "all")
    with st.container(key="doc_topic_row"):
        f_cols = st.columns([0.8, 1.15, 1.15, 1.0, 0.95, 1.65], gap="small")
        for idx, (topic_key, topic_label) in enumerate(TOPIC_FILTERS):
            with f_cols[idx]:
                st.button(
                    topic_label,
                    key=f"doc_topic_btn_{topic_key}",
                    type="primary" if cur_topic == topic_key else "secondary",
                    width="stretch",
                    on_click=_set_doc_topic,
                    args=(topic_key,),
                )

    norm_query = chuan_hoa(search_q) if search_q.strip() else ""
    matched_docs = [
        doc for doc in docs_list
        if (cur_topic == "all" or doc["category"] == cur_topic)
        and (not norm_query or norm_query in doc["haystack"])
    ]

    if matched_docs:
        for idx, doc in enumerate(matched_docs):
            is_open = True if (norm_query or cur_topic != "all" or idx == 0) else False
            with st.expander(f"{doc['title']}   ·   {doc['code']}", expanded=is_open):
                st.markdown(
                    clean_html(_highlight_text_html(doc["content"], search_q)),
                    unsafe_allow_html=True,
                )
    else:
        st.info("Không có văn bản nội quy nào khớp với từ khóa hoặc chủ đề đang lọc.")