import pandas as pd
import shutil
import os

# =============================================================================
# המודל הוא בינארי: crying vs. background
#
# scream ו-explosion הוצאו בכוונה — הם שלב שני שדורש דאטה נפרד ומגוון.
# עד אז הם לא נכנסים לאימון כדי לא לזהם את ה-background.
#
# SPEECH: חשוב לכלול קטגוריות דיבור ב-background!
# ללא נתוני דיבור, המודל לא ראה מעולם ספקטרוגרמת קול אנושי רגיל,
# ולכן מבלבל דיבור עם בכי (שניהם קול אנושי עם אנרגיה בתדרי הקול).
# מקורות מומלצים להוספה ידנית ל-data/raw/background:
#   - Mozilla Common Voice  (https://commonvoice.mozilla.org)
#   - LibriSpeech           (https://www.openslr.org/12)
#   - FSD50K תגית "Speech"  (https://zenodo.org/record/4060432)
# =============================================================================

ESC50_DIR = r"C:\Users\This User\Downloads\ESC-50-master\ESC-50-master"
OUTPUT_DIR = r"C:\Users\This User\Desktop\SOS-Audio-Detection\data\raw"

CATEGORY_MAP = {
    # --- מצוקה ---
    "crying_baby":      "crying",

    # --- רעשי בית ---
    "vacuum_cleaner":   "background",
    "washing_machine":  "background",
    "clock_tick":       "background",
    "door_wood_knock":  "background",

    # --- רעשי רחוב ---
    "car_horn":         "background",
    "engine":           "background",
    "train":            "background",
    "airplane":         "background",
    "footsteps":        "background",

    # --- רעשי חוץ ---
    "wind":             "background",
    "rain":             "background",
    "sea_waves":        "background",
    "insects":          "background",
    "chirping_birds":   "background",

    # --- רעשי אנשים (לא בכי) ---
    # אלה חשובים כדי שהמודל ילמד שקול אנושי ≠ בכי
    "laughing":         "background",
    "keyboard_typing":  "background",
    "clapping":         "background",
    "breathing":        "background",

    # --- קטגוריות שהוצאו בכוונה ---
    # "siren"         → scream (שלב שני)
    # "glass_breaking"→ scream (שלב שני)
    # "fireworks"     → explosion (שלב שני)
    # "thunderstorm"  → explosion (שלב שני)
}

CATEGORIES = ["crying", "background"]

def main():
    csv_path = os.path.join(ESC50_DIR, "meta", "esc50.csv")
    audio_dir = os.path.join(ESC50_DIR, "audio")

    df = pd.read_csv(csv_path)

    # צור תיקיות יעד
    for cat in CATEGORIES:
        os.makedirs(os.path.join(OUTPUT_DIR, cat), exist_ok=True)

    copied = 0
    for _, row in df.iterrows():
        category = CATEGORY_MAP.get(row["category"])
        if category is None:
            continue
        src = os.path.join(audio_dir, row["filename"])
        dst = os.path.join(OUTPUT_DIR, category, row["filename"])
        shutil.copy2(src, dst)
        copied += 1

    print(f"הועתקו {copied} קבצים בהצלחה!")
    for folder in CATEGORIES:
        folder_path = os.path.join(OUTPUT_DIR, folder)
        count = len(os.listdir(folder_path)) if os.path.exists(folder_path) else 0
        print(f"  {folder}: {count} קבצים")

    print("\nתזכורת: הוסף קבצי WAV של דיבור לתיקיית data/raw/background")
    print("ראה הערות בראש הקובץ לפרטים על מקורות מומלצים.")

if __name__ == "__main__":
    main()
