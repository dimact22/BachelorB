from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import os
from db.dbconn import telegram_users
from datetime import datetime
from telegram import Bot

BOT_TOKEN = os.getenv("TelegramToken")

bot = Bot(token=BOT_TOKEN)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat

    data = {
        "telegram_id": user.id,
        "chat_id": chat.id,
        "username": '@' + user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "linked_at": datetime.utcnow(),
    }

    telegram_users.update_one(
        {"telegram_id": user.id},
        {"$set": data},
        upsert=True
    )

    await update.message.reply_text(
        "✅ Telegram успішно привʼязаний до акаунта"
    )

application = ApplicationBuilder().token(BOT_TOKEN).build()
application.add_handler(CommandHandler("start", start))