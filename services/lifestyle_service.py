import datetime as dt
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from models import MoodLog, SymptomLog, WaterLog, Medication, ReminderLog, User


def log_symptom(
    session: Session,
    user: User,
    description: str,
    severity: int,
    medication: Optional[Medication] = None,
) -> SymptomLog:
    entry = SymptomLog(
        user_id=user.id,
        description=description,
        severity=severity,
        related_medication_id=medication.id if medication else None,
    )
    session.add(entry)
    session.commit()
    session.refresh(entry)
    return entry


def symptom_insight(session: Session, user: User) -> Optional[str]:
    latest = (
        session.query(SymptomLog)
        .filter(SymptomLog.user_id == user.id)
        .order_by(SymptomLog.logged_at.desc())
        .limit(5)
        .all()
    )
    if not latest:
        return None

    missed = (
        session.query(ReminderLog)
        .filter(
            ReminderLog.user_id == user.id,
            ReminderLog.status.in_(["missed", "skipped"]),
            ReminderLog.scheduled_for >= dt.datetime.utcnow() - dt.timedelta(days=7),
        )
        .all()
    )
    if not missed:
        return None

    symptom_days = {entry.logged_at.date() for entry in latest}
    missed_days = {log.scheduled_for.date() for log in missed}
    overlap = symptom_days & missed_days
    if overlap:
        return (
            "Замечаю, что вы жалуетесь на симптомы в дни с пропусками. "
            "Пожалуйста, обсудите это с врачом."
        )
    return None


def log_mood(session: Session, user: User, score: int, note: Optional[str] = None) -> MoodLog:
    entry = MoodLog(user_id=user.id, score=score, note=note)
    session.add(entry)
    session.commit()
    session.refresh(entry)
    return entry


def log_water(session: Session, user: User, amount_ml: int) -> WaterLog:
    entry = WaterLog(user_id=user.id, amount_ml=amount_ml)
    session.add(entry)
    session.commit()
    session.refresh(entry)
    return entry
