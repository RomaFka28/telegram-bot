from telegram import Update
from telegram.ext import ContextTypes

from database import get_db
from services import lifestyle_service, user_service


async def symptom_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text.replace("/symptom", "", 1).strip()
    if not text:
        await update.message.reply_text("Пример: /symptom Головная боль, 7/10")
        return
    parts = [part.strip() for part in text.split(",")]
    description = parts[0]
    severity = 5
    if len(parts) > 1:
        digits = "".join(ch for ch in parts[1] if ch.isdigit())
        if digits.isdigit():
            severity = max(1, min(10, int(digits)))

    db = next(get_db())
    try:
        user = user_service.ensure_user(db, update.effective_user)
        lifestyle_service.log_symptom(db, user, description, severity)
        insight = lifestyle_service.symptom_insight(db, user)
    finally:
        db.close()

    response = f"Записал симптом «{description}», интенсивность {severity}/10."
    if insight:
        response += f"\n\n{insight}"
    await update.message.reply_text(response)


async def mood_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Использование: /mood <оценка 1-10> [комментарий]")
        return
    try:
        score = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Нужна числовая оценка от 1 до 10.")
        return
    note = " ".join(context.args[1:]) if len(context.args) > 1 else None

    db = next(get_db())
    try:
        user = user_service.ensure_user(db, update.effective_user)
        lifestyle_service.log_mood(db, user, max(1, min(10, score)), note)
    finally:
        db.close()
    await update.message.reply_text("Настроение сохранено.")


async def water_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    amount = 250
    if context.args:
        try:
            amount = int(context.args[0])
        except ValueError:
            pass
    db = next(get_db())
    try:
        user = user_service.ensure_user(db, update.effective_user)
        lifestyle_service.log_water(db, user, amount)
    finally:
        db.close()
    await update.message.reply_text(f"Отлично! +{amount} мл к дневному балансу.")
