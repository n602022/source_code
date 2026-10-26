# -*- coding: utf-8 -*-
"""
ui_theme.py — Quản lý giao diện Sáng / Tối / Theo hệ thống và nạp stylesheet tập trung.

TỐI ƯU HÓA TỐC ĐỘ CHUYỂN TRANG & ĐỒNG BỘ GIAO DIỆN TOÀN HỆ THỐNG (PROTOTYPE V2):
- Biên dịch trước (pre-compile) toàn bộ 6 tổ hợp <style> vào bộ nhớ đệm RAM (_STYLE_TAG_CACHE).
- Header hợp nhất 1 hàng (`.st-key-util_bar_row`): Tiêu đề trang `<h1>` bên trái căn thẳng hàng với khối logo Sidebar;
  Huy hiệu trạng thái, nút Chuông thông báo và hồ sơ `Minh An / Giám sát viên` nằm gọn bên phải, tiết kiệm ~90px chiều dọc.
- Thanh Telemetry 1 dòng thông minh (`.sg-telemetry-line`) trên trang Quét AI & Camera: hiển thị gọn số công nhân,
  độ nét và độ lóa, tự động đổi màu cảnh báo vàng khi phát hiện khung hình mờ hoặc chói sáng.
- Chip ngữ cảnh sự kiện (`.sg-chat-ctx-chip`) tích hợp ngay trên thanh tiêu đề khung Chat Trợ lý AI.
- Căn giữa hoàn hảo theo trục dọc cho chữ trong 6 thẻ lọc chủ đề trên trang Tài liệu an toàn (`.st-key-doc_topic_row button`).
"""
import re
from pathlib import Path
from urllib.parse import quote
import streamlit as st

BASE_DIR = Path(__file__).resolve().parent
CSS_PATH = BASE_DIR / "assets" / "style.css"

DARK_VARS_CSS = """
:root, .stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"] {
    --bg: #0B1220 !important;
    --surface: #111C2E !important;
    --surface2: #17243A !important;
    --border: #30445F !important;
    --border-strong: #3E5578 !important;
    --panel-bg: #0F1A2D !important;
    --text: #E8EEF8 !important;
    --muted: #A6B4C8 !important;
    --primary: #7895FF !important;
    --primary-hover: #93A9FF !important;
    --primary-contrast: #0B1220 !important;
    --primary-soft: rgba(120, 149, 255, 0.16) !important;
    --btn-bg: #17243A !important;
    --btn-hover: #1D2D48 !important;
    --btn-border: #34465F !important;
    --toggle-off-bg: #324460 !important;
    --toggle-off-hover: #3E5476 !important;
    --toggle-off-border: #4B6387 !important;
    --chat-bubble-bg: #131F35 !important;
    --chat-input-bg: #131F33 !important;
    --expander-header-bg: #162338 !important;
    --danger: #FF7777 !important;
    --danger-bg: rgba(214, 69, 69, 0.22) !important;
    --danger-text: #FF9B9B !important;
    --warning: #FFC35A !important;
    --warning-bg: rgba(185, 119, 14, 0.24) !important;
    --warning-text: #FFD27D !important;
    --success: #45D6A5 !important;
    --success-bg: rgba(22, 133, 107, 0.24) !important;
    --success-text: #6EE7B7 !important;
    --info: #72B5FF !important;
    --rejected-bg: rgba(95, 108, 128, 0.26) !important;
    --rejected-text: #CBD5E1 !important;
    --shadow: 0 7px 22px rgba(0, 0, 0, 0.12) !important;
    color-scheme: dark !important;
}
"""

LIGHT_VARS_CSS = """
:root, .stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"] {
    --bg: #F4F6FA !important;
    --surface: #FFFFFF !important;
    --surface2: #EDF1F7 !important;
    --border: #DCE3ED !important;
    --border-strong: #CDD6E3 !important;
    --panel-bg: transparent !important;
    --text: #172033 !important;
    --muted: #617086 !important;
    --primary: #3157D5 !important;
    --primary-hover: #2445B5 !important;
    --primary-contrast: #FFFFFF !important;
    --primary-soft: #EEF2FF !important;
    --btn-bg: #FFFFFF !important;
    --btn-hover: #F3F6FD !important;
    --btn-border: #D6DEEA !important;
    --toggle-off-bg: #CBD5E1 !important;
    --toggle-off-hover: #B8C5D6 !important;
    --toggle-off-border: #B4C2D4 !important;
    --chat-bubble-bg: #EEF2F8 !important;
    --chat-input-bg: #EDF1F7 !important;
    --expander-header-bg: #F7F9FC !important;
    --danger: #D64545 !important;
    --danger-bg: #FEE5E5 !important;
    --danger-text: #A62F35 !important;
    --warning: #B9770E !important;
    --warning-bg: #FFF2D3 !important;
    --warning-text: #875500 !important;
    --success: #16856B !important;
    --success-bg: #DDF7EB !important;
    --success-text: #08765E !important;
    --info: #3574C5 !important;
    --rejected-bg: #E9EDF3 !important;
    --rejected-text: #5F6C80 !important;
    --shadow: 0 5px 20px rgba(22, 38, 65, 0.055) !important;
    color-scheme: light !important;
}
"""

SYSTEM_VARS_CSS = (
    LIGHT_VARS_CSS
    + "\n@media (prefers-color-scheme: dark) {\n"
    + DARK_VARS_CSS
    + "\n}\n"
)

_SEC = ':is(button[kind="secondary"], [data-testid="stBaseButton-secondary"], [data-testid="stPopoverButton"])'
_PRI = ':is(button[kind="primary"], [data-testid="stBaseButton-primary"])'
_ROW5 = '[data-testid="stHorizontalBlock"]:has(> :is([data-testid="stColumn"], [data-testid="column"]):nth-child(5))'

FONT_IMPORT = (
    "@import url('https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@400;500;600;700;800"
    "&family=Inter:wght@400;500;600;700;800&display=swap');\n"
)

_NAV_SVG = {
    "dashboard": '<rect x="3.5" y="3.5" width="7" height="7" rx="1.2"/><rect x="13.5" y="3.5" width="7" height="7" rx="1.2"/>'
                 '<rect x="3.5" y="13.5" width="7" height="7" rx="1.2"/><rect x="13.5" y="13.5" width="7" height="7" rx="1.2"/>',
    "scan": '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M10 9l5 3-5 3z"/>',
    "review": '<path d="M5 12.5l4.2 4.2L19 6.8"/>',
    "chat": '<path d="M4 5.5A2.5 2.5 0 0 1 6.5 3h11A2.5 2.5 0 0 1 20 5.5v8a2.5 2.5 0 0 1-2.5 2.5h-6l-4.5 4v-4H6.5A2.5 2.5 0 0 1 4 13.5z"/>',
    "docs": '<path d="M6 3.5h8l4 4V20a.5.5 0 0 1-.5.5h-11A.5.5 0 0 1 6 20z"/><path d="M14 3.5v4h4M9 12h6M9 15.5h6"/>',
}

# Ô vuông bo góc 35x35 chứa mũi tên tải lên ở chính giữa (giống .file-icon trong preview.html)
_UPLOAD_BOX_SVG_URI = "data:image/svg+xml," + quote(
    '<svg xmlns="http://www.w3.org/2000/svg" width="35" height="35" viewBox="0 0 35 35" fill="none">'
    '<rect x="0" y="0" width="35" height="35" rx="9" fill="#7895FF" fill-opacity="0.14"/>'
    '<g transform="translate(8.5, 8.5)" stroke="#7895FF" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M9 12V3m-3 3 3-3 3 3"/>'
    '<path d="M3 11.25v3a.75.75 0 0 0 .75.75h10.5a.75.75 0 0 0 .75-.75v-3"/>'
    '</g></svg>',
    safe="/:=,.- ",
)


def _nav_icon_css() -> str:
    rules = []
    for key, body in _NAV_SVG.items():
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#000" '
            'stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">' + body + "</svg>"
        )
        uri = "data:image/svg+xml," + quote(svg, safe="/:=,.- ")
        rules.append(f'[data-testid="stSidebar"] .st-key-nav_btn_{key} button {{ --sg-ico: url("{uri}"); }}')
    return "\n".join(rules)


