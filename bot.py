import re
import asyncio
import time
import os
import sys
import subprocess
from curl_cffi import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, unquote
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command

import config
import ui
import uploader
import database

# Define search patterns
MAGNET_PATTERN = re.compile(r"magnet:\?xt=urn:[a-z0-9]+:[a-zA-Z0-9]+", re.IGNORECASE)
DOWNLOAD_PATTERN = re.compile(r"\.(zip|rar|mp4|exe|7z|mkv|iso|dmg|apk)$", re.IGNORECASE)
DIRECT_HOSTS = re.compile(r"(gdtot|hubdrive|sharer\.pw|filepress|drive\.google\.com|cloud|multiup|droplink)", re.IGNORECASE)

dp = Dispatcher()

def get_best_heading(link_tag):
    """Attempts to find the most descriptive heading for a given link tag."""
    link_text = link_tag.get_text(strip=True)
    link_text_upper = link_text.upper()
    
    # 1. If the link text itself is descriptive (and not just "Download" or "Magnet")
    if link_text and len(link_text) > 8 and link_text_upper not in ["MAGNET LINK", "DIRECT LINK", "DOWNLOAD NOW", "TORRENT DOWNLOAD", "DOWNLOAD"]:
        return ui.clean_heading(link_text)
    
    # 2. Look for the nearest preceding text node or heading tag
    curr = link_tag
    for _ in range(10): # Look up through parents
        # Look for previous siblings of the current ancestor
        prev = curr.find_previous(string=lambda t: t and len(t.strip()) > 10)
        if prev:
            text = prev.strip()
            # Avoid picking up generic button labels as headings
            if text.upper() not in ["MAGNET", "TORRENT", "DOWNLOAD", "MIRROR", "LINK"]:
                return ui.clean_heading(text)
        
        # Check if the parent itself has a descriptive class or ID that might hint at quality
        if curr.parent:
            curr = curr.parent
        else:
            break
            
    return "Unknown File"

def scrape_url_for_links(target_url):
    """
    Parses the provided URL and extracts all links with robust context detection.
    """
    profiles = ["chrome120", "chrome110", "safari_15_6_1"]
    last_error = ""
    response = None
    target_url = target_url.strip()
    for i, profile in enumerate(profiles):
        try:
            response = requests.get(target_url, timeout=25, impersonate=profile)
            if response.status_code == 200: break
            else: last_error = f"Status {response.status_code}"
        except Exception as e:
            last_error = str(e)
            if i < len(profiles) - 1:
                time.sleep(2)
                continue
            return f"Error: {last_error}"
    try:
        if not response or not response.text: return f"Error: {last_error or 'No content'}"
        soup = BeautifulSoup(response.text, 'html.parser')
        raw_title = soup.title.string.strip() if soup.title else target_url
        page_title = ui.clean_heading(raw_title)
        
        items = [] # Use a list to maintain order and allow multiple items with same name
        seen_magnets = set()
        seen_torrents = set()
        seen_downloads = set()
        
        for link in soup.find_all('a'):
            href = link.get('href', '')
            
            # Robust Magnet Extraction
            magnet_link = None
            if MAGNET_PATTERN.search(href):
                magnet_link = href
            else:
                for attr, val in link.attrs.items():
                    if isinstance(val, str) and MAGNET_PATTERN.search(val):
                        magnet_link = val
                        break
            
            link_text_upper = link.get_text(strip=True).upper()
            is_magnet = magnet_link is not None
            is_torrent = href.lower().endswith('.torrent') or 'TORRENT' in link_text_upper or '/files/file/' in href.lower()
            is_direct = (not is_torrent) and (not is_magnet) and ('DIRECT LINK' in link_text_upper or 'DOWNLOAD' in link_text_upper or DOWNLOAD_PATTERN.search(href) or DIRECT_HOSTS.search(href))
            
            if is_magnet or is_torrent or is_direct:
                heading = get_best_heading(link)
                
                link_type = "magnet" if is_magnet else ("torrent" if is_torrent else "download")
                actual_link = magnet_link if is_magnet else urljoin(target_url, href)
                
                # Check for duplicates of the same link
                if is_magnet and actual_link in seen_magnets: continue
                if is_torrent and actual_link in seen_torrents: continue
                if is_direct and actual_link in seen_downloads: continue
                
                # Try to merge with an existing item if the heading is similar and the slot is empty
                merged = False
                for item_name, links in items:
                    if item_name == heading and links[link_type] is None:
                        links[link_type] = actual_link
                        merged = True
                        break
                
                if not merged:
                    # Create a new item
                    new_links = {"magnet": None, "torrent": None, "download": None, "raw_magnet": None}
                    new_links[link_type] = actual_link
                    
                    # Ensure heading uniqueness in the final list for UI purposes
                    final_heading = heading
                    suffix = 2
                    existing_headings = [name for name, _ in items]
                    while final_heading in existing_headings:
                        final_heading = f"{heading} ({suffix})"
                        suffix += 1
                        
                    items.append((final_heading, new_links))
                
                # Mark as seen
                if is_magnet: seen_magnets.add(actual_link)
                elif is_torrent: seen_torrents.add(actual_link)
                elif is_direct: seen_downloads.add(actual_link)
                        
        # Final sweep for raw magnets in text nodes
        seen_raw = set()
        for text_node in soup.find_all(string=MAGNET_PATTERN):
            rm_match = MAGNET_PATTERN.search(text_node)
            if not rm_match: continue
            rm = rm_match.group(0)
            if rm in seen_raw or rm in seen_magnets: continue
            seen_raw.add(rm)
            
            # Extract context for raw magnet
            dn_match = re.search(r'&dn=([^&]+)', rm)
            if dn_match: heading = ui.clean_heading(unquote(dn_match.group(1)).replace('+', ' '))
            else:
                nearby_text = ""
                curr = text_node.parent
                for _ in range(5):
                    if not curr: break
                    potential_text = curr.get_text(strip=True)
                    if len(potential_text) > len(rm) + 5:
                        nearby_text = potential_text.replace(rm, "").strip()
                        if len(nearby_text) > 10: break
                    curr = curr.parent
                if nearby_text: heading = ui.clean_heading(nearby_text)
                else:
                    hash_match = re.search(r'xt=urn:btih:([a-zA-Z0-9]+)', rm, re.IGNORECASE)
                    heading = f"Magnet Hash: {hash_match.group(1)[:10]}..." if hash_match else "Unknown Raw Magnet"
            
            # Add as a new raw magnet item
            final_heading = heading
            suffix = 2
            existing_headings = [name for name, _ in items]
            while final_heading in existing_headings:
                final_heading = f"{heading} ({suffix})"
                suffix += 1
            
            items.append((final_heading, {"magnet": None, "torrent": None, "download": None, "raw_magnet": rm}))
                
        return {"page_title": page_title, "items": items}
    except Exception as e: return f"Error: {str(e)}"

