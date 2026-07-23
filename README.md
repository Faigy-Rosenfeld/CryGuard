# 👶 CRY-GUARD — Baby Monitor

> Real-time baby cry detection · Instant parent notification

[![Python](https://img.shields.io/badge/Python-3.13-3776AB?style=flat&logo=python&logoColor=white)](https://python.org)
[![TensorFlow](https://img.shields.io/badge/TensorFlow-2.x-FF6F00?style=flat&logo=tensorflow&logoColor=white)](https://tensorflow.org)
[![React](https://img.shields.io/badge/React-18-61DAFB?style=flat&logo=react&logoColor=black)](https://reactjs.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.139-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)

---

## 📖 Project Description

CRY-GUARD is an AI system that continuously listens through the microphone, detects baby crying in real time, and sends an instant alert to the parent — via a live UI and SMS.

Developed as a final project in **Artificial Intelligence** by:
- 👩‍💻 Faigy Rosenfeld
- 👩‍💻 Tzipi Tsukrov
- 👩‍💻 Avital Choen

---

## 📸 Screenshots

### Main Interface
![Main Interface](screenshots/the_system.png)

### Alert — Cry Detected
![Active Alert](screenshots/alarm.png)

### Baby Calmed Down
![Alert Off](screenshots/finish_alarm.png)

---

## ✨ Key Features

| Feature | Description |
|---------|-------------|
| 🎤 **Real-time Listening** | Continuously active microphone with per-second analysis |
| 🤖 **Custom CNN** | Deep Learning model trained from scratch on thousands of samples |
| 📊 **Live Waveform Graph** | Real-time visualization of audio volume |
| 🔔 **Smart Alerting** | Triggers only after sustained crying — not every noise |
| 📱 **SMS via Twilio** | Sends a message directly to the parent's phone |
| 🌙 **Night Mode** | 5-second threshold at night / 10 seconds during the day |
| 📋 **Event History** | Logs all events with precise timestamps |

---

## 🏗️ System Architecture

```
🎤 Microphone (22,050 Hz)
      ↓
📦 Rolling Buffer (2s window / 1s step)
      ↓
🎼 Mel Spectrogram (128 × T)
      ↓
🤖 CNN Model (4 × Conv2D)
      ↓
📈 Classification: crying / background
      ↓
🔔 WebSocket → React UI + SMS
```

### CNN Model

```
Input(128, T, 1)
Conv2D(32)  → BatchNorm → MaxPool → Dropout(0.25)
Conv2D(64)  → BatchNorm → MaxPool → Dropout(0.25)
Conv2D(128) → BatchNorm → MaxPool → Dropout(0.25)
Conv2D(128) → BatchNorm → GlobalAvgPool
Dense(256)  → Dropout(0.5)
Dense(2)    → Softmax → [crying, background]
```

---

## 📁 Project Structure

```
CRY-GUARD/
├── backend/                # FastAPI server
│   ├── main.py             # Core logic + WebSocket
│   ├── episode_tracker.py  # Cry event lifecycle tracking
│   ├── night_mode.py       # Day/night mode controller
│   └── priority_scorer.py  # Priority scoring 0–100
├── frontend/               # React UI
│   └── src/
│       ├── App.js          # Main component
│       └── App.css         # Styling
├── models/
│   ├── cryguard_model.keras   # Trained model
│   └── norm_stats.json        # Normalization statistics
├── audio/                  # Audio samples for testing
├── screenshots/            # Screenshots
├── .env                    # Environment variables (not committed to Git)
├── requirements.txt
└── README.md
```

---

## 🚀 Installation & Setup

### Prerequisites

- Python 3.10+
- Node.js 18+
- Connected microphone
- Twilio account (optional — for SMS)

### 1. Clone & Install Python Dependencies

```bash
git clone https://github.com/your-repo/cry-guard.git
cd cry-guard

pip install -r requirements.txt
```

### 2. Configure Environment Variables

Create a `.env` file in the root directory:

```env
API_KEY=cryguard-secret-key-2024
TWILIO_ACCOUNT_SID=your_sid
TWILIO_AUTH_TOKEN=your_token
TWILIO_FROM_NUMBER=+1234567890
```

> Without Twilio — the system works fully, just without SMS sending.

### 3. Start the Backend

```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8080
```

### 4. Start the Frontend

```bash
cd frontend
npm install
npm start
```

Open your browser at `http://localhost:3000` 🎉

---

## 🎛️ How to Use

1. Click the **▶** button to start listening
2. The microphone activates — the graph displays the audio level
3. When sustained crying is detected — a **red alert** appears
4. An SMS is sent to the configured phone number (if enabled)
5. When the baby calms down — a **green message** appears

---

## 🧠 Training Data

The model was trained on data from multiple sources:

| Source | Content | Amount |
|--------|---------|--------|
| Donate-a-Cry | Baby crying | 457 files |
| ESC-50 | Environmental sounds + crying | 2,000 files |
| AudioSet | Home and background sounds | Various |
| MUSAN | Music, speech, noise | Various |

### Data Augmentation (crying class only)
- Gaussian Noise — simulates different microphones
- Time Shift — varied timing
- Amplitude Scale — volume 0.7–1.3
- SpecAugment — Frequency + Time masking

---

## 🛠️ Technologies

**Backend & AI**
`Python` · `TensorFlow 2.x` · `Keras` · `librosa` · `FastAPI` · `WebSocket` · `sounddevice` · `Twilio`

**Frontend**
`React 18` · `JavaScript` · `Canvas API` · `WebSocket`

**Training**
`Google Colab (GPU)` · `scikit-learn` · `numpy` · `matplotlib`

---

## 👩‍💻 Custom Development

All of the following was built from scratch in this project:
- Full CNN architecture
- Priority Scorer — 0–100 scoring based on duration, continuity, frequency, and confidence
- Episode Tracker — cry event lifecycle management
- Night Mode Controller — dynamic alert threshold
- FastAPI Backend + WebSocket with broadcast to all clients