OVERRIDE_CSS = """
/* ============ 0. Khung chung + font prototype ============ */
.stApp, .stApp :is(p, div, h1, h2, h3, h4, h5, li, label, button, input, textarea, small, strong, a) {
    font-family: "Be Vietnam Pro", Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
[data-testid="stAppDeployButton"], .stAppDeployButton { display: none !important; }
[data-testid="stHeader"] { background: transparent !important; }
[data-testid="stMainBlockContainer"], .block-container { padding-top: 2.2rem !important; }

/* ============ 1. Nút ở vùng nội dung chính (.pill / .action) ============ */
[data-testid="stMain"] __SEC__ {
    background: var(--btn-bg) !important;
    color: var(--text) !important;
    border: 1px solid var(--btn-border) !important;
    border-radius: 8px !important;
    min-height: 38px !important;
    padding: 6px 14px !important;
    font-size: 13px !important;
    font-weight: 600 !important;
    box-shadow: none !important;
    transition: background .15s ease, border-color .15s ease, color .15s ease;
}
[data-testid="stMain"] __SEC__:hover {
    background: var(--btn-hover) !important;
    border-color: var(--primary) !important;
    color: var(--primary) !important;
}
[data-testid="stMain"] __PRI__ {
    background: var(--primary) !important;
    color: var(--primary-contrast) !important;
    border: 1px solid var(--primary) !important;
    border-radius: 8px !important;
    min-height: 38px !important;
    padding: 6px 14px !important;
    font-size: 13px !important;
    font-weight: 700 !important;
    box-shadow: none !important;
}
[data-testid="stMain"] __PRI__:hover {
    background: var(--primary-hover) !important;
    border-color: var(--primary-hover) !important;
}
[data-testid="stMain"] __SEC__ :is(p, span, div),
[data-testid="stMain"] __PRI__ :is(p, span, div) { color: inherit !important; }

/* Hàng >= 5 nút (thanh bộ lọc) hoặc key range_* / doc_topic_btn_* / rev_tab_* / chip*: nút đang chọn = .pill.active */
[data-testid="stMain"] __ROW5__ __PRI__,
[data-testid="stMain"] :is([class*="st-key-chip"], [class*="st-key-range_"], [class*="st-key-doc_topic_btn_"], [class*="st-key-rev_tab_"]) __PRI__ {
    background: var(--primary-soft) !important;
    color: var(--primary) !important;
    border: 1px solid var(--primary) !important;
    font-weight: 750 !important;
}
[data-testid="stMain"] __ROW5__ __PRI__:hover,
[data-testid="stMain"] :is([class*="st-key-chip"], [class*="st-key-range_"], [class*="st-key-doc_topic_btn_"], [class*="st-key-rev_tab_"]) __PRI__:hover {
    background: var(--primary-soft) !important;
    color: var(--primary-hover) !important;
}

/* Cụm Segmented Pill cho nhóm Thời gian (Dashboard) & nhóm Trạng thái (Duyệt vi phạm) */
[data-testid="stMain"] :is(.st-key-dash_range_group, .st-key-rev_tab_group) {
    background: var(--surface) !important;
    border: 1px solid var(--border-strong) !important;
    border-radius: 10px !important;
    padding: 3px 4px !important;
    box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04) !important;
}
[data-testid="stMain"] :is(.st-key-dash_range_group, .st-key-rev_tab_group) [data-testid="stHorizontalBlock"] {
    gap: 4px !important;
    align-items: center !important;
}
[data-testid="stMain"] :is(.st-key-dash_range_group, .st-key-rev_tab_group) button {
    min-height: 33px !important;
    height: 33px !important;
    border-radius: 7px !important;
    padding: 0 10px !important;
    border: 1px solid transparent !important;
    background: transparent !important;
    font-size: 12px !important;
    font-weight: 600 !important;
    color: var(--muted) !important;
}
[data-testid="stMain"] :is(.st-key-dash_range_group, .st-key-rev_tab_group) button:hover {
    background: var(--surface2) !important;
    color: var(--text) !important;
    border-color: transparent !important;
}
[data-testid="stMain"] :is(.st-key-dash_range_group, .st-key-rev_tab_group) __PRI__,
[data-testid="stMain"] :is(.st-key-dash_range_group, .st-key-rev_tab_group) __PRI__:hover {
    background: var(--primary-soft) !important;
    color: var(--primary) !important;
    border: 1px solid var(--primary) !important;
    font-weight: 750 !important;
}

/* Dải 5 thẻ trạng thái Camera hệ thống trên trang Tổng quan (.st-key-panel_dash_cameras) */
[data-testid="stMain"] .st-key-panel_dash_cameras {
    margin-top: 6px !important;
}
[data-testid="stMain"] [class*="st-key-dash_cam_jump_"] button {
    min-height: 70px !important;
    padding: 8px 10px !important;
    border-radius: 10px !important;
    background: var(--surface2) !important;
    border: 1px solid var(--border) !important;
    text-align: left !important;
    justify-content: flex-start !important;
}
[data-testid="stMain"] [class*="st-key-dash_cam_jump_"] button:hover {
    background: var(--primary-soft) !important;
    border-color: var(--primary) !important;
    transform: translateY(-1px) !important;
}
[data-testid="stMain"] [class*="st-key-dash_cam_jump_"] button > div {
    justify-content: flex-start !important;
    text-align: left !important;
    width: 100% !important;
}
[data-testid="stMain"] [class*="st-key-dash_cam_jump_"] button p {
    font-size: 10.5px !important;
    line-height: 1.42 !important;
    color: var(--muted) !important;
    text-align: left !important;
    margin: 0 !important;
}
[data-testid="stMain"] [class*="st-key-dash_cam_jump_"] button p strong {
    font-size: 12px !important;
    font-weight: 750 !important;
    color: var(--text) !important;
}

/* Liên kết dạng chữ (.text-link) */
[data-testid="stMain"] :is([class*="st-key-viewall"], [class*="st-key-view_all"], [class*="st-key-textlink"], [class*="st-key-dash_top_goto"]) button {
    background: transparent !important;
    border: 0 !important;
    min-height: 0 !important;
    padding: 2px 0 !important;
    color: var(--primary) !important;
    font-size: 12px !important;
    font-weight: 750 !important;
    justify-content: flex-end !important;
}
[data-testid="stMain"] :is([class*="st-key-viewall"], [class*="st-key-view_all"], [class*="st-key-textlink"], [class*="st-key-dash_top_goto"]) button:hover {
    background: transparent !important; text-decoration: underline; color: var(--primary-hover) !important;
}

/* Căn ngang hàng tuyệt đối tiêu đề "Vi phạm gần đây" với nút "Xem tất cả →" trên Dashboard & "Hồ sơ thẩm định" trên Review */
[data-testid="stMain"] :is(.st-key-dash_recent_header, .st-key-rev_detail_head_row) {
    margin-bottom: 6px !important;
}
[data-testid="stMain"] :is(.st-key-dash_recent_header, .st-key-rev_detail_head_row) [data-testid="stHorizontalBlock"] {
    align-items: center !important;
}
[data-testid="stMain"] :is(.st-key-dash_recent_header, .st-key-rev_detail_head_row) [data-testid="stElementContainer"],
[data-testid="stMain"] :is(.st-key-dash_recent_header, .st-key-rev_detail_head_row) [data-testid="stMarkdownContainer"],
[data-testid="stMain"] :is(.st-key-dash_recent_header, .st-key-rev_detail_head_row) .stButton {
    margin: 0 !important;
    padding: 0 !important;
    display: flex !important;
    align-items: center !important;
    min-height: 28px !important;
}
[data-testid="stMain"] :is(.st-key-dash_recent_header, .st-key-rev_detail_head_row) .sg-panel-title {
    margin: 0 !important;
    padding: 0 !important;
    line-height: 1 !important;
    display: inline-flex !important;
    align-items: center !important;
    min-height: 28px !important;
}
[data-testid="stMain"] .st-key-dash_recent_header .st-key-dash_top_goto_review,
[data-testid="stMain"] .st-key-rev_detail_head_row [class*="st-key-textlink_ask_ai_"] {
    width: 100% !important;
    display: flex !important;
    align-items: center !important;
    justify-content: flex-end !important;
}
[data-testid="stMain"] .st-key-dash_recent_header .st-key-dash_top_goto_review button,
[data-testid="stMain"] .st-key-rev_detail_head_row [class*="st-key-textlink_ask_ai_"] button {
    height: 28px !important;
    min-height: 28px !important;
    padding: 0 !important;
    margin: 0 !important;
    display: inline-flex !important;
    align-items: center !important;
    justify-content: flex-end !important;
    line-height: 1 !important;
}
[data-testid="stMain"] .st-key-dash_recent_header .st-key-dash_top_goto_review button > div,
[data-testid="stMain"] .st-key-dash_recent_header .st-key-dash_top_goto_review button [data-testid="stMarkdownContainer"],
[data-testid="stMain"] .st-key-dash_recent_header .st-key-dash_top_goto_review button p,
[data-testid="stMain"] .st-key-rev_detail_head_row [class*="st-key-textlink_ask_ai_"] button > div,
[data-testid="stMain"] .st-key-rev_detail_head_row [class*="st-key-textlink_ask_ai_"] button p {
    display: inline-flex !important;
    align-items: center !important;
    height: 100% !important;
    margin: 0 !important;
    padding: 0 !important;
    line-height: 1 !important;
}

/* Ghim cố định (Sticky) cho khung Hồ sơ thẩm định (Review) */
[data-testid="stMain"] .st-key-panel_review_detail {
    position: sticky !important;
    top: 18px !important;
    z-index: 4 !important;
}

/* Nút tải xuống */
[data-testid="stMain"] [data-testid="stDownloadButton"] button {
    background: var(--btn-bg) !important;
    color: var(--text) !important;
    border: 1px solid var(--btn-border) !important;
    border-radius: 8px !important;
    min-height: 38px !important;
    font-size: 13px !important;
    font-weight: 600 !important;
}
[data-testid="stMain"] [data-testid="stDownloadButton"] button :is(p, span) { color: inherit !important; }

/* ============ 2. Popover, ô nhập liệu (Đổ nền đặc var(--surface) đồng bộ Sáng / Tối) ============ */
[data-testid="stPopoverBody"], div[data-baseweb="popover"] > div {
    background: var(--surface) !important;
    color: var(--text) !important;
    border: 1px solid var(--border) !important;
    border-radius: 12px !important;
    box-shadow: 0 12px 32px rgba(12, 24, 44, .16) !important;
}
[data-testid="stPopoverBody"] :is(p, span, li, small, strong, label) { color: var(--text) !important; }

[data-testid="stMain"] [data-testid="stTextInputRootElement"] {
    background: var(--surface) !important;
    background-color: var(--surface) !important;
    border: 1px solid var(--border-strong) !important;
    border-radius: 10px !important;
    box-shadow: none !important;
    overflow: hidden !important;
}
[data-testid="stMain"] [data-testid="stTextInputRootElement"]:focus-within {
    border-color: var(--primary) !important;
    box-shadow: 0 0 0 1px var(--primary-soft) !important;
}
[data-testid="stMain"] [data-testid="stTextInputRootElement"] [data-baseweb="input"],
[data-testid="stMain"] [data-testid="stTextInputRootElement"] [data-baseweb="base-input"],
[data-testid="stMain"] [data-testid="stTextInputRootElement"] [data-baseweb="input"] > div {
    background: var(--surface) !important;
    background-color: var(--surface) !important;
    border: 0 !important;
    border-color: transparent !important;
    box-shadow: none !important;
    outline: none !important;
}
[data-testid="stMain"] [data-baseweb="select"] > div,
[data-testid="stMain"] [data-baseweb="textarea"] {
    background: var(--surface) !important;
    background-color: var(--surface) !important;
    color: var(--text) !important;
    border: 1px solid var(--border-strong) !important;
    border-radius: 9px !important;
    box-shadow: none !important;
}
[data-testid="stMain"] :is(input, textarea) {
    background: var(--surface) !important;
    background-color: var(--surface) !important;
    color: var(--text) !important;
    -webkit-text-fill-color: var(--text) !important;
    caret-color: var(--primary) !important;
    font-size: 13px !important;
    font-weight: 500 !important;
}
[data-testid="stMain"] :is(input, textarea)::placeholder,
[data-testid="stMain"] :is(input, textarea)::-webkit-input-placeholder {
    color: var(--muted) !important;
    -webkit-text-fill-color: var(--muted) !important;
    opacity: 1 !important;
}

/* ============ 3 & 4. Header hợp nhất 1 hàng (.st-key-util_bar_row): Tiêu đề trái | Trạng thái + Chuông + Minh An phải ============ */
[data-testid="stMain"] .st-key-util_bar_row {
    padding-right: 12px !important;
}
[data-testid="stMain"] .st-key-util_bar_row [data-testid="stHorizontalBlock"] {
    align-items: center !important;
    gap: 10px !important;
}
.sg-unified-title h1 {
    font-size: 24px !important;
    font-weight: 800 !important;
    color: var(--text) !important;
    margin: 0 !important;
    padding: 0 !important;
    line-height: 1.2 !important;
    letter-spacing: -0.01em !important;
}
.sg-unified-status-wrap {
    display: flex !important;
    align-items: center !important;
    justify-content: flex-end !important;
    width: 100% !important;
}
[data-testid="stMain"] .st-key-util_bell,
[data-testid="stMain"] .st-key-util_bell [data-testid="stPopover"],
[data-testid="stMain"] .st-key-util_bell [data-testid="stPopover"] > div {
    display: flex !important;
    justify-content: flex-end !important;
    width: auto !important;
    margin-left: auto !important;
}
[data-testid="stMain"] .st-key-util_user,
[data-testid="stMain"] .st-key-util_user [data-testid="stPopover"],
[data-testid="stMain"] .st-key-util_user [data-testid="stPopover"] > div {
    display: flex !important;
    justify-content: flex-end !important;
    width: auto !important;
    margin-left: auto !important;
}
[data-testid="stMain"] .st-key-util_bell button,
[data-testid="stMain"] .st-key-util_user button {
    position: relative !important;
    background: var(--surface) !important;
    border: 1px solid var(--border) !important;
    box-shadow: none !important;
    color: var(--text) !important;
}
[data-testid="stMain"] .st-key-util_bell button:hover,
[data-testid="stMain"] .st-key-util_user button:hover {
    border-color: var(--primary) !important; background: var(--surface2) !important; color: var(--text) !important;
}
[data-testid="stMain"] .st-key-util_bell button {
    width: 40px !important; min-width: 40px !important; height: 40px !important; min-height: 40px !important;
    border-radius: 50% !important; padding: 0 !important; margin-left: auto !important;
    display: flex !important; justify-content: center !important; align-items: center !important;
}
[data-testid="stMain"] .st-key-util_bell button p { display: none !important; }
[data-testid="stMain"] .st-key-util_bell button > div { justify-content: center !important; width: auto !important; }
[data-testid="stMain"] .st-key-util_bell button > div > :nth-child(n+2) { display: none !important; }
[data-testid="stMain"] .st-key-util_bell button [data-testid="stIconMaterial"] { font-size: 20px !important; margin: 0 !important; }

/* Khung "Minh An / Giám sát viên": khoảng cách giữa avatar MA (left 6px + 30px = 36px) và chữ là 20px */
[data-testid="stMain"] .st-key-util_user button {
    width: 184px !important;
    min-width: 180px !important;
    max-width: 190px !important;
    height: 42px !important;
    min-height: 42px !important;
    border-radius: 999px !important;
    padding: 0 14px 0 56px !important;
    text-align: left !important;
    justify-content: space-between !important;
    margin-left: auto !important;
}
[data-testid="stMain"] .st-key-util_user button > div {
    width: 100% !important;
    display: flex !important;
    align-items: center !important;
    justify-content: space-between !important;
    gap: 10px !important;
    text-align: left !important;
}
[data-testid="stMain"] .st-key-util_user button > div > :first-child {
    flex: 1 1 auto !important;
    text-align: left !important;
}
[data-testid="stMain"] .st-key-util_user button::before {
    content: "MA"; position: absolute; left: 6px; top: 50%; transform: translateY(-50%);
    width: 30px; height: 30px; border-radius: 50%;
    background: #E7EDF8; color: #233F7B; border: 1px solid #D4DEEF;
    display: flex; align-items: center; justify-content: center;
    font-size: 10.5px; font-weight: 800;
}
[data-testid="stMain"] .st-key-util_user button p {
    line-height: 1.24 !important; font-size: 10.5px !important; text-align: left !important;
    color: var(--muted) !important; margin: 0 !important; white-space: nowrap !important;
}
[data-testid="stMain"] .st-key-util_user button p strong { font-size: 12px !important; color: var(--text) !important; }

/* ============ 5. Sidebar (.sidebar / .nav / .theme-select) ============ */
[data-testid="stSidebar"] { background: #111D30 !important; }
[data-testid="stSidebar"] [data-testid="stVerticalBlock"] { gap: 0.4rem !important; }

[data-testid="stSidebar"] [class*="st-key-nav_btn_"] button {
    display: flex !important;
    justify-content: flex-start !important;
    align-items: center !important;
    gap: 11px !important;
    min-height: 42px !important;
    padding: 0 12px !important;
    border-radius: 9px !important;
    background: transparent !important;
    border: 0 !important;
    box-shadow: none !important;
    color: #C2CEE0 !important;
    font-size: 13px !important;
    font-weight: 600 !important;
}
[data-testid="stSidebar"] [class*="st-key-nav_btn_"] button > div {
    justify-content: flex-start !important; flex: 1 1 auto; width: auto !important; text-align: left !important;
}
[data-testid="stSidebar"] [class*="st-key-nav_btn_"] button :is(p, span) {
    color: inherit !important; text-align: left !important; margin: 0 !important; font-size: inherit !important;
}
[data-testid="stSidebar"] [class*="st-key-nav_btn_"] button [data-testid="stIconMaterial"] {
    font-size: 19px !important; color: #9CB0CE !important;
}
[data-testid="stSidebar"] [class*="st-key-nav_btn_"] button:hover {
    background: #1A2A42 !important; color: #FFFFFF !important;
}
[data-testid="stSidebar"] [class*="st-key-nav_btn_"] __PRI__,
[data-testid="stSidebar"] [class*="st-key-nav_btn_"] __PRI__:hover {
    background: #183966 !important;
    box-shadow: inset 3px 0 #7895FF !important;
    color: #FFFFFF !important;
}
[data-testid="stSidebar"] [class*="st-key-nav_btn_"] __PRI__ [data-testid="stIconMaterial"] { color: #A9BBFF !important; }

[data-testid="stSidebar"] .st-key-theme_switch {
    background: #1B2B43;
    border: 1px solid #31435E;
    border-radius: 10px;
    padding: 4px;
}
[data-testid="stSidebar"] .st-key-theme_switch [data-testid="stHorizontalBlock"] { gap: 3px !important; }
[data-testid="stSidebar"] .st-key-theme_switch button {
    min-height: 36px !important;
    height: auto !important;
    padding: 6px 3px !important;
    border-radius: 7px !important;
    background: transparent !important;
    border: 0 !important;
    box-shadow: none !important;
    color: #B8C7DB !important;
}
[data-testid="stSidebar"] .st-key-theme_switch button,
[data-testid="stSidebar"] .st-key-theme_switch button > div,
[data-testid="stSidebar"] .st-key-theme_switch button [data-testid="stMarkdownContainer"],
[data-testid="stSidebar"] .st-key-theme_switch button p {
    overflow: visible !important; text-overflow: clip !important;
    white-space: normal !important; word-break: normal !important; overflow-wrap: normal !important;
}
[data-testid="stSidebar"] .st-key-theme_switch button p {
    font-size: 11px !important; line-height: 1.2 !important; margin: 0 !important;
    color: inherit !important; text-align: center !important;
}
[data-testid="stSidebar"] .st-key-theme_switch __PRI__,
[data-testid="stSidebar"] .st-key-theme_switch __PRI__:hover {
    background: #7895FF !important; color: #0B1220 !important; font-weight: 800 !important;
}
[data-testid="stSidebar"] .st-key-theme_switch __PRI__ p { font-weight: 800 !important; }

/* ============ 6. Căn chỉnh & khoảng cách + Thẻ video sự kiện & Nút tải xuống trên thẻ ============ */
[data-testid="stSidebar"] .sg-side-label { margin: 6px 9px 10px !important; }
[data-testid="stSidebar"] .st-key-theme_switch button {
    height: 46px !important; min-height: 46px !important;
    display: flex !important; align-items: center !important; justify-content: center !important;
}
[data-testid="stSidebar"] .st-key-theme_switch button > div { justify-content: center !important; width: 100% !important; }

[data-testid="stMain"] __SEC__, [data-testid="stMain"] __PRI__,
[data-testid="stMain"] [data-testid="stDownloadButton"] button,
[data-testid="stMain"] __SEC__ p, [data-testid="stMain"] __PRI__ p,
[data-testid="stMain"] [data-testid="stDownloadButton"] button p {
    overflow: visible !important; text-overflow: clip !important;
    white-space: normal !important; line-height: 1.2 !important;
}
[data-testid="stMain"] __SEC__, [data-testid="stMain"] __PRI__,
[data-testid="stMain"] [data-testid="stDownloadButton"] button { padding: 6px 10px !important; }

/* Thẻ video sự kiện (.sg-incident-card) trên cả Dashboard và Duyệt vi phạm */
.sg-incident-card {
    display: flex !important;
    flex-direction: column !important;
    margin-bottom: 6px !important;
}
.sg-incident-body {
    padding: 10px 11px !important;
    display: flex !important;
    flex-direction: column !important;
    gap: 2px !important;
}
.sg-incident-badges {
    display: flex !important;
    align-items: center !important;
    gap: 6px !important;
    min-height: 20px !important;
    margin-bottom: 3px !important;
}
.sg-incident-title {
    font-size: 11.5px !important;
    font-weight: 750 !important;
    line-height: 1.35 !important;
    color: var(--text) !important;
    margin: 2px 0 3px !important;
    white-space: nowrap !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
}
.sg-incident-meta {
    font-size: 10.5px !important;
    line-height: 1.42 !important;
    color: var(--muted) !important;
    margin: 1px 0 0 !important;
    white-space: nowrap !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
}
.sg-incident-foot {
    display: flex !important;
    align-items: center !important;
    justify-content: space-between !important;
    gap: 8px !important;
    margin-top: 1px !important;
}
.sg-incident-meta-group {
    min-width: 0 !important;
    flex: 1 1 auto !important;
}
/* Nút tải xuống bằng chứng (.sg-card-dl-btn) ở góc dưới bên phải mỗi thẻ sự kiện */
a.sg-card-dl-btn,
span.sg-card-dl-btn {
    width: 31px !important;
    height: 31px !important;
    min-width: 31px !important;
    border-radius: 8px !important;
    border: 1px solid var(--border-strong) !important;
    background: var(--surface2) !important;
    color: var(--primary) !important;
    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;
    text-decoration: none !important;
    flex-shrink: 0 !important;
    transition: background .15s ease, border-color .15s ease, color .15s ease, transform .12s ease !important;
}
a.sg-card-dl-btn:hover {
    background: var(--primary) !important;
    border-color: var(--primary) !important;
    color: var(--primary-contrast) !important;
    transform: translateY(-1px) !important;
}
span.sg-card-dl-btn.disabled {
    opacity: 0.38 !important;
    color: var(--muted) !important;
    cursor: not-allowed !important;
}

.sg-bar-row { grid-template-columns: minmax(0, 1.5fr) 28px minmax(56px, 1fr) !important; align-items: center !important; font-size: 12px !important; }
.sg-bar-row > :first-child { line-height: 1.3 !important; }
.sg-score-list { gap: 10px 14px !important; }
.sg-score-item { font-size: 11.5px !important; line-height: 1.3 !important; }

[data-testid="stMain"] [data-testid="stWidgetLabel"] p { font-size: 13px !important; font-weight: 600 !important; color: var(--text) !important; }
[data-testid="stMain"] [data-testid="stRadio"] label p,
[data-testid="stMain"] [data-testid="stCheckbox"] label p { font-size: 13px !important; line-height: 1.35 !important; }
[data-testid="stMain"] [data-testid="stCaptionContainer"] { font-size: 12px !important; line-height: 1.55 !important; }
[data-testid="stMain"] :is([data-testid="stSliderTickBarMin"], [data-testid="stSliderTickBarMax"], [data-testid="stTickBarMin"], [data-testid="stTickBarMax"]) { color: var(--muted) !important; }
[data-testid="stMain"] [data-testid="stSliderThumbValue"] { font-size: 12px !important; font-weight: 700 !important; }
[data-testid="stMain"] hr { margin: 14px 0 !important; border-color: var(--border) !important; }
[data-testid="stMain"] h4 { font-size: 15px !important; font-weight: 780 !important; padding: 0 !important; margin: 0 0 4px !important; }

/* ============ 7. Trang Quét AI: Bố cục 2 cột cân bằng + Thanh Telemetry 1 dòng (.sg-telemetry-line) ============ */
[data-testid="stMain"] :is(.st-key-panel_scan_sources, .st-key-panel_scan_center, .st-key-panel_scan_controls) {
    padding: 15px 16px !important;
    height: auto !important;
    min-height: 0 !important;
}
[data-testid="stMain"] :is(.st-key-panel_scan_sources, .st-key-panel_scan_center, .st-key-panel_scan_controls) [data-testid="stVerticalBlock"] {
    gap: 8px !important;
}
[data-testid="stMain"] :is(.st-key-panel_scan_sources, .st-key-panel_scan_center, .st-key-panel_scan_controls) [data-testid="stMarkdownContainer"] {
    margin-bottom: 0 !important;
}

/* Hàng tiêu đề + thanh chuyển nguồn nằm cùng 1 dòng trong khung Nguồn camera */
[data-testid="stMain"] .st-key-scan_sources_top_bar [data-testid="stHorizontalBlock"] {
    align-items: center !important;
}

/* Thanh chuyển nguồn (.source-switch): Hệ thống | Tải tệp */
[data-testid="stMain"] .st-key-source_switch {
    background: var(--surface2) !important;
    border: 1px solid var(--border) !important;
    border-radius: 9px !important;
    padding: 3px !important;
    margin: 0 !important;
}
[data-testid="stMain"] .st-key-source_switch [data-testid="stHorizontalBlock"] {
    gap: 4px !important;
    align-items: center !important;
}
[data-testid="stMain"] .st-key-source_switch [data-testid="stColumn"] {
    min-width: 0 !important;
}
[data-testid="stMain"] .st-key-source_switch button {
    height: 32px !important;
    min-height: 32px !important;
    max-height: 32px !important;
    width: 100% !important;
    padding: 0 8px !important;
    margin: 0 !important;
    border-radius: 7px !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    background: transparent !important;
    border: 1px solid transparent !important;
    color: var(--muted) !important;
    font-size: 12px !important;
    font-weight: 600 !important;
    line-height: 1 !important;
    box-shadow: none !important;
}
[data-testid="stMain"] .st-key-source_switch button > div,
[data-testid="stMain"] .st-key-source_switch button [data-testid="stMarkdownContainer"] {
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    width: 100% !important;
    height: 100% !important;
    margin: 0 !important;
    padding: 0 !important;
    line-height: 1 !important;
}
[data-testid="stMain"] .st-key-source_switch button p {
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    font-size: 12px !important;
    line-height: 1 !important;
    margin: 0 !important;
    padding: 0 !important;
    white-space: nowrap !important;
    transform: translateY(-1px) !important;
}
[data-testid="stMain"] .st-key-source_switch button:hover {
    background: transparent !important;
    color: var(--text) !important;
    border-color: transparent !important;
}
[data-testid="stMain"] .st-key-source_switch __PRI__,
[data-testid="stMain"] .st-key-source_switch __PRI__:hover {
    background: var(--surface) !important;
    color: var(--primary) !important;
    border: 1px solid var(--border) !important;
    box-shadow: 0 1px 2px rgba(15, 23, 42, .08) !important;
    font-weight: 700 !important;
}
[data-testid="stMain"] .st-key-source_switch __PRI__ p {
    color: var(--primary) !important;
    font-weight: 700 !important;
}

/* Dải 5 thẻ camera nằm ngang (.st-key-camopt_*): ảnh thumbnail phía trên + tên & trạng thái phía dưới */
[data-testid="stMain"] [class*="st-key-camopt_"] button {
    display: flex !important;
    flex-direction: column !important;
    align-items: stretch !important;
    justify-content: flex-start !important;
    gap: 7px !important;
    width: 100% !important;
    min-height: 122px !important;
    padding: 7px !important;
    margin: 0 !important;
    border-radius: 10px !important;
    text-align: left !important;
    background: var(--surface2) !important;
    color: var(--text) !important;
    border: 1px solid var(--border) !important;
    box-shadow: none !important;
}
[data-testid="stMain"] [class*="st-key-camopt_"] button::before {
    content: "";
    width: 100%;
    height: 60px;
    border-radius: 7px;
    background-color: var(--surface);
    background-size: cover;
    background-position: center;
    background-repeat: no-repeat;
    border: 1px solid var(--border);
}
[data-testid="stMain"] [class*="st-key-camopt_"] button:hover {
    background: var(--surface) !important;
    border-color: var(--primary) !important;
    color: var(--text) !important;
}
[data-testid="stMain"] [class*="st-key-camopt_"] __PRI__,
[data-testid="stMain"] [class*="st-key-camopt_"] __PRI__:hover {
    background: var(--primary-soft) !important;
    border: 1.5px solid var(--primary) !important;
    color: var(--text) !important;
    box-shadow: 0 0 0 1px var(--primary-soft) !important;
}
[data-testid="stMain"] [class*="st-key-camopt_"] button > div {
    justify-content: flex-start !important;
    text-align: left !important;
    width: 100% !important;
    padding: 0 2px !important;
}
[data-testid="stMain"] [class*="st-key-camopt_"] button p {
    font-size: 10.5px !important;
    line-height: 1.38 !important;
    text-align: left !important;
    margin: 0 !important;
    color: var(--muted) !important;
    font-weight: 500 !important;
}
[data-testid="stMain"] [class*="st-key-camopt_"] button p strong {
    font-size: 11.5px !important;
    color: var(--text) !important;
    font-weight: 750 !important;
}
[data-testid="stMain"] [class*="st-key-camopt_"] button span[style*="color"] {
    color: var(--success) !important;
}

/* Khung Tải tệp nằm ngang (.file-drop + thẻ trạng thái bên phải) */
[data-testid="stMain"] .st-key-panel_scan_sources [data-testid="stFileUploader"] {
    margin: 0 !important;
    padding: 0 !important;
}
[data-testid="stMain"] .st-key-panel_scan_sources [data-testid="stFileUploader"] [data-testid="stWidgetLabel"] {
    display: none !important;
}
[data-testid="stMain"] .st-key-panel_scan_sources [data-testid="stFileUploaderDropzone"] {
    position: relative !important;
    display: flex !important;
    flex-direction: column !important;
    align-items: center !important;
    justify-content: center !important;
    text-align: center !important;
    padding: 15px 14px 14px !important;
    border: 1px dashed var(--border-strong) !important;
    border-radius: 10px !important;
    background: var(--surface2) !important;
    min-height: 118px !important;
    cursor: pointer !important;
    transition: border-color .15s ease, background .15s ease;
}
[data-testid="stMain"] .st-key-panel_scan_sources [data-testid="stFileUploaderDropzone"]:hover {
    border-color: var(--primary) !important;
    background: var(--primary-soft) !important;
}
[data-testid="stMain"] .st-key-panel_scan_sources [data-testid="stFileUploaderDropzone"]::before {
    content: "Chọn video hoặc ảnh từ máy tính" !important;
    display: block !important;
    padding-top: 40px !important;
    background-image: url("__UPLOAD_BOX_SVG__") !important;
    background-repeat: no-repeat !important;
    background-position: top center !important;
    background-size: 33px 33px !important;
    font-size: 12px !important;
    font-weight: 700 !important;
    color: var(--text) !important;
    line-height: 1.35 !important;
    text-align: center !important;
    pointer-events: none !important;
}
[data-testid="stMain"] .st-key-panel_scan_sources [data-testid="stFileUploaderDropzone"]::after {
    content: "Hỗ trợ MP4, MOV, AVI, JPG, PNG, WEBP" !important;
    display: block !important;
    margin-top: 3px !important;
    font-size: 10.5px !important;
    font-weight: 500 !important;
    color: var(--muted) !important;
    line-height: 1.4 !important;
    text-align: center !important;
    pointer-events: none !important;
}
[data-testid="stMain"] .st-key-panel_scan_sources [data-testid="stFileUploaderDropzone"] [data-testid="stFileUploaderDropzoneInstructions"],
[data-testid="stMain"] .st-key-panel_scan_sources [data-testid="stFileUploaderDropzone"] small {
    display: none !important;
}
[data-testid="stMain"] .st-key-panel_scan_sources [data-testid="stFileUploaderDropzone"] button {
    position: absolute !important;
    inset: 0 !important;
    width: 100% !important;
    height: 100% !important;
    min-height: 100% !important;
    opacity: 0 !important;
    z-index: 5 !important;
    cursor: pointer !important;
    margin: 0 !important;
    padding: 0 !important;
    border: 0 !important;
}

.sg-upload-status-card {
    padding: 13px 15px !important;
    border-radius: 10px !important;
    background: var(--surface2) !important;
    border: 1px solid var(--border) !important;
    min-height: 118px !important;
    display: flex !important;
    flex-direction: column !important;
    justify-content: center !important;
    gap: 4px !important;
}
.sg-upload-status-card.active {
    background: var(--primary-soft) !important;
    border-color: var(--primary) !important;
}
.sg-upload-pill {
    display: inline-flex !important;
    align-self: flex-start !important;
    padding: 2px 8px !important;
    border-radius: 999px !important;
    background: var(--surface) !important;
    border: 1px solid var(--border) !important;
    color: var(--primary) !important;
    font-size: 9.5px !important;
    font-weight: 800 !important;
    letter-spacing: 0.04em !important;
}
.sg-upload-status-card strong {
    font-size: 12.5px !important;
    font-weight: 750 !important;
    color: var(--text) !important;
    line-height: 1.35 !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
    white-space: nowrap !important;
}
.sg-upload-status-card p {
    margin: 0 !important;
    font-size: 11px !important;
    color: var(--muted) !important;
    line-height: 1.48 !important;
}

/* Khung màn hình chính (.monitor-panel) */
.sg-monitor-heading {
    display: flex !important;
    align-items: flex-start !important;
    justify-content: space-between !important;
    gap: 10px !important;
    margin-bottom: 4px !important;
}
.sg-monitor-badge {
    display: inline-flex !important;
    align-items: center !important;
    padding: 5px 10px !important;
    border-radius: 999px !important;
    background: var(--surface2) !important;
    border: 1px solid var(--border) !important;
    color: var(--text) !important;
    font-size: 10px !important;
    font-weight: 800 !important;
    letter-spacing: .04em !important;
    white-space: nowrap !important;
}
.sg-monitor-badge.live {
    background: var(--primary-soft) !important;
    border-color: var(--primary) !important;
    color: var(--primary) !important;
}
.sg-monitor-frame {
    position: relative !important;
    aspect-ratio: 16 / 8.4 !important;
    max-height: 360px !important;
    width: 100% !important;
    overflow: hidden !important;
    border-radius: 10px !important;
    background: #0E1626 !important;
    border: 1px solid var(--border-strong) !important;
    margin-bottom: 2px !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
}
.sg-monitor-blur-bg {
    position: absolute !important;
    inset: -18px !important;
    background-size: cover !important;
    background-position: center !important;
    background-repeat: no-repeat !important;
    filter: blur(22px) brightness(0.40) saturate(1.1) !important;
    transform: scale(1.08) !important;
    z-index: 0 !important;
    pointer-events: none !important;
}
.sg-monitor-frame img {
    position: relative !important;
    z-index: 1 !important;
    width: 100% !important;
    height: 100% !important;
    max-width: 100% !important;
    max-height: 100% !important;
    display: block !important;
    object-fit: contain !important;
    filter: drop-shadow(0 4px 16px rgba(0, 0, 0, 0.45)) !important;
}
[data-testid="stMain"] .st-key-panel_review_detail [data-testid="stImage"] img {
    max-height: 300px !important;
    width: 100% !important;
    object-fit: contain !important;
    background: #0E1626 !important;
    border-radius: 10px !important;
    border: 1px solid var(--border) !important;
}
.sg-monitor-overlay {
    position: absolute !important;
    z-index: 2 !important;
    max-width: calc(100% - 20px) !important;
    padding: 6px 9px !important;
    border-radius: 6px !important;
    background: rgba(10, 18, 32, 0.84) !important;
    color: #F3F6FB !important;
    font-size: 9.5px !important;
    font-weight: 750 !important;
    letter-spacing: .03em !important;
}
.sg-monitor-overlay.top-left { top: 10px !important; left: 10px !important; }
.sg-monitor-overlay.top-right { top: 10px !important; right: 10px !important; }
.sg-monitor-overlay.bottom-left {
    bottom: 10px !important;
    left: 10px !important;
    max-width: 92% !important;
    font-weight: 500 !important;
    letter-spacing: 0 !important;
    font-size: 10.5px !important;
}
.sg-scan-state-text {
    font-size: 11.5px !important;
    color: var(--muted) !important;
    line-height: 1.4 !important;
    padding-left: 4px !important;
}

/* Thanh Telemetry 1 dòng gọn gàng dưới màn hình quét (.sg-telemetry-line) */
.sg-telemetry-line {
    display: flex !important;
    align-items: center !important;
    justify-content: space-between !important;
    gap: 12px !important;
    margin-top: 6px !important;
    padding: 9px 13px !important;
    border-radius: 9px !important;
    background: var(--surface2) !important;
    border: 1px solid var(--border) !important;
    font-size: 11.5px !important;
    color: var(--text) !important;
}
.sg-telemetry-line.warn {
    background: var(--warning-bg) !important;
    border-color: var(--warning) !important;
    color: var(--warning-text) !important;
}
.sg-tele-main {
    display: flex !important;
    align-items: center !important;
    gap: 8px !important;
    min-width: 0 !important;
    flex-wrap: wrap !important;
}
.sg-tele-dot {
    width: 8px !important;
    height: 8px !important;
    border-radius: 50% !important;
    background: var(--success) !important;
    flex-shrink: 0 !important;
}
.sg-tele-dot.warn {
    background: var(--warning) !important;
}
.sg-tele-sep {
    color: var(--muted) !important;
    font-weight: 700 !important;
}
.sg-tele-metrics {
    font-size: 11px !important;
    color: var(--muted) !important;
    white-space: nowrap !important;
    font-variant-numeric: tabular-nums !important;
}
.sg-telemetry-line.warn .sg-tele-metrics,
.sg-telemetry-line.warn .sg-tele-metrics b {
    color: var(--warning-text) !important;
}
.sg-tele-metrics b {
    color: var(--text) !important;
    font-weight: 750 !important;
}

/* Khung phải (.scan-controls) */
.sg-ctrl-label {
    display: flex !important;
    align-items: center !important;
    justify-content: space-between !important;
    gap: 8px !important;
    font-size: 11.5px !important;
    font-weight: 600 !important;
    color: var(--text) !important;
    margin: 4px 0 0 !important;
}
.sg-ctrl-label b {
    color: var(--primary) !important;
    font-weight: 800 !important;
    white-space: nowrap !important;
}
[data-testid="stMain"] .st-key-panel_scan_controls [data-testid="stSlider"] [data-testid="stWidgetLabel"],
[data-testid="stMain"] .st-key-panel_scan_controls [data-testid="stSelectbox"] [data-testid="stWidgetLabel"] {
    display: none !important;
}
[data-testid="stMain"] .st-key-panel_scan_controls [data-testid="stSlider"] :is(
    [data-testid="stTickBar"],
    [data-testid="stSliderTickBar"],
    [data-testid="stTickBarMin"],
    [data-testid="stTickBarMax"],
    [data-testid="stSliderTickBarMin"],
    [data-testid="stSliderTickBarMax"],
    [data-testid="stThumbValue"],
    [data-testid="stSliderThumbValue"]
) {
    display: none !important;
}
[data-testid="stMain"] .st-key-panel_scan_controls [data-testid="stSlider"] {
    padding-top: 0 !important;
    padding-bottom: 2px !important;
}
.sg-threshold-note {
    padding: 10px 12px !important;
    border-radius: 9px !important;
    background: var(--surface2) !important;
    border: 1px solid var(--border) !important;
    font-size: 11.5px !important;
    margin: 5px 0 2px !important;
}
.sg-threshold-note b {
    display: block !important;
    font-size: 10.5px !important;
    font-weight: 700 !important;
    color: var(--text) !important;
}
.sg-threshold-note p {
    margin: 4px 0 0 !important;
    font-size: 11.5px !important;
    font-weight: 500 !important;
    line-height: 1.55 !important;
    color: var(--text) !important;
}
.sg-behavior-heading {
    margin: 6px 0 2px !important;
    padding-top: 11px !important;
    border-top: 1px solid var(--border) !important;
}

/* Công tắc gạt (.switch-row) */
[data-testid="stMain"] .st-key-panel_scan_controls [data-testid="stElementContainer"]:has([data-baseweb="checkbox"]),
[data-testid="stMain"] .st-key-panel_scan_controls [class*="st-key-scan_tgl_"],
[data-testid="stMain"] .st-key-panel_scan_controls [data-testid="stCheckbox"],
[data-testid="stMain"] .st-key-panel_scan_controls [data-testid="stCheckbox"] > div {
    width: 100% !important;
    max-width: 100% !important;
    display: block !important;
    margin: 0 !important;
    padding: 0 !important;
}
[data-testid="stMain"] .st-key-panel_scan_controls [data-baseweb="checkbox"],
[data-testid="stMain"] [class*="st-key-scan_tgl_"] [data-baseweb="checkbox"] {
    display: flex !important;
    flex-direction: row-reverse !important;
    justify-content: space-between !important;
    align-items: center !important;
    width: 100% !important;
    max-width: 100% !important;
    box-sizing: border-box !important;
    min-height: 32px !important;
    padding: 2px 0 !important;
    margin: 0 !important;
    gap: 10px !important;
    cursor: pointer !important;
}
[data-testid="stMain"] .st-key-panel_scan_controls [data-baseweb="checkbox"] [data-testid="stWidgetLabel"],
[data-testid="stMain"] [class*="st-key-scan_tgl_"] [data-baseweb="checkbox"] [data-testid="stWidgetLabel"] {
    flex: 1 1 auto !important;
    margin: 0 auto 0 0 !important;
    padding: 0 !important;
    text-align: left !important;
}
[data-testid="stMain"] .st-key-panel_scan_controls [data-baseweb="checkbox"] [data-testid="stWidgetLabel"] p,
[data-testid="stMain"] [class*="st-key-scan_tgl_"] [data-baseweb="checkbox"] [data-testid="stWidgetLabel"] p {
    font-size: 11.5px !important;
    font-weight: 500 !important;
    color: var(--text) !important;
    margin: 0 !important;
    text-align: left !important;
}
[data-testid="stMain"] .st-key-panel_scan_controls [data-baseweb="checkbox"] > :not(input):not([data-testid="stWidgetLabel"]),
[data-testid="stMain"] [class*="st-key-scan_tgl_"] [data-baseweb="checkbox"] > :not(input):not([data-testid="stWidgetLabel"]) {
    flex: 0 0 36px !important;
    width: 36px !important;
    min-width: 36px !important;
    height: 20px !important;
    min-height: 20px !important;
    margin: 0 0 0 auto !important;
    padding: 2px !important;
    border-radius: 999px !important;
    background-color: var(--toggle-off-bg) !important;
    background-image: none !important;
    border: 1px solid var(--toggle-off-border) !important;
    box-sizing: border-box !important;
    display: flex !important;
    align-items: center !important;
    transition: background-color .15s ease, border-color .15s ease !important;
}
[data-testid="stMain"] .st-key-panel_scan_controls [data-baseweb="checkbox"]:hover > :not(input):not([data-testid="stWidgetLabel"]),
[data-testid="stMain"] [class*="st-key-scan_tgl_"] [data-baseweb="checkbox"]:hover > :not(input):not([data-testid="stWidgetLabel"]) {
    background-color: var(--toggle-off-hover) !important;
    border-color: var(--toggle-off-border) !important;
}
[data-testid="stMain"] .st-key-panel_scan_controls [data-baseweb="checkbox"]:is(:has(input:checked), :has(input[aria-checked="true"]), [aria-checked="true"]) > :not(input):not([data-testid="stWidgetLabel"]),
[data-testid="stMain"] .st-key-panel_scan_controls [data-baseweb="checkbox"]:is(:has(input:checked), :has(input[aria-checked="true"]), [aria-checked="true"]):hover > :not(input):not([data-testid="stWidgetLabel"]),
[data-testid="stMain"] [class*="st-key-scan_tgl_"] [data-baseweb="checkbox"]:is(:has(input:checked), :has(input[aria-checked="true"]), [aria-checked="true"]) > :not(input):not([data-testid="stWidgetLabel"]),
[data-testid="stMain"] [class*="st-key-scan_tgl_"] [data-baseweb="checkbox"]:is(:has(input:checked), :has(input[aria-checked="true"]), [aria-checked="true"]):hover > :not(input):not([data-testid="stWidgetLabel"]) {
    background-color: var(--primary) !important;
    border-color: var(--primary) !important;
}
[data-testid="stMain"] .st-key-panel_scan_controls [data-baseweb="checkbox"] > :not(input):not([data-testid="stWidgetLabel"]) > *,
[data-testid="stMain"] [class*="st-key-scan_tgl_"] [data-baseweb="checkbox"] > :not(input):not([data-testid="stWidgetLabel"]) > * {
    background-color: #FFFFFF !important;
    border-radius: 50% !important;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.32) !important;
}

/* ============ 7B. Cụm phân trang hiện đại trong Nhật ký phiên quét & Duyệt vi phạm ============ */
[data-testid="stMain"] :is(.st-key-scan_log_pager, .st-key-rev_card_pager) {
    background: var(--surface2) !important;
    border: 1px solid var(--border) !important;
    border-radius: 10px !important;
    padding: 3px 4px !important;
    margin: 0 !important;
}
[data-testid="stMain"] :is(.st-key-scan_log_pager, .st-key-rev_card_pager) [data-testid="stHorizontalBlock"] {
    gap: 4px !important;
    align-items: center !important;
}
[data-testid="stMain"] :is(.st-key-scan_log_pager, .st-key-rev_card_pager) [data-testid="stColumn"] {
    min-width: 0 !important;
}
[data-testid="stMain"] :is(.st-key-scan_log_pager, .st-key-rev_card_pager) button {
    height: 30px !important;
    min-height: 30px !important;
    max-height: 30px !important;
    padding: 0 8px !important;
    margin: 0 !important;
    border-radius: 7px !important;
    background: var(--surface) !important;
    border: 1px solid var(--border) !important;
    color: var(--text) !important;
    font-size: 12px !important;
    font-weight: 650 !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    box-shadow: 0 1px 2px rgba(15, 23, 42, 0.06) !important;
}
[data-testid="stMain"] .st-key-rev_card_pager __PRI__,
[data-testid="stMain"] .st-key-rev_card_pager __PRI__:hover {
    background: var(--primary) !important;
    border-color: var(--primary) !important;
    color: var(--primary-contrast) !important;
    font-weight: 800 !important;
}
[data-testid="stMain"] :is(.st-key-scan_log_pager, .st-key-rev_card_pager) button > div,
[data-testid="stMain"] :is(.st-key-scan_log_pager, .st-key-rev_card_pager) button [data-testid="stMarkdownContainer"] {
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    height: 100% !important;
    margin: 0 !important;
    padding: 0 !important;
}
[data-testid="stMain"] :is(.st-key-scan_log_pager, .st-key-rev_card_pager) button p {
    font-size: 12px !important;
    font-weight: 650 !important;
    line-height: 1 !important;
    margin: 0 !important;
    padding: 0 !important;
    white-space: nowrap !important;
    transform: translateY(-0.5px) !important;
}
[data-testid="stMain"] .st-key-rev_card_pager __PRI__ p {
    color: var(--primary-contrast) !important;
    font-weight: 800 !important;
}
[data-testid="stMain"] :is(.st-key-scan_log_pager, .st-key-rev_card_pager) __SEC__:hover:not(:disabled) {
    background: var(--primary-soft) !important;
    border-color: var(--primary) !important;
    color: var(--primary) !important;
}
[data-testid="stMain"] :is(.st-key-scan_log_pager, .st-key-rev_card_pager) button:disabled {
    background: transparent !important;
    border-color: transparent !important;
    color: var(--muted) !important;
    opacity: 0.42 !important;
    box-shadow: none !important;
}

/* Thanh phân trang trang Duyệt vi phạm (.st-key-rev_card_footer) */
[data-testid="stMain"] .st-key-rev_card_footer {
    margin-top: 8px !important;
    padding: 9px 14px !important;
    border-radius: 12px !important;
    background: var(--surface) !important;
    border: 1px solid var(--border-strong) !important;
    box-shadow: var(--shadow) !important;
}
[data-testid="stMain"] .st-key-rev_card_footer > [data-testid="stVerticalBlock"] {
    gap: 0 !important;
}
[data-testid="stMain"] .st-key-rev_card_footer [data-testid="stHorizontalBlock"] {
    align-items: center !important;
    margin: 0 !important;
    padding: 0 !important;
}
[data-testid="stMain"] .st-key-rev_card_footer [data-testid="stColumn"] {
    display: flex !important;
    align-items: center !important;
    min-height: 36px !important;
}
[data-testid="stMain"] .st-key-rev_card_footer [data-testid="stColumn"] > [data-testid="stVerticalBlock"] {
    justify-content: center !important;
    gap: 0 !important;
    width: 100% !important;
}
[data-testid="stMain"] .st-key-rev_card_footer [data-testid="stColumn"]:first-child [data-testid="stElementContainer"],
[data-testid="stMain"] .st-key-rev_card_footer [data-testid="stColumn"]:first-child [data-testid="stMarkdown"],
[data-testid="stMain"] .st-key-rev_card_footer [data-testid="stColumn"]:first-child [data-testid="stMarkdownContainer"] {
    margin: 0 !important;
    padding: 0 !important;
    display: flex !important;
    align-items: center !important;
    height: 36px !important;
    min-height: 36px !important;
}
.sg-rev-page-meta {
    display: inline-flex !important;
    align-items: center !important;
    gap: 5px !important;
    height: 36px !important;
    font-size: 13px !important;
    font-weight: 500 !important;
    color: var(--muted) !important;
    line-height: 1 !important;
    margin: 0 !important;
    padding: 0 2px !important;
    white-space: nowrap !important;
    transform: translateY(-1px) !important;
}
.sg-rev-page-meta b {
    color: var(--text) !important;
    font-weight: 750 !important;
    font-variant-numeric: tabular-nums !important;
}
.sg-page-indicator {
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    gap: 4px !important;
    height: 28px !important;
    padding: 0 8px !important;
    font-size: 11.5px !important;
    font-weight: 600 !important;
    color: var(--muted) !important;
    white-space: nowrap !important;
    font-variant-numeric: tabular-nums !important;
}
.sg-page-indicator b {
    color: var(--text) !important;
    font-weight: 800 !important;
}

[data-testid="stMain"] .st-key-panel_scan_log {
    margin-top: 6px !important;
}
[data-testid="stMain"] .st-key-panel_scan_log .sg-table-wrap {
    margin-top: 10px !important;
    margin-bottom: 6px !important;
}

.sg-guide-box { font-size: 12px !important; line-height: 1.55 !important; padding: 10px 12px !important; }

/* ============ 7C. Trang Trợ lý AI (.st-key-panel_assistant): Khung Chat toàn chiều rộng + Chip ngữ cảnh ============ */
[data-testid="stMain"] .st-key-panel_assistant {
    padding: 0 !important;
    border-radius: 16px !important;
    overflow: hidden !important;
    background: var(--surface) !important;
    border: 1px solid var(--border-strong) !important;
    box-shadow: var(--shadow) !important;
}
[data-testid="stMain"] .st-key-panel_assistant > [data-testid="stVerticalBlock"] {
    gap: 0 !important;
    padding: 0 !important;
    margin: 0 !important;
}
[data-testid="stMain"] .st-key-panel_assistant > [data-testid="stVerticalBlock"] > [data-testid="stElementContainer"] {
    margin: 0 !important;
    padding: 0 !important;
}
[data-testid="stMain"] .st-key-panel_assistant [data-testid="stMarkdownContainer"] {
    margin-bottom: 0 !important;
}

.sg-chat-intro {
    display: flex !important;
    align-items: center !important;
    justify-content: space-between !important;
    gap: 12px !important;
    padding: 18px 22px 15px !important;
    margin: 0 !important;
    border-bottom: 1px solid var(--border) !important;
    flex-wrap: wrap !important;
}
.sg-chat-mark {
    width: 38px !important;
    height: 38px !important;
    min-width: 38px !important;
    border-radius: 10px !important;
    background: var(--primary-soft) !important;
    border: 1px solid var(--border) !important;
    color: var(--primary) !important;
    display: grid !important;
    place-items: center !important;
}
.sg-chat-intro-text h2 {
    font-size: 16px !important;
    font-weight: 780 !important;
    color: var(--text) !important;
    margin: 0 !important;
    padding: 0 !important;
    line-height: 1.25 !important;
}
.sg-chat-intro-text p {
    font-size: 11.5px !important;
    color: var(--muted) !important;
    margin: 3px 0 0 !important;
    padding: 0 !important;
    line-height: 1.4 !important;
}
.sg-chat-ctx-chip {
    display: inline-flex !important;
    align-items: center !important;
    gap: 5px !important;
    padding: 6px 12px !important;
    border-radius: 999px !important;
    background: var(--primary-soft) !important;
    border: 1px solid var(--primary) !important;
    color: var(--primary) !important;
    font-size: 11.5px !important;
    font-weight: 650 !important;
    white-space: nowrap !important;
}
.sg-chat-ctx-chip b {
    font-weight: 800 !important;
}

/* Vùng luồng hội thoại ở giữa (.st-key-chat_stream_area) */
[data-testid="stMain"] .st-key-chat_stream_area {
    min-height: 340px !important;
    max-height: 520px !important;
    overflow-y: auto !important;
    padding: 20px 32px !important;
    display: flex !important;
    flex-direction: column !important;
}
[data-testid="stMain"] .st-key-chat_stream_area > [data-testid="stVerticalBlock"] {
    gap: 12px !important;
}

/* Bong bóng tin nhắn AI (.sg-chat-msg-ai & subpanel_chat_*) */
.sg-chat-msg-ai,
[data-testid="stMain"] .st-key-chat_stream_area [class*="st-key-subpanel_chat_"] {
    max-width: 820px !important;
    padding: 14px 16px !important;
    border-radius: 12px !important;
    background: var(--chat-bubble-bg) !important;
    border: 1px solid var(--border) !important;
    color: var(--text) !important;
    font-size: 12.5px !important;
    line-height: 1.6 !important;
    box-shadow: none !important;
}
.sg-chat-msg-ai b,
.sg-chat-ai-head b {
    display: block !important;
    font-size: 12px !important;
    font-weight: 750 !important;
    color: var(--text) !important;
    margin-bottom: 5px !important;
}
.sg-chat-msg-ai p {
    margin: 0 !important;
    font-size: 12.5px !important;
    line-height: 1.6 !important;
    color: var(--text) !important;
}
.sg-chat-ai-head {
    display: flex !important;
    align-items: center !important;
    justify-content: space-between !important;
    margin-bottom: 4px !important;
}
.sg-chat-ai-head span {
    font-size: 10.5px !important;
    color: var(--muted) !important;
}

/* Bong bóng tin nhắn người dùng (.sg-chat-msg-user) */
.sg-chat-msg-user {
    max-width: 720px !important;
    margin-left: auto !important;
    padding: 11px 15px !important;
    border-radius: 12px !important;
    background: var(--primary-soft) !important;
    border: 1px solid var(--primary) !important;
    color: var(--text) !important;
    font-size: 12.5px !important;
    line-height: 1.5 !important;
}
.sg-chat-msg-meta {
    font-size: 10px !important;
    font-weight: 600 !important;
    color: var(--primary) !important;
    margin-bottom: 3px !important;
}
.sg-chat-msg-text {
    color: var(--text) !important;
    font-weight: 500 !important;
}

/* Vùng tương tác ở đáy khung chat (.st-key-chat_bottom_dock) */
[data-testid="stMain"] .st-key-chat_bottom_dock {
    padding: 8px 22px 22px !important;
}
[data-testid="stMain"] .st-key-chat_bottom_dock > [data-testid="stVerticalBlock"] {
    gap: 8px !important;
}
.sg-chat-suggest-label {
    font-size: 11px !important;
    font-weight: 700 !important;
    color: var(--muted) !important;
    margin: 0 0 2px !important;
    padding: 0 !important;
}

/* Hàng 4 nút gợi ý bo tròn dạng viên thuốc (.st-key-chat_suggest_row) */
[data-testid="stMain"] .st-key-chat_suggest_row [data-testid="stHorizontalBlock"] {
    gap: 8px !important;
}
[data-testid="stMain"] .st-key-chat_suggest_row button {
    border-radius: 999px !important;
    min-height: 34px !important;
    height: 34px !important;
    padding: 0 11px !important;
    background: var(--chat-bubble-bg) !important;
    border: 1px solid var(--border-strong) !important;
    color: var(--text) !important;
    font-size: 11px !important;
    font-weight: 650 !important;
    box-shadow: none !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
}
[data-testid="stMain"] .st-key-chat_suggest_row button > div,
[data-testid="stMain"] .st-key-chat_suggest_row button [data-testid="stMarkdownContainer"] {
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    height: 100% !important;
    margin: 0 !important;
    padding: 0 !important;
}
[data-testid="stMain"] .st-key-chat_suggest_row button p {
    font-size: 11px !important;
    font-weight: 650 !important;
    line-height: 1 !important;
    margin: 0 !important;
    padding: 0 !important;
    white-space: nowrap !important;
    transform: translateY(-1px) !important;
}
[data-testid="stMain"] .st-key-chat_suggest_row button:hover {
    background: var(--primary-soft) !important;
    border-color: var(--primary) !important;
    color: var(--primary) !important;
}

/* Thanh nhập câu hỏi hợp nhất ở đáy (.st-key-panel_assistant [data-testid="stForm"]) */
[data-testid="stMain"] .st-key-panel_assistant [data-testid="stForm"] {
    background: var(--chat-input-bg) !important;
    background-color: var(--chat-input-bg) !important;
    border: 1px solid var(--border-strong) !important;
    border-radius: 12px !important;
    padding: 6px 8px 6px 14px !important;
    margin-top: 4px !important;
    box-shadow: none !important;
}
[data-testid="stMain"] .st-key-panel_assistant [data-testid="stForm"]:focus-within {
    border-color: var(--primary) !important;
    box-shadow: 0 0 0 1px var(--primary-soft) !important;
}
[data-testid="stMain"] .st-key-panel_assistant [data-testid="stForm"] [data-testid="stHorizontalBlock"] {
    align-items: center !important;
    gap: 10px !important;
}
[data-testid="stMain"] .st-key-panel_assistant [data-testid="stForm"] [data-testid="stTextInput"],
[data-testid="stMain"] .st-key-panel_assistant [data-testid="stForm"] [data-testid="stTextInput"] > div,
[data-testid="stMain"] .st-key-panel_assistant [data-testid="stForm"] [data-testid="stTextInputRootElement"],
[data-testid="stMain"] .st-key-panel_assistant [data-testid="stForm"] [data-testid="stTextInputRootElement"] > div,
[data-testid="stMain"] .st-key-panel_assistant [data-testid="stForm"] [data-baseweb="input"],
[data-testid="stMain"] .st-key-panel_assistant [data-testid="stForm"] [data-baseweb="base-input"],
[data-testid="stMain"] .st-key-panel_assistant [data-testid="stForm"] [data-baseweb="input"] > div {
    background: var(--chat-input-bg) !important;
    background-color: var(--chat-input-bg) !important;
    border: 0 !important;
    border-color: transparent !important;
    box-shadow: none !important;
    outline: none !important;
    padding: 0 !important;
    margin: 0 !important;
}
[data-testid="stMain"] .st-key-panel_assistant [data-testid="stForm"] input {
    background: var(--chat-input-bg) !important;
    background-color: var(--chat-input-bg) !important;
    border: 0 !important;
    box-shadow: none !important;
    outline: none !important;
    color: var(--text) !important;
    -webkit-text-fill-color: var(--text) !important;
    caret-color: var(--primary) !important;
    font-size: 12.5px !important;
    font-weight: 500 !important;
    padding: 6px 2px !important;
}
[data-testid="stMain"] .st-key-panel_assistant [data-testid="stForm"] input::placeholder,
[data-testid="stMain"] .st-key-panel_assistant [data-testid="stForm"] input::-webkit-input-placeholder {
    color: var(--muted) !important;
    -webkit-text-fill-color: var(--muted) !important;
    opacity: 1 !important;
}
[data-testid="stMain"] .st-key-panel_assistant [data-testid="stForm"] [data-testid="InputInstructions"] {
    display: none !important;
}
[data-testid="stMain"] .st-key-panel_assistant [data-testid="stFormSubmitButton"] button {
    min-height: 36px !important;
    height: 36px !important;
    border-radius: 8px !important;
    padding: 0 14px !important;
    font-size: 12px !important;
    font-weight: 700 !important;
}

/* ============ 7D. Trang Tài liệu an toàn: Thanh tìm kiếm & 6 nút chủ đề căn giữa chữ hoàn hảo ============ */
[data-testid="stMain"] .st-key-doc_toolbar_row [data-testid="stElementContainer"],
[data-testid="stMain"] .st-key-doc_toolbar_row [data-testid="stMarkdownContainer"] {
    margin: 0 !important;
    padding: 0 !important;
}
[data-testid="stMain"] .st-key-doc_topic_row {
    margin: 6px 0 10px !important;
}
[data-testid="stMain"] .st-key-doc_topic_row button {
    height: 36px !important;
    min-height: 36px !important;
    max-height: 36px !important;
    border-radius: 999px !important;
    padding: 0 14px !important;
    margin: 0 !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    white-space: nowrap !important;
}
[data-testid="stMain"] .st-key-doc_topic_row button > div,
[data-testid="stMain"] .st-key-doc_topic_row button [data-testid="stMarkdownContainer"] {
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    width: 100% !important;
    height: 100% !important;
    margin: 0 !important;
    padding: 0 !important;
    line-height: 1 !important;
}
[data-testid="stMain"] .st-key-doc_topic_row button p {
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    white-space: nowrap !important;
    font-size: 12px !important;
    line-height: 1 !important;
    margin: 0 !important;
    padding: 0 !important;
    transform: translateY(-1.5px) !important;
}
.sg-doc-body-text {
    font-size: 13px !important;
    line-height: 1.75 !important;
    color: var(--text) !important;
}
mark.sg-doc-mark {
    background: var(--warning-bg) !important;
    color: var(--warning-text) !important;
    border: 1px solid var(--warning) !important;
    padding: 1px 5px !important;
    border-radius: 4px !important;
    font-weight: 700 !important;
}

/* ============ 8. Khung ứng dụng: sidebar 236px + vùng nội dung căn giữa (theo prototype) ============ */
[data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stDecoration"], [data-testid="stSidebarHeader"],
[data-testid="stSidebarCollapseButton"], [data-testid="stExpandSidebarButton"],
[data-testid="stSidebarCollapsedControl"], [data-testid="stSidebarResizeHandle"] { display: none !important; }

[data-testid="stSidebar"] {
    width: 236px !important; min-width: 236px !important; max-width: 236px !important;
    background: #111D30 !important;
    transition: width .2s ease, min-width .2s ease, max-width .2s ease;
}
[data-testid="stSidebarContent"] { height: 100vh !important; overflow-y: auto !important; overflow-x: hidden !important; }
[data-testid="stSidebarUserContent"] {
    padding: 22px 14px 16px !important; min-height: 100%;
    display: flex !important; flex-direction: column !important;
}
[data-testid="stSidebarUserContent"] > [data-testid="stVerticalBlock"] {
    flex: 1 1 auto; min-height: calc(100vh - 38px);
}

/* Thương hiệu (.brand / .logo) */
[data-testid="stSidebar"] .sg-brand {
    display: flex !important; align-items: center; gap: 11px;
    padding: 2px 8px 22px !important; margin-bottom: 22px !important;
    border-bottom: 1px solid #293950;
}
[data-testid="stSidebar"] .sg-logo {
    width: 39px; height: 39px; min-width: 39px; border-radius: 11px;
    background: #203A66; border: 1px solid #34527D;
    display: grid; place-items: center; color: #A9BBFF;
}
[data-testid="stSidebar"] .sg-logo svg { width: 23px; height: 23px; fill: none; stroke: currentColor; stroke-width: 1.5; stroke-linecap: round; stroke-linejoin: round; }
[data-testid="stSidebar"] .sg-brand-title { font-size: 14px; font-weight: 800; letter-spacing: .03em; color: #F3F6FC; line-height: 1.2; }
[data-testid="stSidebar"] .sg-brand-sub { display: block; color: #9BAEC7; font-size: 11px; margin-top: 3px; }
[data-testid="stSidebar"] .sg-side-label {
    color: #8EA2BE; letter-spacing: .15em; font-size: 10px; font-weight: 800;
    text-transform: uppercase; margin: 0 9px 9px !important;
}

/* Nhóm chân: ghim sát đáy sidebar */
[data-testid="stSidebar"] .st-key-sb_bottom { margin-top: auto; }
[data-testid="stSidebar"] [data-testid="stVerticalBlock"] > *:has(> .st-key-sb_bottom) { margin-top: auto; }
[data-testid="stSidebar"] .st-key-sb_footer { border-top: 1px solid #293950; padding-top: 16px; margin-bottom: 6px; }
[data-testid="stSidebar"] .st-key-sb_toggle_btn button {
    display: flex !important; justify-content: flex-start !important; align-items: center !important; gap: 10px !important;
    min-height: 38px !important; padding: 0 12px !important; border-radius: 9px !important;
    background: transparent !important; border: 0 !important; box-shadow: none !important;
    color: #9CB0CE !important; font-size: 12px !important; font-weight: 600 !important;
}
[data-testid="stSidebar"] .st-key-sb_toggle_btn button:hover { background: #1A2A42 !important; color: #FFFFFF !important; }
[data-testid="stSidebar"] .st-key-sb_toggle_btn button > div { justify-content: flex-start !important; flex: 1 1 auto; width: auto !important; }
[data-testid="stSidebar"] .st-key-sb_toggle_btn button :is(p, span) { color: inherit !important; margin: 0 !important; font-size: inherit !important; }

/* Vùng nội dung: căn giữa, tối đa 1800px, tự giãn theo độ rộng sidebar */
[data-testid="stMainBlockContainer"], .block-container {
    max-width: 1800px !important; width: 100% !important;
    margin: 0 auto !important; padding: 20px 30px 34px !important;
}

/* ============ 9. Sidebar khớp prototype: lề, icon nét mảnh, chiều cao, khoảng cách ============ */
[data-testid="stSidebar"] > div:first-child,
[data-testid="stSidebarContent"] { padding: 0 !important; }
[data-testid="stSidebarContent"] > :not([data-testid="stSidebarHeader"]),
[data-testid="stSidebarUserContent"] { padding: 22px 14px 16px !important; }
[data-testid="stSidebarUserContent"] > [data-testid="stVerticalBlock"],
[data-testid="stSidebarContent"] > :not([data-testid="stSidebarHeader"]) > [data-testid="stVerticalBlock"] { padding: 0 !important; width: 100% !important; }
[data-testid="stSidebar"] [data-testid="stVerticalBlock"]:is(:has(> .st-key-sb_bottom), :has(> * > .st-key-sb_bottom)) {
    min-height: calc(100vh - 38px) !important;
}
[data-testid="stSidebar"] [data-testid="stVerticalBlock"] { gap: 5px !important; }
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] { width: 100%; }
[data-testid="stSidebar"] .sg-brand { width: 100%; box-sizing: border-box; }
[data-testid="stSidebar"] .sg-brand-title, [data-testid="stSidebar"] .sg-brand-sub { white-space: nowrap; }
[data-testid="stSidebar"] .sg-side-label { margin: 0 9px 4px !important; }

[data-testid="stSidebar"] [class*="st-key-nav_btn_"],
[data-testid="stSidebar"] [class*="st-key-nav_btn_"] .stButton,
[data-testid="stSidebar"] [class*="st-key-nav_btn_"] button { width: 100% !important; }
[data-testid="stSidebar"] [class*="st-key-nav_btn_"] button { min-height: 40px !important; height: 40px !important; }
[data-testid="stSidebar"] [class*="st-key-nav_btn_"] button p { font-size: 13px !important; font-weight: 600 !important; }

[data-testid="stSidebar"] [class*="st-key-nav_btn_"] button [data-testid="stIconMaterial"] { display: none !important; }
[data-testid="stSidebar"] [class*="st-key-nav_btn_"] button::before {
    content: ""; flex: 0 0 19px; width: 19px; height: 19px; background-color: #9CB0CE;
    -webkit-mask: var(--sg-ico) center / contain no-repeat; mask: var(--sg-ico) center / contain no-repeat;
}
[data-testid="stSidebar"] [class*="st-key-nav_btn_"] button:hover::before { background-color: #C2CEE0; }
[data-testid="stSidebar"] [class*="st-key-nav_btn_"] __PRI__::before { background-color: #A9BBFF; }
__NAV_ICONS__

[data-testid="stSidebar"] .st-key-theme_switch button { height: 40px !important; min-height: 40px !important; }
[data-testid="stSidebar"] .st-key-theme_switch button p { font-weight: 500 !important; }
[data-testid="stSidebar"] .st-key-theme_switch __PRI__ p { font-weight: 800 !important; }
[data-testid="stSidebar"] .sg-status-mini { font-size: 12px !important; gap: 8px; display: flex; align-items: center; }

/* ============ 10. Hết chồng đè + căn hàng Header với khối thương hiệu ============ */
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"],
[data-testid="stSidebar"] [data-testid="stMarkdown"] { margin-bottom: 0 !important; }
[data-testid="stMain"] [data-testid="stMarkdownContainer"]:has(> .sg-utility-divider) { margin-bottom: 0 !important; }

[data-testid="stElementContainer"]:has(style), .element-container:has(style) { display: none !important; }

[data-testid="stSidebar"] .sg-side-label { margin: 0 9px 4px !important; line-height: 1.4 !important; }
[data-testid="stSidebar"] .sg-side-label-gap { margin-top: 14px !important; }
[data-testid="stSidebar"] .st-key-sb_footer { padding-top: 16px; margin-bottom: 10px; }
[data-testid="stSidebar"] .st-key-sb_toggle_btn { margin-top: 2px; }

.sg-utility-divider { height: 1px; background: var(--border); margin: 8px 12px 10px 0 !important; }

/* ============ 11. Căn thanh Sáng/Tối/Theo hệ thống: 1 dòng, giữa nút ============ */
[data-testid="stSidebar"] .st-key-theme_switch [data-testid="stColumn"] { min-width: 0 !important; }
[data-testid="stSidebar"] .st-key-theme_switch button {
    display: flex !important; align-items: center !important; justify-content: center !important;
    padding: 0 2px !important; white-space: nowrap !important; line-height: 1 !important;
}
[data-testid="stSidebar"] .st-key-theme_switch button > div,
[data-testid="stSidebar"] .st-key-theme_switch button [data-testid="stMarkdownContainer"] {
    display: flex !important; align-items: center !important; justify-content: center !important;
    width: auto !important; height: 100%; margin: 0 !important; padding: 0 !important; white-space: nowrap !important;
}
[data-testid="stSidebar"] .st-key-theme_switch button p {
    margin: 0 !important; line-height: 1 !important; white-space: nowrap !important; font-size: 11px !important;
}

/* ============ 12. Khung viền & Thẻ Expander rõ ràng ở cả Sáng và Tối ============ */
[data-testid="stMain"] [data-testid="stVerticalBlockBorderWrapper"] {
    border-color: var(--border-strong) !important; border-radius: 14px !important; background: var(--panel-bg) !important;
}
[data-testid="stMain"] [data-testid="stExpander"] {
    background: transparent !important;
    border: 0 !important;
    margin-bottom: 10px !important;
}
[data-testid="stMain"] [data-testid="stExpander"] details {
    background: var(--surface) !important;
    background-color: var(--surface) !important;
    border: 1px solid var(--border-strong) !important;
    border-radius: 12px !important;
    overflow: hidden !important;
    box-shadow: var(--shadow) !important;
}
[data-testid="stMain"] [data-testid="stExpander"] summary,
[data-testid="stMain"] [data-testid="stExpander"] details > summary,
[data-testid="stMain"] [data-testid="stExpander"] summary > div {
    background: var(--expander-header-bg) !important;
    background-color: var(--expander-header-bg) !important;
    color: var(--text) !important;
}
[data-testid="stMain"] [data-testid="stExpander"] summary,
[data-testid="stMain"] [data-testid="stExpander"] details > summary {
    padding: 13px 16px !important;
    border-bottom: 1px solid var(--border) !important;
    transition: background-color .15s ease !important;
}
[data-testid="stMain"] [data-testid="stExpander"] details:not([open]) > summary {
    border-bottom: 0 !important;
}
[data-testid="stMain"] [data-testid="stExpander"] summary:hover,
[data-testid="stMain"] [data-testid="stExpander"] details > summary:hover,
[data-testid="stMain"] [data-testid="stExpander"] summary:hover > div {
    background: var(--surface2) !important;
    background-color: var(--surface2) !important;
}
[data-testid="stMain"] [data-testid="stExpander"] summary :is(p, span, div, strong) {
    color: var(--text) !important;
    -webkit-text-fill-color: var(--text) !important;
    font-size: 13.5px !important;
    font-weight: 750 !important;
}
[data-testid="stMain"] [data-testid="stExpander"] summary svg {
    color: var(--muted) !important;
    fill: var(--muted) !important;
}
[data-testid="stMain"] [data-testid="stExpander"] [data-testid="stExpanderDetails"],
[data-testid="stMain"] [data-testid="stExpander"] details > div {
    background: var(--surface) !important;
    background-color: var(--surface) !important;
    color: var(--text) !important;
    padding: 14px 18px 16px !important;
}
[data-testid="stMain"] [data-testid="stExpander"] [data-testid="stExpanderDetails"] :is(p, span, li, div) {
    color: var(--text) !important;
    font-size: 13px !important;
    line-height: 1.72 !important;
}

[data-testid="stMain"] [data-testid="stAlert"] {
    border: 1px solid var(--border-strong) !important; border-radius: 10px !important; background: var(--surface2) !important;
}
[data-testid="stMain"] [data-testid="stAlert"] :is(p, span, div, li, strong) { color: var(--text) !important; }
[data-testid="stMain"] [data-testid="stAlert"]:has([data-testid="stAlertContentInfo"]) { background: var(--primary-soft) !important; border-color: var(--primary) !important; }
[data-testid="stMain"] [data-testid="stAlert"]:has([data-testid="stAlertContentWarning"]) { background: var(--warning-bg) !important; border-color: var(--warning) !important; }
[data-testid="stMain"] [data-testid="stAlert"]:has([data-testid="stAlertContentError"]) { background: var(--danger-bg) !important; border-color: var(--danger) !important; }
[data-testid="stMain"] [data-testid="stAlert"]:has([data-testid="stAlertContentSuccess"]) { background: var(--success-bg) !important; border-color: var(--success) !important; }
[data-testid="stMain"] [data-testid="stFileUploaderDropzone"] {
    background: var(--surface2) !important; border: 1px dashed var(--border-strong) !important; border-radius: 10px !important;
}
[data-testid="stMain"] [data-testid="stFileUploaderDropzone"] :is(span, small, p, div) {
    color: var(--muted) !important; white-space: normal !important; overflow: visible !important; text-overflow: clip !important;
}
[data-testid="stMain"] [data-testid="stSlider"] [data-testid*="TickBar"] { color: var(--muted) !important; opacity: 1 !important; }
[data-testid="stMain"] [data-testid="stTooltipIcon"] svg { color: var(--muted) !important; stroke: var(--muted) !important; }
[data-testid="stMain"] [data-testid="stMarkdownContainer"] code {
    background: var(--surface2) !important; color: var(--primary) !important;
    border: 1px solid var(--border) !important; border-radius: 6px !important; padding: .1em .45em !important;
}

/* ============ 13. Bảng dữ liệu hiện đại (.sg-table) ============ */
.sg-table-wrap {
    border: 1px solid var(--border-strong); border-radius: 12px; background: var(--surface);
    overflow: auto; margin-top: 8px; margin-bottom: 14px; box-shadow: var(--shadow);
}
.sg-table { width: 100%; border-collapse: separate; border-spacing: 0; font-size: 12.5px; }
.sg-table thead th {
    position: sticky; top: 0; z-index: 1; background: var(--surface2); color: var(--muted);
    font-size: 10.5px; font-weight: 800; letter-spacing: .07em; text-transform: uppercase;
    text-align: left; padding: 11px 14px; border-bottom: 1px solid var(--border-strong); white-space: nowrap;
}
.sg-table tbody td { padding: 11px 14px; color: var(--text); border-bottom: 1px solid var(--border); vertical-align: middle; }
.sg-table tbody tr:last-child td { border-bottom: 0; }
.sg-table tbody tr:nth-child(even) td { background: color-mix(in srgb, var(--surface2) 38%, transparent); }
.sg-table tbody tr:hover td { background: var(--primary-soft); }
.sg-table td.sg-id { font-weight: 800; color: var(--primary); font-variant-numeric: tabular-nums; white-space: nowrap; }
.sg-table td.sg-muted { color: var(--muted); font-variant-numeric: tabular-nums; white-space: nowrap; }
.sg-table td.sg-ellipsis { max-width: 280px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.sg-pill {
    display: inline-flex; align-items: center; gap: 6px; padding: 3px 10px; border-radius: 999px;
    font-size: 11px; font-weight: 700; white-space: nowrap; background: var(--rejected-bg); color: var(--rejected-text);
}
.sg-pill::before { content: ""; width: 6px; height: 6px; border-radius: 50%; background: currentColor; }
.sg-pill.ok { background: var(--success-bg); color: var(--success-text); }
.sg-pill.warn { background: var(--warning-bg); color: var(--warning-text); }
.sg-pill.bad { background: var(--danger-bg); color: var(--danger-text); }
.sg-pill.info { background: var(--primary-soft); color: var(--primary); }
.sg-pill.mute { background: var(--rejected-bg); color: var(--rejected-text); }
.sg-table-empty { padding: 22px; text-align: center; color: var(--muted); border: 1px dashed var(--border-strong); border-radius: 12px; margin-bottom: 14px; }

/* ============ 14. Khung nội dung (panel): nền + viền + bo góc + bóng, giống .panel của prototype ============ */
[data-testid="stMain"] [class*="st-key-panel_"]:not(.st-key-panel_assistant) {
    background: var(--surface) !important;
    border: 1px solid var(--border-strong) !important;
    border-radius: 16px !important;
    padding: 18px 20px !important;
    box-shadow: var(--shadow) !important;
}
[data-testid="stMain"] [class*="st-key-subpanel_"]:not([class*="st-key-subpanel_chat_"]) {
    background: var(--surface2) !important;
    border: 1px solid var(--border) !important;
    border-radius: 12px !important;
    padding: 14px 16px !important;
}

/* ============ 16. Tinh chỉnh nguyên tắc thiết kế: phản hồi, tương phản, rõ ràng ============ */
/* Phản hồi: vòng focus rõ cho thao tác bàn phím + hiệu ứng nhấn nút */
:is(button, summary, input, textarea, [role="button"], [data-baseweb="select"] > div):focus-visible {
    outline: 2px solid var(--primary) !important; outline-offset: 2px !important;
}
[data-testid="stMain"] button:not(:disabled):active { transform: translateY(1px); }
/* Giữ nội dung trang hiện tại hiển thị đầy đủ trong lúc chờ dựng trang mới (không mờ đi gây cảm giác chậm) */
[data-stale="true"], [data-testid="stElementContainer"][data-stale="true"] { opacity: 1 !important; transition: none !important; }

/* Tương phản + nhất quán: thao tác nguy hiểm (Dừng khẩn cấp + Làm mới dữ liệu ca trực) luôn mang màu đỏ, tách khỏi nút thường */
[data-testid="stMain"] :is([class*="st-key-em_stop_"], [class*="st-key-estop_"], .st-key-scan_btn_reset_shift) button {
    background: var(--danger-bg) !important; color: var(--danger-text) !important;
    border: 1px solid var(--danger) !important; font-weight: 700 !important;
}
[data-testid="stMain"] :is([class*="st-key-em_stop_"], [class*="st-key-estop_"], .st-key-scan_btn_reset_shift) button:hover {
    background: var(--danger) !important; color: #FFFFFF !important; border-color: var(--danger) !important;
}
[data-testid="stMain"] :is([class*="st-key-em_stop_"], [class*="st-key-estop_"], .st-key-scan_btn_reset_shift) button :is(p, span) { color: inherit !important; }

/* Hộp thoại xác nhận (hiển thị ngoài vùng chính nên cần tự định kiểu cho cả Sáng/Tối) */
[data-testid="stDialog"] div[role="dialog"] {
    background: var(--surface) !important; color: var(--text) !important;
    border: 1px solid var(--border-strong) !important; border-radius: 16px !important;
}
[data-testid="stDialog"] :is(p, span, li, h1, h2, h3, label, strong) { color: var(--text) !important; }
[data-testid="stDialog"] button[kind="secondary"], [data-testid="stDialog"] [data-testid="stBaseButton-secondary"] {
    background: var(--btn-bg) !important; color: var(--text) !important;
    border: 1px solid var(--btn-border) !important; border-radius: 8px !important; min-height: 38px !important; font-weight: 600 !important;
}
[class*="st-key-dlg_confirm_wrap"] button {
    background: var(--danger) !important; border: 1px solid var(--danger) !important; color: #FFFFFF !important;
    border-radius: 8px !important; min-height: 38px !important; font-weight: 700 !important;
}
[class*="st-key-dlg_confirm_wrap"] button :is(p, span) { color: #FFFFFF !important; }

/* Phân cấp: thẻ "Cần giám sát duyệt lại" nổi bật khi còn việc tồn đọng */
.sg-kpi-card.needs-action { box-shadow: 0 0 0 2px var(--warning-bg), var(--shadow) !important; background: color-mix(in srgb, var(--warning-bg) 40%, var(--surface)) !important; }

/* Phản hồi trạng thái hệ thống trên tiêu đề trang */
.sg-top-status.warn { background: var(--warning-bg) !important; color: var(--warning-text) !important; border-color: var(--warning) !important; }
.sg-top-status.busy { background: var(--primary-soft) !important; color: var(--primary) !important; border-color: var(--primary) !important; }
.sg-top-status.warn .sg-dot, .sg-top-status.busy .sg-dot { background: currentColor !important; }

"""