# --- Helpers ---
def is_session_active(user_id):
    scrape = database.get_scrape(user_id)
    if not scrape: return False
    prefs = database.get_prefs(user_id)
    elapsed_mins = (time.time() - scrape["created_at"]) / 60
    return elapsed_mins < prefs.get("expiry_minutes", 10)

def is_admin(user_id):
    return user_id == config.ADMIN_ID

async def restart_bot():
    """Restarts the current program with robust path handling for Windows."""
    await asyncio.sleep(2)
    script_path = os.path.abspath(sys.argv[0])
    python_path = sys.executable
    try:
        if os.name == 'nt':
            subprocess.Popen([python_path, script_path], 
                             creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
                             close_fds=True)
        else:
            os.execl(python_path, python_path, script_path)
    except: pass
    os._exit(0)

# --- Settings Handlers ---
@dp.message(Command("settings"))
@dp.callback_query(F.data == "open_settings")
async def cb_open_settings(event):
    text = "⚙️ <b>Settings Menu</b>\nSelect setting type:"
    markup = ui.build_settings_choice_menu()
    if isinstance(event, Message): await event.reply(text, reply_markup=markup, parse_mode="HTML")
    else: await event.message.edit_text(text, reply_markup=markup, parse_mode="HTML")

@dp.callback_query(F.data == "user_settings")
async def cb_user_settings(cq: CallbackQuery):
    prefs = database.get_prefs(cq.from_user.id)
    await cq.message.edit_text(ui.get_user_settings_msg(prefs), reply_markup=ui.build_user_settings_menu(), parse_mode="HTML")

@dp.callback_query(F.data == "admin_settings")
async def cb_admin_settings(cq: CallbackQuery):
    if not is_admin(cq.from_user.id): return await cq.answer("⛔️ Only admin will use this setting", show_alert=True)
    prefs = database.get_prefs(cq.from_user.id)
    await cq.message.edit_text(ui.get_admin_settings_msg(prefs), reply_markup=ui.build_admin_settings_menu(), parse_mode="HTML")

@dp.callback_query(F.data == "menu_welcome")
async def cb_menu_welcome(cq: CallbackQuery):
    await cq.message.edit_text(ui.get_welcome_msg(cq.from_user.first_name, config.BOT_NAME), reply_markup=ui.build_welcome_menu(), parse_mode="HTML")

@dp.message(Command("restart"))
async def cmd_restart(message: Message):
    if not is_admin(message.from_user.id): return
    await message.reply("🔄 <b>Restarting bot...</b>", parse_mode="HTML")
    await restart_bot()

