import os
import re
import time
import asyncio
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import FloodWait, PhoneNumberInvalid, PhoneNumberBanned, PhoneCodeInvalid, SessionPasswordNeeded

# Get environment variables
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")

# Initialize the bot
app = Client("string_session_bot", bot_token=BOT_TOKEN, api_id=API_ID, api_hash=API_HASH)

# Store user sessions temporarily
user_sessions = {}

def extract_digits_only(text):
    """Extract only digits from text, ignoring any separators"""
    return ''.join(re.findall(r'\d', text))

def format_phone_number(phone_text):
    """Clean and format phone number"""
    # Remove all non-digit characters except +
    cleaned = re.sub(r'[^\d+]', '', phone_text.strip())
    
    # Ensure it starts with +
    if not cleaned.startswith('+'):
        # If it starts with digits, assume it needs +
        if cleaned and cleaned[0].isdigit():
            cleaned = '+' + cleaned
    
    return cleaned

def extract_verification_code(text):
    """Extract verification code from text with separators like 1x2x3x4x5"""
    # Remove all non-digit characters
    digits_only = extract_digits_only(text)
    
    # Verification codes are typically 4-6 digits
    if 4 <= len(digits_only) <= 6:
        return digits_only
    
    return None

@app.on_message(filters.command("start") & filters.private)
async def start_command(client, message):
    welcome_text = """
🔐 <b>Zylence String Session Generator Bot</b>

This bot helps you generate Pyrogram string sessions for your Telegram account.

<b>How to use:</b>
1. Click "Generate Session" below
2. Send your API ID
3. Send your API Hash  
4. Send your phone number (any format)
5. Send verification code (use format: 1x2x3x4x5)
6. Get your string session!

⚠️ <b>Important:</b> Never share your string session with anyone!
    """
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 Generate Session", callback_data="generate")]
    ])
    
    await message.reply_text(welcome_text, reply_markup=keyboard, parse_mode=enums.ParseMode.HTML)

@app.on_callback_query(filters.regex("generate"))
async def generate_session(client, callback_query):
    user_id = callback_query.from_user.id
    user_sessions[user_id] = {"step": "api_id"}
    
    await callback_query.message.edit_text(
        "📝 <b>Step 1/4</b>\n\nPlease send your <b>API ID</b>:\n\n"
        "ℹ️ You can get this from https://my.telegram.org",
        parse_mode=enums.ParseMode.HTML
    )

@app.on_message(filters.text & filters.private & ~filters.command(["start", "cancel"]))
async def handle_session_generation(client, message):
    user_id = message.from_user.id
    
    if user_id not in user_sessions:
        return
    
    session_data = user_sessions[user_id]
    step = session_data["step"]
    text = message.text.strip()
    
    print(f"User {user_id} in step '{step}' sent: '{text}'")  # Debug log
    
    if step == "api_id":
        # API ID can be any number of digits
        digits_only = extract_digits_only(text)
        if digits_only and len(digits_only) >= 6:
            try:
                api_id = int(digits_only)
                session_data["api_id"] = api_id
                session_data["step"] = "api_hash"
                
                await message.reply_text(
                    "✅ API ID accepted!\n\n"
                    "📝 <b>Step 2/4</b>\n\nPlease send your <b>API Hash</b>:",
                    parse_mode=enums.ParseMode.HTML
                )
            except ValueError:
                await message.reply_text("❌ Invalid API ID. Please send a valid number.")
        else:
            await message.reply_text("❌ Invalid API ID. Please send a valid number (at least 6 digits).")
    
    elif step == "api_hash":
        # API Hash validation (should be around 32 characters)
        if len(text) >= 30:
            session_data["api_hash"] = text
            session_data["step"] = "phone"
            
            await message.reply_text(
                "✅ API Hash accepted!\n\n"
                "📝 <b>Step 3/4</b>\n\nPlease send your <b>phone number</b>:\n\n"
                "📱 <b>Any format works:</b>\n"
                "• +1234567890\n"
                "• +1 234 567 890\n"
                "• +1-234-567-890\n"
                "• +1 (234) 567-890",
                parse_mode=enums.ParseMode.HTML
            )
        else:
            await message.reply_text("❌ Invalid API Hash. Please send a valid API Hash (should be around 32 characters).")
    
    elif step == "phone":
        # Format phone number (accept any format)
        formatted_phone = format_phone_number(text)
        
        if formatted_phone.startswith('+') and len(extract_digits_only(formatted_phone)) >= 10:
            session_data["phone"] = formatted_phone
            await message.reply_text(f"✅ Phone number accepted: {formatted_phone}")
            await start_session_generation(client, message, session_data)
        else:
            await message.reply_text(
                "❌ Invalid phone number format.\n\n"
                "Please include country code:\n"
                "Example: +1234567890"
            )
    
    elif step == "code":
        # Extract verification code (handle separators)
        verification_code = extract_verification_code(text)
        
        if verification_code:
            await message.reply_text(f"🔐 Processing code: {verification_code}")
            await handle_verification_code(client, message, verification_code)
        else:
            await message.reply_text(
                "❌ Invalid verification code format.\n\n"
                "📱 <b>Send your code like this:</b>\n"
                "• 1x2x3x4x5\n"
                "• 1-2-3-4-5\n"
                "• 1 2 3 4 5\n"
                "• 12345\n\n"
                "The bot will extract the numbers automatically!"
            )
    
    elif step == "password":
        # Handle 2FA password
        await handle_2fa_password(client, message, text)

