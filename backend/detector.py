"""
CRY-GUARD — Audio Detector
============================
Handles all audio-related logic: microphone input, feature extraction,
CNN model inference, and the main async processing loop.

Consumed by main.py — do not run this file directly.

Exposed interface:
    is_listening    -- bool flag, set by main.py to start/stop processing
    buffer          -- current rolling audio window (managed internally)
    audio_queue     -- thread-safe queue fed by the mic callback
    mic_stream      -- sound device InputStream (started at import time)
    process_chunk() -- classify a 2-second audio window
    audio_loop()    -- async background task, call once at server startup
"""

import asyncio
import queue
import json
import numpy as np
import sounddevice as sd
import librosa
from tensorflow import keras

# ── Model constants ────────────────────────────────────────────────────────────
CATEGORIES = ["crying", "background"]  # Must match the order used during training
SR         = 22050                     # Sample rate (Hz)
DURATION   = 2                         # Analysis window length (seconds)
STEP       = 1                         # Step size — one new chunk per second
THRESHOLD  = 0.35                      # Minimum model confidence to trigger an alert (0–1)

# Load model and normalization statistics once at import time
model = keras.models.load_model("models/cryguard_model.keras")
with open("models/norm_stats.json") as f:
    _stats = json.load(f)
MEAN = _stats["mean"]  # Mel Spectrogram mean from the training set
STD  = _stats["std"]   # Mel Spectrogram std from the training set

# ── Shared state (read/written by main.py) ─────────────────────────────────────
is_listening = False   # Set to True by /start endpoint, False by /stop
buffer       = None    # Rolling numpy array of the last DURATION seconds of audio

# ── Internal audio pipeline ────────────────────────────────────────────────────
audio_queue: queue.Queue = queue.Queue()  # Mic chunks waiting to be processed


def audio_callback(indata, frames, time, status):
    """
    sounddevice callback — runs in a dedicated thread every STEP seconds.
    Sanitizes the incoming chunk and places it in the queue for async processing.

    Args:
        indata  -- numpy array of shape (frames, channels)
        frames  -- number of samples in this chunk
        time    -- sounddevice timestamps (unused)
        status  -- hardware status flags; printed if non-zero
    """
    if status:
        print(f"[MIC] {status}")
    chunk = indata[:, 0].copy()                                    # take channel 0 (mono)
    chunk = np.nan_to_num(chunk, nan=0.0, posinf=0.0, neginf=0.0) # sanitize
    chunk = np.clip(chunk, -1.0, 1.0)                             # hard clip
    audio_queue.put(chunk)


# Open the microphone stream immediately when this module is imported.
# device=1 is the built-in Intel Smart Sound microphone on this machine.
# To list available devices: python -c "import sounddevice as sd; print(sd.query_devices())"
mic_stream = sd.InputStream(
    device=1,
    samplerate=SR,
    channels=1,
    dtype="float32",
    blocksize=int(STEP * SR),   # one chunk = exactly one second
    callback=audio_callback,
)
mic_stream.start()


def process_chunk(audio: np.ndarray) -> dict:
    """
    Classify a 2-second audio window using the CNN model.

    Pipeline:
        1. Compute Mel Spectrogram (128 frequency bins)
        2. Convert power to dB scale
        3. Normalize using training set mean and std
        4. Run model inference
        5. Compute RMS for waveform volume display

    Args:
        audio -- numpy float32 array of exactly DURATION * SR samples

    Returns:
        dict:
            label      -- "crying" or "background"
            confidence -- model confidence as a percentage (0–100)
            alert      -- True if label is "crying" and confidence >= THRESHOLD
            volume     -- normalized RMS volume for the waveform graph (0–1)
            probs      -- confidence percentage per category
    """
    mel   = librosa.feature.melspectrogram(y=audio, sr=SR, n_mels=128)
    mel   = librosa.power_to_db(mel, ref=np.max)
    mel   = (mel - MEAN) / (STD + 1e-8)
    mel   = np.nan_to_num(mel, nan=0.0, posinf=0.0, neginf=0.0)
    mel   = mel[np.newaxis, ..., np.newaxis]   # shape: (1, 128, T, 1)

    probs = model.predict(mel, verbose=0)[0]
    probs = np.nan_to_num(probs, nan=0.5)
    probs = probs / (probs.sum() + 1e-8)       # renormalize — guards against NaN output

    label      = CATEGORIES[np.argmax(probs)]
    confidence = float(probs.max())
    rms        = float(np.sqrt(np.mean(audio ** 2)))
    volume     = min(1.0, rms * 80)            # scaled up for visible waveform bars

    return {
        "label":      label,
        "confidence": round(confidence * 100, 1),
        "alert":      label != "background" and confidence >= THRESHOLD,
        "volume":     round(volume, 3),
        "probs":      {cat: round(float(p) * 100, 1) for cat, p in zip(CATEGORIES, probs)},
    }


async def audio_loop(broadcast_fn, send_sms_fn):
    """
    Main async processing loop — should be started once as a background task.

    When listening is active:
        1. Pull a chunk from audio_queue without blocking the event loop
        2. Append to the rolling buffer
        3. Once the buffer reaches DURATION seconds, run process_chunk
        4. Call broadcast_fn to push results to WebSocket clients
        5. Call send_sms_fn if the result contains an alert

    When listening is off:
        Drain the queue and sleep to avoid busy-waiting.

    Args:
        broadcast_fn  -- async callable(result: dict) — sends result to all WS clients
        send_sms_fn   -- callable(label: str) — sends SMS alert
    """
    global buffer, is_listening
    buf_size = int(DURATION * SR)
    loop     = asyncio.get_event_loop()

    while True:
        if not is_listening:
            while not audio_queue.empty():
                audio_queue.get_nowait()
            await asyncio.sleep(0.1)
            continue

        try:
            new_audio = await loop.run_in_executor(
                None, lambda: audio_queue.get(timeout=2)
            )
        except queue.Empty:
            continue

        rms_val = float(np.sqrt(np.mean(new_audio ** 2)))
        print(f"[MIC] RMS={rms_val:.4f}")

        buffer = new_audio.copy() if buffer is None else np.concatenate([buffer, new_audio])

        if len(buffer) < buf_size:
            continue

        buffer = buffer[-buf_size:]   # keep only the last DURATION seconds
        result = process_chunk(buffer.copy())
        print(f"[DET] {result['label']} {result['confidence']}% vol={result['volume']}")

        await broadcast_fn(result)

        if result["alert"]:
            send_sms_fn(result["label"])