@dp.callback_query(F.data == "restart_bot")
async def cb_restart_bot(cq: CallbackQuery):
    if not is_admin(cq.from_user.id): return
    await cq.message.edit_text("🔄 <b>Restarting bot...</b>", parse_mode="HTML")
    await restart_bot()

@dp.callback_query(F.data == "toggle_upload")
async def cb_toggle_upload(cq: CallbackQuery):
    prefs = database.get_prefs(cq.from_user.id)
    prefs["upload_file"] = not prefs["upload_file"]
    database.save_prefs(cq.from_user.id, prefs)
    await cq.answer(f"Torrent Upload: {'Enabled' if prefs['upload_file'] else 'Disabled'}")
    await cb_user_settings(cq)

@dp.callback_query(F.data == "set_pref_cat")
async def cb_set_pref_cat(cq: CallbackQuery):
    await cq.message.edit_text("🎯 <b>Select default category:</b>", reply_markup=ui.build_pref_cat_menu(), parse_mode="HTML")

@dp.callback_query(F.data.startswith("prefcat_"))
async def cb_save_pref_cat(cq: CallbackQuery):
    prefs = database.get_prefs(cq.from_user.id)
    prefs["default_category"] = cq.data.replace("prefcat_", "")
    database.save_prefs(cq.from_user.id, prefs)
    await cq.answer(f"Default set to: {prefs['default_category']}")
    await cb_user_settings(cq)

@dp.callback_query(F.data == "set_expiry")
async def cb_set_expiry(cq: CallbackQuery):
    if not is_admin(cq.from_user.id): return
    await cq.message.edit_text("⏱ <b>Set Session Expiry:</b>", reply_markup=ui.build_expiry_menu(), parse_mode="HTML")

@dp.callback_query(F.data.startswith("expiry_"))
async def cb_save_expiry(cq: CallbackQuery):
    if not is_admin(cq.from_user.id): return
    prefs = database.get_prefs(cq.from_user.id)
    prefs["expiry_minutes"] = int(cq.data.replace("expiry_", ""))
    database.save_prefs(cq.from_user.id, prefs)
    await cq.answer(f"Expiry set to: {prefs['expiry_minutes']}m")
    await cb_admin_settings(cq)

@dp.callback_query(F.data == "set_pagesize")
async def cb_set_pagesize(cq: CallbackQuery):
    if not is_admin(cq.from_user.id): return
    await cq.message.edit_text("📏 <b>Set Links Per Page:</b>", reply_markup=ui.build_pagesize_menu(), parse_mode="HTML")

@dp.callback_query(F.data.startswith("pagesize_"))
async def cb_save_pagesize(cq: CallbackQuery):
    if not is_admin(cq.from_user.id): return
    prefs = database.get_prefs(cq.from_user.id)
    prefs["page_size"] = int(cq.data.replace("pagesize_", ""))
    database.save_prefs(cq.from_user.id, prefs)
    await cq.answer(f"Page size set to: {prefs['page_size']}")
    await cb_admin_settings(cq)

# --- Core Handlers ---
@dp.message(CommandStart())
async def send_welcome(message: Message):
    await message.reply(ui.get_welcome_msg(message.from_user.first_name, config.BOT_NAME), reply_markup=ui.build_welcome_menu(), parse_mode="HTML")

@dp.message()
async def handle_url(message: Message):
    if not message.text or not message.text.lower().startswith(('http://', 'https://')): return
    progress_msg = await message.reply(ui.MSG_ANALYZING)
    loop = asyncio.get_event_loop()
    try:
        result = await asyncio.wait_for(loop.run_in_executor(None, scrape_url_for_links, message.text.strip()), timeout=90)
    except asyncio.TimeoutError: return await progress_msg.edit_text("❌ <b>Scraping Timeout</b>", parse_mode="HTML")
    except Exception as e: return await progress_msg.edit_text(f"❌ <b>Error:</b> {str(e)}", parse_mode="HTML")
    if isinstance(result, str): return await progress_msg.edit_text(f"❌ <b>Error:</b> {result}", parse_mode="HTML")
    if not result["items"]: return await progress_msg.edit_text(ui.MSG_NO_LINKS, parse_mode="HTML")
    database.save_scrape(message.from_user.id, message.text.strip(), result["page_title"], result["items"])
    prefs = database.get_prefs(message.from_user.id)
    def_cat = prefs.get("default_category", "ask")
    if def_cat != "ask" and any(links.get(def_cat) for _, links in result["items"]):
        return await progress_msg.edit_text(f"🚀 <b>{result['page_title']}</b>\nSelect Delivery Mode:", reply_markup=ui.build_category_menu(result["items"], def_cat, show_back=False), parse_mode="HTML")
    await progress_msg.edit_text(ui.get_main_menu_text(result["page_title"]), reply_markup=ui.build_main_menu(result["items"]), parse_mode="HTML")

