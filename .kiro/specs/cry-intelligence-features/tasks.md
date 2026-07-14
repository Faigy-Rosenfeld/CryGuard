# Implementation Plan: Cry Intelligence Features

## Overview

Implement three intelligence layers on top of the existing CRYGUARD backend and React frontend: a `PriorityScorer` that maps cry attributes to an urgency level, an `EpisodeTracker` that groups cry detections into summarised episodes, and a `NightModeController` that auto-selects alert thresholds based on local time. All three modules are wired into `audio_loop()` in `backend/main.py`, and the frontend receives enriched payloads through the existing WebSocket plus episode history from a new `/episodes` REST endpoint.

---

## Tasks

- [ ] 1. Add `hypothesis` to `requirements.txt`
  - Append `hypothesis==6.112.1` as a dev dependency to `requirements.txt`
  - _Requirements: setup for property-based tests across all modules_

- [ ] 2. Implement `NightModeController` (`backend/night_mode.py`)
  - [ ] 2.1 Create `backend/night_mode.py` with `NightModeController` class
    - Read `NIGHT_MODE_START_HOUR` and `DAY_MODE_START_HOUR` from environment; fall back to 22 / 7 and log a warning on invalid or out-of-range values
    - Implement `get_mode()` — returns `"night"` when current local hour is in `[night_start, 24) ∪ [0, day_start)`, otherwise `"day"`; handles midnight-crossing and same-day ranges
    - Implement `get_threshold()` — returns `5` in Night_Mode, `10` in Day_Mode
    - Implement `check_transition()` — compares current mode to `_prev_mode`; returns the new mode string on transition and `None` otherwise; resets internal cry-accumulation state on transition
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.9_
  - [ ]* 2.2 Write unit tests for `NightModeController` (`tests/test_night_mode.py`)
    - Test midnight-crossing case (22:00–07:00): hours 22, 23, 0, 6 → `"night"`; hour 7, 14 → `"day"`
    - Test exact boundary hours (7, 22)
    - Test same-day night range edge case
    - Test env-var parsing: valid values, out-of-range int, non-integer string → falls back to default
    - Test `check_transition()` idempotency: repeated calls in same mode return `None` (Property 9)
    - Test `get_threshold()` returns 5 for night, 10 for day (Property 8)
    - _Requirements: 3.1–3.9_

- [ ] 3. Implement `PriorityScorer` (`backend/priority_scorer.py`)
  - [ ] 3.1 Create `backend/priority_scorer.py` with `UrgencyLevel` enum and `PriorityScorer` class
    - Define `UrgencyLevel(str, Enum)` with values `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`
    - Implement `compute(cry_duration_sec, continuity_ratio, event_count_60s, confidence_score) -> tuple[UrgencyLevel, float]`
    - Normalise: `norm_duration = min(duration/60, 1)*100`, `norm_continuity = ratio*100`, `norm_event_count = min(count/5, 1)*100`, `norm_confidence = confidence_score`
    - Average the four normalised values; map result to `UrgencyLevel` using ranges `[0,25)→LOW`, `[25,50)→MEDIUM`, `[50,75)→HIGH`, `[75,100]→CRITICAL`
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.8_
  - [ ]* 3.2 Write property tests for `PriorityScorer` (`tests/test_priority_scorer.py`)
    - **Property 1: Score Boundedness** — for any valid inputs, `0.0 ≤ priority_score ≤ 100.0`
    - **Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5**
    - **Property 2: Urgency Exhaustiveness** — every score in [0, 100] maps to exactly one `UrgencyLevel`
    - **Validates: Requirements 1.2, 1.3, 1.4, 1.5**
    - **Property 3: Priority Scorer Determinism** — `compute(a,b,c,d) == compute(a,b,c,d)` for identical inputs
    - **Validates: Requirements 1.8**
  - [ ]* 3.3 Write unit tests for `PriorityScorer` (`tests/test_priority_scorer.py`)
    - Test all four urgency boundary values: scores at 0, 24.9, 25.0, 49.9, 50.0, 74.9, 75.0, 100.0
    - Test each normalisation cap: `cry_duration_sec=60` → `norm_duration=100`, `event_count_60s=5` → `norm_event_count=100`
    - Test zero-input case returns `UrgencyLevel.LOW`
    - _Requirements: 1.1–1.5, 1.8_

- [ ] 4. Checkpoint — backend modules defined
  - Ensure `backend/night_mode.py` and `backend/priority_scorer.py` import cleanly and all tests pass. Ask the user if anything is unclear before continuing.

