import datetime as dt
import re

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    Update,
)
from telegram.ext import ContextTypes, ConversationHandler

from database import get_db
from models import Reminder, User
from services import achievement_service, medication_service, reminder_service, user_service
from handlers.states import ReminderState
from utils.personality import personality_text

QUICK_TIME_CHOICES = ["07:00", "08:00", "09:00", "12:00", "18:00", "21:00"]
DAY_MAPPING = {
    "пн": "mon",
    "пон": "mon",
    "mon": "mon",
    "вт": "tue",
    "tue": "tue",
    "ср": "wed",
    "wed": "wed",
    "чт": "thu",
    "thu": "thu",
    "пт": "fri",
    "fri": "fri",
    "сб": "sat",
    "суб": "sat",
    "sat": "sat",
    "вс": "sun",
    "sun": "sun",
}
DAY_NAMES = {
    "mon": "пн",
    "tue": "вт",
    "wed": "ср",
    "thu": "чт",
    "fri": "пт",
    "sat": "сб",
    "sun": "вс",
}


def _schedule_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("К конкретному времени", callback_data="rem_type:fixed_time"),
                InlineKeyboardButton("По дням недели", callback_data="rem_type:weekly"),
            ],
            [
                InlineKeyboardButton("Через интервалы", callback_data="rem_type:interval"),
                InlineKeyboardButton("После события", callback_data="rem_type:event"),
            ],
            [
                InlineKeyboardButton("По геолокации", callback_data="rem_type:geo"),
            ],
        ]
    )


def _quick_time_keyboard() -> ReplyKeyboardMarkup:
    rows = [QUICK_TIME_CHOICES[i : i + 3] for i in range(0, len(QUICK_TIME_CHOICES), 3)]
    return ReplyKeyboardMarkup(rows, resize_keyboard=True, one_time_keyboard=True)


def _parse_time(value: str) -> dt.time | None:
    cleaned = value.strip()
    cleaned = cleaned.replace(".", ":").replace(",", ":")
    cleaned = re.sub(r"\s+", "", cleaned)
    match = re.match(r"^(\d{1,2})[:\-]?(\d{2})$", cleaned)
    if not match:
        if cleaned.isdigit() and len(cleaned) in {3, 4}:
            match = re.match(r"^(\d{1,2})(\d{2})$", cleaned)
        else:
            return None
    hour = int(match.group(1))
    minute = int(match.group(2))
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    return dt.time(hour=hour, minute=minute)


