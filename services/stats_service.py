import datetime as dt
import io
from typing import Dict, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sqlalchemy.orm import Session

from models import Medication, Reminder, ReminderLog, User


def adherence_summary(session: Session, user: User, days: int = 30) -> Dict:
    since = dt.datetime.utcnow() - dt.timedelta(days=days)
    logs = (
        session.query(ReminderLog)
        .filter(
            ReminderLog.user_id == user.id,
            ReminderLog.scheduled_for >= since,
        )
        .all()
    )
    taken = sum(1 for log in logs if log.status == "taken")
    missed = sum(1 for log in logs if log.status in {"missed", "skipped"})
    total = taken + missed or 1
    adherence = round((taken / total) * 100, 1)

    per_med: Dict[str, Dict[str, int]] = {}
    med_logs = (
        session.query(Medication.name, ReminderLog.status)
        .join(Reminder, Reminder.id == ReminderLog.reminder_id)
        .join(Medication, Medication.id == Reminder.medication_id, isouter=True)
        .filter(
            ReminderLog.user_id == user.id,
            ReminderLog.scheduled_for >= since,
        )
        .all()
    )
    for name, status in med_logs:
        key = name or "Без привязки"
        record = per_med.setdefault(key, {"taken": 0, "total": 0})
        if status in {"taken"}:
            record["taken"] += 1
        if status in {"taken", "missed", "skipped"}:
            record["total"] += 1

    return {
        "taken": taken,
        "missed": missed,
        "adherence": adherence,
        "total": total,
        "per_med": per_med,
    }


def weekly_plot(session: Session, user: User, weeks: int = 4) -> bytes:
    since = dt.datetime.utcnow() - dt.timedelta(weeks=weeks)
    logs = (
        session.query(ReminderLog)
        .filter(
            ReminderLog.user_id == user.id,
            ReminderLog.scheduled_for >= since,
        )
        .all()
    )
    buckets: Dict[str, Tuple[int, int]] = {}
    for log in logs:
        year_week = f"{log.scheduled_for.isocalendar().year}-W{log.scheduled_for.isocalendar().week}"
        taken, total = buckets.get(year_week, (0, 0))
        if log.status == "taken":
            taken += 1
        if log.status in {"taken", "missed", "skipped"}:
            total += 1
        buckets[year_week] = (taken, total)

    labels = sorted(buckets.keys())
    adherence = [
        (buckets[label][0] / buckets[label][1] * 100) if buckets[label][1] else 0
        for label in labels
    ]

    plt.style.use("seaborn-v0_8")
    fig, ax = plt.subplots(figsize=(6, 3))
    ax.plot(labels, adherence, marker="o")
    ax.set_ylim(0, 100)
    ax.set_ylabel("Соблюдение %")
    ax.set_title("Еженедельная динамика")
    ax.grid(True, axis="y", linestyle="--", alpha=0.3)
    fig.tight_layout()

    buffer = io.BytesIO()
    fig.savefig(buffer, format="png")
    plt.close(fig)
    buffer.seek(0)
    return buffer.read()
