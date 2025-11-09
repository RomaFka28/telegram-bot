import datetime as dt
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from models import Reminder, ReminderLog, User


def create_reminder(
    session: Session,
    user: User,
    payload: Dict,
    medication_id: Optional[int] = None,
) -> Reminder:
    reminder = Reminder(
        user_id=user.id,
        medication_id=medication_id,
        label=payload.get("label"),
        schedule_type=payload.get("schedule_type", "fixed_time"),
        timezone=user.timezone,
        time_of_day=payload.get("time_of_day"),
        days_of_week=payload.get("days_of_week"),
        interval_hours=payload.get("interval_hours"),
        offset_minutes=payload.get("offset_minutes"),
        event_label=payload.get("event_label"),
        geo_lat=payload.get("geo_lat"),
        geo_lon=payload.get("geo_lon"),
        nag_enabled=payload.get("nag_enabled", False),
        nag_interval_minutes=payload.get("nag_interval_minutes", 15),
        snooze_limit=payload.get("snooze_limit", 3),
    )
    session.add(reminder)
    session.commit()
    session.refresh(reminder)
    return reminder


def log_reminder(session: Session, reminder: Reminder, scheduled_for: dt.datetime) -> ReminderLog:
    log = ReminderLog(
        reminder_id=reminder.id,
        user_id=reminder.user_id,
        scheduled_for=scheduled_for,
        status="pending",
    )
    session.add(log)
    session.commit()
    session.refresh(log)
    return log


def get_log(session: Session, log_id: int) -> Optional[ReminderLog]:
    return session.query(ReminderLog).filter(ReminderLog.id == log_id).first()


def update_log_status(
    session: Session, log: ReminderLog, status: str, note: Optional[str] = None
) -> ReminderLog:
    log.status = status
    log.taken_at = dt.datetime.utcnow()
    if note:
        log.note = note
    session.commit()
    session.refresh(log)
    return log


def snooze_log(session: Session, log: ReminderLog, minutes: int) -> ReminderLog:
    new_time = log.scheduled_for + dt.timedelta(minutes=minutes)
    log.scheduled_for = new_time
    log.status = "snoozed"
    session.commit()
    session.refresh(log)
    return log


def get_user_reminders(session: Session, user: User) -> List[Reminder]:
    return (
        session.query(Reminder)
        .filter(Reminder.user_id == user.id, Reminder.active.is_(True))
        .order_by(Reminder.created_at.desc())
        .all()
    )


def upcoming_reminders(session: Session) -> List[Reminder]:
    return session.query(Reminder).filter(Reminder.active.is_(True)).all()


def deactivate_reminder(session: Session, reminder: Reminder) -> Reminder:
    reminder.active = False
    session.commit()
    session.refresh(reminder)
    return reminder
