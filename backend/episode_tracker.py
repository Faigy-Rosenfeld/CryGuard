"""
Episode Tracker — מנהל מחזור חיים של אירוע בכי בודד.

מעקב: התחלה → פעיל → סיום → סיכום
שומר עד 100 אירועים בזיכרון.
"""

from __future__ import annotations
import uuid
import time
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Optional, List


MAX_EPISODES = 100

URGENCY_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}


def _peak(a: str, b: str) -> str:
    """מחזיר את רמת הדחיפות הגבוהה יותר מבין שתיים."""
    return a if URGENCY_ORDER.get(a, 0) >= URGENCY_ORDER.get(b, 0) else b


@dataclass
class Episode:
    episode_id:       str
    start_time:       str          # ISO 8601
    end_time:         Optional[str] = None
    duration_seconds: int           = 0
    urgency_level:    str           = "low"
    _start_mono:      float         = field(default_factory=time.monotonic, repr=False)
    _peak_urgency:    str           = field(default="low", repr=False)

    def update(self, urgency_level: str) -> None:
        """מעדכן משך ורמת דחיפות שיאית בזמן שהאירוע פעיל."""
        self.duration_seconds = int(time.monotonic() - self._start_mono)
        self._peak_urgency    = _peak(self._peak_urgency, urgency_level)
        self.urgency_level    = self._peak_urgency

    def close(self) -> dict:
        """סוגר את האירוע ומחזיר dict של הסיכום."""
        now = datetime.now()
        self.end_time         = now.isoformat(timespec="seconds")
        self.duration_seconds = int(time.monotonic() - self._start_mono)
        self.urgency_level    = self._peak_urgency
        return self.to_dict()

    def to_dict(self) -> dict:
        return {
            "episode_id":       self.episode_id,
            "start_time":       self.start_time,
            "end_time":         self.end_time,
            "duration_seconds": self.duration_seconds,
            "urgency_level":    self.urgency_level,
        }


class EpisodeTracker:
    """מנהל אחד אירוע פעיל ורשימת היסטוריה."""

    def __init__(self) -> None:
        self._active:    Optional[Episode] = None
        self._completed: List[Episode]     = []   # עד MAX_EPISODES, הישן ביותר ראשון

    # ── ממשק ציבורי ──

    def start_episode(self) -> Episode:
        """יוצר אירוע חדש. אם יש אחד פעיל, סוגר אותו קודם."""
        if self._active:
            self._finalize(self._active)

        now = datetime.now()
        ep  = Episode(
            episode_id  = str(uuid.uuid4()),
            start_time  = now.isoformat(timespec="seconds"),
            _start_mono = time.monotonic(),
        )
        self._active = ep
        return ep

    def update_active(self, urgency_level: str) -> None:
        """מעדכן אירוע פעיל עם רמת דחיפות עדכנית."""
        if self._active:
            self._active.update(urgency_level)

    def end_episode(self) -> Optional[dict]:
        """סוגר את האירוע הפעיל ומחזיר את הסיכום שלו (dict)."""
        if not self._active:
            return None
        summary = self._finalize(self._active)
        self._active = None
        return summary

    def close_on_shutdown(self) -> Optional[dict]:
        """סוגר אירוע פעיל בעת כיבוי המערכת."""
        if self._active:
            summary = self._finalize(self._active)
            self._active = None
            return summary
        return None

    @property
    def active_episode(self) -> Optional[Episode]:
        return self._active

    def get_all(self) -> List[dict]:
        """מחזיר כל האירועים הגמורים, מהחדש לישן."""
        return [ep.to_dict() for ep in reversed(self._completed)]

    # ── פנימי ──

    def _finalize(self, ep: Episode) -> dict:
        summary = ep.close()
        self._completed.append(ep)
        # שמור עד MAX_EPISODES
        if len(self._completed) > MAX_EPISODES:
            self._completed.pop(0)
        return summary
