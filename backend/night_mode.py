"""
Night Mode Controller — קובע את סף ההתראה לפי שעת היום.

Day Mode  (07:00–22:00): סף 10 שניות
Night Mode (22:00–07:00): סף 5 שניות

ניתן לשנות דרך משתני סביבה:
  DAY_MODE_START_HOUR   (ברירת מחדל: 7)
  NIGHT_MODE_START_HOUR (ברירת מחדל: 22)
"""

from __future__ import annotations
import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

_DEFAULT_DAY_START   = 7
_DEFAULT_NIGHT_START = 22

DAY_THRESHOLD_SEC   = 10
NIGHT_THRESHOLD_SEC = 5


def _load_hour(env_var: str, default: int) -> int:
    raw = os.getenv(env_var)
    if raw is None:
        return default
    try:
        val = int(raw)
        if 0 <= val <= 23:
            return val
        logger.error(
            "[NightMode] %s=%r is out of range [0,23] — using default %d",
            env_var, raw, default,
        )
    except (ValueError, TypeError):
        logger.error(
            "[NightMode] %s=%r is not a valid integer — using default %d",
            env_var, raw, default,
        )
    return default


# טעינת הגדרות פעם אחת בעת import
DAY_START_HOUR   = _load_hour("DAY_MODE_START_HOUR",   _DEFAULT_DAY_START)
NIGHT_START_HOUR = _load_hour("NIGHT_MODE_START_HOUR", _DEFAULT_NIGHT_START)


def is_night_mode(now: datetime | None = None) -> bool:
    """מחזיר True אם השעה הנוכחית נמצאת בטווח הלילה."""
    hour = (now or datetime.now()).hour
    if NIGHT_START_HOUR > DAY_START_HOUR:
        # מצב רגיל: לילה = 22–07
        return hour >= NIGHT_START_HOUR or hour < DAY_START_HOUR
    else:
        # מצב הפוך (נדיר): יום חוצה חצות
        return DAY_START_HOUR > hour >= NIGHT_START_HOUR


def get_mode_label(now: datetime | None = None) -> str:
    """מחזיר 'night' או 'day'."""
    return "night" if is_night_mode(now) else "day"


def get_alert_threshold(now: datetime | None = None) -> int:
    """מחזיר את סף ההתראה בשניות בהתאם למצב הנוכחי."""
    return NIGHT_THRESHOLD_SEC if is_night_mode(now) else DAY_THRESHOLD_SEC
