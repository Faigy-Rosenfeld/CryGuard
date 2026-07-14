import os
import numpy as np
import librosa
import warnings
warnings.filterwarnings("ignore")

RAW_DIR       = "data/raw"
PROCESSED_DIR = "data/processed"
CATEGORIES    = ["crying", "background"]
SR            = 22050
DURATION      = 2.0          # אורך כל segment בשניות
STRIDE        = 1.0          # stride של sliding window בשניות
N_MELS        = 128
SUPPORTED     = (".wav", ".mp3", ".ogg", ".flac", ".m4a")


def file_to_segments(file_path):
    """
    טוען קובץ ומחזיר רשימת segments של DURATION שניות.

    קבצים קצרים מ-DURATION → padding ל-segment בודד.
    קבצים ארוכים → sliding window עם stride STRIDE.
    כך קבצי 5 שניות (ESC-50) מניבים 4 segments במקום segment בודד,
    וסביר יותר לתפוס את ה-event בפועל.
    """
    try:
        audio, _ = librosa.load(file_path, sr=SR, mono=True)
    except Exception as e:
        print(f"  ⚠️  שגיאת טעינה: {file_path} ({e})")
        return []

    target_len = int(SR * DURATION)
    stride_len = int(SR * STRIDE)

    if len(audio) < target_len:
        # קצר מדי — padding לאורך מינימלי
        audio = np.pad(audio, (0, target_len - len(audio)))
        return [audio]

    segments = []
    start = 0
    while start + target_len <= len(audio):
        segments.append(audio[start : start + target_len])
        start += stride_len
    return segments


def audio_to_mel(audio):
    mel = librosa.feature.melspectrogram(y=audio, sr=SR, n_mels=N_MELS)
    return librosa.power_to_db(mel, ref=np.max)


def main():
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    total_ok  = 0
    total_err = 0

    for category in CATEGORIES:
        category_dir = os.path.join(RAW_DIR, category)
        if not os.path.isdir(category_dir):
            print(f"  ⚠️  תיקייה לא קיימת: {category_dir} — מדולגת")
            continue

        cat_ok = 0
        files  = [f for f in os.listdir(category_dir) if f.lower().endswith(SUPPORTED)]

        for filename in files:
            file_path = os.path.join(category_dir, filename)
            stem      = os.path.splitext(filename)[0]
            segments  = file_to_segments(file_path)

            for i, seg in enumerate(segments):
                suffix    = f"_{i}" if len(segments) > 1 else ""
                save_path = os.path.join(PROCESSED_DIR, f"{category}_{stem}{suffix}.npy")
                if os.path.exists(save_path):
                    cat_ok += 1
                    continue
                try:
                    mel = audio_to_mel(seg)
                    np.save(save_path, mel)
                    cat_ok += 1
                except Exception as e:
                    print(f"  ⚠️  שגיאת עיבוד: {filename} segment {i} ({e})")
                    total_err += 1

        total_ok += cat_ok
        print(f"{category}: {cat_ok} דוגמאות ({len(files)} קבצים)")

    print(f'\nסה"כ: {total_ok} דוגמאות | שגיאות: {total_err}')
    print(f"נשמרו ב-{PROCESSED_DIR}")


if __name__ == "__main__":
    main()
