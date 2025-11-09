from typing import Optional

from sqlalchemy.orm import Session

from models import User
from utils.personality import DEFAULT_PERSONALITY


def get_user(session: Session, telegram_id: int) -> Optional[User]:
    return session.query(User).filter(User.telegram_id == telegram_id).first()


def ensure_user(session: Session, telegram_user) -> User:
    user = get_user(session, telegram_user.id)
    if user:
        user.username = telegram_user.username
        user.name = telegram_user.full_name or telegram_user.first_name or user.name
        session.commit()
        return user

    user = User(
        telegram_id=telegram_user.id,
        username=telegram_user.username,
        name=telegram_user.full_name or telegram_user.first_name or "Дружище",
        timezone="UTC",
        bot_personality=DEFAULT_PERSONALITY,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def update_profile(
    session: Session,
    user: User,
    *,
    name: Optional[str] = None,
    timezone: Optional[str] = None,
    personality: Optional[str] = None,
    goal: Optional[str] = None,
    theme: Optional[str] = None,
    age: Optional[int] = None,
    weight: Optional[int] = None,
) -> User:
    if name:
        user.name = name
    if timezone:
        user.timezone = timezone
    if personality:
        user.bot_personality = personality
    if goal is not None:
        user.goal = goal
    if theme:
        user.theme = theme
    if age is not None:
        user.age = age
    if weight is not None:
        user.weight = weight
    session.commit()
    session.refresh(user)
    return user
