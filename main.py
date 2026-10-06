import os
import re
import asyncio
import http.server
import socketserver
import threading
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.types import DocumentAttributeVideo

API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
SESSION_STRING = os.environ.get("SESSION_STRING")

# --- GROUP CONFIGURATION ---
TARGET_GROUP_ID = -1003894042476  # Tumhare "Server 1" ki Group ID

client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
link_queue = asyncio.Queue()
is_processing = False

def start_server():
    class QuietHandler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, format, *args): return
    with socketserver.TCPServer(("", 7860), QuietHandler) as httpd:
        httpd.serve_forever()

threading.Thread(target=start_server, daemon=True).start()
print("⚡ Ultra Smart Downloader Engine Starting...")

async def progress_callback(current, total, status_msg, action_text):
    percentage = (current / total) * 100
    if current % (15 * 1024 * 1024) < (1024 * 1024) or current == total:
        try:
            await status_msg.edit(f"⏳ {action_text}...\n📊 Progress: {percentage:.1f}% ({current // (1024*1024)}MB / {total // (1024*1024)}MB)")
        except Exception:
            pass

# --- DOWNLOAD MODE WORKER (FINAL & SAFE VERSION) ---
async def queue_worker():
    global is_processing
    while True:
        channel_id, msg_id, status_msg = await link_queue.get()
        is_processing = True
        try:
            try:
                await status_msg.edit(f"📥 Message ID {msg_id} download ho raha hai...")
            except Exception:
                pass
                
            msg = await client.get_messages(channel_id, ids=msg_id)
            
            if msg:
                if msg.media:
                    original_caption = msg.message if msg.message else ""
                    final_caption = original_caption
                    
                    # Formatting, entities aur buttons capture karne ke liye
                    caption_entities = msg.entities if hasattr(msg, 'entities') else None
                    buttons = msg.reply_markup if hasattr(msg, 'reply_markup') else None
                    
                    path = await client.download_media(
                        msg,
                        progress_callback=lambda c, t: progress_callback(c, t, status_msg, f"ID {msg_id} - Downloading")
                    )
                    
                    # Original attributes aur thumbnail safely retain karne ke liye
                    attributes = []
                    try:
                        if hasattr(msg.media, 'document') and msg.media.document:
                            for attr in msg.media.document.attributes:
                                if isinstance(attr, DocumentAttributeVideo):
                                    attributes.append(attr)
                    except Exception:
                        attributes = None

                    try:
                        await status_msg.edit(f"📤 Group me upload ho raha hai...")
                    except Exception:
                        pass
                        
                    # File ko original format, caption, formatting aur buttons ke sath bhejna
                    await client.send_file(
                        TARGET_GROUP_ID,
                        path,
                        caption=final_caption,
                        formatting_entities=caption_entities,
                        buttons=buttons,
                        attributes=attributes if attributes else None,
                        progress_callback=lambda c, t: progress_callback(c, t, status_msg, f"ID {msg_id} - Uploading")
                    )
                    
                    if os.path.exists(path):
                        os.remove(path)
                    try:
                        await status_msg.delete()
                    except Exception:
                        pass
                    
                elif msg.message:
                    # Text message ke liye formatting aur buttons ke sath
                    await client.send_message(
                        TARGET_GROUP_ID, 
                        msg.message, 
                        formatting_entities=msg.entities, 
                        buttons=msg.reply_markup
                    )
                    try:
                        await status_msg.delete()
                    except Exception:
                        pass
                else:
                    try:
                        await status_msg.edit(f"ℹ️ Message ID {msg_id} khali hai.")
                    except Exception:
                        pass
            else:
                try:
                    await status_msg.edit(f"❌ Message ID {msg_id} nahi mila.")
                except Exception:
                    pass
        except Exception as e:
            try:
                await client.send_message(TARGET_GROUP_ID, f"❌ Error ID {msg_id} par: {str(e)}")
            except Exception:
                pass
            
        link_queue.task_done()
        await asyncio.sleep(2.5)

# --- NEW PRO LINK PARSER (FOOLPROOF) ---
def parse_telegram_link(url):
    """Har tarah ke telegram private/public links se Chat ID aur Message ID nikalega"""
    try:
        clean_url = url.split('?')[0].strip()
        numbers = re.findall(r'\d+', clean_url)
        
        if 't.me/c/' in clean_url:
            chat_id = int('-100' + numbers[0])
            last_part = url.split('/')[-1].strip()
            return chat_id, last_part
        else:
            parts = clean_url.split('/')
            chat_id = parts[-2]
            last_part = parts[-1]
            return chat_id, last_part
    except Exception:
        return None, None

@client.on(events.NewMessage(chats=TARGET_GROUP_ID))
async def master_handler(event):
    text = event.raw_text.strip()
    
    # 🏎️ 1. DIRECT FORWARD MODE
    if text.lower().startswith('f '):
        parts = [p.strip() for p in re.split(r'\s+-\s+|\s+', text) if p.strip()]
        if len(parts) < 3:
            await event.reply("❌ Sahi format use karo:\n`f - SourceLink - TargetLink`")
            return
            
        src_chat, src_last = parse_telegram_link(parts[1])
        tgt_chat, _ = parse_telegram_link(parts[2])
        
        if not src_chat or not tgt_chat:
            await event.reply("❌ Links sahi se samajh nahi aaye.")
            return
            
        status_msg = await event.reply("⚡ Direct Forward Mode Active...")
        try:
            if '-' in src_last:
                range_match = re.match(r'(\d+)-(\d+)', src_last)
                if range_match:
                    start_id = int(range_match.group(1))
                    end_id = int(range_match.group(2))
                    msg_ids = list(range(start_id, end_id + 1))
                    await client.forward_messages(tgt_chat, msg_ids, src_chat)
                    await status_msg.edit("🎉 Range successfully forward ho gayi!")
            else:
                msg_id = int(src_last)
                await client.forward_messages(tgt_chat, msg_id, src_chat)
                await status_msg.edit(f"🎉 Message ID {msg_id} forward ho gaya!")
        except Exception as e:
            await status_msg.edit(f"❌ Error: {str(e)}")
            
    # 📥 2. DOWNLOAD MODE
    elif 't.me/c/' in text or 't.me/' in text:
        chat_id, last_path = parse_telegram_link(text)
        if not chat_id:
            return
            
        if '-' in last_path:
            range_match = re.match(r'(\d+)-(\d+)', last_path)
            if range_match:
                start_id = int(range_match.group(1))
                end_id = int(range_match.group(2))
                if start_id > end_id:
                    await event.reply("❌ Galat range!")
                    return
                    
                total_files = end_id - start_id + 1
                await event.reply(f"🚀 Total **{total_files}** posts queue me add ho gayi hain...")
                for m_id in range(start_id, end_id + 1):
                    status_msg = await event.reply(f"⏳ Post ID {m_id} line me hai...")
                    await link_queue.put((chat_id, m_id, status_msg))
        else:
            try:
                msg_id = int(last_path)
                status_msg = await event.reply(f"⏳ Post ID {msg_id} queue me add ho gaya...")
                await link_queue.put((chat_id, msg_id, status_msg))
            except ValueError:
                pass

async def main():
    await client.connect()
    if not await client.is_user_authorized():
        print("\n❌ SESSION INVALID!")
        return
    print("✅ Bot is running perfectly!")
    asyncio.create_task(queue_worker())
    await client.run_until_disconnected()

client.loop.run_until_complete(main())
