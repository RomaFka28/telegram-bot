from telegram import Update
from telegram.ext import ContextTypes

from database import get_db
from services import family_service, user_service


async def family_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db = next(get_db())
    try:
        user = user_service.ensure_user(db, update.effective_user)
        caregivers = family_service.caregivers(db, user)
        receivers = family_service.care_receivers(db, user)
    finally:
        db.close()

    lines = ["👨‍👩‍👧 Семейный режим"]
    if caregivers:
        lines.append("Твои наблюдатели:")
        lines.extend([f"- {link.caregiver.name}" for link in caregivers if link.caregiver])
    else:
        lines.append("Пока никто не подписан на твой прогресс.")

    if receivers:
        lines.append("\nТы следишь за:")
        lines.extend([f"- {link.care_receiver.name}" for link in receivers if link.care_receiver])
    await update.message.reply_text("\n".join(lines))


async def family_invite(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db = next(get_db())
    try:
        user = user_service.ensure_user(db, update.effective_user)
        invite = family_service.create_invite(db, user)
    finally:
        db.close()
    await update.message.reply_text(
        "Поделись кодом приглашения с близким человеком:\n"
        f"/family_accept {invite.token}"
    )


async def family_accept(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Использование: /family_accept <код>")
        return
    token = context.args[0]
    db = next(get_db())
    try:
        user = user_service.ensure_user(db, update.effective_user)
        link = family_service.accept_invite(db, user, token)
    finally:
        db.close()

    if not link:
        await update.message.reply_text("Код не найден или уже использован.")
    else:
        await update.message.reply_text("Готово! Теперь ты получаешь важные уведомления.")


async def notify_caregivers(context: ContextTypes.DEFAULT_TYPE, telegram_id: int, text: str) -> None:
    db = next(get_db())
    try:
        user = user_service.get_user(db, telegram_id)
        if not user:
            return
        links = family_service.caregivers(db, user)
        targets = [link.caregiver for link in links if link.caregiver and link.caregiver.telegram_id]
    finally:
        db.close()

    for caregiver in targets:
        await context.bot.send_message(chat_id=caregiver.telegram_id, text=text)
