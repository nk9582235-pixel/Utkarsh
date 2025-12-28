"""
URL to Video Bot - Streaming Upload with Detailed Progress
Features: ETA, Progress Bar, Speed, File Type Stats
Render-Ready with Health Check Server
"""
import os
import asyncio
import logging
import aiohttp
import io
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import FloodWait
# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)
# =============================================================================
# HEALTH CHECK SERVER FOR RENDER
# =============================================================================
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'URL Video Bot is running!')
    def log_message(self, format, *args):
        pass  # Suppress logs
def start_health_server():
    port = int(os.environ.get('PORT', 10000))
    server = HTTPServer(('0.0.0.0', port), HealthHandler)
    print(f"🌐 Health server started on port {port}")
    server.serve_forever()
# =============================================================================
# CONFIGURATION - Environment Variables for Render
# =============================================================================
try:
    from bot_config import API_ID, API_HASH, BOT_TOKEN, ADMIN_IDS
    print("📝 Using bot_config.py credentials")
except ImportError:
    print("📝 Using environment variables...")
    API_ID = os.environ.get("API_ID")
    API_HASH = os.environ.get("API_HASH")
    BOT_TOKEN = os.environ.get("BOT_TOKEN")
    ADMIN_IDS = [int(x) for x in os.environ.get("ADMIN_IDS", "915101089").split(",")]
# =============================================================================
# HELPER FUNCTIONS
# =============================================================================
def format_time(seconds):
    """Convert seconds to human readable format"""
    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        m, s = divmod(int(seconds), 60)
        return f"{m}m {s}s"
    else:
        h, remainder = divmod(int(seconds), 3600)
        m, s = divmod(remainder, 60)
        return f"{h}h {m}m"
def format_size(bytes_size):
    """Convert bytes to human readable format"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_size < 1024:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024
    return f"{bytes_size:.1f} TB"
def detect_file_type(url: str, content_type: str = ""):
    """Detect file type from URL and content-type"""
    url_lower = url.lower().split('?')[0]
    
    # Video extensions
    if any(ext in url_lower for ext in ['.mp4', '.mkv', '.avi', '.mov', '.webm', '.flv', '.m3u8', 'enc_plain']):
        return 'video', '.mp4', '🎬'
    # PDF
    elif '.pdf' in url_lower:
        return 'pdf', '.pdf', '📄'
    # Images
    elif any(ext in url_lower for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']):
        ext = Path(url_lower).suffix or '.jpg'
        return 'photo', ext, '🖼️'
    # Check content-type
    elif 'video' in content_type:
        return 'video', '.mp4', '🎬'
    elif 'pdf' in content_type:
        return 'pdf', '.pdf', '📄'
    elif 'image' in content_type:
        return 'photo', '.jpg', '🖼️'
    
    return 'document', '.bin', '📁'
async def download_to_file(url: str, timeout: int = 600):
    """Download URL to temp file (more reliable for large files)"""
    import tempfile
    downloaded = 0
    
    try:
        logger.info(f"📥 Downloading: {url[:80]}...")
        
        # Create temp file
        suffix = '.mp4' if 'mp4' in url or 'video' in url else '.tmp'
        tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
        tmp_path = tmp.name
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
                if resp.status != 200:
                    logger.error(f"❌ HTTP {resp.status} for {url[:50]}")
                    raise Exception(f"HTTP {resp.status}")
                
                content_type = resp.headers.get('Content-Type', '')
                total_size = int(resp.headers.get('Content-Length', 0))
                logger.info(f"📦 Size: {total_size/1024/1024:.1f}MB, Type: {content_type}")
                
                async for chunk in resp.content.iter_chunked(1024 * 1024):  # 1MB chunks
                    tmp.write(chunk)
                    downloaded += len(chunk)
        
        tmp.close()
        logger.info(f"✅ Downloaded to temp: {downloaded/1024/1024:.1f}MB")
        return tmp_path, downloaded, content_type
    except Exception as e:
        logger.error(f"❌ Download failed: {e}")
        raise
# =============================================================================
# BOT SETUP
# =============================================================================
app = Client("streaming_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
user_sessions = {}
def is_admin(user_id):
    return user_id in ADMIN_IDS
# =============================================================================
# COMMANDS
# =============================================================================
@app.on_message(filters.command("start") & filters.private)
async def start_command(client: Client, message: Message):
    await message.reply("""
