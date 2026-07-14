import sys
import os
import asyncio
import queue
import numpy as np
import sounddevice as sd
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from dotenv import load_dotenv
from tensorflow import keras
from twilio.rest import Client
from pydantic import BaseModel
import librosa
import json

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

load_dotenv()
API_KEY      = os.getenv("API_KEY")
TWILIO_SID   = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_FROM  = os.getenv("TWILIO_FROM_NUMBER")
twilio_client = Client(TWILIO_SID, TWILIO_TOKEN) if TWILIO_SID and TWILIO_TOKEN and TWILIO_FROM else None

parent_phone  = None
alert_cooldown = {}
alert_prefs   = {"crying": True}
api_key_header = APIKeyHeader(name="X-API-Key")

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

CATEGORIES = ["crying", "background"]
SR         = 22050
DURATION   = 2
STEP       = 1
THRESHOLD  = 0.35

model = keras.models.load_model("models/cryguard_model.keras")
with open("models/norm_stats.json") as f:
    _stats = json.load(f)
MEAN, STD = _stats["mean"], _stats["std"]

is_listening = False
buffer       = None

# רשימת כל ה-WebSocket clients המחוברים
connected_clients: list[WebSocket] = []

# תור אודיו מה-mic
audio_queue: queue.Queue = queue.Queue()

def audio_callback(indata, frames, time, status):
    if status:
        print(f"[MIC] {status}")
    chunk = indata[:, 0].copy()
    chunk = np.nan_to_num(chunk, nan=0.0, posinf=0.0, neginf=0.0)
    chunk = np.clip(chunk, -1.0, 1.0)
    audio_queue.put(chunk)

mic_stream = sd.InputStream(
    samplerate=SR,
    channels=1,
    dtype="float32",
    blocksize=int(STEP * SR),
    callback=audio_callback,
)
mic_stream.start()


class PhoneRequest(BaseModel):
    phone: str

class PrefsRequest(BaseModel):
    crying: bool = True


def send_sms(label: str):
    import time
    if not parent_phone:
        print("[SMS] No phone number set")
        return
    now = time.time()
    if not alert_prefs.get(label, True):
        return
    if now - alert_cooldown.get(label, 0) < 60:
        return
    alert_cooldown[label] = now

    body = {"crying": "👶 התרעה: התינוק בוכה!"}.get(label, "🚨 התרעת CRYGUARD")

    if not twilio_client:
        print("[SMS] Twilio is not configured. Please set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, and TWILIO_FROM_NUMBER in the .env file.")
        return

    try:
        twilio_client.messages.create(
            body=body,
            from_=TWILIO_FROM,
            to=parent_phone,
        )
        print(f"[SMS] Sent via Twilio to {parent_phone}")
    except Exception as exc:
        print(f"[SMS] Twilio failed: {exc}")


def verify_key(key: str = Depends(api_key_header)):
    if key != API_KEY:
        raise HTTPException(status_code=403, detail="Forbidden")
    return key


def process_chunk(audio: np.ndarray) -> dict:
    mel  = librosa.feature.melspectrogram(y=audio, sr=SR, n_mels=128)
    mel  = librosa.power_to_db(mel, ref=np.max)
    mel  = (mel - MEAN) / (STD + 1e-8)
    mel  = np.nan_to_num(mel, nan=0.0, posinf=0.0, neginf=0.0)
    mel  = mel[np.newaxis, ..., np.newaxis]
    probs = model.predict(mel, verbose=0)[0]
    probs = np.nan_to_num(probs, nan=0.5)
    probs = probs / (probs.sum() + 1e-8)

    label      = CATEGORIES[np.argmax(probs)]
    confidence = float(probs.max())
    rms        = float(np.sqrt(np.mean(audio ** 2)))
    volume     = min(1.0, rms * 20)

    return {
        "label":      label,
        "confidence": round(confidence * 100, 1),
        "alert":      label != "background" and confidence >= THRESHOLD,
        "volume":     round(volume, 3),
        "probs":      {cat: round(float(p) * 100, 1) for cat, p in zip(CATEGORIES, probs)},
    }


async def broadcast(result: dict):
    """שולח תוצאה לכל ה-clients המחוברים"""
    dead = []
    for ws in connected_clients:
        try:
            await ws.send_json(result)
        except Exception:
            dead.append(ws)
    for ws in dead:
        connected_clients.remove(ws)


async def audio_loop():
    """לולאה מרכזית אחת — קוראת מהמיק ושולחת לכולם"""
    global buffer, is_listening
    buf_size = int(DURATION * SR)
    loop     = asyncio.get_event_loop()

    while True:
        if not is_listening:
            # רוקן תור ישן
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

        if buffer is None:
            buffer = new_audio.copy()
        else:
            buffer = np.concatenate([buffer, new_audio])

        if len(buffer) < buf_size:
            continue

        buffer = buffer[-buf_size:]
        result = process_chunk(buffer.copy())
        print(f"[DET] {result['label']} {result['confidence']}% vol={result['volume']}")

        if connected_clients:
            await broadcast(result)

        if result["alert"]:
            send_sms(result["label"])


@app.on_event("startup")
async def startup():
    asyncio.create_task(audio_loop())


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    key = websocket.query_params.get("api_key")
    if key != API_KEY:
        await websocket.close(code=1008)
        return

    await websocket.accept()
    connected_clients.append(websocket)
    print(f"[WS] client חובר — סה\"כ: {len(connected_clients)}")

    try:
        while True:
            # מחכים לסגירה מהצד של ה-client
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        if websocket in connected_clients:
            connected_clients.remove(websocket)
        print(f"[WS] client התנתק — נותרו: {len(connected_clients)}")


@app.post("/prefs")
async def set_prefs(req: PrefsRequest, key: str = Depends(verify_key)):
    global alert_prefs
    alert_prefs = req.dict()
    return {"status": "ok"}


@app.post("/phone")
async def set_phone(req: PhoneRequest, key: str = Depends(verify_key)):
    global parent_phone
    parent_phone = req.phone
    return {"status": "ok", "phone": parent_phone}


@app.post("/start")
async def start(key: str = Depends(verify_key)):
    global is_listening, buffer
    buffer = None
    is_listening = True
    return {"status": "listening"}


@app.post("/stop")
async def stop(key: str = Depends(verify_key)):
    global is_listening, buffer
    is_listening = False
    buffer = None
    return {"status": "stopped"}


@app.get("/status")
async def status(key: str = Depends(verify_key)):
    return {"is_listening": is_listening}
