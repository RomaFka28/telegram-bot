import datetime as dt
from typing import Optional

import pytz
from timezonefinder import TimezoneFinder

_CITY_ALIASES = {
    "moscow": "Europe/Moscow",
    "moskva": "Europe/Moscow",
    "spb": "Europe/Moscow",
    "saint petersburg": "Europe/Moscow",
    "sankt-peterburg": "Europe/Moscow",
    "petersburg": "Europe/Moscow",
    "novosibirsk": "Asia/Novosibirsk",
    "ekaterinburg": "Asia/Yekaterinburg",
    "yekaterinburg": "Asia/Yekaterinburg",
    "tomsk": "Asia/Tomsk",
    "omsk": "Asia/Omsk",
    "krasnoyarsk": "Asia/Krasnoyarsk",
    "kazan": "Europe/Moscow",
    "sochi": "Europe/Moscow",
}

_tz_finder = TimezoneFinder()


def resolve_timezone(value: str) -> Optional[str]:
    if not value:
        return None
    key = value.strip().lower()
    alias = _CITY_ALIASES.get(key)
    if alias:
        return alias
    try:
        pytz.timezone(value)
        return value
    except Exception:
        return None


def timezone_from_location(lat: float, lon: float) -> Optional[str]:
    try:
        zone = _tz_finder.timezone_at(lat=lat, lng=lon)
        if not zone:
            zone = _tz_finder.closest_timezone_at(lat=lat, lng=lon)
        return zone
    except Exception:
        return None


def normalize_timezone(value: str) -> str:
    return resolve_timezone(value) or "UTC"


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