🚀 **Streaming URL Bot** ⚡
Send me a TXT file with URLs and I'll stream them to Telegram!
**Features:**
• ⚡ Fast streaming upload
• 📊 Live progress with ETA
• 🎬 Videos, 📄 PDFs, 🖼️ Images support
**Commands:**
• `/upload` - Start uploading
• `/setchannel <id>` - Set destination
• `/status` - View progress
• `/cancel` - Stop upload
**TXT Format:**
```
Video Name:https://url.com/video.mp4
PDF Name:https://url.com/file.pdf
```
""")
@app.on_message(filters.document & filters.private)
async def handle_document(client: Client, message: Message):
    """Handle uploaded TXT files"""
    if not is_admin(message.from_user.id):
        return
    
    doc = message.document
    if not doc.file_name.endswith('.txt'):
        await message.reply("❌ Please send a TXT file.")
        return
    
    status_msg = await message.reply("📥 Analyzing file...")
    
    try:
        file_path = await message.download()
        
        # Parse URLs and detect types
        urls = []
        type_counts = {'video': 0, 'pdf': 0, 'photo': 0, 'document': 0}
        
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('=') or line.startswith('Course:') or line.startswith('Info:'):
                    continue
                
                # Parse format: name:url
                if ':http' in line:
                    idx = line.find(':http')
                    name = line[:idx].strip()
                    url = line[idx+1:].strip()
                elif line.startswith('http'):
                    name = Path(line.split('?')[0]).stem[:50]
                    url = line
                else:
                    continue
                
                if url.startswith('http'):
                    file_type, ext, emoji = detect_file_type(url)
                    type_counts[file_type] += 1
                    urls.append({
                        'name': name,
                        'url': url,
                        'type': file_type,
                        'ext': ext,
                        'emoji': emoji
                    })
        
        os.remove(file_path)
        
        if not urls:
            await status_msg.edit_text("❌ No valid URLs found.")
            return
        
        # Preserve existing destination if set
        existing_dest = user_sessions.get(message.from_user.id, {}).get('destination')
        
        user_sessions[message.from_user.id] = {
            'urls': urls,
            'type_counts': type_counts,
            'current_idx': 0,
            'uploading': False,
            'cancelled': False,
            'destination': existing_dest,  # Keep existing destination
            'start_time': None,
            'total_bytes': 0
        }
        
        await status_msg.edit_text(f"""
✅ **File Analyzed!**
📊 **Total Links: {len(urls)}**
**📁 File Types:**
🎬 Videos: {type_counts['video']}
📄 PDFs: {type_counts['pdf']}
🖼️ Images: {type_counts['photo']}
📁 Others: {type_counts['document']}
━━━━━━━━━━━━━━━━━━━━━
**📍 Current Destination:** `{existing_dest or 'Personal Chat'}`
• `/upload` - Start uploading
• `/setchannel -100xxxxx` - Change channel
• `/setchannel 0` - Reset to personal chat
""")
        
    except Exception as e:
        logger.error(f"Error: {e}")
        await status_msg.edit_text(f"❌ Error: {str(e)[:200]}")
@app.on_message(filters.command("upload") & filters.private)
async def upload_command(client: Client, message: Message):
    """Start streaming upload with detailed progress"""
    if not is_admin(message.from_user.id):
        return
    
    user_id = message.from_user.id
    session = user_sessions.get(user_id)
    
    if not session or not session.get('urls'):
        await message.reply("❌ No URLs loaded. Send a TXT file first!")
        return
    
    if session.get('uploading'):
        await message.reply("⏳ Already uploading...")
        return
    
    session['uploading'] = True
    session['cancelled'] = False
    session['start_time'] = time.time()
    session['total_bytes'] = 0
    
    urls = session['urls']
    type_counts = session['type_counts']
    total = len(urls)
    dest = session.get('destination') or message.chat.id
    
    status_msg = await message.reply("🚀 Starting...")
    
    # Stats tracking
    success = 0
    failed = 0
    skipped = 0
    total_bytes = 0
    last_update = 0
    
    for idx, item in enumerate(urls):
        if session.get('cancelled'):
            break
        
        session['current_idx'] = idx
        name = item['name']
        url = item['url']
        file_type = item['type']
        ext = item['ext']
        emoji = item['emoji']
        
        clean_name = "".join(c for c in name if c.isalnum() or c in " -_()").strip()[:55] or f"File_{idx+1}"
        
        # Update progress (every 3 seconds or every file for small batches)
        current_time = time.time()
        if current_time - last_update >= 3 or total < 20:
            last_update = current_time
            
            # Calculate ETA
            elapsed = current_time - session['start_time']
            if idx > 0:
                avg_time = elapsed / idx
                remaining = (total - idx) * avg_time
                eta = format_time(remaining)
            else:
                eta = "Calculating..."
            
            # Calculate speed
            if elapsed > 0 and total_bytes > 0:
                speed = total_bytes / elapsed
                speed_str = f"{format_size(speed)}/s"
            else:
                speed_str = "..."
            
            # Progress bar
            percent = int((idx / total) * 100)
            filled = percent // 5
            bar = "█" * filled + "░" * (20 - filled)
            
            try:
                await status_msg.edit_text(f"""
