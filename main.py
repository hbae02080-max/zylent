import os
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import asyncio

# Get environment variables
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")

# Initialize the bot
app = Client("string_session_bot", bot_token=BOT_TOKEN, api_id=API_ID, api_hash=API_HASH)

# Store user sessions temporarily
user_sessions = {}

@app.on_message(filters.command("start") & filters.private)
async def start_command(client, message):
    welcome_text = """
🔐 <b>Zylence String Session Generator Bot</b>

This bot helps you generate Pyrogram string sessions for your Telegram account.

<b>How to use:</b>
1. Click "Generate Session" below
2. Send your API ID
3. Send your API Hash  
4. Send the verification code you receive
5. Get your string session!

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
        "📝 <b>Step 1/3</b>\n\nPlease send your <b>API ID</b>:\n\n"
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
    
    if step == "api_id":
        # API ID can be any number of digits (typically 7-8 digits but can vary)
        if text.isdigit() and len(text) >= 6:  # At least 6 digits
            try:
                api_id = int(text)
                session_data["api_id"] = api_id
                session_data["step"] = "api_hash"
                
                await message.reply_text(
                    "📝 <b>Step 2/3</b>\n\nPlease send your <b>API Hash</b>:",
                    parse_mode=enums.ParseMode.HTML
                )
            except ValueError:
                await message.reply_text("❌ Invalid API ID. Please send a valid number.")
        else:
            await message.reply_text("❌ Invalid API ID. Please send a valid number (at least 6 digits).")
    
    elif step == "api_hash":
        # API Hash is typically 32 characters long
        if len(text) >= 30:  # Allow some flexibility
            session_data["api_hash"] = text
            session_data["step"] = "phone"
            
            await message.reply_text(
                "📝 <b>Step 3/3</b>\n\nPlease send your <b>phone number</b> (with country code):\n\n"
                "Example: +1234567890",
                parse_mode=enums.ParseMode.HTML
            )
        else:
            await message.reply_text("❌ Invalid API Hash. Please send a valid API Hash (should be around 32 characters).")
    
    elif step == "phone":
        # Basic phone number validation
        if text.startswith('+') and len(text) >= 10:
            session_data["phone"] = text
            await start_session_generation(client, message, session_data)
        else:
            await message.reply_text("❌ Invalid phone number. Please include country code (e.g., +1234567890).")
    
    elif step == "code":
        # Verification codes can be 4-6 digits
        if text.isdigit() and 4 <= len(text) <= 6:
            await handle_verification_code(client, message, text)
        else:
            await message.reply_text("❌ Invalid verification code. Please send only the numbers (4-6 digits).")

async def start_session_generation(bot_client, message, session_data):
    user_id = message.from_user.id
    
    try:
        temp_client = Client(
            f"temp_session_{user_id}",
            api_id=session_data["api_id"],
            api_hash=session_data["api_hash"],
            phone_number=session_data["phone"],
            device_model="ZylenceUserBot"
        )
        
        await message.reply_text("📱 Sending verification code...")
        
        await temp_client.connect()
        sent_code = await temp_client.send_code(session_data["phone"])
        
        session_data["temp_client"] = temp_client
        session_data["phone_code_hash"] = sent_code.phone_code_hash
        session_data["step"] = "code"
        
        await message.reply_text(
            "📨 <b>Verification code sent!</b>\n\n"
            "Please check your Telegram app and send the verification code here.\n\n"
            "Format: <code>12345</code> (just the numbers, 4-6 digits)",
            parse_mode=enums.ParseMode.HTML
        )
        
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
        
        try:
            os.remove(f"temp_session_{user_id}.session")
        except:
            pass
            
    except Exception as e:
        await message.reply_text(f"❌ Error during sign in: {str(e)}")
        
        try:
            await session_data["temp_client"].disconnect()
        except:
            pass
        
        if user_id in user_sessions:
            del user_sessions[user_id]

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
