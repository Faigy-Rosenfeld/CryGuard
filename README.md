# 👶 CRY-GUARD — שומר הבית

> זיהוי בכי תינוק חכם בזמן אמת · התרעה מיידית לטלפון ההורה

[![Python](https://img.shields.io/badge/Python-3.13-blue?logo=python)](https://python.org)
[![TensorFlow](https://img.shields.io/badge/TensorFlow-2.x-orange?logo=tensorflow)](https://tensorflow.org)
[![React](https://img.shields.io/badge/React-18-61DAFB?logo=react)](https://reactjs.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.139-009688?logo=fastapi)](https://fastapi.tiangolo.com)

---

## 📖 תיאור הפרויקט

CRY-GUARD היא מערכת AI שמאזינה ברציפות דרך המיקרופון, מזהה בכי תינוק בזמן אמת, ושולחת התרעה מיידית להורה — בממשק חי ובSMS.

המערכת פותחה כפרויקט גמר בתחום **בינה מלאכותית** על ידי:
- 👩‍💻 פייגי רוזנפלד
- 👩‍💻 ציפי צוקרוב
- 👩‍💻 אביטל

---

## 📸 צילומי מסך

### הממשק הראשי
![הממשק הראשי](screenshots/the_system.png)

### התרעה — בכי זוהה
![התרעה פעילה](screenshots/alarm.png)

### התינוק נרגע
![התרעה כבויה](screenshots/finish_alarm.png)

---

## ✨ תכונות עיקריות

| תכונה | תיאור |
|-------|--------|
| 🎤 **האזנה בזמן אמת** | מיקרופון פעיל ברציפות עם ניתוח כל שנייה |
| 🤖 **CNN מותאם** | מודל Deep Learning שאומן מאפס על אלפי דוגמאות |
| 📊 **גרף גלים חי** | ויזואליזציה של עוצמת הקול בזמן אמת |
| 🔔 **התרעה חכמה** | רק אחרי בכי רציף — לא על כל רחש |
| 📱 **SMS דרך Twilio** | שליחת הודעה ישירות לטלפון ההורה |
| 🌙 **מצב לילה** | סף 5 שניות בלילה / 10 שניות ביום |
| 📋 **היסטוריית אירועים** | תיעוד כל האירועים עם שעה מדויקת |

---

## 🏗️ ארכיטקטורת המערכת

```
🎤 מיקרופון (22,050 Hz)
      ↓
📦 Rolling Buffer (2 שנ' / צעד 1 שנ')
      ↓
🎼 Mel Spectrogram (128 × T)
      ↓
🤖 CNN Model (4 × Conv2D)
      ↓
📈 סיווג: crying / background
      ↓
🔔 WebSocket → React UI + SMS
```

### מודל ה-CNN

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

## 📁 מבנה הפרויקט

```
CRY-GUARD/
├── backend/                # שרת FastAPI
│   ├── main.py             # לוגיקה ראשית + WebSocket
│   ├── episode_tracker.py  # מעקב אחר אירועי בכי
│   ├── night_mode.py       # בקר מצב לילה/יום
│   └── priority_scorer.py  # ניקוד דחיפות 0–100
├── frontend/               # ממשק React
│   └── src/
│       ├── App.js          # קומפוננטה ראשית
│       └── App.css         # עיצוב
├── models/
│   ├── cryguard_model.keras   # מודל מאומן
│   └── norm_stats.json        # סטטיסטיקות נרמול
├── audio/                  # קטעי שמע לבדיקה
├── screenshots/            # צילומי מסך
├── .env                    # משתני סביבה (לא מועלה ל-Git)
├── requirements.txt
└── README.md
```

---

## 🚀 התקנה והפעלה

### דרישות מקדימות

- Python 3.10+
- Node.js 18+
- מיקרופון מחובר
- חשבון Twilio (אופציונלי — לשליחת SMS)

### 1. שכפול והתקנת Python

```bash
git clone https://github.com/your-repo/cry-guard.git
cd cry-guard

pip install -r requirements.txt
```

### 2. הגדרת משתני סביבה

צרי קובץ `.env` בתיקייה הראשית:

```env
API_KEY=cryguard-secret-key-2024
TWILIO_ACCOUNT_SID=your_sid
TWILIO_AUTH_TOKEN=your_token
TWILIO_FROM_NUMBER=+1234567890
```

> ללא Twilio — המערכת עובדת מלא, רק ללא שליחת SMS.

### 3. הפעלת Backend

```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8080
```

### 4. הפעלת Frontend

```bash
cd frontend
npm install
npm start
```

פתחי דפדפן על `http://localhost:3000` 🎉

---

## 🎛️ שימוש במערכת

1. לחצי על כפתור **▶** להפעלת ההאזנה
2. המיקרופון מתחיל לעבוד — הגרף מציג את רמת הקול
3. כשמזוהה בכי רציף — מופיעה **התרעה אדומה**
4. SMS נשלח לטלפון שהוגדר (אם הופעל)
5. כשהתינוק נרגע — מופיעה **הודעה ירוקה**

---

## 🧠 נתוני האימון

המודל אומן על נתונים ממקורות מגוונים:

| מקור | תוכן | כמות |
|------|------|------|
| Donate-a-Cry | בכי תינוקות | 457 קבצים |
| ESC-50 | רעשי סביבה + בכי | 2,000 קבצים |
| AudioSet | רעשי בית ורקע | מגוון |
| MUSAN | מוזיקה, דיבור, רעש | מגוון |

### Data Augmentation (על crying בלבד)
- Gaussian Noise — סימולציית מיקרופונים שונים
- Time Shift — תזמון שונה
- Amplitude Scale — עוצמה 0.7–1.3
- SpecAugment — Frequency + Time masking

---

## 🛠️ טכנולוגיות

**Backend & AI**
`Python` · `TensorFlow 2.x` · `Keras` · `librosa` · `FastAPI` · `WebSocket` · `sounddevice` · `Twilio`

**Frontend**
`React 18` · `JavaScript` · `Canvas API` · `WebSocket`

**אימון**
`Google Colab (GPU)` · `scikit-learn` · `numpy` · `matplotlib`

---

## 👩‍💻 פיתוח עצמי

כל הקוד הבא פותח מאפס בפרויקט זה:
- ארכיטקטורת CNN המלאה
- Priority Scorer — ניקוד 0–100 לפי משך, רציפות, תדירות וביטחון
- Episode Tracker — מחזור חיי אירוע בכי
- Night Mode Controller — סף התרעה דינמי
- Backend FastAPI + WebSocket עם broadcast לכל הלקוחות

---

*פרויקט גמר · מסלול בינה מלאכותית · 2024–2025*