OVERRIDE_CSS = (
    OVERRIDE_CSS
    .replace("__SEC__", _SEC)
    .replace("__PRI__", _PRI)
    .replace("__ROW5__", _ROW5)
    .replace("__NAV_ICONS__", _nav_icon_css())
    .replace("__UPLOAD_BOX_SVG__", _UPLOAD_BOX_SVG_URI)
)


def _split_top_level(selector_list: str):
    """Tách danh sách selector theo dấu phẩy ở độ sâu 0 (không tách dấu phẩy trong :is(...))."""
    parts, depth, buf = [], 0, []
    for ch in selector_list:
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
    if "".join(buf).strip():
        parts.append("".join(buf).strip())
    return parts


def _boost_specificity(css: str) -> str:
    """
    Thêm tiền tố `html:not(#sg)` vào mọi selector để có độ ưu tiên cỡ ID (1,0,1).
    """
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    out = []
    for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", css):
        sels = _split_top_level(m.group(1).strip())
        boosted = ",\n".join("html:not(#sg) " + s for s in sels)
        out.append(boosted + " {" + m.group(2).strip() + "}")
    return "\n".join(rules for rules in out)


OVERRIDE_CSS = _boost_specificity(OVERRIDE_CSS)

# Sidebar thu gọn: chỉ còn logo + icon điều hướng (rộng 72px)
COLLAPSED_CSS = _boost_specificity("""
[data-testid="stSidebar"] { width: 72px !important; min-width: 72px !important; max-width: 72px !important; }
[data-testid="stSidebarContent"] > :not([data-testid="stSidebarHeader"]),
[data-testid="stSidebarUserContent"] { padding: 18px 10px 14px !important; }
[data-testid="stSidebar"] .sg-brand { justify-content: center !important; gap: 0 !important; padding: 0 0 16px !important; margin-bottom: 16px !important; width: 100% !important; }
[data-testid="stSidebar"] .sg-brand > div:not(.sg-logo) { display: none !important; }
[data-testid="stSidebar"] .sg-side-label { display: none !important; }
[data-testid="stSidebar"] .st-key-sb_footer { display: none !important; }
[data-testid="stSidebar"] [class*="st-key-nav_btn_"] button,
[data-testid="stSidebar"] .st-key-sb_toggle_btn button {
    width: 100% !important; justify-content: center !important; padding: 0 !important; gap: 0 !important;
    min-height: 44px !important; height: 44px !important; position: relative !important;
    box-shadow: none !important; border-left: 0 !important;
}
[data-testid="stSidebar"] [class*="st-key-nav_btn_"] button > div,
[data-testid="stSidebar"] .st-key-sb_toggle_btn button > div { display: none !important; }
[data-testid="stSidebar"] [class*="st-key-nav_btn_"] button::before { flex: 0 0 22px; width: 22px; height: 22px; margin: 0 auto; }
[data-testid="stSidebar"] .st-key-sb_toggle_btn button > div:first-child { display: flex !important; flex: 0 0 auto !important; width: auto !important; }
[data-testid="stSidebar"] .st-key-sb_toggle_btn button p { display: none !important; }
[data-testid="stSidebar"] .st-key-sb_toggle_btn button [data-testid="stIconMaterial"] { font-size: 22px !important; margin: 0 !important; }
[data-testid="stSidebar"] [class*="st-key-nav_btn_"] :is(button[kind="primary"], [data-testid="stBaseButton-primary"]) { box-shadow: inset 3px 0 #7895FF !important; }
[data-testid="stSidebar"] [class*="st-key-nav_btn_"] button::after {
    position: absolute !important; top: 7px; right: 10px; margin: 0 !important; padding: 0 !important;
    min-width: 9px !important; width: 9px; height: 9px !important; font-size: 0 !important;
}
""")

