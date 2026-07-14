import json
import numpy as np
import sounddevice as sd
from tensorflow import keras
from audio_utils import extract_melspectrogram

MODEL_PATH = "models/sos_model.keras"
NORM_PATH  = "models/norm_stats.json"
CATEGORIES = ["crying", "background"]
SR         = 22050
DURATION   = 2
STEP       = 1
THRESHOLD  = 0.35

model = keras.models.load_model(MODEL_PATH)
with open(NORM_PATH) as f:
    stats = json.load(f)
MEAN, STD = stats["mean"], stats["std"]


def process_chunk(audio: np.ndarray) -> None:
    mel = extract_melspectrogram(audio, sr=SR)
    mel = (mel - MEAN) / (STD + 1e-8)
    mel = mel[np.newaxis, ..., np.newaxis]
    probs = model.predict(mel, verbose=0)[0]
    label = CATEGORIES[np.argmax(probs)]
    confidence = probs.max()
    print(f"[שומע] {label} ({confidence:.0%})")
    if label == "crying" and confidence >= THRESHOLD:
        print(f"[התרעה!] בכי זוהה ({confidence:.0%})")


def listen():
    print("מאזין... (Ctrl+C לעצירה)")
    buffer     = np.zeros(int(DURATION * SR), dtype="float32")
    chunk_size = int(STEP * SR)
    try:
        while True:
            new_audio = sd.rec(chunk_size, samplerate=SR, channels=1, dtype="float32")
            sd.wait()
            buffer = np.roll(buffer, -chunk_size)
            buffer[-chunk_size:] = new_audio.flatten()
            process_chunk(buffer.copy())
    except KeyboardInterrupt:
        print("עצר.")


if __name__ == "__main__":
    listen()
