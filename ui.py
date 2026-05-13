import re
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# --- Button Labels ---
LABEL_MAGNET = "🧲 Magnet Links"
LABEL_TORRENT = "📄 Torrent Files"
LABEL_DIRECT = "🔗 Direct Links"
LABEL_RAW = "🧬 Raw Magnets"
LABEL_SEND_ALL = "📤 Send All"
LABEL_BACK = "🔙 Back"

# --- Message Templates ---
def get_welcome_msg(user_name, bot_name):
    return (
        f"🚀 <b>Welcome {user_name}!</b>\n\n"
        f"I am <b>{bot_name}</b>.\n"
        "Send me any website link to extract files and magnets.\n\n"
        "Adjust your experience in settings:"
    )

def build_welcome_menu():
    buttons = [
        [InlineKeyboardButton(text="⚙️ Settings", callback_data="open_settings")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

MSG_ANALYZING = "🔍 Analyzing webpage structures..."
MSG_EXPIRED = "⚠️ <b>Session Expired!</b>\nThe data for this link has expired. Please send the URL again to re-scrape."
MSG_DELIVERING = "📦 Delivering file..."
MSG_NO_LINKS = "😕 No valid links were detected on the page."
MSG_NO_TARGETS = "😕 No targeted link types found."
MSG_ADMIN_ONLY = "⛔️ <b>Access Denied!</b>\nOnly administrators can modify this setting."

def get_main_menu_text(page_title):
    return f"🎬 <b>Target:</b> {page_title}\n\n✅ <b>Scraping complete.</b>\nPlease select a link category:"

def get_category_title(action):
    titles = {
        "magnet": "🧲 <b>Magnet Links</b>",
        "torrent": "📄 <b>Torrent Files</b>",
        "download": "🔗 <b>Direct Links</b>",
        "raw_magnet": "🧬 <b>Raw Magnets</b>"
    }
    return titles.get(action, "<b>Links</b>")

def get_delivery_complete_msg(category):
    label = get_category_title(category).replace("<b>", "").replace("</b>", "").strip()
    return f"✅ <b>All {label} have been delivered!</b>"

def get_upload_fail_msg(heading):
    return f"❌ <b>Failed to upload file:</b> {heading}"

# --- Settings ---
def build_settings_choice_menu():
    buttons = [
        [InlineKeyboardButton(text="👤 User Settings", callback_data="user_settings")],
        [InlineKeyboardButton(text="🔐 Admin Settings", callback_data="admin_settings")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="menu_welcome")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_user_settings_msg(prefs):
    upload_status = "✅ Enabled" if prefs.get("upload_file", True) else "❌ Disabled"
    pref_cat = prefs.get("default_category", "ask").replace("_", " ").title()
    if pref_cat == "Ask": pref_cat = "Ask Every Time"
    
    return (
        "👤 <b>User Settings</b>\n\n"
        f"📂 <b>Torrent File Upload:</b> {upload_status}\n"
        "<i>(If enabled, torrent files are uploaded directly to Telegram. If disabled, a download link will be sent instead.)</i>\n\n"
        f"🎯 <b>Default Category:</b> {pref_cat}\n\n"
        "Adjust your personal preferences below:"
    )

def build_user_settings_menu():
    buttons = [
        [InlineKeyboardButton(text="📂 Torrent File Upload", callback_data="toggle_upload")],
        [InlineKeyboardButton(text="🎯 Set Default Category", callback_data="set_pref_cat")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="open_settings")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_admin_settings_msg(prefs):
    expiry = prefs.get("expiry_minutes", 10)
    page_size = prefs.get("page_size", 6)
    return (
        "🔐 <b>Admin Control Panel</b>\n\n"
        f"⏱ <b>Session Expiry:</b> {expiry} minutes\n"
        f"📏 <b>Links Per Page:</b> {page_size}\n\n"
        "Manage global bot behaviors:"
    )

def build_admin_settings_menu():
    buttons = [
        [InlineKeyboardButton(text="⏱ Set Session Expiry", callback_data="set_expiry")],
        [InlineKeyboardButton(text="📏 Set Page Size", callback_data="set_pagesize")],
        [InlineKeyboardButton(text="🔄 Restart Bot", callback_data="restart_bot")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="open_settings")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def build_expiry_menu():
    buttons = [
        [InlineKeyboardButton(text="5 Minutes", callback_data="expiry_5")],
        [InlineKeyboardButton(text="10 Minutes", callback_data="expiry_10")],
        [InlineKeyboardButton(text="30 Minutes", callback_data="expiry_30")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="admin_settings")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def build_pagesize_menu():
    buttons = [
        [InlineKeyboardButton(text="4 Items", callback_data="pagesize_4")],
        [InlineKeyboardButton(text="6 Items", callback_data="pagesize_6")],
        [InlineKeyboardButton(text="8 Items", callback_data="pagesize_8")],
        [InlineKeyboardButton(text="10 Items", callback_data="pagesize_10")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="admin_settings")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def build_pref_cat_menu():
    buttons = [
        [InlineKeyboardButton(text="🧲 Magnets", callback_data="prefcat_magnet")],
        [InlineKeyboardButton(text="📄 Torrents", callback_data="prefcat_torrent")],
        [InlineKeyboardButton(text="🔗 Direct Links", callback_data="prefcat_download")],
        [InlineKeyboardButton(text="🧬 Raw Magnets", callback_data="prefcat_raw_magnet")],
        [InlineKeyboardButton(text="❓ Ask Every Time", callback_data="prefcat_ask")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="user_settings")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# --- Paged List UI ---

def get_paged_list_text(items, category, page, page_size):
    filtered = [(h, l) for h, l in items if l.get(category)]
    start = page * page_size
    end = start + page_size
    page_items = filtered[start:end]
    cat_title = get_category_title(category)
    text = f"{cat_title}\n\n"
    for i, (heading, _) in enumerate(page_items):
        display_num = start + i + 1
        text += f"<b>{display_num}.</b> {heading}\n\n"
    total_pages = (len(filtered) + page_size - 1) // page_size
    text += f"📄 <b>Page {page+1} / {total_pages}</b>"
    return text

def build_paged_list_menu(items, category, page, page_size):
    filtered = [(h, l) for h, l in items if l.get(category)]
    start = page * page_size
    end = min(start + page_size, len(filtered))
    count = end - start
    buttons = []
    row = []
    row_max = 4 if page_size > 6 else 3
    for i in range(count):
        display_num = start + i + 1
        actual_idx = start + i
        row.append(InlineKeyboardButton(text=str(display_num), callback_data=f"send_{category}_{actual_idx}"))
        if len(row) == row_max:
            buttons.append(row)
            row = []
    if row: buttons.append(row)
    nav_row = []
    if page > 0: nav_row.append(InlineKeyboardButton(text="◀️ Previous", callback_data=f"page_{category}_{page-1}"))
    if end < len(filtered): nav_row.append(InlineKeyboardButton(text="Next Page ⏩", callback_data=f"page_{category}_{page+1}"))
    if nav_row: buttons.append(nav_row)
    buttons.append([InlineKeyboardButton(text=LABEL_BACK, callback_data=f"menu_{category}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def build_category_menu(items, category, show_back=True):
    buttons = [
        [InlineKeyboardButton(text="📤 Send All (Loop)", callback_data=f"sendall_{category}")],
        [InlineKeyboardButton(text="📑 Select Files (Numbered List)", callback_data=f"page_{category}_0")]
    ]
    if show_back:
        buttons.append([InlineKeyboardButton(text="🔙 Back to Main", callback_data="menu_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# --- UI Logic ---

def clean_heading(raw_text):
    if not raw_text: return "Unknown File"
    cleaned = re.sub(r'(?i)^(?:www\.)?[a-z0-9-]+\.[a-z]{2,6}(?:\.[a-z]{2,6})?\s*[-–:]+\s*', '', raw_text).strip()
    if not cleaned: return raw_text[:200]
    return cleaned[:200]

def build_main_menu(items):
    has_magnet = any(links.get("magnet") for _, links in items)
    has_torrent = any(links.get("torrent") for _, links in items)
    has_direct = any(links.get("download") for _, links in items)
    has_raw = any(links.get("raw_magnet") for _, links in items)
    buttons = []
    if has_magnet: buttons.append([InlineKeyboardButton(text=LABEL_MAGNET, callback_data="menu_magnet")])
    if has_torrent: buttons.append([InlineKeyboardButton(text=LABEL_TORRENT, callback_data="menu_torrent")])
    if has_direct: buttons.append([InlineKeyboardButton(text=LABEL_DIRECT, callback_data="menu_download")])
    if has_raw: buttons.append([InlineKeyboardButton(text=LABEL_RAW, callback_data="menu_raw_magnet")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)
