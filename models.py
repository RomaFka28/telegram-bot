import datetime as dt
import uuid
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    BigInteger,
    String,
    Text,
    UniqueConstraint,
    Time,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class TimestampMixin:
    created_at = Column(DateTime, default=dt.datetime.utcnow)
    updated_at = Column(
        DateTime, default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow
    )


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(BigInteger, unique=True, index=True, nullable=False)
    username = Column(String, nullable=True)
    name = Column(String, nullable=False)
    timezone = Column(String, default="UTC")
    bot_personality = Column(String, default="caring_nurse")
    goal = Column(String, nullable=True)
    theme = Column(String, default="calm")
    emoji_pack = Column(String, default="classic")
    age = Column(Integer, nullable=True)
    weight = Column(Integer, nullable=True)
    hydration_goal_ml = Column(Integer, default=2000)
    last_location_lat = Column(Float, nullable=True)
    last_location_lon = Column(Float, nullable=True)
    last_check_in = Column(DateTime, nullable=True)

    medications = relationship(
        "Medication", back_populates="user", cascade="all, delete-orphan"
    )
    reminders = relationship(
        "Reminder", back_populates="user", cascade="all, delete-orphan"
    )
    reminder_logs = relationship(
        "ReminderLog", back_populates="user", cascade="all, delete-orphan"
    )
    symptoms = relationship(
        "SymptomLog", back_populates="user", cascade="all, delete-orphan"
    )
    moods = relationship(
        "MoodLog", back_populates="user", cascade="all, delete-orphan"
    )
    water_logs = relationship(
        "WaterLog", back_populates="user", cascade="all, delete-orphan"
    )
    family_links_as_caregiver = relationship(
        "FamilyLink",
        foreign_keys="FamilyLink.caregiver_id",
        back_populates="caregiver",
        cascade="all, delete-orphan",
    )
    family_links_as_receiver = relationship(
        "FamilyLink",
        foreign_keys="FamilyLink.care_receiver_id",
        back_populates="care_receiver",
        cascade="all, delete-orphan",
    )


class Medication(Base, TimestampMixin):
    __tablename__ = "medications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    dosage = Column(String, nullable=True)
    form = Column(String, nullable=True)
    category = Column(String, nullable=True)
    photo_file_id = Column(String, nullable=True)
    dose_units = Column(String, default="pill")
    dose_size = Column(Float, default=1)
    pack_total = Column(Float, default=0)
    stock_remaining = Column(Float, default=0)
    notes = Column(Text, nullable=True)
    archived = Column(Boolean, default=False)

    user = relationship("User", back_populates="medications")
    reminders = relationship(
        "Reminder", back_populates="medication", cascade="all, delete-orphan"
    )
    restocks = relationship(
        "MedicationRestock",
        back_populates="medication",
        cascade="all, delete-orphan",
    )


class MedicationRestock(Base):
    __tablename__ = "medication_restocks"

    id = Column(Integer, primary_key=True, index=True)
    medication_id = Column(Integer, ForeignKey("medications.id"), nullable=False)
    quantity = Column(Float, nullable=False)
    note = Column(String, nullable=True)
    created_at = Column(DateTime, default=dt.datetime.utcnow)

    medication = relationship("Medication", back_populates="restocks")


class Reminder(Base, TimestampMixin):
    __tablename__ = "reminders"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    medication_id = Column(Integer, ForeignKey("medications.id"), nullable=True)
    label = Column(String, nullable=True)
    schedule_type = Column(String, default="fixed_time")
    timezone = Column(String, default="UTC")
    time_of_day = Column(Time, nullable=True)
    days_of_week = Column(String, nullable=True)
    interval_hours = Column(Integer, nullable=True)
    offset_minutes = Column(Integer, nullable=True)
    event_label = Column(String, nullable=True)
    geo_lat = Column(Float, nullable=True)
    geo_lon = Column(Float, nullable=True)
    nag_enabled = Column(Boolean, default=False)
    nag_interval_minutes = Column(Integer, default=15)
    snooze_limit = Column(Integer, default=3)
    active = Column(Boolean, default=True)

    medication = relationship("Medication", back_populates="reminders")
    user = relationship("User", back_populates="reminders")
    logs = relationship(
        "ReminderLog", back_populates="reminder", cascade="all, delete-orphan"
    )


class ReminderLog(Base):
    __tablename__ = "reminder_logs"

    id = Column(Integer, primary_key=True, index=True)
    reminder_id = Column(Integer, ForeignKey("reminders.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    scheduled_for = Column(DateTime, nullable=False)
    status = Column(String, default="pending")
    taken_at = Column(DateTime, nullable=True)
    note = Column(String, nullable=True)

    reminder = relationship("Reminder", back_populates="logs")
    user = relationship("User", back_populates="reminder_logs")


class SymptomLog(Base):
    __tablename__ = "symptom_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    description = Column(Text, nullable=False)
    severity = Column(Integer, nullable=False)
    logged_at = Column(DateTime, default=dt.datetime.utcnow)
    related_medication_id = Column(Integer, ForeignKey("medications.id"), nullable=True)

    user = relationship("User", back_populates="symptoms")
    medication = relationship("Medication")


class MoodLog(Base):
    __tablename__ = "mood_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    score = Column(Integer, nullable=False)
    note = Column(Text, nullable=True)
    logged_at = Column(DateTime, default=dt.datetime.utcnow)

    user = relationship("User", back_populates="moods")


class WaterLog(Base):
    __tablename__ = "water_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    amount_ml = Column(Integer, nullable=False)
    logged_at = Column(DateTime, default=dt.datetime.utcnow)

    user = relationship("User", back_populates="water_logs")


class Achievement(Base):
    __tablename__ = "achievements"

    id = Column(Integer, primary_key=True, index=True)
    slug = Column(String, unique=True, nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    icon = Column(String, nullable=True)
    threshold = Column(Integer, nullable=True)


class UserAchievement(Base):
    __tablename__ = "user_achievements"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    achievement_id = Column(Integer, ForeignKey("achievements.id"), nullable=False)
    awarded_at = Column(DateTime, default=dt.datetime.utcnow)

    user = relationship("User")
    achievement = relationship("Achievement")

    __table_args__ = (
        UniqueConstraint("user_id", "achievement_id", name="uq_user_achievement"),
    )


class FamilyLink(Base):
    __tablename__ = "family_links"

    id = Column(Integer, primary_key=True, index=True)
    token = Column(String, unique=True, nullable=False, default=lambda: uuid.uuid4().hex)
    caregiver_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    care_receiver_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(String, default="pending")
    created_at = Column(DateTime, default=dt.datetime.utcnow)

    caregiver = relationship(
        "User",
        foreign_keys=[caregiver_id],
        back_populates="family_links_as_caregiver",
    )
    care_receiver = relationship(
        "User",
        foreign_keys=[care_receiver_id],
        back_populates="family_links_as_receiver",
    )