🚀 **Uploading to Telegram**
**Progress:**
[{bar}] {percent}%
📁 {idx}/{total} files
**Current:** {emoji} {clean_name[:30]}...
**Stats:**
✅ Success: {success}
❌ Failed: {failed}
⏭️ Skipped: {skipped}
**Performance:**
⏱️ ETA: {eta}
💾 Uploaded: {format_size(total_bytes)}
🚄 Speed: {speed_str}
**File Types:**
🎬 {type_counts['video']} | 📄 {type_counts['pdf']} | 🖼️ {type_counts['photo']} | 📁 {type_counts['document']}
""")
            except:
                pass
        
        # Create per-file progress message
        file_msg = None
        try:
            file_msg = await message.reply(f"""
📥 **Processing File {idx+1}/{total}**
{emoji} **{clean_name[:45]}**
⏳ Starting download...
""")
        except:
            pass
        
        try:
            # Update per-file message: downloading
            if file_msg:
                try:
                    await file_msg.edit_text(f"""
📥 **Downloading {idx+1}/{total}**
{emoji} **{clean_name[:45]}**
⏳ Downloading from CDN...
🔗 Source: `{url[:50]}...`
""")
                except:
                    pass
            
            # Download to temp file
            tmp_path, size, content_type = await download_to_file(url)
            total_bytes += size
            session['total_bytes'] = total_bytes
            
            # Skip if too large
            if size > 2 * 1024 * 1024 * 1024:
                skipped += 1
                os.unlink(tmp_path)
                if file_msg:
                    try:
                        await file_msg.delete()
                    except:
                        pass
                continue
            
            # Update per-file message: uploading
            if file_msg:
                try:
                    await file_msg.edit_text(f"""
📤 **Uploading {idx+1}/{total}**
{emoji} **{clean_name[:45]}**
📦 Size: **{format_size(size)}**
⬆️ Uploading to Telegram...
""")
                except:
                    pass
            
            # Upload progress callback - updates per-file message with %
            last_progress_update = [0]
            async def upload_progress(current, total_size):
                nonlocal last_progress_update
                if time.time() - last_progress_update[0] >= 2:  # Update every 2 sec
                    last_progress_update[0] = time.time()
                    pct = int((current / total_size) * 100)
                    upload_bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
                    if file_msg:
                        try:
                            await file_msg.edit_text(f"""
📤 **Uploading {idx+1}/{total}**
{emoji} **{clean_name[:40]}**
📦 Size: **{format_size(total_size)}**
[{upload_bar}] {pct}%
⬆️ {format_size(current)} / {format_size(total_size)}
""")
                        except:
                            pass
            
            # Upload based on type
            try:
                logger.info(f"📤 Uploading: {clean_name} ({format_size(size)})")
                if file_type == 'video':
                    await client.send_video(
                        dest, tmp_path,
                        caption=f"🎬 {clean_name}",
                        file_name=f"{clean_name}{ext}",
                        supports_streaming=True,
                        progress=upload_progress
                    )
                elif file_type == 'pdf':
                    await client.send_document(
                        dest, tmp_path,
                        caption=f"📄 {clean_name}",
                        file_name=f"{clean_name}{ext}",
                        progress=upload_progress
                    )
                elif file_type == 'photo':
                    await client.send_photo(
                        dest, tmp_path,
                        caption=f"🖼️ {clean_name}",
                        progress=upload_progress
                    )
                else:
                    await client.send_document(
                        dest, tmp_path,
                        caption=f"📁 {clean_name}",
                        file_name=f"{clean_name}{ext}",
                        progress=upload_progress
                    )
                
                success += 1
                logger.info(f"✅ {idx+1}/{total} {clean_name} ({format_size(size)})")
                
                # Delete per-file message on success
                if file_msg:
                    try:
                        await file_msg.delete()
                    except:
                        pass
                
            except FloodWait as e:
                logger.warning(f"FloodWait: {e.value}s")
                if file_msg:
                    try:
                        await file_msg.edit_text(f"⏳ Rate limited, waiting {e.value}s...")
                    except:
                        pass
                await asyncio.sleep(e.value + 2)
                await client.send_document(dest, tmp_path, caption=f"{emoji} {clean_name}")
                success += 1
                if file_msg:
                    try:
                        await file_msg.delete()
                    except:
                        pass
            finally:
                # Cleanup temp file
                try:
                    os.unlink(tmp_path)
                except:
                    pass
            
            await asyncio.sleep(0.5)  # Small delay
            
        except Exception as e:
            logger.error(f"❌ {clean_name}: {e}")
            failed += 1
            # Update per-file message with error
            if file_msg:
                try:
                    await file_msg.edit_text(f"❌ **Failed:** {clean_name[:30]}...\nError: {str(e)[:50]}")
                    await asyncio.sleep(2)
                    await file_msg.delete()
                except:
                    pass
    
    session['uploading'] = False
    
    # Final stats
    elapsed = time.time() - session['start_time']
    
    status_icon = "⏹️ Cancelled!" if session.get('cancelled') else "✅ Complete!"
    await status_msg.edit_text(f"""
{status_icon}
**📊 Final Report:**
**Results:**
✅ Success: {success}
❌ Failed: {failed}
⏭️ Skipped: {skipped}
📁 Total: {total}
**Performance:**
⏱️ Time: {format_time(elapsed)}
💾 Data: {format_size(total_bytes)}
🚄 Avg Speed: {format_size(total_bytes/elapsed) if elapsed > 0 else 'N/A'}/s
**By Type:**
🎬 Videos: {type_counts['video']}
📄 PDFs: {type_counts['pdf']}
🖼️ Images: {type_counts['photo']}
📁 Others: {type_counts['document']}
""")
@app.on_message(filters.command("setchannel") & filters.private)
async def setchannel_command(client: Client, message: Message):
    if not is_admin(message.from_user.id):
        return
    
    args = message.text.split()
    if len(args) < 2:
        await message.reply("""
