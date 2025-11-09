import pytz
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from database import get_db
from services import user_service
from handlers.states import SetupState
from utils.messages import DISCLAIMER, PERSONALITY_CHOICES, THEME_CHOICES


async def start_setup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        f"{DISCLAIMER}\n\nКак тебя зовут?",
    )
    return SetupState.NAME


async def collect_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["setup_name"] = update.message.text.strip()
    await update.message.reply_text(
        "Укажи свой часовой пояс (например, Europe/Moscow)."
    )
    return SetupState.TIMEZONE


async def collect_timezone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    tz_value = update.message.text.strip()
    try:
        pytz.timezone(tz_value)
    except pytz.UnknownTimeZoneError:
        await update.message.reply_text(
            "Не удалось распознать часовой пояс. Попробуй ещё раз (пример: Europe/Moscow)."
        )
        return SetupState.TIMEZONE
    context.user_data["setup_timezone"] = tz_value
    personas = "\n".join([f"- {title}" for _, title in PERSONALITY_CHOICES])
    await update.message.reply_text(
        "Выбери стиль общения:\n" + personas
    )
    return SetupState.PERSONALITY


async def collect_personality(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    choice = update.message.text.strip().lower()
    slug = None
    for key, label in PERSONALITY_CHOICES:
        if choice == key or choice.lower() in label.lower():
            slug = key
            break
    if not slug:
        await update.message.reply_text("Пожалуйста, выбери один из вариантов из списка.")
        return SetupState.PERSONALITY
    context.user_data["setup_personality"] = slug
    await update.message.reply_text("Какую цель поставим? (например, 30 дней без пропусков)")
    return SetupState.GOAL


async def collect_goal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["setup_goal"] = update.message.text.strip()
    themes = "\n".join([f"- {label}" for _, label in THEME_CHOICES])
    await update.message.reply_text(
        "Выбери тему оформления (эмодзи/цвет):\n" + themes
    )
    return SetupState.THEME


async def collect_theme(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    choice = update.message.text.strip().lower()
    slug = None
    for key, label in THEME_CHOICES:
        if choice == key or choice.lower() in label.lower():
            slug = key
            break
    if not slug:
        await update.message.reply_text("Выбери тему из списка.")
        return SetupState.THEME
    context.user_data["setup_theme"] = slug
    await update.message.reply_text(
        "Последний штрих: укажи возраст и вес (формат: 30, 70) или напиши '-' если не хочешь делиться."
    )
    return SetupState.OPTIONAL


async def finalize_setup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    age = weight = None
    if text != "-":
        parts = [part.strip() for part in text.replace(";", ",").split(",")]
        if len(parts) >= 1 and parts[0].isdigit():
            age = int(parts[0])
        if len(parts) >= 2 and parts[1].isdigit():
            weight = int(parts[1])

    db = next(get_db())
    try:
        user = user_service.ensure_user(db, update.effective_user)
        user_service.update_profile(
            db,
            user,
            name=context.user_data.get("setup_name"),
            timezone=context.user_data.get("setup_timezone"),
            personality=context.user_data.get("setup_personality"),
            goal=context.user_data.get("setup_goal"),
            theme=context.user_data.get("setup_theme"),
            age=age,
            weight=weight,
        )
    finally:
        db.close()

    await update.message.reply_text(
        "Профиль готов! Добавь лекарства через /add_med и я настрою напоминания."
    )
    context.user_data.clear()
    return ConversationHandler.END
