from telegram import (
    Update,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    KeyboardButton,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import ContextTypes, ConversationHandler

from database import get_db
from services import user_service
from handlers.states import SetupState
from utils.messages import DISCLAIMER, PERSONALITY_CHOICES
from utils.timezone import resolve_timezone, timezone_from_location

GOAL_PRESETS = [
    ("goal:discipline", "30 дней без пропусков"),
    ("goal:hydration", "Выпивать 2 литра воды"),
    ("goal:energy", "Больше энергии днём"),
    ("goal:sleep", "Стабильный сон"),
    ("goal:custom", "Своя цель"),
]


def _personality_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(label, callback_data=f"persona:{slug}")]
         for slug, label in PERSONALITY_CHOICES]
    )


def _goal_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(label, callback_data=slug)] for slug, label in GOAL_PRESETS]
    )


async def _prompt_personality(update: Update) -> int:
    await update.message.reply_text(
        "Выбери стиль общения, чтобы я знал, как лучше мотивировать:",
        reply_markup=_personality_keyboard(),
    )
    return SetupState.PERSONALITY


async def _prompt_goal(update: Update) -> int:
    await update.message.reply_text(
        "Какая цель на ближайшее время?\n"
        "Можешь выбрать готовую или написать свою.",
        reply_markup=_goal_keyboard(),
    )
    return SetupState.GOAL


async def _prompt_final_step(message: Update | Message) -> int:
    await message.reply_text(
        "Последний шаг: укажи возраст и вес через пробел (например `30 70`).\n"
        "Если не хочешь делиться — напиши «-».",
        parse_mode="Markdown",
    )
    return SetupState.OPTIONAL


async def start_setup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        f"{DISCLAIMER}\n\nПривет! Как тебя зовут?",
    )
    return SetupState.NAME


async def collect_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["setup_name"] = update.message.text.strip()
    keyboard = ReplyKeyboardMarkup(
        [[KeyboardButton("📍 Отправить геолокацию", request_location=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
    await update.message.reply_text(
        "Отправь точку на карте — так я точно определю часовой пояс и напоминания будут вовремя.\n"
        "Если удобнее, просто напиши город (например, Томск или Казань).",
        reply_markup=keyboard,
    )
    return SetupState.TIMEZONE


async def collect_timezone_from_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    location = update.message.location
    timezone = timezone_from_location(location.latitude, location.longitude)
    if not timezone:
        await update.message.reply_text(
            "Не удалось определить часовой пояс. Напиши его вручную в формате Europe/Moscow.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return SetupState.TIMEZONE
    context.user_data["setup_timezone"] = timezone
    await update.message.reply_text(
        f"Использую часовой пояс {timezone}.",
        reply_markup=ReplyKeyboardRemove(),
    )
    return await _prompt_personality(update)


async def collect_timezone_from_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    tz_value = update.message.text.strip()
    resolved = resolve_timezone(tz_value)
    if not resolved:
        await update.message.reply_text(
            "Не получилось распознать часовой пояс. Напиши его в формате Europe/Moscow или отправь геолокацию.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return SetupState.TIMEZONE
    context.user_data["setup_timezone"] = resolved
    await update.message.reply_text(
        f"Отлично, записываю {resolved}.",
        reply_markup=ReplyKeyboardRemove(),
    )
    return await _prompt_personality(update)


async def collect_personality_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    slug = query.data.split(":", 1)[1]
    context.user_data["setup_personality"] = slug
    await query.edit_message_text("Стиль общения сохранён.")
    return await _prompt_goal(query.message)


async def collect_goal_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    slug = query.data
    preset_map = dict(GOAL_PRESETS)
    if slug == "goal:custom":
        await query.edit_message_text("Напиши свою цель в следующем сообщении.")
        return SetupState.GOAL
    context.user_data["setup_goal"] = preset_map.get(slug, "")
    await query.edit_message_text(f"Цель «{preset_map.get(slug)}» сохранена.")
    return await _prompt_final_step(query.message)


async def collect_goal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["setup_goal"] = update.message.text.strip()
    return await _prompt_final_step(update.message)


async def finalize_setup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    age = weight = None
    if text != "-":
        parts = text.replace(",", " ").split()
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
            age=age,
            weight=weight,
        )
    finally:
        db.close()

    await update.message.reply_text(
        "Отлично! Профиль настроен. Добавь препараты через /add_med и я начну заботу.",
        reply_markup=ReplyKeyboardRemove(),
    )
    context.user_data.clear()
    return ConversationHandler.END
