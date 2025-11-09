from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from models import Medication, MedicationRestock, User
from config import settings


def _safe_float(value, default: float = 0.0) -> float:
    if value in (None, "", "null"):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def create_medication(session: Session, user: User, data: Dict) -> Medication:
    medication = Medication(
        user=user,
        name=data.get("name", "Без названия"),
        dosage=data.get("dosage"),
        form=data.get("form"),
        category=data.get("category"),
        dose_units=data.get("dose_units", "unit"),
        dose_size=_safe_float(data.get("dose_size"), 1),
        pack_total=_safe_float(data.get("pack_total")),
        stock_remaining=_safe_float(
            data.get("stock_remaining"),
            _safe_float(data.get("pack_total")),
        ),
        notes=data.get("notes"),
        photo_file_id=data.get("photo_file_id"),
    )
    session.add(medication)
    session.commit()
    session.refresh(medication)
    quantity = data.get("stock_remaining") or data.get("pack_total")
    if quantity:
        session.add(
            MedicationRestock(
                medication_id=medication.id,
                quantity=float(quantity),
                note="Initial stock",
            )
        )
        session.commit()
    return medication


def list_medications(session: Session, user: User, include_archived: bool = False) -> List[Medication]:
    query = session.query(Medication).filter(Medication.user_id == user.id)
    if not include_archived:
        query = query.filter(Medication.archived.is_(False))
    return query.order_by(Medication.name.asc()).all()


def restock_medication(
    session: Session, medication: Medication, quantity: float, note: Optional[str] = None
) -> Medication:
    medication.stock_remaining += quantity
    medication.pack_total += quantity
    restock_entry = MedicationRestock(
        medication_id=medication.id,
        quantity=quantity,
        note=note or "Manual restock",
    )
    session.add(restock_entry)
    session.commit()
    session.refresh(medication)
    return medication


def get_restock_history(session: Session, medication: Medication, limit: int = 10) -> List[MedicationRestock]:
    return (
        session.query(MedicationRestock)
        .filter(MedicationRestock.medication_id == medication.id)
        .order_by(MedicationRestock.created_at.desc())
        .limit(limit)
        .all()
    )


def toggle_archive(session: Session, medication: Medication, archived: bool) -> Medication:
    medication.archived = archived
    session.commit()
    session.refresh(medication)
    return medication


def consume_dose(session: Session, medication: Medication, multiplier: float = 1.0) -> Medication:
    dose = medication.dose_size * multiplier
    medication.stock_remaining = max(0.0, medication.stock_remaining - dose)
    session.commit()
    session.refresh(medication)
    return medication


def is_low_stock(medication: Medication) -> bool:
    return medication.stock_remaining <= settings.low_stock_threshold
