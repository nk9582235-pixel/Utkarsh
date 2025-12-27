"""
Utkarsh Telegram Bot V2 - Fast Streaming Upload
Downloads and uploads simultaneously without saving to disk
"""
import asyncio
import os
import sys
import io
import time
import logging
import aiohttp
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import FloodWait
# Simple HTTP handler for Render health check
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'Bot is running!')
    def log_message(self, format, *args):
        pass  # Suppress logs
def start_health_server():
    port = int(os.environ.get('PORT', 10000))
    server = HTTPServer(('0.0.0.0', port), HealthHandler)
    server.serve_forever()
# Import config
try:
    from bot_config import (
        API_ID, API_HASH, BOT_TOKEN, ADMIN_IDS, 
        DOWNLOAD_PATH, MAX_FILE_SIZE_MB, PARALLEL_DOWNLOADS,
        UTKARSH_USERNAME, UTKARSH_PASSWORD, DESTINATION_CHAT_ID
    )
except ImportError:
    print("❌ Please configure bot_config.py with your credentials!")
    sys.exit(1)
# Import extractor
from utkarsh_extractor import UtkarshExtractor
# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)
# Create download directory
Path(DOWNLOAD_PATH).mkdir(parents=True, exist_ok=True)
# Initialize bot
app = Client("utkarsh_bot_v2", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
# State management
user_sessions = {}
def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS
def format_size(size_bytes):
    """Format bytes to human readable"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.2f}{unit}"
        size_bytes /= 1024
    return f"{size_bytes:.2f}TB"
def format_speed(bytes_per_sec):
    """Format speed to human readable"""
    return f"{bytes_per_sec / (1024*1024):.2f}MiB/s"
async def stream_upload_video(client: Client, chat_id: int, url: str, title: str, 
                              status_msg: Message, idx: int, total: int):
    """
    Stream video directly from URL to Telegram without saving to disk
    Uses chunked download/upload for speed
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0',
        'Referer': 'https://utkarshapp.com/',
    }
    
    start_time = time.time()
    downloaded = 0
    last_update_time = 0
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status != 200:
                    return False, f"HTTP {response.status}"
                
                total_size = int(response.headers.get('content-length', 0))
                
                if total_size == 0:
                    return False, "Unknown file size"
                
                if total_size > MAX_FILE_SIZE_MB * 1024 * 1024:
                    return False, f"Too large ({format_size(total_size)})"
                
                # Create in-memory buffer for streaming
                buffer = io.BytesIO()
                
                async for chunk in response.content.iter_chunked(1024 * 1024):  # 1MB chunks
                    buffer.write(chunk)
                    downloaded += len(chunk)
                    
                    # Update progress every 2 seconds
                    current_time = time.time()
                    if current_time - last_update_time >= 2:
                        elapsed = current_time - start_time
                        speed = downloaded / elapsed if elapsed > 0 else 0
                        percent = (downloaded / total_size) * 100 if total_size > 0 else 0
                        eta = (total_size - downloaded) / speed if speed > 0 else 0
                        
                        progress_bar = "➣" * int(percent / 5) + "━" * (20 - int(percent / 5))
                        
                        progress_text = f"""
📥 **𝐃𝐎𝐖𝐍𝐋𝐎𝐀𝐃𝐈𝐍𝐆 𝐕𝐈𝐃𝐄𝐎** 📥
🗃️ File Size: {format_size(total_size)}
📂 File Name: {title[:50]}...
╔══════════════════════════╗
╠  ✨ **𝐔𝐓𝐊𝐀𝐑𝐒𝐇 𝐁𝐎𝐓** ⁬
╚══════════════════════════╝
╭━━━━━━━━━━━━━━━━➣
┃  {progress_bar} ({percent:.1f}%)
┣⪼ 𝗦𝗣𝗘𝗘𝗗 ⚡ ➠ {format_speed(speed)}
┣⪼ 𝗟𝗢𝗔𝗗𝗘𝗗 🗂️ ➠ {format_size(downloaded)}
┣⪼ 𝗦𝗜𝗭𝗘 🧲 ➠ {format_size(total_size)}
┣⪼ 𝗘𝗧𝗔 ⏳ ➠ {int(eta)}s
┣⪼ [{idx}/{total}]
╰━━━━━━━━━━━━━━━━➣
"""
                        try:
                            await status_msg.edit_text(progress_text)
                        except:
                            pass
                        last_update_time = current_time
                
                # Upload to Telegram
                buffer.seek(0)
                buffer.name = f"{title[:50]}.mp4"
                
                # Update status for upload
                try:
                    await status_msg.edit_text(f"📤 **𝐔𝐏𝐋𝐎𝐀𝐃𝐈𝐍𝐆** [{idx}/{total}]\n\n🗃️ Size: {format_size(total_size)}\n📂 {title[:40]}...")
                except:
                    pass
                
                # Track upload progress
                upload_start = time.time()
                
                async def upload_progress(current, total):
                    nonlocal last_update_time
                    now = time.time()
                    if now - last_update_time >= 1:
                        elapsed = now - upload_start
                        speed = current / elapsed if elapsed > 0 else 0
                        percent = (current / total) * 100
                        progress_bar = "➣" * int(percent / 5) + "━" * (20 - int(percent / 5))
                        
                        try:
                            await status_msg.edit_text(f"""
📤 **𝐔𝐏𝐋𝐎𝐀𝐃𝐈𝐍𝐆 𝐕𝐈𝐃𝐄𝐎** 📤
🗃️ File Size: {format_size(total)}
📂 File Name: {title[:50]}...
╭━━━━━━━━━━━━━━━━➣
┃  {progress_bar} ({percent:.1f}%)
┣⪼ 𝗦𝗣𝗘𝗘𝗗 ⚡ ➠ {format_speed(speed)}
┣⪼ 𝗟𝗢𝗔𝗗𝗘𝗗 🗂️ ➠ {format_size(current)}
┣⪼ 𝗦𝗜𝗭𝗘 🧲 ➠ {format_size(total)}
┣⪼ [{idx}/{total}]
╰━━━━━━━━━━━━━━━━➣
""")
                        except:
                            pass
                        last_update_time = now
                
                # Send video to Telegram
                await client.send_video(
                    chat_id,
                    buffer,
                    caption=f"""
——— ✦ {idx} ✦ ———
🎞️ Title: {title}
📚 Course: Utkarsh Batch
🌟 Extracted By: Utkarsh Bot
""",
                    progress=upload_progress
                )
                
                return True, None
                
    except Exception as e:
        logger.error(f"Stream error: {e}")
        return False, str(e)
