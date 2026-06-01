import os
import numpy as np
import librosa

RAW_DIR = "data/raw"
PROCESSED_DIR = "data/processed"
CATEGORIES = ["scream", "crying", "explosion", "background"]

def process_file(file_path):
    audio, sr = librosa.load(file_path, sr=22050, duration=5.0)
    target_length = 22050 * 5
    if len(audio) < target_length:
        audio = np.pad(audio, (0, target_length - len(audio)))
    else:
        audio = audio[:target_length]
    mel = librosa.feature.melspectrogram(y=audio, sr=sr, n_mels=128)
    return librosa.power_to_db(mel, ref=np.max)

def main():
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    total = 0
    for category in CATEGORIES:
        category_dir = os.path.join(RAW_DIR, category)
        for filename in os.listdir(category_dir):
            if not filename.endswith(".wav"):
                continue
            file_path = os.path.join(category_dir, filename)
            mel_db = process_file(file_path)
            save_path = os.path.join(PROCESSED_DIR, f"{category}_{filename.replace('.wav', '.npy')}")
            np.save(save_path, mel_db)
            total += 1
        print(f"{category}: עובד בהצלחה")
    print(f"\nסה\"כ עובדו {total} קבצים ונשמרו ב-{PROCESSED_DIR}")

if __name__ == "__main__":
    main()