async def start_reminder_setup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    db = next(get_db())
    try:
        user = user_service.ensure_user(db, update.effective_user)
        meds = medication_service.list_medications(db, user)
    finally:
        db.close()

    if not meds:
        await update.message.reply_text("Сначала добавь препарат через /add_med.")
        return ConversationHandler.END

    keyboard = [
        [InlineKeyboardButton(med.name, callback_data=f"rem_med:{med.id}")]
        for med in meds
    ]
    keyboard.append([InlineKeyboardButton("Общее напоминание", callback_data="rem_med:0")])
    await update.message.reply_text(
        "Выбери препарат для напоминания:", reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ReminderState.PICK_MED


async def select_medication(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    med_id = int(query.data.split(":")[1])
    context.user_data["reminder_payload"] = {"med_id": med_id or None}
    await query.edit_message_text("Препарат выбран. Теперь зададим расписание:", reply_markup=_schedule_keyboard())
    return ReminderState.SCHEDULE_TYPE


async def select_schedule_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    schedule_type = query.data.split(":")[1]
    context.user_data["reminder_payload"]["schedule_type"] = schedule_type

    if schedule_type in {"fixed_time", "weekly"}:
        await query.edit_message_text("Режим задан.")
        await query.message.reply_text(
            "Укажи время в формате ЧЧ:ММ или нажми готовую кнопку.",
            reply_markup=_quick_time_keyboard(),
        )
        return ReminderState.TIME
    if schedule_type == "interval":
        await query.edit_message_text("Какой интервал в часах между приёмами?")
        return ReminderState.INTERVAL
    if schedule_type == "event":
        await query.edit_message_text(
            "Опиши событие и смещение. Пример: «После завтрака +30» — напомню через 30 минут после завтрака."
        )
        return ReminderState.EVENT
    if schedule_type == "geo":
        await query.edit_message_text("Отправь геолокацию точки, где нужно напоминать.")
        return ReminderState.GEO
    return ConversationHandler.END


async def handle_time_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    when = _parse_time(update.message.text)
    if not when:
        await update.message.reply_text("Не получилось распознать время. Формат ЧЧ:ММ.")
        return ReminderState.TIME
    context.user_data["reminder_payload"]["time_of_day"] = when
    schedule_type = context.user_data["reminder_payload"]["schedule_type"]
    await update.message.reply_text(
        f"Фиксирую {when.strftime('%H:%M')}.",
        reply_markup=ReplyKeyboardRemove(),
    )
    if schedule_type == "weekly":
        await update.message.reply_text("Укажи дни недели (пример: пн, ср, пт).")
        return ReminderState.DAYS
    return await _finalize_reminder(update, context)


async def handle_days(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    tokens = [token.strip().lower() for token in update.message.text.split(",")]
    mapped = []
    for token in tokens:
        mapped.append(DAY_MAPPING.get(token[:3], token[:3]))
    context.user_data["reminder_payload"]["days_of_week"] = ",".join(mapped)
    return await _finalize_reminder(update, context)


async def handle_interval(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        interval = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("Нужно указать количество часов.")
        return ReminderState.INTERVAL
    context.user_data["reminder_payload"]["interval_hours"] = max(1, interval)
    return await _finalize_reminder(update, context)


async def handle_event(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    if "," in text:
        event_label, offset = text.split(",", 1)
        digits = "".join(ch for ch in offset if ch.isdigit() or ch == "-")
        minutes = int(digits) if digits else 0
    else:
        event_label = text
        minutes = 0
    event_label = event_label.strip()
    context.user_data["reminder_payload"]["event_label"] = event_label
    context.user_data["reminder_payload"]["offset_minutes"] = minutes
    if minutes:
        await update.message.reply_text(f"Напомню через {minutes} минут после «{event_label}».")
    else:
        await update.message.reply_text(f"Напомню сразу после события «{event_label}».")
    return await _finalize_reminder(update, context)


async def handle_geo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message.location:
        await update.message.reply_text("Пожалуйста, отправь геолокацию через кнопку.")
        return ReminderState.GEO
    context.user_data["reminder_payload"]["geo_lat"] = update.message.location.latitude
    context.user_data["reminder_payload"]["geo_lon"] = update.message.location.longitude
    return await _finalize_reminder(update, context)


async def _finalize_reminder(update, context) -> int:
    payload = context.user_data.get("reminder_payload", {})
    db = next(get_db())
    try:
        user = user_service.ensure_user(db, update.effective_user)
        med_id = payload.get("med_id")
        reminder = reminder_service.create_reminder(
            db,
            user,
            payload,
            medication_id=med_id if med_id else None,
        )
        scheduler = context.application.bot_data.get("reminder_scheduler")
        if scheduler:
            scheduler.schedule(reminder)
    finally:
        db.close()

    schedule_type = payload.get("schedule_type", "fixed_time")
    summary = "Напоминание сохранено."
    if schedule_type in {"fixed_time", "weekly"} and payload.get("time_of_day"):
        time_str = payload["time_of_day"].strftime("%H:%M")
        if schedule_type == "weekly" and payload.get("days_of_week"):
            names = [
                DAY_NAMES.get(day.strip(), day.strip())
                for day in payload["days_of_week"].split(",")
                if day.strip()
            ]
            summary = f"Буду напоминать по {', '.join(names)} в {time_str}."
        else:
            summary = f"Буду напоминать каждый день в {time_str}."
    elif schedule_type == "interval":
        summary = f"Буду напоминать каждые {payload.get('interval_hours')} час(а/ов)."
    elif schedule_type == "event":
        label = payload.get("event_label", "событие")
        minutes = payload.get("offset_minutes", 0)
        delay = f"{minutes} мин" if minutes else "без задержки"
        summary = f"Напомню после «{label}» ({delay})."
    elif schedule_type == "geo":
        summary = "Напомню, как только окажешься в сохранённой точке."

    context.user_data.pop("reminder_payload", None)
    await update.message.reply_text(summary)
    return ConversationHandler.END


def reminder_keyboard(log_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Принял ✅", callback_data=f"rem_action:take:{log_id}"),
                InlineKeyboardButton("Пропустил 🚫", callback_data=f"rem_action:skip:{log_id}"),
            ],
            [
                InlineKeyboardButton("Отложить 10м", callback_data=f"rem_snooze:{log_id}:10"),
                InlineKeyboardButton("30м", callback_data=f"rem_snooze:{log_id}:30"),
                InlineKeyboardButton("1ч", callback_data=f"rem_snooze:{log_id}:60"),
            ],
        ]
    )


async def reminder_job_callback(context: ContextTypes.DEFAULT_TYPE) -> None:
    reminder_id = context.job.data.get("reminder_id")
    manual_log_id = context.job.data.get("log_id")
    db = next(get_db())
    try:
        reminder = db.query(Reminder).filter(Reminder.id == reminder_id).first()
        if not reminder or not reminder.active:
            return
        user = db.query(User).filter(User.id == reminder.user_id).first()
        if not user:
            return
        if manual_log_id:
            log = reminder_service.get_log(db, manual_log_id)
        else:
            log = None
        if not log:
            scheduled_for = dt.datetime.utcnow()
            log = reminder_service.log_reminder(db, reminder, scheduled_for)
        text = personality_text(
            user.bot_personality,
            "reminder",
            med_name=reminder.medication.name if reminder.medication else reminder.label or "лекарство",
            name=user.name,
        ) or "Пора принять лекарство!"
        await context.bot.send_message(
            chat_id=user.telegram_id,
            text=text,
            reply_markup=reminder_keyboard(log.id),
        )
        if reminder.nag_enabled:
            context.job_queue.run_once(
                nag_callback,
                when=reminder.nag_interval_minutes * 60,
                data={"log_id": log.id},
                name=f"nag::{log.id}",
            )
    finally:
        db.close()


async def nag_callback(context: ContextTypes.DEFAULT_TYPE) -> None:
    log_id = context.job.data.get("log_id")
    db = next(get_db())
    try:
        log = reminder_service.get_log(db, log_id)
        if not log or log.status != "pending":
            return
        user = db.query(User).filter(User.id == log.user_id).first()
        if not user:
            return
        await context.bot.send_message(
            chat_id=user.telegram_id,
            text="Напоминаю, что приём ещё не подтверждён.",
            reply_markup=reminder_keyboard(log.id),
        )
    finally:
        db.close()


async def reminder_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    _, action, log_id = query.data.split(":")
    log_id = int(log_id)

    db = next(get_db())
    try:
        log = reminder_service.get_log(db, log_id)
        if not log:
            await query.edit_message_text("Запись не найдена.")
            return
        reminder = db.query(Reminder).filter(Reminder.id == log.reminder_id).first()
        user = db.query(User).filter(User.id == log.user_id).first()
        if action == "take":
            reminder_service.update_log_status(db, log, "taken")
            if reminder and reminder.medication:
                medication_service.consume_dose(db, reminder.medication)
            achievement_service.evaluate_user(db, user)
            await query.edit_message_text("Засчитано! Так держать.")
        elif action == "skip":
            reminder_service.update_log_status(db, log, "missed")
            await query.edit_message_text("Записал пропуск. Я напомню позже.")
    finally:
        db.close()


async def reminder_snooze(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    _, log_id, minutes = query.data.split(":")
    log_id = int(log_id)
    minutes = int(minutes)

    db = next(get_db())
    try:
        log = reminder_service.get_log(db, log_id)
        if not log:
            await query.edit_message_text("Напоминание не найдено.")
            return
        reminder = db.query(Reminder).filter(Reminder.id == log.reminder_id).first()
        if not reminder:
            await query.edit_message_text("Напоминание удалено.")
            return
        reminder_service.update_log_status(db, log, "snoozed")
        new_time = dt.datetime.utcnow() + dt.timedelta(minutes=minutes)
        new_log = reminder_service.log_reminder(db, reminder, new_time)
        context.job_queue.run_once(
            reminder_job_callback,
            when=minutes * 60,
            data={"reminder_id": reminder.id, "log_id": new_log.id},
        )
    finally:
        db.close()
    await query.edit_message_text(f"Отложил на {minutes} мин.")
