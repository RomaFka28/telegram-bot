import csv
import io
import json
from typing import Tuple

from sqlalchemy.orm import Session

from models import Medication, ReminderLog, User


def _collect_payload(session: Session, user: User) -> dict:
    medications = (
        session.query(Medication)
        .filter(Medication.user_id == user.id)
        .all()
    )
    logs = (
        session.query(ReminderLog)
        .filter(ReminderLog.user_id == user.id)
        .order_by(ReminderLog.scheduled_for.desc())
        .all()
    )
    return {
        "user": {
            "name": user.name,
            "timezone": user.timezone,
            "goal": user.goal,
        },
        "medications": [
            {
                "name": med.name,
                "dosage": med.dosage,
                "form": med.form,
                "category": med.category,
                "remaining": med.stock_remaining,
            }
            for med in medications
        ],
        "logs": [
            {
                "reminder_id": log.reminder_id,
                "scheduled_for": log.scheduled_for.isoformat(),
                "status": log.status,
                "note": log.note,
            }
            for log in logs
        ],
    }


def export_json(session: Session, user: User) -> Tuple[str, bytes]:
    payload = _collect_payload(session, user)
    content = json.dumps(payload, ensure_ascii=False, indent=2)
    return "health_buddy_export.json", content.encode("utf-8")


def export_csv(session: Session, user: User) -> Tuple[str, bytes]:
    payload = _collect_payload(session, user)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Medication", "Dosage", "Form", "Category", "Remaining"])
    for med in payload["medications"]:
        writer.writerow(
            [
                med["name"],
                med.get("dosage"),
                med.get("form"),
                med.get("category"),
                med.get("remaining"),
            ]
        )

    writer.writerow([])
    writer.writerow(["Reminder ID", "Scheduled For", "Status", "Note"])
    for log in payload["logs"]:
        writer.writerow(
            [
                log["reminder_id"],
                log["scheduled_for"],
                log["status"],
                log.get("note"),
            ]
        )

    return "health_buddy_export.csv", buffer.getvalue().encode("utf-8")
