import pandas as pd
import shutil
import os

ESC50_DIR = r"C:\Users\This User\Downloads\ESC-50-master\ESC-50-master"
OUTPUT_DIR = r"C:\Users\This User\Desktop\SOS-Audio-Detection\data\raw"

CATEGORY_MAP = {
    # צלילי מצוקה
    "crying_baby":      "crying",
    "siren":            "scream",
    "glass_breaking":   "scream",
    "fireworks":        "explosion",
    "thunderstorm":     "explosion",
    # רעשי בית
    "vacuum_cleaner":   "background",
    "washing_machine":  "background",
    "clock_tick":       "background",
    "door_wood_knock":  "background",
    # רעשי רחוב
    "car_horn":         "background",
    "engine":           "background",
    "train":            "background",
    "airplane":         "background",
    "footsteps":        "background",
    # רעשי חוץ
    "wind":             "background",
    "rain":             "background",
    "sea_waves":        "background",
    "insects":          "background",
    "chirping_birds":   "background",
    # רעשי אנשים
    "laughing":         "background",
    "keyboard_typing":  "background",
    "clapping":         "background",
    "breathing":        "background",
}

def main():
    csv_path = os.path.join(ESC50_DIR, "meta", "esc50.csv")
    audio_dir = os.path.join(ESC50_DIR, "audio")

    df = pd.read_csv(csv_path)

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
    for folder in ["scream", "crying", "explosion", "background"]:
        count = len(os.listdir(os.path.join(OUTPUT_DIR, folder)))
        print(f"  {folder}: {count} קבצים")

if __name__ == "__main__":
    main()
