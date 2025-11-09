from telegram import (
    Update,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    KeyboardButton,
)
from telegram.ext import ContextTypes, ConversationHandler

from database import get_db
from services import user_service
from handlers.states import SetupState
from utils.messages import DISCLAIMER, PERSONALITY_CHOICES, THEME_CHOICES
from utils.timezone import resolve_timezone, timezone_from_location


async def _prompt_personality(update: Update) -> int:
    personas = "\n".join([f"- {title}" for _, title in PERSONALITY_CHOICES])
    await update.message.reply_text(
        "Выбери стиль общения:\n" + personas,
        reply_markup=ReplyKeyboardRemove(),
    )
    return SetupState.PERSONALITY


async def start_setup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        f"{DISCLAIMER}\n\nПривет! Как тебя зовут?",
    )
    return SetupState.NAME


async def collect_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["setup_name"] = update.message.text.strip()
    keyboard = ReplyKeyboardMarkup(
        [[KeyboardButton("📍 Поделиться геолокацией", request_location=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
    await update.message.reply_text(
        "Отправь точку на карте — так я определю твой часовой пояс и смогу напоминать вовремя.\n"
        "Если не хочешь делиться геолокацией, просто напиши часовой пояс (например, Europe/Moscow).",
        reply_markup=keyboard,
    )
    return SetupState.TIMEZONE


async def collect_timezone_from_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    location = update.message.location
    timezone = timezone_from_location(location.latitude, location.longitude)
    if not timezone:
        await update.message.reply_text(
            "Не получилось понять часовой пояс по координатам. Напиши его вручную, например Europe/Moscow.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return SetupState.TIMEZONE
    context.user_data["setup_timezone"] = timezone
    await update.message.reply_text(
        f"Отлично, буду ориентироваться на {timezone}.",
        reply_markup=ReplyKeyboardRemove(),
    )
    return await _prompt_personality(update)


async def collect_timezone_from_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    tz_value = update.message.text.strip()
    resolved = resolve_timezone(tz_value)
    if not resolved:
        await update.message.reply_text(
            "Не удалось распознать часовой пояс. Укажи его в формате Europe/Moscow или отправь геолокацию.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return SetupState.TIMEZONE
    context.user_data["setup_timezone"] = resolved
    await update.message.reply_text(
        f"Супер, фиксирую {resolved}.",
        reply_markup=ReplyKeyboardRemove(),
    )
    return await _prompt_personality(update)


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
    await update.message.reply_text("Какая цель? Например: «30 дней без пропусков».")
    return SetupState.GOAL


async def collect_goal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["setup_goal"] = update.message.text.strip()
    themes = "\n".join([f"- {label}" for _, label in THEME_CHOICES])
    await update.message.reply_text(
        "Выбери тему оформления (цвета/эмодзи):\n" + themes
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
        "Последний шаг: напиши возраст и вес (например, 30, 70) или «-», если не хочешь делиться.",
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
        "Профиль готов! Добавь лекарства через /add_med и я начну напоминать.",
    )
    context.user_data.clear()
    return ConversationHandler.END