📍 **Set Destination Channel**
Usage: `/setchannel <channel_id>`
**How to get channel ID:**
1. Add the bot as admin to your channel
2. Forward any message from channel to @userinfobot
3. Use the ID (starts with -100)
Example: `/setchannel -1001234567890`
Use `/setchannel 0` to reset to personal chat
""")
        return
    
    try:
        channel_id = int(args[1])
        
        # Reset to personal chat
        if channel_id == 0:
            user_sessions.setdefault(message.from_user.id, {})['destination'] = None
            await message.reply("✅ Reset to **Personal Chat**")
            return
        
        # Validate channel ID format (should start with -100)
        if not str(channel_id).startswith('-100'):
            await message.reply(f"""
❌ Invalid channel ID format!
Your ID: `{channel_id}`
Expected: `-100xxxxxxxxxx`
Channel IDs must start with `-100`
Forward a message from your channel to @userinfobot to get the correct ID.
""")
            return
        
        # Test if bot can send to this channel
        status_msg = await message.reply("🔍 Testing channel access...")
        try:
            test_msg = await client.send_message(channel_id, "✅ Bot connected! (This message will be deleted)")
            await test_msg.delete()
            
            user_sessions.setdefault(message.from_user.id, {})['destination'] = channel_id
            await status_msg.edit_text(f"✅ **Channel verified!**\n\nDestination: `{channel_id}`\n\nBot can send messages to this channel.")
        except Exception as e:
            await status_msg.edit_text(f"""
❌ **Cannot access channel!**
Error: `{str(e)[:100]}`
**Make sure:**
1. Bot is added to the channel
2. Bot has **admin privileges** (post messages)
3. Channel ID is correct
""")
    except ValueError:
        await message.reply("❌ Invalid ID - must be a number")
@app.on_message(filters.command("status") & filters.private)
async def status_command(client: Client, message: Message):
    if not is_admin(message.from_user.id):
        return
    
    session = user_sessions.get(message.from_user.id, {})
    urls = session.get('urls', [])
    type_counts = session.get('type_counts', {})
    
    if not urls:
        await message.reply("📭 No URLs loaded. Send a TXT file to start.")
        return
    
    await message.reply(f"""
📊 **Current Status**
📁 Links: {len(urls)}
📤 Uploading: {'Yes' if session.get('uploading') else 'No'}
📍 Progress: {session.get('current_idx', 0)}/{len(urls)}
💾 Uploaded: {format_size(session.get('total_bytes', 0))}
**Types:**
🎬 Videos: {type_counts.get('video', 0)}
📄 PDFs: {type_counts.get('pdf', 0)}
🖼️ Images: {type_counts.get('photo', 0)}
📁 Others: {type_counts.get('document', 0)}
""")
@app.on_message(filters.command("cancel") & filters.private)
async def cancel_command(client: Client, message: Message):
    if not is_admin(message.from_user.id):
        return
    
    session = user_sessions.get(message.from_user.id, {})
    if session.get('uploading'):
        session['cancelled'] = True
        await message.reply("⏹️ Stopping upload...")
    else:
        await message.reply("❌ Nothing to cancel")
# =============================================================================
# MAIN
# =============================================================================
if __name__ == "__main__":
    print("🚀 Streaming URL Bot Starting...")
    print("⚡ Features: Videos, PDFs, Images, ETA, Progress")
    print("📤 Send a TXT file with URLs!")
    
    # Start health check server in background (for Render)
    health_thread = threading.Thread(target=start_health_server, daemon=True)
    health_thread.start()
    
    app.run()
