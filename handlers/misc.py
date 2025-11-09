from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from database import get_db
from services import user_service
from utils.messages import DISCLAIMER
from utils.personality import personality_text


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db = next(get_db())
    try:
        user = user_service.ensure_user(db, update.effective_user)
        persona = user.bot_personality
        display_name = user.name
    finally:
        db.close()

    text = personality_text(persona, "welcome", name=display_name) or "Привет!"
    await update.message.reply_text(
        f"{DISCLAIMER}\n\n{text}\n\nИспользуй /setup, чтобы пройти онбординг."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    commands = (
        "/setup — онбординг\n"
        "/profile — профиль и настройки\n"
        "/add_med — добавить лекарство\n"
        "/meds — список лекарств\n"
        "/set_reminder — настроить напоминание\n"
        "/stats — статистика\n"
        "/achievements — достижения\n"
        "/export [json|csv] — экспорт данных\n"
        "/symptom /mood /water — трекеры\n"
        "/family — семейный режим\n"
    )
    await update.message.reply_text(f"{DISCLAIMER}\n\n{commands}")


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Хорошо, вернёмся к этому позже.")
    return ConversationHandler.END
