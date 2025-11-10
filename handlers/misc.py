from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler

from database import get_db
from services import user_service
from utils.messages import DISCLAIMER
from utils.personality import personality_text

SETUP_BUTTON = "🚀 Настроить профиль"
ADD_BUTTON = "💊 Добавить препарат"
LIST_BUTTON = "📦 Мои препараты"
REMINDER_BUTTON = "⏰ Новое напоминание"
STATS_BUTTON = "📈 Статистика"


def _keyboard(onboarded: bool) -> ReplyKeyboardMarkup:
    if not onboarded:
        return ReplyKeyboardMarkup([[SETUP_BUTTON]], resize_keyboard=True, one_time_keyboard=True)
    return ReplyKeyboardMarkup(
        [
            [ADD_BUTTON, LIST_BUTTON],
            [REMINDER_BUTTON, STATS_BUTTON],
        ],
        resize_keyboard=True,
    )


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db = next(get_db())
    try:
        user = user_service.ensure_user(db, update.effective_user)
        persona = user.bot_personality
        display_name = user.name
        onboarded = bool(user.goal)
    finally:
        db.close()

    text = personality_text(persona, "welcome", name=display_name) or "Привет!"
    keyboard = _keyboard(onboarded)
    await update.message.reply_text(
        f"{DISCLAIMER}\n\n{text}\n\n"
        "Нажимай кнопки ниже — так быстрее. Если нужно вручную, просто напиши команду.",
        reply_markup=keyboard,
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    commands = (
        "🚀 Настройка: /setup\n"
        "💊 Добавить препарат: /add_med\n"
        "📦 Мои препараты: /meds\n"
        "⏰ Напоминания: /set_reminder\n"
        "📈 Статистика: /stats\n"
        "🏅 Достижения: /achievements\n"
        "📤 Экспорт: /export [json|csv]\n"
        "📒 Трекеры: /symptom, /mood, /water\n"
        "📷 Фото: отправь упаковку — пришлю `file_id`, чтобы вставить в WebApp."
    )
    await update.message.reply_text(f"{DISCLAIMER}\n\n{commands}", parse_mode="Markdown")


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Хорошо, вернёмся к этому позже.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    photo = update.message.photo[-1]
    file_id = photo.file_id
    await update.message.reply_text(
        f"Вот `file_id` этой фотографии:\n`{file_id}`\n"
        "Скопируй его и вставь в поле «ID фото» во встроенной форме.",
        parse_mode="Markdown",
    )
