from enum import IntEnum, auto


class SetupState(IntEnum):
    NAME = auto()
    TIMEZONE = auto()
    PERSONALITY = auto()
    GOAL = auto()
    THEME = auto()
    OPTIONAL = auto()


class ReminderState(IntEnum):
    PICK_MED = auto()
    SCHEDULE_TYPE = auto()
    TIME = auto()
    DAYS = auto()
    INTERVAL = auto()
    EVENT = auto()
    GEO = auto()
    CONFIRM = auto()


class ProfileEditState(IntEnum):
    VALUE = auto()


class SymptomState(IntEnum):
    DESCRIPTION = auto()
    SEVERITY = auto()