@app.on_message(filters.command("start") & filters.private)
async def start_command(client: Client, message: Message):
    if not is_admin(message.from_user.id):
        await message.reply("❌ You are not authorized to use this bot.")
        return
    
    welcome = """
🎓 **Utkarsh Video Bot V2** ⚡
*Fast Streaming Upload - No Disk Required!*
Commands:
• `/batch <id>` - Extract URLs from batch ID
• `/download` - Stream videos directly to Telegram
• `/setchannel <id>` - Set destination channel (0 = personal)
• `/status` - Check progress
• `/cancel` - Cancel current operation
Example: `/batch 19376`
"""
    await message.reply(welcome)
@app.on_message(filters.command("batch") & filters.private)
async def batch_command(client: Client, message: Message):
    if not is_admin(message.from_user.id):
        return
    
    args = message.text.split()
    if len(args) < 2:
        await message.reply("❌ Usage: `/batch 19376`")
        return
    
    batch_id = args[1]
    user_id = message.from_user.id
    
    status_msg = await message.reply(f"📥 Extracting batch **{batch_id}**...")
    
    try:
        extractor = UtkarshExtractor()
        
        # Login first
        if not extractor.login(UTKARSH_USERNAME, UTKARSH_PASSWORD):
            await status_msg.edit_text("❌ Login failed! Check credentials.")
            return
        
        await status_msg.edit_text(f"✅ Logged in! Extracting URLs...")
        
        urls, txt_file = extractor.extract_batch(batch_id)
        
        if not urls:
            await status_msg.edit_text("❌ No URLs found.")
            return
        
        user_sessions[user_id] = {
            'batch_id': batch_id,
            'urls': urls,
            'txt_file': txt_file,
            'downloading': False,
            'current_idx': 0
        }
        
        await status_msg.edit_text(f"✅ Extracted **{len(urls)}** videos!")
        if txt_file and os.path.exists(txt_file):
            await message.reply_document(
                txt_file,
                caption=f"📄 Batch {batch_id}\n🎬 {len(urls)} videos\n\nSend `/download` to start streaming!"
            )
        
    except Exception as e:
        logger.error(f"Extraction error: {e}")
        await status_msg.edit_text(f"❌ Error: {str(e)[:200]}")
@app.on_message(filters.command("setchannel") & filters.private)
async def setchannel_command(client: Client, message: Message):
    """Set destination channel for uploads"""
    if not is_admin(message.from_user.id):
        return
    
    user_id = message.from_user.id
    args = message.text.split()
    
    if len(args) < 2:
        current = user_sessions.get(user_id, {}).get('destination', DESTINATION_CHAT_ID)
        await message.reply(f"""
📍 **Set Destination Channel**
Current: `{current if current else 'Personal Chat'}`
Usage:
• `/setchannel 0` - Send to personal chat
• `/setchannel -1001234567890` - Send to channel
To get channel ID:
1. Add @userinfobot to channel
2. Forward any message from channel to it
""")
        return
    
    try:
        channel_id = int(args[1])
        if user_id not in user_sessions:
            user_sessions[user_id] = {}
        user_sessions[user_id]['destination'] = channel_id
        
        if channel_id == 0:
            await message.reply("✅ Videos will be sent to **personal chat**")
        else:
            await message.reply(f"✅ Videos will be sent to channel: `{channel_id}`")
    except ValueError:
        await message.reply("❌ Invalid channel ID. Use a number like `-1001234567890`")
