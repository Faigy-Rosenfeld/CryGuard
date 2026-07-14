import sys
import os
import asyncio
import numpy as np
import sounddevice as sd
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from dotenv import load_dotenv
from tensorflow import keras
from twilio.rest import Client
from pydantic import BaseModel

import json

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))
from audio_utils import extract_melspectrogram

load_dotenv()
API_KEY = os.getenv("API_KEY")
TWILIO_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_FROM = os.getenv("TWILIO_FROM_NUMBER")
twilio_client = Client(TWILIO_SID, TWILIO_TOKEN)

parent_phone = None
alert_cooldown = {}
alert_prefs = {"crying": True}
api_key_header = APIKeyHeader(name="X-API-Key")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # רק ה-React שלנו יכול לדבר עם השרת
    allow_methods=["*"],
    allow_headers=["*"],
)

CATEGORIES = ["crying", "background"]
SR = 22050
DURATION = 2
STEP = 1
THRESHOLD = 0.35
MEAN, STD = -30.0, 15.0

model = keras.models.load_model("models/sos_model.keras")
with open("models/norm_stats.json") as f:
    _stats = json.load(f)
MEAN, STD = _stats["mean"], _stats["std"]
buffer = np.zeros(int(DURATION * SR), dtype="float32")
is_listening = False


class PhoneRequest(BaseModel):
    phone: str

class PrefsRequest(BaseModel):
    crying: bool = True


def send_sms(label: str):
    """שולח SMS להורה — רק אם עברו 60 שניות מההתרעה האחרונה"""
    import time
    if not parent_phone:
        return
    now = time.time()
    if not alert_prefs.get(label, True):
        return
    if now - alert_cooldown.get(label, 0) < 60:
        return
    alert_cooldown[label] = now
    messages = {
        "crying": "👶 התרעה: התינוק בוכה!",
    }
    twilio_client.messages.create(
        body=messages.get(label, "🚨 התרעת SOS"),
        from_=TWILIO_FROM,
        to=parent_phone,
    )


def verify_key(key: str = Depends(api_key_header)):
    """בודק שה-API Key נכון — אחרת דוחה את הבקשה"""
    if key != API_KEY:
        raise HTTPException(status_code=403, detail="Forbidden")
    return key


def process_chunk(audio: np.ndarray) -> dict:
    mel = extract_melspectrogram(audio, sr=SR)
    mel = (mel - MEAN) / (STD + 1e-8)
    mel = mel[np.newaxis, ..., np.newaxis]
    probs = model.predict(mel, verbose=0)[0]
    label = CATEGORIES[np.argmax(probs)]
    confidence = float(probs.max())
    return {
        "label": label,
        "confidence": round(confidence * 100, 1),
        "alert": label != "background" and confidence >= THRESHOLD,
        "probs": {cat: round(float(p) * 100, 1) for cat, p in zip(CATEGORIES, probs)},
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket — שולח תוצאות זיהוי בזמן אמת ל-React"""
    global buffer, is_listening

    # בדיקת API Key דרך query parameter ב-WebSocket
    key = websocket.query_params.get("api_key")
    if key != API_KEY:
        await websocket.close(code=1008)  # 1008 = Policy Violation
        return

    await websocket.accept()
    chunk_size = int(STEP * SR)
    try:
        while True:
            if not is_listening:
                await asyncio.sleep(0.1)
                continue
            loop = asyncio.get_event_loop()
            new_audio = await loop.run_in_executor(
                None,
                lambda: sd.rec(chunk_size, samplerate=SR, channels=1, dtype="float32", blocking=True).flatten()
            )
            buffer = np.roll(buffer, -chunk_size)
            buffer[-chunk_size:] = new_audio
            result = process_chunk(buffer.copy())
            await websocket.send_json(result)
            if result["alert"]:
                send_sms(result["label"])
    except WebSocketDisconnect:
        is_listening = False


@app.post("/prefs")
async def set_prefs(req: PrefsRequest, key: str = Depends(verify_key)):
    global alert_prefs
    alert_prefs = req.dict()
    return {"status": "ok"}


@app.post("/phone")
async def set_phone(req: PhoneRequest, key: str = Depends(verify_key)):
    """שומר את מספר הטלפון של ההורה"""
    global parent_phone
    parent_phone = req.phone
    return {"status": "ok", "phone": parent_phone}


@app.post("/start")
async def start(key: str = Depends(verify_key)):
    """מתחיל האזנה — דורש API Key תקין"""
    global is_listening
    is_listening = True
    return {"status": "listening"}


@app.post("/stop")
async def stop(key: str = Depends(verify_key)):
    """עוצר האזנה — דורש API Key תקין"""
    global is_listening
    is_listening = False
    return {"status": "stopped"}


@app.get("/status")
async def status(key: str = Depends(verify_key)):
    """מחזיר את מצב ההאזנה הנוכחי"""
    return {"is_listening": is_listening}
