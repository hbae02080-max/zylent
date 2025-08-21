# multipurpose_bot.py
# A bot that handles user registrations and provides channel posting tools for admins.

import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError
from telegram.ext import (
    Application,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from telegram.constants import ParseMode

# --- ⚠️ IMPORTANT: CONFIGURATION ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")  # Bot token from environment
ADMIN_GROUP_ID = int(os.environ.get("ADMIN_GROUP_ID"))  # Admin group ID
CHANNEL_ID = int(os.environ.get("CHANNEL_ID"))  # Target channel ID
ALLOWED_USER_IDS = list(map(int, os.environ.get("ALLOWED_USER_IDS", "").split(",")))  # Comma-separated admin IDs

# --- Logging Setup ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Conversation States ---
ASKING_CHANNEL, ASKING_CONTACT = range(2)
GETTING_CONTENT, GETTING_BUTTON_NAME, GETTING_BUTTON_LINK, ASKING_MORE_BUTTONS, CONFIRMING_POST = range(10, 15)

# --- Helper Function for Security ---
def is_admin(user_id: int) -> bool:
    return user_id in ALLOWED_USER_IDS

# ============================================================================== #
# USER REGISTRATION FUNCTIONS
# ============================================================================== #

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.message.from_user
    chat_id = update.message.chat_id

    if is_admin(user.id) and chat_id == ADMIN_GROUP_ID:
        await update.message.reply_text("👑 Welcome, Admin! Use the /newpost command to create a new channel post.")
        return

    if context.user_data.get('registered'):
        await update.message.reply_text(
            "Hello again! You have already registered. We will contact you if you are selected as a winner. Good luck! ✨"
        )
        return

    welcome_text = (
        "👋 Welcome to our Giveaway!\n\n"
        "To enter, please click the button below to begin your registration."
    )
    keyboard = [[InlineKeyboardButton("📝 Register Now", callback_data='register')]]
    await update.message.reply_text(welcome_text, reply_markup=InlineKeyboardMarkup(keyboard))

async def start_registration_flow(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if context.user_data.get('registered'):
        await query.edit_message_text("You have already completed your registration. Good luck!")
        return ConversationHandler.END

    await query.edit_message_text(
        "Great! Let's get started.\n\n"
        "First, please send the link or username of your Telegram channel (e.g., @MyChannel)."
    )
    return ASKING_CHANNEL

async def get_channel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    channel_input = update.message.text.strip()

    if not (channel_input.startswith('@') or 't.me/' in channel_input):
        await update.message.reply_text(
            "⚠️ Invalid format.\n\nPlease provide a valid Telegram channel username starting with '@' (e.g., @MyChannel) or a full link (e.g., t.me/MyChannel). Try again."
        )
        return ASKING_CHANNEL

    context.user_data['channel_link'] = channel_input
    await update.message.reply_text(
        "Channel received. ✅\n\n"
        "Now, please provide a username we can use to contact you (e.g., @YourUsername)."
    )
    return ASKING_CONTACT

async def get_contact_and_finish(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    contact_input = update.message.text.strip()

    if not contact_input.startswith('@'):
        await update.message.reply_text(
            "⚠️ Invalid format.\n\nYour contact username must start with '@' (e.g., @YourUsername). Please try again."
        )
        return ASKING_CONTACT

    user = update.message.from_user
    context.user_data['contact_username'] = contact_input

    await update.message.reply_text(
        "Thank you! Your registration is complete. 🎉\n\n"
        "We will contact the winners directly. Good luck!"
    )

    admin_notification = (
        f"📝 <b>New Giveaway Registration</b>\n\n"
        f"<b>From User:</b> {user.full_name}\n"
        f"<b>User's Username:</b> @{user.username if user.username else 'N/A'}\n"
        f"<b>User ID:</b> <code>{user.id}</code>\n\n"
        f"<b>Channel:</b> {context.user_data['channel_link']}\n"
        f"<b>Contact:</b> {context.user_data['contact_username']}"
    )
    try:
        await context.bot.send_message(chat_id=ADMIN_GROUP_ID, text=admin_notification, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"Failed to send notification to admin group {ADMIN_GROUP_ID}: {e}")

    context.user_data['registered'] = True
    context.user_data.pop('channel_link', None)
    context.user_data.pop('contact_username', None)
    return ConversationHandler.END

# ============================================================================== #
# ADMIN POST CREATOR FUNCTIONS
# ============================================================================== #

async def newpost_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.chat_data.clear()
    await update.message.reply_text(
        "Starting new post creation.\n\nPlease send the content (text or photo with caption)."
    )
    return GETTING_CONTENT

async def get_content(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text:
        context.chat_data.update({
            'content_type': 'text', 'text': update.message.text, 'entities': update.message.entities
        })
    elif update.message.photo:
        context.chat_data.update({
            'content_type': 'photo', 'photo_id': update.message.photo[-1].file_id,
            'caption': update.message.caption, 'caption_entities': update.message.caption_entities
        })
    else:
        await update.message.reply_text("Unsupported content. Please send text or a photo.")
        return GETTING_CONTENT

    context.chat_data['buttons'] = []
    await update.message.reply_text("Content received. Let's add the first button.\n\nPlease send the **text** for the button.")
    return GETTING_BUTTON_NAME

async def get_button_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.chat_data['temp_button_name'] = update.message.text
    await update.message.reply_text(f"Button text set to: \"{update.message.text}\"\n\nNow, send the **URL** for this button.")
    return GETTING_BUTTON_LINK

async def get_button_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    button_url = update.message.text
    if not button_url.startswith(('http://', 'https://', 't.me/')):
        await update.message.reply_text("Invalid URL. Please send a valid link.")
        return GETTING_BUTTON_LINK

    button_name = context.chat_data.pop('temp_button_name')
    context.chat_data['buttons'].append({'text': button_name, 'url': button_url})
    keyboard = [
        [InlineKeyboardButton("Yes, add another", callback_data='add_another_yes'),
         InlineKeyboardButton("No, finish", callback_data='add_another_no')]
    ]
    await update.message.reply_text("Button added! Add another?", reply_markup=InlineKeyboardMarkup(keyboard))
    return ASKING_MORE_BUTTONS

async def ask_more_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if query.data == 'add_another_yes':
        await query.edit_message_text("Okay, send the **text** for the next button.")
        return GETTING_BUTTON_NAME
    else:
        await query.edit_message_text("Great. Here is a preview of your post:")
        await send_preview(update.effective_chat.id, context)
        return CONFIRMING_POST

async def send_preview(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    buttons_data = context.chat_data.get('buttons', [])
    keyboard = [[InlineKeyboardButton(b['text'], url=b['url'])] for b in buttons_data]
    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
    content_type = context.chat_data['content_type']

    try:
        if content_type == 'text':
            await context.bot.send_message(
                chat_id=chat_id, text=context.chat_data['text'],
                entities=context.chat_data['entities'], reply_markup=reply_markup
            )
        elif content_type == 'photo':
            await context.bot.send_photo(
                chat_id=chat_id, photo=context.chat_data['photo_id'],
                caption=context.chat_data['caption'], caption_entities=context.chat_data['caption_entities'],
                reply_markup=reply_markup
            )
    except Exception as e:
        logger.error(f"Error sending preview: {e}")
        await context.bot.send_message(chat_id, f"Error creating preview: {e}")

    confirmation_keyboard = [
        [InlineKeyboardButton("✅ Post", callback_data='confirm_post'),
         InlineKeyboardButton("✏️ Restart", callback_data='confirm_edit'),
         InlineKeyboardButton("❌ Cancel", callback_data='confirm_cancel')]
    ]
    await context.bot.send_message(
        chat_id=chat_id, text="What would you like to do?", reply_markup=InlineKeyboardMarkup(confirmation_keyboard)
    )

async def handle_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.message.delete()

    if query.data == 'confirm_post':
        await publish_post(context)
        await context.bot.send_message(update.effective_chat.id, "✅ Post successfully published to the channel!")
        context.chat_data.clear()
        return ConversationHandler.END
    elif query.data == 'confirm_edit':
        await context.bot.send_message(update.effective_chat.id, "Okay, let's start over.")
        return await newpost_start(query.message, context)
    else:
        await context.bot.send_message(update.effective_chat.id, "Post creation cancelled.")
        context.chat_data.clear()
        return ConversationHandler.END

async def publish_post(context: ContextTypes.DEFAULT_TYPE):
    buttons_data = context.chat_data.get('buttons', [])
    keyboard = [[InlineKeyboardButton(b['text'], url=b['url'])] for b in buttons_data]
    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
    content_type = context.chat_data['content_type']

    try:
        if content_type == 'text':
            await context.bot.send_message(
                chat_id=CHANNEL_ID, text=context.chat_data['text'],
                entities=context.chat_data['entities'], reply_markup=reply_markup
            )
        elif content_type == 'photo':
            await context.bot.send_photo(
                chat_id=CHANNEL_ID, photo=context.chat_data['photo_id'],
                caption=context.chat_data['caption'], caption_entities=context.chat_data['caption_entities'],
                reply_markup=reply_markup
            )
    except TelegramError as e:
        logger.error(f"Failed to post to channel {CHANNEL_ID}: {e}")
        await context.bot.send_message(ADMIN_GROUP_ID, f"⚠️ Error posting to channel: {e.message}")

# ============================================================================== #
# CANCEL HANDLER
# ============================================================================== #

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_message = update.message or update.callback_query.message
    if 'channel_link' in context.user_data or 'contact_username' in context.user_data:
        context.user_data.pop('channel_link', None)
        context.user_data.pop('contact_username', None)
        await user_message.reply_text("Registration has been cancelled.")
    else:
        context.chat_data.clear()
        await user_message.reply_text("Operation has been cancelled.")

    return ConversationHandler.END

# ============================================================================== #
# MAIN
# ============================================================================== #

def main() -> None:
    application = Application.builder().token(BOT_TOKEN).build()

    admin_in_group_filter = filters.User(user_id=ALLOWED_USER_IDS) & filters.Chat(chat_id=ADMIN_GROUP_ID)

    registration_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_registration_flow, pattern='^register$')],
        states={
            ASKING_CHANNEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_channel)],
            ASKING_CONTACT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_contact_and_finish)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        persistent=False, name="registration_conv"
    )

    post_creator_conv = ConversationHandler(
        entry_points=[CommandHandler("newpost", newpost_start, filters=admin_in_group_filter)],
        states={
            GETTING_CONTENT: [MessageHandler(filters.TEXT | filters.PHOTO & ~filters.COMMAND, get_content)],
            GETTING_BUTTON_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_button_name)],
            GETTING_BUTTON_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_button_link)],
            ASKING_MORE_BUTTONS: [CallbackQueryHandler(ask_more_buttons, pattern='^add_another_')],
            CONFIRMING_POST: [CallbackQueryHandler(handle_confirmation, pattern='^confirm_')]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        persistent=False, name="post_creator_conv"
    )

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(registration_conv)
    application.add_handler(post_creator_conv)

    print("Multipurpose bot is starting...")
    application.run_polling()


if __name__ == '__main__':
    main()
