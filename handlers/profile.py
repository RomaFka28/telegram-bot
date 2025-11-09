from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes, ConversationHandler

from database import get_db
from handlers.states import ProfileEditState
from services import user_service
from utils.messages import DISCLAIMER


def _profile_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Изменить имя", callback_data="profile_edit:name")],
            [InlineKeyboardButton("Часовой пояс", callback_data="profile_edit:timezone")],
            [InlineKeyboardButton("Стиль общения", callback_data="profile_edit:personality")],
            [InlineKeyboardButton("Цель", callback_data="profile_edit:goal")],
        ]
    )


async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db = next(get_db())
    try:
        model = user_service.ensure_user(db, update.effective_user)
    finally:
        db.close()

    message = (
        f"{DISCLAIMER}\n\n"
        f"👤 {model.name}\n"
        f"Часовой пояс: {model.timezone or 'не задан'}\n"
        f"Стиль общения: {model.bot_personality}\n"
        f"Цель: {model.goal or 'не задана'}\n"
        f"Возраст: {model.age or '—'} | Вес: {model.weight or '—'}\n"
    )
    await update.message.reply_text(message, reply_markup=_profile_keyboard())


async def profile_edit_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    field = query.data.split(":")[1]
    context.user_data["profile_edit_field"] = field
    labels = {
        "name": "Напиши новое имя.",
        "timezone": "Укажи часовой пояс (например, Europe/Moscow).",
        "personality": "Укажи новый стиль общения.",
        "goal": "Опиши новую цель.",
    }
    await query.edit_message_text(labels.get(field, "Введи значение."))
    return ProfileEditState.VALUE


async def apply_profile_edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    field = context.user_data.get("profile_edit_field")
    if not field:
        await update.message.reply_text("Нечего обновлять.")
        return ConversationHandler.END

    value = update.message.text.strip()
    db = next(get_db())
    try:
        user = user_service.ensure_user(db, update.effective_user)
        kwargs = {field if field != "timezone" else "timezone": value}
        user_service.update_profile(db, user, **kwargs)
    finally:
        db.close()

    await update.message.reply_text("Профиль обновлён.", reply_markup=_profile_keyboard())
    return ConversationHandler.END
