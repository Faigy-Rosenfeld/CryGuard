<<<<<<< HEAD
import json
import numpy as np
import sounddevice as sd
from tensorflow import keras
from audio_utils import extract_melspectrogram

MODEL_PATH = "src/sos_model.keras"
NORM_PATH  = "src/norm_stats.json"
CATEGORIES = ["scream", "crying", "explosion", "background"]
SR = 22050
DURATION = 2
STEP = 1
THRESHOLD = 0.50

model = keras.models.load_model(MODEL_PATH)
with open(NORM_PATH) as f:
    _stats = json.load(f)
MEAN, STD = _stats["mean"], _stats["std"]
=======
import numpy as np                              # ספרייה לעבודה עם מערכים ומספרים
import json                                      # לטעינת ערכי נרמול שנשמרו באימון
import sounddevice as sd                         # ספרייה להקלטה מהמיקרופון
from tensorflow import keras                     # מייבא את keras מתוך tensorflow — משמש לטעינת המודל שאימנו
from audio_utils import extract_melspectrogram   # הפונקציה שהכנו שממירה אודיו לתמונת צליל (mel spectrogram)

MODEL_PATH = "src/sos_model.keras"               # הנתיב לקובץ המודל השמור
NORM_PATH = "src/norm_stats.json"                # ערכי נרמול שנשמרו בזמן האימון
CATEGORIES = ["crying", "background"]
SR = 22050                                       # קצב דגימה — 22050 נקודות לשנייה (סטנדרט לאודיו)
DURATION = 2                                     # כמה שניות לכל חלון האזנה — חייב להתאים לאימון (2 שניות)
STEP = 1                                         # כל כמה שניות מתחיל חלון חדש (חפיפה של 4 שניות)
THRESHOLD = 0.30                                 # רף הביטחון — המודל חייב להיות בטוח ב-30% לפחות כדי להתריע

model = keras.models.load_model(MODEL_PATH)      # טוען את המודל המאומן מהדיסק לזיכרון

# טעינת ערכי הנרמול האמיתיים מהאימון (במקום ניחוש)
with open(NORM_PATH, "r") as f:
    norm_stats = json.load(f)
MEAN = norm_stats["mean"]
STD = norm_stats["std"]
print(f"[נרמול] mean={MEAN:.4f}, std={STD:.4f}")
>>>>>>> a7c069e6dc4b6d7c827e27f2e41c6169155fe75a


def process_chunk(audio: np.ndarray) -> None:    # פונקציה שמקבלת חתיכת אודיו ומנתחת אותה
    mel = extract_melspectrogram(audio, sr=SR)    # ממירה את האודיו ל-mel spectrogram (מטריצת תדרים לאורך הזמן)
    mel = (mel - MEAN) / (STD + 1e-8)            # מנרמל את הערכים כמו שעשינו באימון (1e-8 מונע חלוקה באפס)
    mel = mel[np.newaxis, ..., np.newaxis]        # מוסיף ממדים שהמודל מצפה להם: (1, n_mels, frames, 1)

    probs = model.predict(mel, verbose=0)[0]      # מריץ את המודל ומקבל הסתברות לכל קטגוריה (verbose=0 = בלי הדפסות)
    label = CATEGORIES[np.argmax(probs)]          # בוחר את הקטגוריה עם ההסתברות הגבוהה ביותר
    confidence = probs.max()                      # שומר את רמת הביטחון של הקטגוריה שנבחרה

    print(f"[שומע] {label} ({confidence:.0%})")           # מדפיס כל זיהוי לאבחון
    if label != "background" and confidence >= THRESHOLD:  # אם זה לא רקע ורמת הביטחון מספיק גבוהה
        print(f"[התרעה!] {label} ({confidence:.0%})")      # מדפיס התרעה עם שם האירוע ואחוז הביטחון


def listen():
    print(f"מאזין... (Ctrl+C לעצירה)")
    buffer = np.zeros(int(DURATION * SR), dtype="float32")   # באפר שמחזיק תמיד את 2 השניות האחרונות
    chunk_size = int(STEP * SR)                              # גודל כל הקלטה חדשה — שנייה אחת
    try:
        while True:
            new_audio = sd.rec(chunk_size, samplerate=SR, channels=1, dtype="float32")  # מקליט שנייה חדשה
            sd.wait()                                                                    # מחכה שתסתיים
            buffer = np.roll(buffer, -chunk_size)            # מזיז את הבאפר שנייה אחת אחורה
            buffer[-chunk_size:] = new_audio.flatten()       # מוסיף את השנייה החדשה לסוף
            process_chunk(buffer.copy())                     # מנתח את 2 השניות המלאות
    except KeyboardInterrupt:
        print("עצר.")


if __name__ == "__main__":   # רץ רק אם הקובץ הופעל ישירות (לא יורד אם מישהו עושה import לקובץ)
    listen()                 # מפעיל את פונקציית ההאזנה