- [ ] 5. Implement `EpisodeTracker` (`backend/episode_tracker.py`)
  - [ ] 5.1 Create `backend/episode_tracker.py` with `CryEpisode` dataclass and `EpisodeTracker` class
    - Define `CryEpisode` dataclass with fields: `episode_id` (str), `start_time` (str, ISO 8601), `end_time` (Optional[str])`, `duration_seconds` (int), `urgency_level` (str)
    - Implement `__init__` — initialises `active_episode = None`, `_cry_seconds_counter = 0.0`, `_peak_urgency = None`, `_completed: deque[dict]` (maxlen=100)
    - Implement `update(label, urgency_level, timestamp, threshold_sec, calm_chunks, calm_threshold) -> Optional[dict]`:
      - On `"crying"`: increment `_cry_seconds_counter` by `STEP`; open episode when `_cry_seconds_counter >= threshold_sec`; update running `duration_seconds` and `peak_urgency` (non-decreasing by rank)
      - On `"background"`: reset `_cry_seconds_counter = 0`; close episode when `calm_chunks >= calm_threshold`; enforce 100-cap via `deque(maxlen=100)`; return episode summary dict with `type="episode_end"`
    - Implement `get_episodes() -> list[dict]` — returns `list(reversed(self._completed))`
    - Implement `close_active(shutdown_time: float) -> None` — if episode active, set `end_time`, compute `duration_seconds`, append to completed list
    - _Requirements: 2.1, 2.2, 2.3, 2.5, 2.7, 2.8, 2.9_
  - [ ]* 5.2 Write property tests for `EpisodeTracker` (`tests/test_episode_tracker.py`)
    - **Property 4: Episode Cap Invariant** — after N > 100 episode closes, `len(get_episodes()) ≤ 100`
    - **Validates: Requirements 2.7**
    - **Property 5: Episode Monotone Urgency** — within a single episode, `peak_urgency` rank never decreases
    - **Validates: Requirements 2.2, 2.3**
    - **Property 6: Single Active Episode** — at most one episode is active at any point
    - **Validates: Requirements 2.1, 2.8**
  - [ ]* 5.3 Write unit tests for `EpisodeTracker` (`tests/test_episode_tracker.py`)
    - Test episode opens exactly at threshold (not before)
    - Test episode closes on calm, returning summary dict with all required fields (`episode_id`, `start_time`, `end_time`, `duration_seconds`, `urgency_level`, `type`)
    - Test 100-episode cap: adding 101st discards oldest
    - Test `close_active()` on shutdown: active episode is stored with valid `end_time` and `duration_seconds ≥ 0` (Property 10)
    - Test `get_episodes()` returns most-recent-first order
    - _Requirements: 2.1, 2.2, 2.3, 2.5, 2.6, 2.7, 2.8, 2.9_

- [ ] 6. Wire all three modules into `backend/main.py`
  - [ ] 6.1 Import modules and instantiate singletons at module level
    - Add `import time` (if not already present)
    - Import `NightModeController`, `PriorityScorer`, `EpisodeTracker` from their respective modules
    - Instantiate `night_mode_ctrl`, `priority_scorer`, `episode_tracker` at module level (after `model` load)
    - _Requirements: 1.1, 2.1, 3.1_
  - [ ] 6.2 Add per-chunk state variables to `audio_loop()`
    - Add `cry_seconds`, `continuity_window` (deque, maxlen=10), `event_window` (list of timestamps for 60 s window), `calm_chunks` counter alongside the existing `buffer` variable
    - Compute `continuity_ratio` as `sum(continuity_window) / len(continuity_window)` (or 0 if empty)
    - Compute `event_count_60s` by counting entries in `event_window` within the last 60 s; append new entry when a cry sequence starts
    - _Requirements: 1.1_
  - [ ] 6.3 Integrate `NightModeController` and `PriorityScorer` into the detection path
    - After `process_chunk()`, call `night_mode_ctrl.get_threshold()` and `night_mode_ctrl.check_transition()`
    - On transition, `await broadcast({"type": "mode_change", "mode": transition})` and reset `cry_seconds = 0`
    - When `result["label"] == "crying"`, call `priority_scorer.compute(...)` and attach `urgency_level`, `priority_score`, `threshold` to `result`
    - Update `cry_seconds`, `continuity_window`, `calm_chunks` appropriately on each chunk
    - _Requirements: 1.1, 1.6, 3.1, 3.2, 3.3, 3.7_
  - [ ] 6.4 Integrate `EpisodeTracker` and add `/episodes` REST endpoint
    - After computing urgency, call `episode_tracker.update(...)` and `await broadcast({**episode_event, "type": "episode_end"})` when an episode ends
    - Add `GET /episodes` endpoint protected by `verify_key`, returning `episode_tracker.get_episodes()`
    - Add FastAPI `shutdown` lifecycle event that calls `episode_tracker.close_active(time.time())`
    - _Requirements: 2.1, 2.2, 2.3, 2.5, 2.6, 2.9_

- [ ] 7. Checkpoint — backend fully integrated
  - Start the backend, connect a WebSocket client, and verify that detection messages include `urgency_level`, `priority_score`, and `threshold`; verify `/episodes` returns `[]` initially. Ensure all unit and property tests pass. Ask the user if questions arise.

- [ ] 8. Update React frontend (`frontend/src/App.js`)
  - [ ] 8.1 Add `episodes` and `currentMode` state variables
    - Add `const [episodes, setEpisodes] = useState([])` and `const [currentMode, setCurrentMode] = useState(null)`
    - _Requirements: 4.1, 3.8_
  - [ ] 8.2 Handle `mode_change` and `episode_end` WebSocket messages
    - In `socket.onmessage`, before existing alert logic, check `data.type === "mode_change"` → `setCurrentMode(data.mode)` and return
    - Check `data.type === "episode_end"` → `setEpisodes(prev => [data, ...prev].slice(0, 100))` and return
    - _Requirements: 3.8, 4.1_
  - [ ] 8.3 Attach `urgency_level` to cry event entries and display in alert banner
    - When `inAlertRef.current` transitions to `true`, include `urgency: data.urgency_level` in the event object pushed to `events`
    - In the alert banner JSX, display the `urgency_level` string (e.g., below the "בכי זוהה" label) when `isCrying` and urgency is available
    - In the recent-events list, render the urgency badge next to cry events
    - _Requirements: 1.7, 1.9_
  - [ ] 8.4 Fetch episode history from `/episodes` on load and reconnect
    - Inside `socket.onopen`, fetch `${API_URL}/episodes` with `X-API-Key` header; on success (`r.ok`) call `setEpisodes(data)`; on failure swallow the error silently
    - _Requirements: 4.2_
  - [ ] 8.5 Render the unified episode history panel with colour-coded urgency
    - Add a new `<div className="panel">` section (below the existing bottom row or as a third row) titled "היסטוריית אירועים"
    - Map `episodes` to list items showing: `start_time` (formatted with `toLocaleString`), `duration_seconds`, and `urgency_level`
    - Apply inline style or CSS class for urgency colour: `low` → green, `medium` → amber/yellow, `high` → orange, `critical` → red
    - When `episodes.length > 20`, wrap list in a scrollable container with a fixed `max-height` so it does not push other panels
    - _Requirements: 4.1, 4.3, 4.4_
  - [ ] 8.6 Add Night/Day mode status bar
    - In the header or status panel, render a `currentMode` indicator: show "🌙 לילה" when `currentMode === "night"`, "☀️ יום" when `"day"`, or nothing when `null`
    - _Requirements: 3.8_

- [ ] 9. Final checkpoint — full stack integration
  - Ensure all tests pass (`pytest tests/`). Verify the frontend renders the episode history panel, urgency badges, and mode status bar correctly in the browser. Ask the user if questions arise.

---

## Notes

- Tasks marked with `*` are optional and can be skipped for an MVP build.
- Each task references specific requirements for traceability.
- Properties 7–9 (mode exclusivity, threshold correspondence, transition idempotency) are covered by the `NightModeController` unit tests in task 2.2 rather than as separate property-based test sub-tasks, because they are most naturally expressed as parametrised unit tests with `unittest.mock.patch`.
- Property 6 (single active episode) and Property 10 (episode closure on shutdown) are covered in the `EpisodeTracker` unit tests in task 5.3.
- The `hypothesis` dev dependency (task 1) must be installed before running any `*` test tasks.
- `CALM_WINDOW` from `App.js` (`20`) is the calm-threshold value to pass to `episode_tracker.update()` as `calm_threshold`.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1"] },
    { "id": 1, "tasks": ["2.1", "3.1"] },
    { "id": 2, "tasks": ["2.2", "3.2", "3.3", "5.1"] },
    { "id": 3, "tasks": ["5.2", "5.3", "6.1"] },
    { "id": 4, "tasks": ["6.2"] },
    { "id": 5, "tasks": ["6.3"] },
    { "id": 6, "tasks": ["6.4"] },
    { "id": 7, "tasks": ["8.1"] },
    { "id": 8, "tasks": ["8.2", "8.3", "8.4"] },
    { "id": 9, "tasks": ["8.5", "8.6"] }
  ]
}
```
