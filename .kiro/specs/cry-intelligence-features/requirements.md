# Requirements Document

## Introduction

This feature set extends the CRYGUARD system ("שומר הבית / Guardian Aura") with three intelligence layers on top of the existing AI-based baby cry detector:

1. **Priority Score** — calculates an urgency level (low / medium / high / critical) for each cry event, based on cry duration, continuity, event frequency, and model confidence.
2. **Cry Episodes** — groups consecutive cry detections into a single episode with start time, end time, duration, and urgency level; stores all episodes in a reviewable history.
3. **Night Mode** — adapts alert thresholds automatically based on time of day: a longer minimum cry duration during daytime (to suppress false alarms) and a shorter one at night (for faster parental response).

The system runs a Python/FastAPI backend (`backend/main.py`) with real-time audio analysis (`src/realtime_detector.py`) and a React frontend (`frontend/src/App.js`) communicating via WebSocket.

---

## Glossary

- **Detector**: The backend component in `backend/main.py` responsible for real-time audio analysis and WebSocket broadcasting.
- **Priority_Scorer**: The new backend module that computes urgency level from cry signal attributes.
- **Episode_Tracker**: The new backend module that manages the lifecycle of a single cry episode (start → active → ended → summarised).
- **Night_Mode_Controller**: The new backend module that determines whether the system is in Day Mode or Night Mode based on the current local time and applies the corresponding alert threshold.
- **Frontend**: The React application in `frontend/src/App.js` that displays status, alerts, and history to the user.
- **Urgency_Level**: An enumerated classification of cry severity — one of `low`, `medium`, `high`, or `critical`.
- **Cry_Episode**: A contiguous sequence of cry detections treated as a single event, characterised by start time, end time, duration, and Urgency_Level.
- **Alert_Threshold**: The minimum number of seconds of continuous crying required before an alert is raised.
- **Day_Mode**: The operating mode active during configurable daytime hours, using a longer Alert_Threshold (default 10 seconds).
- **Night_Mode**: The operating mode active during configurable nighttime hours, using a shorter Alert_Threshold (default 5 seconds).
- **Confidence_Score**: The model's probability output for the `crying` class, expressed as a percentage (0–100).
- **Cry_Window**: The rolling time window used by the frontend to decide whether crying is currently active (existing constant `CRY_WINDOW`).
- **Calm_Window**: The rolling time window used by the frontend to decide whether the baby has calmed (existing constant `CALM_WINDOW`).

---

## Requirements

### Requirement 1: Priority Score Calculation

**User Story:** As a parent, I want each cry alert to show an urgency level, so that I can quickly assess how serious the situation is without relying solely on an alert existing.

#### Acceptance Criteria

1. WHEN the Detector classifies an audio chunk as `crying`, THE Priority_Scorer SHALL compute an Urgency_Level for that detection using exactly the following four inputs, each weighted equally at 25%: cry duration so far (seconds), continuity ratio (fraction of the last 10 consecutive chunks classified as crying), number of distinct cry events in the last 60 seconds (where a "cry event" is a contiguous sequence of crying-classified chunks), and the Confidence_Score (0–100).
2. THE Priority_Scorer SHALL assign Urgency_Level `low` when the weighted priority score is in the range [0, 25), and exactly one Urgency_Level SHALL be assigned per score (ranges are non-overlapping and exhaustive).
3. THE Priority_Scorer SHALL assign Urgency_Level `medium` when the weighted priority score is in the range [25, 50).
4. THE Priority_Scorer SHALL assign Urgency_Level `high` when the weighted priority score is in the range [50, 75).
5. THE Priority_Scorer SHALL assign Urgency_Level `critical` when the weighted priority score is in the range [75, 100].
6. WHEN the Detector broadcasts a detection result via WebSocket and the label is `crying`, THE Detector SHALL include the field `urgency_level` (one of: `"low"`, `"medium"`, `"high"`, `"critical"`) and `priority_score` (number, 0–100) in the JSON payload.
7. WHEN the Frontend receives a WebSocket message with label `crying` containing `urgency_level`, THE Frontend SHALL display the Urgency_Level in both the alert banner and the corresponding recent-events list entry.
8. THE Priority_Scorer SHALL produce a deterministic output when given identical values for all four inputs: cry duration, continuity ratio, cry event count, and Confidence_Score.
9. WHEN the Frontend receives a WebSocket message where the label is not `crying`, THE Frontend SHALL NOT display an urgency level or priority score for that message.

---

### Requirement 2: Cry Episodes

**User Story:** As a parent, I want the system to group each cry sequence into one episode with a summary, so that I can review the history of crying events, their duration, and severity.

#### Acceptance Criteria

