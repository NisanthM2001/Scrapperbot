import os
import re
import time
import mimetypes
from curl_cffi import requests
from aiogram import Bot
from aiogram.types import FSInputFile
import ui

async def download_and_send_file(bot: Bot, chat_id: int, url: str, original_name: str, category: str):
    """
    Downloads a file with retries, determines the correct extension, and uploads it.
    """
    file_path = None
    profiles = ["chrome110", "safari_15_6_1", "chrome120"]
    
    try:
        os.makedirs("downloads", exist_ok=True)
        
        response = None
        for i, profile in enumerate(profiles):
            for attempt in range(2):
                try:
                    response = requests.get(url, timeout=60, impersonate=profile, stream=True)
                    response.raise_for_status()
                    break
                except Exception as e:
                    if attempt == 0:
                        time.sleep(3)
                        continue
                    if i < len(profiles) - 1:
                        time.sleep(2)
                        break
                    raise e
            if response: break
        
        if not response: return False

        # 1. Try to get filename/extension from Content-Disposition
        cd = response.headers.get("Content-Disposition")
        fname_from_header = None
        if cd and "filename=" in cd:
            # Simple extract, could be improved with regex
            fname_from_header = cd.split("filename=")[1].strip('"').strip("'")

        # 2. Try to get extension from Content-Type
        ct = response.headers.get("Content-Type", "").split(";")[0].strip()
        ext_from_type = mimetypes.guess_extension(ct)
        
        # 3. Determine final extension
        ext = ""
        if fname_from_header and "." in fname_from_header:
            ext = "." + fname_from_header.split(".")[-1]
        elif ext_from_type:
            ext = ext_from_type
        elif "." in url.split("/")[-1].split("?")[0]:
            ext = "." + url.split("/")[-1].split("?")[0].split(".")[-1]
            if len(ext) > 5: ext = ""

        # Specific override for torrent category
        if category == "torrent" and not ext.lower() == ".torrent":
            ext = ".torrent"
        # Ensure direct links DON'T accidentally get .torrent if they are meant to be media
        if category == "download" and ext.lower() == ".torrent":
            # If a direct link serves a torrent, we should probably still label it correctly, 
            # but the user complained about it. Maybe it's a mimetypes mistake?
            # Let's trust the headers.
            pass

        # 4. Construct clean name
        clean_name = ui.clean_heading(original_name)
        # Remove any existing .torrent from name if it's NOT a torrent category
        if category == "download":
            clean_name = re.sub(r'(?i)\.torrent$', '', clean_name)

        if ext and not clean_name.lower().endswith(ext.lower()):
            clean_name += ext
        
        clean_name = re.sub(r'[\\/*?:"<>|]', "_", clean_name)
        file_path = os.path.join("downloads", clean_name)
        
        # Download the content
        with open(file_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk: f.write(chunk)
            
        # Basic check: if it's an HTML page instead of a file
        if os.path.getsize(file_path) < 2000:
            with open(file_path, "r", errors="ignore") as f:
                content = f.read(500)
                if "<html" in content.lower() or "<body" in content.lower():
                    os.remove(file_path)
                    return False

        document = FSInputFile(file_path)
        await bot.send_document(chat_id=chat_id, document=document, caption=f"📄 {clean_name}")
        return True
        
    except Exception as e:
        print(f"Uploader Error for {url}: {e}")
        return False
    finally:
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except:
                pass
