import datetime as dt
from typing import List

from sqlalchemy.orm import Session

from models import Achievement, ReminderLog, UserAchievement, User

ACHIEVEMENTS_CATALOG = [
    {
        "slug": "week_without_miss",
        "title": "Первая неделя без пропусков",
        "description": "7 дней дисциплины — отличный старт!",
        "icon": "🥇",
    },
    {
        "slug": "month_champion",
        "title": "Чемпион месяца",
        "description": "30 дней приёмов подряд, ни шага назад.",
        "icon": "🏆",
    },
    {
        "slug": "master_planner",
        "title": "Мастер планирования",
        "description": "5+ активных напоминаний — твоя система работает как часы.",
        "icon": "🧠",
    },
]


def seed_achievements(session: Session) -> None:
    for entry in ACHIEVEMENTS_CATALOG:
        exists = session.query(Achievement).filter(Achievement.slug == entry["slug"]).first()
        if not exists:
            session.add(Achievement(**entry))
    session.commit()


def _has_award(session: Session, user_id: int, slug: str) -> bool:
    return (
        session.query(UserAchievement)
        .join(Achievement)
        .filter(UserAchievement.user_id == user_id, Achievement.slug == slug)
        .first()
        is not None
    )


def evaluate_user(session: Session, user: User) -> List[Achievement]:
    seed_achievements(session)
    awarded: List[Achievement] = []

    seven_days_ago = dt.datetime.utcnow() - dt.timedelta(days=7)
    logs_last_week = (
        session.query(ReminderLog)
        .filter(
            ReminderLog.user_id == user.id,
            ReminderLog.scheduled_for >= seven_days_ago,
        )
        .all()
    )
    if logs_last_week and all(log.status == "taken" for log in logs_last_week):
        if not _has_award(session, user.id, "week_without_miss"):
            achievement = (
                session.query(Achievement)
                .filter(Achievement.slug == "week_without_miss")
                .first()
            )
            session.add(UserAchievement(user_id=user.id, achievement_id=achievement.id))
            awarded.append(achievement)

    thirty_days_ago = dt.datetime.utcnow() - dt.timedelta(days=30)
    logs_month = (
        session.query(ReminderLog)
        .filter(
            ReminderLog.user_id == user.id,
            ReminderLog.scheduled_for >= thirty_days_ago,
        )
        .all()
    )
    if logs_month and all(log.status == "taken" for log in logs_month):
        if not _has_award(session, user.id, "month_champion"):
            achievement = (
                session.query(Achievement)
                .filter(Achievement.slug == "month_champion")
                .first()
            )
            session.add(UserAchievement(user_id=user.id, achievement_id=achievement.id))
            awarded.append(achievement)

    active_reminders = len([r for r in user.reminders if r.active])
    if active_reminders >= 5 and not _has_award(session, user.id, "master_planner"):
        achievement = (
            session.query(Achievement)
            .filter(Achievement.slug == "master_planner")
            .first()
        )
        session.add(UserAchievement(user_id=user.id, achievement_id=achievement.id))
        awarded.append(achievement)

    session.commit()
    return awarded