1. WHEN the Detector accumulates enough consecutive `crying`-classified chunks to meet the Alert_Threshold (as defined by the Night_Mode_Controller in Requirement 3), THE Episode_Tracker SHALL record the episode start timestamp (ISO 8601 format, local time) and mark the episode as active.
2. WHEN the Detector accumulates enough consecutive non-crying chunks to determine the baby has calmed, THE Episode_Tracker SHALL record the episode end timestamp, calculate the episode duration in seconds (end minus start, rounded down), and assign the peak Urgency_Level observed during the episode.
3. WHEN an episode ends, THE Episode_Tracker SHALL emit an episode summary event containing: `episode_id` (unique string), `start_time` (ISO 8601), `end_time` (ISO 8601), `duration_seconds` (integer), and `urgency_level` (Urgency_Level).
4. WHEN the Frontend receives an episode summary event, THE Frontend SHALL display the episode summary in the events history panel, including start time, end time, duration, and Urgency_Level.
5. THE Episode_Tracker SHALL store all completed episodes in an in-memory list accessible via a backend REST endpoint.
6. WHEN a GET request is made to `/episodes`, THE Episode_Tracker SHALL return the list of all completed Cry_Episodes in reverse chronological order (most recent first); IF no episodes exist, THE Episode_Tracker SHALL return an empty list.
7. THE Episode_Tracker SHALL retain at most 100 completed episodes in memory; IF adding a new episode would exceed 100, THE Episode_Tracker SHALL discard the oldest episode before adding the new one.
8. WHILE an episode is in progress, THE Episode_Tracker SHALL update the running duration and current Urgency_Level once per audio chunk processed.
9. WHEN the system stops or the backend shuts down while an episode is in progress, THE Episode_Tracker SHALL close the active episode, record the shutdown time as the end timestamp, and store the partial episode in the completed list.

---

### Requirement 3: Night Mode

**User Story:** As a parent, I want the system to automatically apply a shorter alert delay at night, so that I am notified faster when my baby cries during sleeping hours.

#### Acceptance Criteria

1. WHEN an audio chunk is processed, THE Night_Mode_Controller SHALL evaluate the current local hour and classify the system into either Day_Mode or Night_Mode.
2. WHILE in Day_Mode, THE Night_Mode_Controller SHALL apply an Alert_Threshold of 10 seconds of continuous crying before triggering an alert.
3. WHILE in Night_Mode, THE Night_Mode_Controller SHALL apply an Alert_Threshold of 5 seconds of continuous crying before triggering an alert.
4. THE Night_Mode_Controller SHALL define Day_Mode as the period from 07:00 (inclusive) to 22:00 (exclusive) local time by default.
5. THE Night_Mode_Controller SHALL define Night_Mode as the period from 22:00 (inclusive) to 07:00 (exclusive) local time by default.
6. WHERE the operator provides `NIGHT_MODE_START_HOUR` and `DAY_MODE_START_HOUR` environment variables as valid integers in the range [0, 23], THE Night_Mode_Controller SHALL use those values instead of the defaults.
7. WHEN the operating mode transitions between Day_Mode and Night_Mode, THE Detector SHALL broadcast a mode-change event exactly once per transition to all connected Frontend clients containing the field `mode` with value `"day"` or `"night"`; additionally, THE Night_Mode_Controller SHALL reset the continuous-cry accumulation counter to zero so the new Alert_Threshold applies from the next detection window.
8. WHEN the Frontend receives a mode-change event, THE Frontend SHALL update the status bar to display either "Day" or "Night" to reflect the current operating mode.
9. IF `NIGHT_MODE_START_HOUR` or `DAY_MODE_START_HOUR` environment variables are set to values outside the range [0, 23], or cannot be parsed as integers, THEN THE Night_Mode_Controller SHALL log a configuration error and fall back to the default values.

---

### Requirement 4: Unified Event History and Persistence

**User Story:** As a parent, I want a consolidated history of all cry episodes with their urgency levels, so that I can identify patterns over time.

#### Acceptance Criteria

1. THE Frontend SHALL display a unified history list that shows Cry_Episodes in reverse chronological order (most recent first), with each entry showing: start time (formatted as a human-readable locale string), duration in seconds, and Urgency_Level; the list SHALL be capped at 100 entries to match the backend retention limit.
2. WHEN the Frontend is first loaded or the WebSocket reconnects, THE Frontend SHALL fetch the episode history from the `/episodes` endpoint and re-populate the history panel upon a successful HTTP 200 response; IF the fetch fails or returns a non-200 status, THE Frontend SHALL leave the history panel empty and SHALL NOT automatically retry until the next page load or reconnect event.
3. THE Frontend SHALL visually distinguish episodes by Urgency_Level using colour coding: `low` → green, `medium` → yellow/amber, `high` → orange, `critical` → red.
4. IF the history panel contains more than 20 episodes, THE Frontend SHALL render the list in a scrollable container with a fixed maximum height, such that the scrollable list does not expand beyond its allocated panel area or push other UI panels out of position.