@dp.callback_query(F.data.startswith("menu_"))
async def handle_menu_navigation(cq: CallbackQuery):
    action = cq.data.replace("menu_", "")
    if not is_session_active(cq.from_user.id): return await cq.message.edit_text(ui.MSG_EXPIRED, parse_mode="HTML")
    data = database.get_scrape(cq.from_user.id)
    if action == "main" or action == "main_settings":
        await cq.message.edit_text(ui.get_main_menu_text(ui.clean_heading(data["title"])), reply_markup=ui.build_main_menu(data["items"]), parse_mode="HTML")
    else: 
        prefs = database.get_prefs(cq.from_user.id)
        show_back = True if prefs.get("default_category", "ask") == "ask" else False
        await cq.message.edit_text(f"{ui.get_category_title(action)}\nSelect Delivery Mode:", reply_markup=ui.build_category_menu(data["items"], action, show_back=show_back), parse_mode="HTML")

@dp.callback_query(F.data.startswith("page_"))
async def handle_paged_navigation(cq: CallbackQuery):
    if not is_session_active(cq.from_user.id): return await cq.message.edit_text(ui.MSG_EXPIRED, parse_mode="HTML")
    data = database.get_scrape(cq.from_user.id)
    parts = cq.data.split("_")
    category = "raw_magnet" if parts[1] == "raw" else parts[1]
    page = int(parts[3]) if parts[1] == "raw" else int(parts[2])
    prefs = database.get_prefs(cq.from_user.id)
    await cq.message.edit_text(ui.get_paged_list_text(data["items"], category, page, prefs["page_size"]), reply_markup=ui.build_paged_list_menu(data["items"], category, page, prefs["page_size"]), parse_mode="HTML")

async def deliver_link(bot, chat_id, heading, links, category, prefs):
    link = links.get(category)
    if not link: return
    if category == "torrent" and prefs.get("upload_file", True):
        await bot.send_chat_action(chat_id, "upload_document")
        if await uploader.download_and_send_file(bot, chat_id, link, heading, category): return
        else: await bot.send_message(chat_id, ui.get_upload_fail_msg(heading), parse_mode="HTML")
    msg = f"🎬 <b>{heading}</b>\n\n"
    if category in ["magnet", "raw_magnet"]: msg += f"🧲 <b>Magnet:</b>\n<code>{link}</code>"
    elif category == "torrent": msg += f"📄 <b>Torrent:</b> <a href='{link}'>Download File</a>"
    elif category == "download": msg += f"🔗 <b>Direct Link:</b> <a href='{link}'>Download Here</a>"
    try: await bot.send_message(chat_id, msg, parse_mode="HTML", disable_web_page_preview=True)
    except: pass

@dp.callback_query(F.data.startswith("send_"))
async def handle_send_item(cq: CallbackQuery):
    if not is_session_active(cq.from_user.id): return await cq.answer(ui.MSG_EXPIRED, show_alert=True)
    data = database.get_scrape(cq.from_user.id)
    parts = cq.data.split("_")
    category = "raw_magnet" if parts[1] == "raw" else parts[1]
    idx = int(parts[3]) if parts[1] == "raw" else int(parts[2])
    filtered_items = [(h, l) for h, l in data["items"] if l.get(category)]
    try:
        heading, links = filtered_items[idx]
        await cq.answer(ui.MSG_DELIVERING)
        await deliver_link(cq.bot, cq.message.chat.id, heading, links, category, database.get_prefs(cq.from_user.id))
    except: await cq.answer("Error.", show_alert=True)

@dp.callback_query(F.data.startswith("sendall_"))
async def handle_send_all(cq: CallbackQuery):
    if not is_session_active(cq.from_user.id): return await cq.answer(ui.MSG_EXPIRED, show_alert=True)
    data = database.get_scrape(cq.from_user.id)
    category = cq.data.replace("sendall_", "")
    await cq.answer("Sending all...")
    count = 0
    for heading, links in data["items"]:
        if links.get(category):
            await deliver_link(cq.bot, cq.message.chat.id, heading, links, category, database.get_prefs(cq.from_user.id))
            count += 1
            await asyncio.sleep(1.5)
            if count >= 50: break
    if count > 0: await cq.message.answer(ui.get_delivery_complete_msg(category), parse_mode="HTML")

async def main():
    bot = Bot(token=config.BOT_TOKEN)
    try: await bot.send_message(config.ADMIN_ID, "✅ <b>Bot Online!</b>", parse_mode="HTML")
    except: pass
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
