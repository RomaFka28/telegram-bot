import datetime as dt
from typing import Optional

import pytz


def normalize_timezone(value: str) -> str:
    try:
        pytz.timezone(value)
        return value
    except Exception:
        return "UTC"


def to_user_datetime(user_timezone: str, naive_dt: dt.datetime) -> dt.datetime:
    tz = pytz.timezone(normalize_timezone(user_timezone))
    if naive_dt.tzinfo:
        return naive_dt.astimezone(tz)
    return tz.localize(naive_dt)


def to_utc(user_timezone: str, naive_dt: dt.datetime) -> dt.datetime:
    localized = to_user_datetime(user_timezone, naive_dt)
    return localized.astimezone(pytz.UTC)


def combine_time(user_timezone: str, time_of_day: dt.time, date: Optional[dt.date] = None) -> dt.datetime:
    date = date or dt.date.today()
    naive = dt.datetime.combine(date, time_of_day)
    return to_utc(user_timezone, naive)
