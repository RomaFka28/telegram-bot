from typing import List, Optional

from sqlalchemy.orm import Session

from models import FamilyLink, User


def create_invite(session: Session, user: User) -> FamilyLink:
    link = FamilyLink(care_receiver_id=user.id)
    session.add(link)
    session.commit()
    session.refresh(link)
    return link


def accept_invite(session: Session, user: User, token: str) -> Optional[FamilyLink]:
    link = session.query(FamilyLink).filter(FamilyLink.token == token).first()
    if not link:
        return None
    link.caregiver_id = user.id
    link.status = "accepted"
    session.commit()
    session.refresh(link)
    return link


def caregivers(session: Session, user: User) -> List[FamilyLink]:
    return (
        session.query(FamilyLink)
        .filter(
            FamilyLink.care_receiver_id == user.id,
            FamilyLink.status == "accepted",
        )
        .all()
    )


def care_receivers(session: Session, user: User) -> List[FamilyLink]:
    return (
        session.query(FamilyLink)
        .filter(
            FamilyLink.caregiver_id == user.id,
            FamilyLink.status == "accepted",
        )
        .all()
    )