@app.on_message(filters.command("download") & filters.private)
async def download_command(client: Client, message: Message):
    if not is_admin(message.from_user.id):
        return
    
    user_id = message.from_user.id
    session = user_sessions.get(user_id)
    
    if not session or not session.get('urls'):
        await message.reply("❌ No batch loaded. Use `/batch <id>` first.")
        return
    
    if session.get('downloading'):
        await message.reply("⏳ Already downloading!")
        return
    
    session['downloading'] = True
    urls = session['urls']
    total = len(urls)
    
    await message.reply(f"""
🚀 **𝐒𝐓𝐀𝐑𝐓𝐈𝐍𝐆 𝐃𝐎𝐖𝐍𝐋𝐎𝐀𝐃** 🚀
┠ 📊 Total Links = {total}
┠ ⚡️ Mode = Streaming (Fast!)
┠ 🔗 Batch = {session.get('batch_id')}
✨ 𝐏𝐎𝐖𝐄𝐑𝐄𝐃 𝐁𝐘: Utkarsh Bot
""")
    
    success = 0
    failed = 0
    
    for idx, (title, url) in enumerate(urls, 1):
        if not session.get('downloading'):
            break
        
        session['current_idx'] = idx
        
        status_msg = await message.reply(f"📥 Starting [{idx}/{total}]...")
        
        # Determine destination
        destination = session.get('destination', DESTINATION_CHAT_ID)
        if destination == 0:
            destination = message.chat.id
        
        try:
            ok, error = await stream_upload_video(client, destination, url, title, status_msg, idx, total)
            
            if ok:
                success += 1
                await status_msg.delete()
            else:
                failed += 1
                await status_msg.edit_text(f"❌ [{idx}] Failed: {error}")
                
        except FloodWait as e:
            await asyncio.sleep(e.value)
        except Exception as e:
            failed += 1
            await status_msg.edit_text(f"❌ [{idx}] Error: {str(e)[:100]}")
        
        # Small delay
        await asyncio.sleep(1)
    
    session['downloading'] = False
    
    await message.reply(f"""
✅ **𝐃𝐎𝐖𝐍𝐋𝐎𝐀𝐃 𝐂𝐎𝐌𝐏𝐋𝐄𝐓𝐄** ✅
┠ ✅ Success = {success}
┠ ❌ Failed = {failed}
┠ 📊 Total = {total}
✨ 𝐏𝐎𝐖𝐄𝐑𝐄𝐃 𝐁𝐘: Utkarsh Bot
""")
@app.on_message(filters.command("status") & filters.private)
async def status_command(client: Client, message: Message):
    if not is_admin(message.from_user.id):
        return
    
    session = user_sessions.get(message.from_user.id)
    
    if not session:
        await message.reply("📊 No active session.")
        return
    
    total = len(session.get('urls', []))
    idx = session.get('current_idx', 0)
    percent = (idx / total * 100) if total > 0 else 0
    
    await message.reply(f"""
🚀 **𝐂𝐔𝐑𝐑𝐄𝐍𝐓 𝐏𝐑𝐎𝐆𝐑𝐄𝐒𝐒** = {percent:.1f}% 🚀
┠ 📊 Total Links = {total}
┠ ⚡️ Currently On = {idx}
┠ ⏳ Remaining = {total - idx}
┠ 📁 Batch = {session.get('batch_id')}
┠ 🔄 Status = {'Downloading' if session.get('downloading') else 'Paused'}
""")
@app.on_message(filters.command("cancel") & filters.private)
async def cancel_command(client: Client, message: Message):
    if not is_admin(message.from_user.id):
        return
    
    session = user_sessions.get(message.from_user.id)
    
    if session and session.get('downloading'):
        session['downloading'] = False
        await message.reply("🛑 Cancelled!")
    else:
        await message.reply("ℹ️ Nothing to cancel.")
if __name__ == "__main__":
    print("🤖 Starting Utkarsh Bot V2 (Fast Streaming)...")
    print("📝 Commands: /batch, /download, /status, /cancel")
    
    # Start health server for Render (keeps free tier happy)
    health_thread = threading.Thread(target=start_health_server, daemon=True)
    health_thread.start()
    print("🌐 Health server started on port", os.environ.get('PORT', 10000))
    
    app.run()