# Đọc và biên dịch sẵn toàn bộ các tổ hợp <style> vào RAM đúng 1 lần khi nạp module
_RAW_BASE_CSS = CSS_PATH.read_text(encoding="utf-8") if CSS_PATH.is_file() else ""
_CLEAN_BASE_CSS = re.sub(r"@import\s+url\([^)]+\)\s*;", "", _RAW_BASE_CSS)

# CSS thô: @keyframes không đi qua _boost_specificity
_EXTRA_RAW_CSS = """
.stApp[data-teststate="running"]::before {
    content: ""; position: fixed; left: 0; top: 0; width: 100%; height: 3px; z-index: 1000000; pointer-events: none;
    background: linear-gradient(90deg, transparent 0, var(--primary) 45%, var(--primary) 55%, transparent 100%) no-repeat;
    background-size: 45% 100%; animation: sg-run 1s linear infinite;
}
@keyframes sg-run { 0% { background-position: -60% 0; } 100% { background-position: 160% 0; } }
@media (prefers-reduced-motion: reduce) {
    .stApp[data-teststate="running"]::before { animation: none; background: var(--primary); opacity: .55; }
    * { transition-duration: .01ms !important; animation-duration: .01ms !important; }
}
"""

_STYLE_TAG_CACHE: dict[tuple[str, bool], str] = {}
for _m_key, _m_css in (("light", LIGHT_VARS_CSS), ("dark", DARK_VARS_CSS), ("system", SYSTEM_VARS_CSS)):
    for _col_flag in (False, True):
        _col_part = COLLAPSED_CSS if _col_flag else ""
        _STYLE_TAG_CACHE[(_m_key, _col_flag)] = (
            f"<style>\n{FONT_IMPORT}{_CLEAN_BASE_CSS}\n{_m_css}\n{OVERRIDE_CSS}\n{_col_part}\n{_EXTRA_RAW_CSS}\n</style>"
        )


def apply_ui_theme():
    """Áp dụng bộ stylesheet đã biên dịch sẵn trong RAM (< 0.001ms, 0 đọc đĩa cứng)."""
    mode = st.session_state.get("theme_mode", "light")
    if mode not in ("light", "dark", "system"):
        mode = "light"
    collapsed = bool(st.session_state.get("sidebar_collapsed", False))
    st.markdown(_STYLE_TAG_CACHE[(mode, collapsed)], unsafe_allow_html=True)