async def start_session_generation(bot_client, message, session_data):
    user_id = message.from_user.id
    session_name = f"user_{user_id}_{int(time.time())}"
    
    try:
        temp_client = Client(
            session_name,
            api_id=session_data["api_id"],
            api_hash=session_data["api_hash"],
            phone_number=session_data["phone"],
            device_model="iPhone 14 Pro",
            system_version="iOS 16.1",
            app_version="9.1.0",
            lang_code="en",
            system_lang_code="en-US",
            ipv6=False
        )
        
        await message.reply_text("📱 Connecting to Telegram...")
        await temp_client.connect()
        
        await message.reply_text("📱 Requesting verification code...")
        sent_code = await temp_client.send_code(session_data["phone"])
        
        session_data["temp_client"] = temp_client
        session_data["phone_code_hash"] = sent_code.phone_code_hash
        session_data["step"] = "code"
        session_data["session_name"] = session_name
        
        await message.reply_text(
            "📨 <b>Verification code sent!</b>\n\n"
            "🔐 <b>IMPORTANT - Send code like this:</b>\n"
            "• If code is 12345, send: <code>1x2x3x4x5</code>\n"
            "• If code is 6789, send: <code>6x7x8x9</code>\n\n"
            "💡 <b>Why?</b> This prevents Telegram from detecting code sharing!\n\n"
            "You can also use: 1-2-3-4-5 or 1 2 3 4 5",
            parse_mode=enums.ParseMode.HTML
        )
        
    except FloodWait as e:
        await message.reply_text(f"⏳ Rate limited. Please try again in {e.value} seconds.")
        if user_id in user_sessions:
            del user_sessions[user_id]
    except Exception as e:
        await message.reply_text(f"❌ Error: {str(e)}")
        if user_id in user_sessions:
            del user_sessions[user_id]

async def handle_verification_code(client, message, code):
    user_id = message.from_user.id
    
    if user_id not in user_sessions or user_sessions[user_id]["step"] != "code":
        return
    
    session_data = user_sessions[user_id]
    
    try:
        temp_client = session_data["temp_client"]
        
        await temp_client.sign_in(
            session_data["phone"],
            session_data["phone_code_hash"],
            code
        )
        
        me = await temp_client.get_me()
        first_name = me.first_name
        
        string_session = await temp_client.export_session_string()
        
        await temp_client.disconnect()
        
        session_text = f"""
🎉 <b>Session Generated Successfully!</b>

👤 <b>Account:</b> {first_name}

🔐 <b>Your String Session:</b>
<code>{string_session}</code>

⚠️ <b>Important Security Notes:</b>
• Never share this session with anyone
• This gives full access to your account
• Store it securely
• You can revoke it anytime from Telegram Settings > Privacy & Security > Active Sessions
        """
        
        await message.reply_text(session_text, parse_mode=enums.ParseMode.HTML)
        
        del user_sessions[user_id]
        
        # Cleanup
        try:
            os.remove(f"{session_data['session_name']}.session")
        except:
            pass
            
    except SessionPasswordNeeded:
        await message.reply_text(
            "🔐 <b>Two-Factor Authentication Detected</b>\n\n"
            "Please send your 2FA password:",
            parse_mode=enums.ParseMode.HTML
        )
        session_data["step"] = "password"
    except PhoneCodeInvalid:
        await message.reply_text(
            "❌ Invalid verification code.\n\n"
            "Please make sure you're using the format: <code>1x2x3x4x5</code>",
            parse_mode=enums.ParseMode.HTML
        )
    except Exception as e:
        await message.reply_text(f"❌ Error during sign in: {str(e)}")
        
        try:
            await session_data["temp_client"].disconnect()
        except:
            pass
        
        if user_id in user_sessions:
            del user_sessions[user_id]

async def handle_2fa_password(client, message, password):
    user_id = message.from_user.id
    session_data = user_sessions[user_id]
    
    try:
        temp_client = session_data["temp_client"]
        await temp_client.check_password(password)
        
        me = await temp_client.get_me()
        first_name = me.first_name
        
        string_session = await temp_client.export_session_string()
        await temp_client.disconnect()
        
        session_text = f"""
🎉 <b>Session Generated Successfully!</b>

👤 <b>Account:</b> {first_name}

🔐 <b>Your String Session:</b>
<code>{string_session}</code>

⚠️ <b>Security Notes:</b>
• Never share this session
• Store it securely
• You can revoke it in Telegram Settings
        """
        
        await message.reply_text(session_text, parse_mode=enums.ParseMode.HTML)
        del user_sessions[user_id]
        
    except Exception as e:
        await message.reply_text(f"❌ Invalid 2FA password: {str(e)}")

@app.on_message(filters.command("cancel") & filters.private)
async def cancel_session(client, message):
    user_id = message.from_user.id
    
    if user_id in user_sessions:
        if "temp_client" in user_sessions[user_id]:
            try:
                await user_sessions[user_id]["temp_client"].disconnect()
            except:
                pass
        
        del user_sessions[user_id]
        await message.reply_text("❌ Session generation cancelled.")
    else:
        await message.reply_text("ℹ️ No active session generation to cancel.")

if __name__ == "__main__":
    print("🤖 String Session Bot Starting...")
    app.run()
