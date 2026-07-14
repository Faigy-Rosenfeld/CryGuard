"""
Priority Scorer — מחשב רמת דחיפות לכל זיהוי בכי.

ציון 0–100 מחולק לפי 4 משתנים שווים (כל אחד 0–25 נקודות):
  1. משך הבכי (cry_duration_sec)
  2. יחס רציפות (continuity_ratio — שבר מתוך 10 צ'אנקים אחרונים)
  3. מספר אירועי בכי ב-60 שניות האחרונות
  4. רמת ביטחון המודל (confidence 0–100)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from collections import deque
import time


# ──────────────────────────────────────────────
# הגדרות ניקוד
# ──────────────────────────────────────────────
DURATION_MAX  = 60.0   # ≥60 שניות → ניקוד מלא
EVENTS_MAX    = 5      # ≥5 אירועים ב-60 שניות → ניקוד מלא
CONTINUITY_WINDOW = 10  # כמה צ'אנקים אחרונים נכללים ביחס הרציפות

URGENCY_LEVELS = ["low", "medium", "high", "critical"]

def _score_to_level(score: float) -> str:
    if score < 25:
        return "low"
    elif score < 50:
        return "medium"
    elif score < 75:
        return "high"
    else:
        return "critical"


@dataclass
class PriorityScorer:
    """מחזיק היסטוריה של צ'אנקים ומחשב ציון דחיפות."""

    # חלון רציפות — 10 צ'אנקים אחרונים (True=בכי, False=שקט)
    _continuity_window: deque = field(
        default_factory=lambda: deque(maxlen=CONTINUITY_WINDOW), init=False
    )

    # חותמות זמן של תחילת כל אירוע בכי ב-60 שניות האחרונות
    _event_times: deque = field(
        default_factory=lambda: deque(), init=False
    )

    def record_chunk(self, is_crying: bool) -> None:
        """קורא לכל צ'אנק (בכי ולא בכי) — מעדכן חלון רציפות."""
        self._continuity_window.append(is_crying)

    def record_episode_start(self) -> None:
        """קורא כאשר מתחיל אירוע בכי חדש — שומר חותמת זמן."""
        self._event_times.append(time.monotonic())

    def _clean_old_events(self) -> None:
        """מסיר אירועים ישנים מחוץ לחלון 60 שניות."""
        now = time.monotonic()
        while self._event_times and now - self._event_times[0] > 60:
            self._event_times.popleft()

    def compute(
        self,
        cry_duration_sec: float,
        confidence: float,          # 0–100
    ) -> dict:
        """
        מחשב ומחזיר dict עם:
          priority_score  (0–100, float)
          urgency_level   ("low" | "medium" | "high" | "critical")
        """
        self._clean_old_events()

        # ── 1. ניקוד משך בכי (0–25) ──
        duration_score = min(1.0, cry_duration_sec / DURATION_MAX) * 25

        # ── 2. ניקוד רציפות (0–25) ──
        window = list(self._continuity_window)
        if window:
            continuity_ratio = sum(window) / len(window)
        else:
            continuity_ratio = 0.0
        continuity_score = continuity_ratio * 25

        # ── 3. ניקוד תדירות אירועים (0–25) ──
        n_events = len(self._event_times)
        frequency_score = min(1.0, n_events / EVENTS_MAX) * 25

        # ── 4. ניקוד ביטחון מודל (0–25) ──
        confidence_score = min(100.0, max(0.0, confidence)) / 100 * 25

        total = duration_score + continuity_score + frequency_score + confidence_score
        total = round(min(100.0, max(0.0, total)), 1)

        return {
            "priority_score": total,
            "urgency_level":  _score_to_level(total),
        }
