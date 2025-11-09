from telegram import Update
from telegram.ext import ContextTypes

from database import get_db
from services import achievement_service, export_service, stats_service, user_service


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db = next(get_db())
    try:
        user = user_service.ensure_user(db, update.effective_user)
        summary = stats_service.adherence_summary(db, user)
        chart = stats_service.weekly_plot(db, user)
    finally:
        db.close()

    text = (
        f"Соблюдение: {summary['adherence']}%\n"
        f"Выполнено: {summary['taken']} | Пропусков: {summary['missed']}\n"
    )
    await update.message.reply_photo(chart, caption=text)


async def achievements_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db = next(get_db())
    try:
        user = user_service.ensure_user(db, update.effective_user)
        new_awards = achievement_service.evaluate_user(db, user)
    finally:
        db.close()

    if new_awards:
        lines = [f"{award.icon or '🎖'} {award.title}" for award in new_awards]
        await update.message.reply_text("Новые достижения:\n" + "\n".join(lines))
    else:
        await update.message.reply_text("Пока новых достижений нет, но прогресс продолжает расти!")


async def export_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    fmt = context.args[0].lower() if context.args else "json"
    db = next(get_db())
    try:
        user = user_service.ensure_user(db, update.effective_user)
        if fmt == "csv":
            filename, payload = export_service.export_csv(db, user)
        else:
            filename, payload = export_service.export_json(db, user)
    finally:
        db.close()

    await update.message.reply_document(document=payload, filename=filename)
