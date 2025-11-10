import json
from typing import Optional

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    Update,
    WebAppInfo,
)
from telegram.ext import ContextTypes, ConversationHandler

from config import settings
from database import get_db
from models import Medication
from services import medication_service, knowledge_service, user_service
from handlers.states import StockEditState

STOCK_EDIT_KEY = "pending_stock_edit"


def _med_inline_keyboard(med: Medication) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton("История запасов", callback_data=f"med_history:{med.id}"),
            InlineKeyboardButton(
                "Архивировать" if not med.archived else "Вернуть",
                callback_data=f"med_toggle:{med.id}",
            ),
        ],
        [
            InlineKeyboardButton("Изменить остаток", callback_data=f"med_stock:{med.id}"),
        ],
    ]
    return InlineKeyboardMarkup(buttons)


async def add_med_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not settings.web_app_url:
        await update.message.reply_text("WEB_APP_URL не настроен. Обратитесь к администратору.")
        return

    button = KeyboardButton(
        text="Открыть форму",
        web_app=WebAppInfo(url=f"{settings.web_app_url}/web/add_med.html"),
    )
    markup = ReplyKeyboardMarkup([[button]], resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text(
        "Нажми кнопку, чтобы заполнить карточку. После отправки я сразу учту лекарство.",
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
    if warnings:
        await update.message.reply_text("\n".join(warnings))
    else:
        await update.message.reply_text(
            f"{medication.name} добавлен. Можно настроить напоминания через /set_reminder."
        )


def _format_med_message(med: Medication) -> str:
    lines = [
        f"💊 {med.name}",
    ]
    details = []
    if med.dosage:
        details.append(med.dosage)
    if med.form:
        details.append(med.form)
    lines.append(" · ".join(details) if details else "Форма: не указана")
    lines.append(f"Категория: {med.category or '—'}")
    lines.append(f"Остаток: {med.stock_remaining:g}")
    lines.append(f"Статус: {'архив' if med.archived else 'активен'}")
    lines.append("")
    lines.append(f"Пополнить: /restock {med.id} 20  # добавит +20 доз")
    lines.append(f"Изменить остаток: /set_stock {med.id} 50  # установит 50 доз")
    return "\n".join(lines)


async def list_meds(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db = next(get_db())
    try:
        user = user_service.ensure_user(db, update.effective_user)
        meds = medication_service.list_medications(db, user, include_archived=True)
    finally:
        db.close()

    if not meds:
        await update.message.reply_text("Пока нет лекарств. Используй /add_med.")
        return

    for med in meds:
        await update.message.reply_text(_format_med_message(med), reply_markup=_med_inline_keyboard(med))


async def med_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    action, med_id = query.data.split(":")
    med_id = int(med_id)

    db = next(get_db())
    try:
        medication = db.query(Medication).filter(Medication.id == med_id).first()
        if not medication:
            await query.edit_message_text("Препарат не найден.")
            return
        if medication.user.telegram_id != query.from_user.id:
            await query.edit_message_text("Недостаточно прав.")
            return

        if action == "med_history":
            history = medication_service.get_restock_history(db, medication)
            if not history:
                await query.edit_message_text("История пока пуста.")
                return
            text = "\n".join(
                f"{item.created_at:%d.%m %H:%M}: +{item.quantity:g} ({item.note or 'без примечаний'})"
                for item in history
            )
            await query.edit_message_text(text)
        elif action == "med_toggle":
            medication_service.toggle_archive(db, medication, not medication.archived)
            await query.edit_message_text(
                "Статус обновлён: {}".format("архив" if medication.archived else "активен")
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
            await update.message.reply_text("Препарат не найден.")
            return
        if medication.user.telegram_id != update.effective_user.id:
            await update.message.reply_text("Недостаточно прав.")
            return
        medication_service.restock_medication(db, medication, quantity, note)
        snapshot = _format_med_message(medication)
    finally:
        db.close()
    await update.message.reply_text("Запас обновлён.")
    await update.message.reply_text(snapshot, reply_markup=_med_inline_keyboard(medication))


async def set_stock_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) < 2:
        await update.message.reply_text("Использование: /set_stock <id> <остаток>")
        return
    try:
        med_id = int(context.args[0])
        value = float(context.args[1])
    except ValueError:
        await update.message.reply_text("ID и остаток должны быть числами.")
        return

    db = next(get_db())
    try:
        medication = db.query(Medication).filter(Medication.id == med_id).first()
        if not medication:
            await update.message.reply_text("Препарат не найден.")
            return
        if medication.user.telegram_id != update.effective_user.id:
            await update.message.reply_text("Недостаточно прав.")
            return
        medication.stock_remaining = max(0.0, value)
        db.commit()
        snapshot = _format_med_message(medication)
    finally:
        db.close()
    await update.message.reply_text(f"Остаток установлен: {value:g}")
    await update.message.reply_text(snapshot, reply_markup=_med_inline_keyboard(medication))


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
            await update.message.reply_text("Препарат не найден.")
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
        f"{item.created_at:%d.%m %H:%M}: +{item.quantity:g} ({item.note or 'без примечаний'})"
        for item in entries
    )
    await update.message.reply_text(text)


async def stock_edit_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    med_id = int(query.data.split(":")[1])

    db = next(get_db())
    try:
        medication = db.query(Medication).filter(Medication.id == med_id).first()
        if not medication:
            await query.edit_message_text("Препарат не найден.")
            return ConversationHandler.END
        if medication.user.telegram_id != query.from_user.id:
            await query.edit_message_text("Недостаточно прав.")
            return ConversationHandler.END
    finally:
        db.close()

    context.user_data[STOCK_EDIT_KEY] = med_id
    await query.message.reply_text(
        f"Напиши новое количество для «{medication.name}» (пример: `45` или `+10`).",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove(),
    )
    return StockEditState.VALUE


async def stock_edit_apply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    med_id = context.user_data.get(STOCK_EDIT_KEY)
    if not med_id:
        return ConversationHandler.END

    text = update.message.text.strip().replace(",", ".")
    try:
        if text.startswith(("+", "-")):
            delta = float(text)
            absolute = None
        else:
            delta = None
            absolute = float(text)
    except ValueError:
        await update.message.reply_text(
            "Не получилось распознать число. Пример: `+10` или `50`.",
            parse_mode="Markdown",
        )
        return StockEditState.VALUE

    db = next(get_db())
    try:
        medication = db.query(Medication).filter(Medication.id == med_id).first()
        if not medication:
            await update.message.reply_text("Препарат не найден.")
            context.user_data.pop(STOCK_EDIT_KEY, None)
            return
        if medication.user.telegram_id != update.effective_user.id:
            await update.message.reply_text("Недостаточно прав.")
            context.user_data.pop(STOCK_EDIT_KEY, None)
            return
        if delta is not None:
            medication.stock_remaining = max(0.0, medication.stock_remaining + delta)
        else:
            medication.stock_remaining = max(0.0, absolute)
        db.commit()
        new_value = medication.stock_remaining
    finally:
        db.close()
    context.user_data.pop(STOCK_EDIT_KEY, None)
    await update.message.reply_text(
        f"Остаток обновлён. Текущее значение: {new_value:g}",
        reply_markup=ReplyKeyboardRemove(),
    )
    await update.message.reply_text(
        _format_med_message(medication),
        reply_markup=_med_inline_keyboard(medication),
    )
    return ConversationHandler.END
