import asyncio
import logging
import os
from functools import partial

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

from config import settings
from database import get_db, init_db
from handlers import (
    SetupState,
    ReminderState,
    ProfileEditState,
    onboarding,
    profile,
    medications,
    reminders,
    stats,
    lifestyle,
    misc,
)
from models import Medication
from services import medication_service, reminder_service
from services.reminder_scheduler import ReminderScheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("health_buddy")


async def stock_watch_job(context):
    notified = context.application.bot_data.setdefault("low_stock_notified", set())
    db = next(get_db())
    try:
        meds = db.query(Medication).filter(Medication.archived.is_(False)).all()
        for med in meds:
            if medication_service.is_low_stock(med):
                if med.id in notified:
                    continue
                text = (
                    f"Заканчивается {med.name}. Осталось всего {med.stock_remaining}."
                    "\nЧто делаем?"
                )
                keyboard = InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "Найти аптеки",
                                url="https://www.google.com/maps/search/%D0%B0%D0%BF%D1%82%D0%B5%D0%BA%D0%B0/",
                            ),
                            InlineKeyboardButton(
                                "Заметка врачу",
                                url="https://t.me/share/url?text=%D0%9F%D0%BE%D0%B7%D0%B2%D0%BE%D0%BD%D0%B8%D1%82%D1%8C%20%D0%B2%D1%80%D0%B0%D1%87%D1%83%20%D0%B7%D0%B0%20%D1%80%D0%B5%D1%86%D0%B5%D0%BF%D1%82%D0%BE%D0%BC",
                            ),
                        ]
                    ]
                )
                await context.bot.send_message(
                    chat_id=med.user.telegram_id,
                    text=text,
                    reply_markup=keyboard,
                )
                notified.add(med.id)
            else:
                notified.discard(med.id)
    finally:
        db.close()


def build_application() -> Application:
    if not settings.bot_token or settings.bot_token == "YOUR_TOKEN":
        raise RuntimeError("TELEGRAM_TOKEN не задан.")

    init_db()
    application = Application.builder().token(settings.bot_token).build()

    # Basic commands
    application.add_handler(CommandHandler("start", misc.start_command))
    application.add_handler(CommandHandler("help", misc.help_command))
    application.add_handler(CommandHandler("profile", profile.show_profile))
    application.add_handler(CommandHandler("add_med", medications.add_med_command))
    application.add_handler(CommandHandler("meds", medications.list_meds))
    application.add_handler(CommandHandler("restock", medications.restock_command))
    application.add_handler(CommandHandler("restock_history", medications.restock_history))
    application.add_handler(CommandHandler("stats", stats.stats_command))
    application.add_handler(CommandHandler("achievements", stats.achievements_command))
    application.add_handler(CommandHandler("export", stats.export_command))
    application.add_handler(CommandHandler("symptom", lifestyle.symptom_command))
    application.add_handler(CommandHandler("mood", lifestyle.mood_command))
    application.add_handler(CommandHandler("water", lifestyle.water_command))

    # Conversations
    setup_conv = ConversationHandler(
        entry_points=[CommandHandler("setup", onboarding.start_setup)],
        states={
            SetupState.NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, onboarding.collect_name)],
            SetupState.TIMEZONE: [
                MessageHandler(filters.LOCATION, onboarding.collect_timezone_from_location),
                MessageHandler(filters.TEXT & ~filters.COMMAND, onboarding.collect_timezone_from_text),
            ],
            SetupState.PERSONALITY: [CallbackQueryHandler(onboarding.collect_personality_choice, pattern="^persona:")],
            SetupState.GOAL: [
                CallbackQueryHandler(onboarding.collect_goal_choice, pattern="^goal:"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, onboarding.collect_goal),
            ],
            SetupState.OPTIONAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, onboarding.finalize_setup)],
        },
        fallbacks=[CommandHandler("cancel", misc.cancel)],
    )
    application.add_handler(setup_conv)

    reminder_conv = ConversationHandler(
        entry_points=[CommandHandler("set_reminder", reminders.start_reminder_setup)],
        states={
            ReminderState.PICK_MED: [CallbackQueryHandler(reminders.select_medication, pattern="^rem_med:")],
            ReminderState.SCHEDULE_TYPE: [CallbackQueryHandler(reminders.select_schedule_type, pattern="^rem_type:")],
            ReminderState.TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, reminders.handle_time_input)],
            ReminderState.DAYS: [MessageHandler(filters.TEXT & ~filters.COMMAND, reminders.handle_days)],
            ReminderState.INTERVAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, reminders.handle_interval)],
            ReminderState.EVENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, reminders.handle_event)],
            ReminderState.GEO: [
                MessageHandler(filters.LOCATION, reminders.handle_geo),
                MessageHandler(filters.TEXT & ~filters.COMMAND, reminders.handle_geo),
            ],
        },
        fallbacks=[CommandHandler("cancel", misc.cancel)],
    )
    application.add_handler(reminder_conv)

    profile_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(profile.profile_edit_callback, pattern="^profile_edit:")],
        states={
            ProfileEditState.VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, profile.apply_profile_edit)],
        },
        fallbacks=[CommandHandler("cancel", misc.cancel)],
    )
    application.add_handler(profile_conv)

    # Inline callbacks
    application.add_handler(CallbackQueryHandler(medications.med_callback, pattern="^med_"))
    application.add_handler(CallbackQueryHandler(reminders.reminder_action, pattern="^rem_action:"))
    application.add_handler(CallbackQueryHandler(reminders.reminder_snooze, pattern="^rem_snooze:"))

    # WebApp payload
    application.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, medications.handle_webapp_payload))

    scheduler = ReminderScheduler(application.job_queue, reminders.reminder_job_callback)
    application.bot_data["reminder_scheduler"] = scheduler
    db = next(get_db())
    try:
        for reminder in reminder_service.upcoming_reminders(db):
            scheduler.schedule(reminder)
    finally:
        db.close()

    application.job_queue.run_repeating(
        stock_watch_job,
        interval=1800,
        first=30,
        name="stock-watch",
    )

    return application


def main():
    application = build_application()
    application.run_polling()


if __name__ == "__main__":
    main()
