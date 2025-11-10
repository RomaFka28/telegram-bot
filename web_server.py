import json
import logging
import os
import time

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from telegram import Bot
from telegram.error import TelegramError
import uvicorn

from config import settings
from database import get_db
from models import Medication
from services import medication_service, stats_service, user_service
from utils.webapp import verify_init_data

app = FastAPI()
logger = logging.getLogger("webapp_api")
bot = Bot(settings.bot_token) if settings.bot_token else None
PROFILE_NOTIFY_COOLDOWN_SECONDS = 60
_profile_notify_last: dict[int, float] = {}

# Mount the static files directory
app.mount("/web", StaticFiles(directory="web"), name="web")

@app.get("/")
async def read_root():
    return {"message": "Health Buddy WebApp Server"}

@app.get("/web/add_med.html", response_class=HTMLResponse)
async def read_add_med_form():
    with open(os.path.join("web", "add_med.html"), "r") as f:
        return f.read()


def resolve_user(db, init_data: str):
    try:
        parsed = verify_init_data(init_data, settings.bot_token)
    except ValueError as exc:
        logger.warning("Invalid init data: %s", exc)
        raise HTTPException(status_code=400, detail="Invalid init data") from exc
    user_payload = parsed.get("user")
    if not user_payload:
        raise HTTPException(status_code=400, detail="User payload missing")
    if isinstance(user_payload, str):
        try:
            user_dict = json.loads(user_payload)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail="Malformed user payload") from exc
    else:
        user_dict = user_payload
    telegram_id = user_dict.get("id")
    if not telegram_id:
        raise HTTPException(status_code=400, detail="User id missing")
    user = user_service.get_user(db, telegram_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user, user_dict

def serialize_medication(med: Medication) -> dict:
    return {
        "id": med.id,
        "name": med.name,
        "dosage": med.dosage,
        "form": med.form,
        "category": med.category,
        "dose_units": med.dose_units,
        "dose_size": med.dose_size,
        "pack_total": med.pack_total,
        "stock_remaining": med.stock_remaining,
        "stock": med.stock_remaining,
        "notes": med.notes,
        "photo_file_id": med.photo_file_id,
        "archived": med.archived,
    }


def serialize_profile(user):
    return {
        "id": user.id,
        "telegram_id": user.telegram_id,
        "name": user.name,
        "goal": user.goal,
        "timezone": user.timezone,
        "personality": user.bot_personality,
        "notify_profile_updates": user.profile_update_notifications,
    }


@app.get("/api/medications")
async def medications_preview(init_data: str):
    db = next(get_db())
    try:
        user, user_payload = resolve_user(db, init_data)
        meds = medication_service.list_medications(db, user, include_archived=True)
        items = [serialize_medication(med) for med in meds]
        logger.info("WebApp GET medications for user %s (%d items)", user.telegram_id, len(items))
        return {"items": items, "user": user_payload}
    except HTTPException as http_exc:
        logger.warning("WebApp GET medications failed: %s", http_exc.detail)
        raise
    except Exception as exc:
        logger.exception("Unexpected error in GET /api/medications")
        raise HTTPException(status_code=500, detail="Internal error") from exc
    finally:
        db.close()


class MedicationUpdate(BaseModel):
    init_data: str
    name: str | None = None
    stock: float | None = None
    dosage: str | None = None
    form: str | None = None
    category: str | None = None
    dose_units: str | None = None
    dose_size: float | None = None
    pack_total: float | None = None
    notes: str | None = None
    photo_file_id: str | None = None
    archived: bool | None = None


class ProfileUpdate(BaseModel):
    init_data: str
    name: str | None = None
    goal: str | None = None
    timezone: str | None = None
    personality: str | None = None
    notify_profile_updates: bool | None = None


@app.put("/api/medications/{med_id}")
async def update_medication(med_id: int, payload: MedicationUpdate):
    db = next(get_db())
    try:
        user, _ = resolve_user(db, payload.init_data)
        medication = (
            db.query(Medication)
            .filter(Medication.id == med_id, Medication.user_id == user.id)
            .first()
        )
        if not medication:
            logger.warning("WebApp update failed: medication %s not found for user %s", med_id, user.telegram_id)
            raise HTTPException(status_code=404, detail="Medication not found")
        before = serialize_medication(medication)
        if payload.name is not None:
            medication.name = payload.name
        if payload.stock is not None:
            medication.stock_remaining = max(0.0, payload.stock)
        if payload.dosage is not None:
            medication.dosage = payload.dosage
        if payload.form is not None:
            medication.form = payload.form
        if payload.category is not None:
            medication.category = payload.category
        if payload.dose_units is not None:
            medication.dose_units = payload.dose_units
        if payload.dose_size is not None:
            medication.dose_size = max(0.0, payload.dose_size)
        if payload.pack_total is not None:
            medication.pack_total = max(0.0, payload.pack_total)
        if payload.notes is not None:
            medication.notes = payload.notes
        if payload.photo_file_id is not None:
            medication.photo_file_id = payload.photo_file_id
        if payload.archived is not None:
            medication.archived = payload.archived
        db.commit()
        db.refresh(medication)
        after = serialize_medication(medication)
        logger.info(
            "Medication %s updated via WebApp by %s (changes=%s)",
            med_id,
            user.telegram_id,
            {k: after[k] for k in after if after[k] != before.get(k)},
        )
        return after
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Unexpected error updating medication via WebApp")
        raise HTTPException(status_code=500, detail="Internal error") from exc
    finally:
        db.close()


@app.get("/api/profile")
async def profile_view(init_data: str):
    db = next(get_db())
    try:
        user, user_payload = resolve_user(db, init_data)
        meds = medication_service.list_medications(db, user, include_archived=True)
        logger.info("WebApp GET profile for user %s", user.telegram_id)
        return {
            "profile": serialize_profile(user),
            "medications": [serialize_medication(med) for med in meds],
            "user": user_payload,
        }
    except HTTPException:
        raise
    except Exception:
        logger.exception("Unexpected error in GET /api/profile")
        raise HTTPException(status_code=500, detail="Internal error")
    finally:
        db.close()


@app.put("/api/profile")
async def profile_update(payload: ProfileUpdate):
    db = next(get_db())
    try:
        user, _ = resolve_user(db, payload.init_data)
        updated = user_service.update_profile(
            db,
            user,
            name=payload.name or user.name,
            goal=payload.goal if payload.goal is not None else user.goal,
            timezone=payload.timezone or user.timezone,
            personality=payload.personality or user.bot_personality,
            profile_update_notifications=payload.notify_profile_updates,
        )
        logger.info("Profile updated via WebApp by %s", user.telegram_id)
        await notify_profile_update(updated)
        return {"profile": serialize_profile(updated)}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Unexpected error in PUT /api/profile")
        raise HTTPException(status_code=500, detail="Internal error")
    finally:
        db.close()


async def notify_profile_update(user):
    if not bot:
        logger.warning("Telegram bot token missing, skip profile update notification")
        return
    if not getattr(user, "profile_update_notifications", True):
        logger.info("Profile update notifications disabled for %s", user.telegram_id)
        return
    now = time.monotonic()
    last_sent = _profile_notify_last.get(user.id)
    if last_sent and now - last_sent < PROFILE_NOTIFY_COOLDOWN_SECONDS:
        logger.info(
            "Skip profile update notification for %s due to cooldown", user.telegram_id
        )
        return
    text = (
        "Профиль обновлён через WebApp.\n"
        f"Цель: {user.goal or '—'}\n"
        f"Часовой пояс: {user.timezone or '—'}\n"
        f"Стиль общения: {user.bot_personality or '—'}"
    )
    try:
        _profile_notify_last[user.id] = now
        await bot.send_message(chat_id=user.telegram_id, text=text)
    except TelegramError as exc:
        logger.warning("Failed to send profile update notice to %s: %s", user.telegram_id, exc)


@app.get("/api/stats/summary")
async def stats_summary(init_data: str, days: int = 30):
    db = next(get_db())
    try:
        user, user_payload = resolve_user(db, init_data)
        summary = stats_service.adherence_summary(db, user, days=days)
        logger.info("WebApp GET stats for user %s (days=%s)", user.telegram_id, days)
        return {"summary": summary, "user": user_payload}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Unexpected error in GET /api/stats/summary")
        raise HTTPException(status_code=500, detail="Internal error")
    finally:
        db.close()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
