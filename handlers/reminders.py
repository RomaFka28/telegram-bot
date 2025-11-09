import datetime as dt

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes, ConversationHandler

from database import get_db
from models import Reminder, User
from services import achievement_service, medication_service, reminder_service, user_service
from handlers.states import ReminderState
from utils.personality import personality_text
from handlers import family as family_handlers


def _schedule_keyboard():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("По времени", callback_data="rem_type:fixed_time"),
                InlineKeyboardButton("По дням недели", callback_data="rem_type:weekly"),
            ],
            [
                InlineKeyboardButton("Интервалы", callback_data="rem_type:interval"),
                InlineKeyboardButton("Перед/после события", callback_data="rem_type:event"),
            ],
            [
                InlineKeyboardButton("Гео-триггер", callback_data="rem_type:geo"),
            ],
        ]
    )


async def start_reminder_setup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    db = next(get_db())
    try:
        user = user_service.ensure_user(db, update.effective_user)
        meds = medication_service.list_medications(db, user)
    finally:
        db.close()

    if not meds:
        await update.message.reply_text("Сначала добавь лекарство через /add_med.")
        return ConversationHandler.END

    keyboard = [
        [InlineKeyboardButton(med.name, callback_data=f"rem_med:{med.id}")]
        for med in meds
    ]
    keyboard.append(
        [InlineKeyboardButton("Общее напоминание", callback_data="rem_med:0")]
    )
    await update.message.reply_text(
        "Выбери лекарство для напоминания:", reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ReminderState.PICK_MED


async def select_medication(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    med_id = int(query.data.split(":")[1])
    context.user_data["reminder_payload"] = {"med_id": med_id or None}
    await query.edit_message_text("Выбери тип расписания.", reply_markup=_schedule_keyboard())
    return ReminderState.SCHEDULE_TYPE


async def select_schedule_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    schedule_type = query.data.split(":")[1]
    context.user_data["reminder_payload"]["schedule_type"] = schedule_type
    if schedule_type in {"fixed_time", "weekly"}:
        await query.edit_message_text("Укажи время в формате ЧЧ:ММ.")
        return ReminderState.TIME
    if schedule_type == "interval":
        await query.edit_message_text("Какой интервал в часах между приёмами?")
        return ReminderState.INTERVAL
    if schedule_type == "event":
        await query.edit_message_text("Опиши событие и смещение, пример: 'После завтрака, +30'.")
        return ReminderState.EVENT
    if schedule_type == "geo":
        await query.edit_message_text("Отправь геолокацию места, где нужно напоминать.")
        return ReminderState.GEO
    return -1


async def handle_time_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    try:
        hour, minute = map(int, text.split(":"))
        when = dt.time(hour=hour, minute=minute)
    except Exception:
        await update.message.reply_text("Не получилось распознать время. Формат ЧЧ:ММ.")
        return ReminderState.TIME
    context.user_data["reminder_payload"]["time_of_day"] = when
    if context.user_data["reminder_payload"]["schedule_type"] == "weekly":
        await update.message.reply_text("Укажи дни недели (пример: пн, ср, пт).")
        return ReminderState.DAYS
    return await _finalize_reminder(update, context)


async def handle_days(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    mapping = {
        "пн": "mon",
        "вт": "tue",
        "ср": "wed",
        "чт": "thu",
        "пт": "fri",
        "сб": "sat",
        "сбт": "sat",
        "вс": "sun",
    }
    days = []
    for token in text.split(","):
        key = token.strip().lower()[:2]
        days.append(mapping.get(key, token.strip().lower()[:3]))
    context.user_data["reminder_payload"]["days_of_week"] = ",".join(days)
    return await _finalize_reminder(update, context)


async def handle_interval(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        interval = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("Нужно число часов.")
        return ReminderState.INTERVAL
    context.user_data["reminder_payload"]["interval_hours"] = max(1, interval)
    return await _finalize_reminder(update, context)


async def handle_event(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    if "," in text:
        event_label, offset = text.split(",", 1)
        offset = offset.strip().replace("+", "")
        digits = "".join(ch for ch in offset if ch.isdigit())
        minutes = int(digits) if digits else 0
    else:
        event_label = text
        minutes = 0
    context.user_data["reminder_payload"]["event_label"] = event_label.strip()
    context.user_data["reminder_payload"]["offset_minutes"] = minutes
    return await _finalize_reminder(update, context)


async def handle_geo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message.location:
        await update.message.reply_text("Пожалуйста, поделись геолокацией через кнопку.")
        return ReminderState.GEO
    context.user_data["reminder_payload"]["geo_lat"] = update.message.location.latitude
    context.user_data["reminder_payload"]["geo_lon"] = update.message.location.longitude
    return await _finalize_reminder(update, context)


async def _finalize_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
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

    context.user_data.pop("reminder_payload", None)
    await update.message.reply_text("Напоминание сохранено! Я начну следить за временем.")
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
            if reminder.medication:
                medication_service.consume_dose(db, reminder.medication)
            achievement_service.evaluate_user(db, user)
            await query.edit_message_text("Отмечено! Молодец 👍")
        elif action == "skip":
            reminder_service.update_log_status(db, log, "missed")
            await query.edit_message_text("Записал пропуск. Я напомню позже.")
            await family_handlers.notify_caregivers(context, user.telegram_id, "❗ Пропущен важный приём.")
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
    await query.edit_message_text(f"Отложил на {minutes} минут.")
