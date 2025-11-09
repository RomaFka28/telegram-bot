import json
from typing import Optional

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    Update,
    WebAppInfo,
)
from telegram.ext import ContextTypes

from config import settings
from database import get_db
from models import Medication
from services import medication_service, knowledge_service, user_service


def _med_inline_keyboard(med: Medication) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(
                "История запасов", callback_data=f"med_history:{med.id}"
            ),
            InlineKeyboardButton(
                "Архивировать" if not med.archived else "Вернуть",
                callback_data=f"med_toggle:{med.id}",
            ),
        ]
    ]
    return InlineKeyboardMarkup(buttons)


async def add_med_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not settings.web_app_url:
        await update.message.reply_text("WEB_APP_URL не задан. Обратись к администратору.")
        return

    button = KeyboardButton(
        text="Открыть форму",
        web_app=WebAppInfo(url=f"{settings.web_app_url}/web/add_med.html"),
    )
    markup = ReplyKeyboardMarkup([[button]], resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text(
        "Нажми кнопку, чтобы добавить лекарство через удобную форму.",
        reply_markup=markup,
    )


async def handle_webapp_payload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    payload = json.loads(update.message.web_app_data.data)
    db = next(get_db())
    try:
        user = user_service.ensure_user(db, update.effective_user)
        medication = medication_service.create_medication(db, user, payload)
        existing_names = [
            med.name for med in medication_service.list_medications(db, user) if med.id != medication.id
        ]
    finally:
        db.close()

    warnings = await knowledge_service.check_interactions(medication.name, existing_names)
    text = (
        "\n".join(warnings)
        if warnings
        else f"{medication.name} сохранён. Настрой напоминания через /set_reminder."
    )
    await update.message.reply_text(text)


async def list_meds(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db = next(get_db())
    try:
        user = user_service.ensure_user(db, update.effective_user)
        meds = medication_service.list_medications(db, user, include_archived=True)
    finally:
        db.close()

    if not meds:
        await update.message.reply_text("Пока нет лекарств. Добавь через /add_med.")
        return

    for med in meds:
        msg = (
            f"{med.name} ({med.dosage or med.form or '—'})\n"
            f"Категория: {med.category or '—'}\n"
            f"Остаток: {med.stock_remaining}\n"
            f"Статус: {'архив' if med.archived else 'активно'}"
        )
        await update.message.reply_text(msg, reply_markup=_med_inline_keyboard(med))


async def med_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    action, med_id = query.data.split(":")
    med_id = int(med_id)

    db = next(get_db())
    try:
        medication = db.query(Medication).filter(Medication.id == med_id).first()
        if not medication:
            await query.edit_message_text("Лекарство не найдено.")
            return
        if medication.user.telegram_id != query.from_user.id:
            await query.edit_message_text("Недостаточно прав.")
            return

        if action == "med_history":
            history = medication_service.get_restock_history(db, medication)
            if not history:
                await query.edit_message_text("История пополнений пока пустая.")
                return
            text = "\n".join(
                f"{item.created_at:%d.%m %H:%M}: +{item.quantity} ({item.note or 'без примечаний'})"
                for item in history
            )
            await query.edit_message_text(text)
        elif action == "med_toggle":
            medication_service.toggle_archive(db, medication, not medication.archived)
            await query.edit_message_text(
                f"Статус обновлён: {'архив' if medication.archived else 'активно'}"
            )
    finally:
        db.close()


async def restock_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) < 2:
        await update.message.reply_text("Использование: /restock <id> <кол-во> [комментарий]")
        return
    try:
        med_id = int(context.args[0])
        quantity = float(context.args[1])
    except ValueError:
        await update.message.reply_text("ID и количество должны быть числами.")
        return
    note = " ".join(context.args[2:]) if len(context.args) > 2 else None

    db = next(get_db())
    try:
        medication = db.query(Medication).filter(Medication.id == med_id).first()
        if not medication:
            await update.message.reply_text("Лекарство не найдено.")
            return
        if medication.user.telegram_id != update.effective_user.id:
            await update.message.reply_text("Недостаточно прав.")
            return
        medication_service.restock_medication(db, medication, quantity, note)
    finally:
        db.close()
    await update.message.reply_text("Запас обновлён.")


async def restock_history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Использование: /restock_history <id>")
        return
    try:
        med_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("ID должен быть числом.")
        return
    db = next(get_db())
    try:
        medication = db.query(Medication).filter(Medication.id == med_id).first()
        if not medication:
            await update.message.reply_text("Лекарство не найдено.")
            return
        if medication.user.telegram_id != update.effective_user.id:
            await update.message.reply_text("Недостаточно прав.")
            return
        entries = medication_service.get_restock_history(db, medication)
    finally:
        db.close()

    if not entries:
        await update.message.reply_text("История пуста.")
        return

    text = "\n".join(
        f"{item.created_at:%d.%m %H:%M}: +{item.quantity} ({item.note or 'без примечаний'})"
        for item in entries
    )
    await update.message.reply_text(text)
