"""
CRY-GUARD — Backend Server
===========================
FastAPI server that manages WebSocket connections, REST endpoints, and SMS alerts.
Audio detection logic lives in detector.py.

Run:
    python -m uvicorn backend.main:app --host 0.0.0.0 --port 8080
"""

import os
import asyncio
import time as _time
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from dotenv import load_dotenv
from twilio.rest import Client
from pydantic import BaseModel

import backend.detector as detector

# ── Environment ────────────────────────────────────────────────────────────────
load_dotenv()
API_KEY      = os.getenv("API_KEY")
TWILIO_SID   = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_FROM  = os.getenv("TWILIO_FROM_NUMBER")

# Twilio client is created only if all credentials are present
twilio_client = Client(TWILIO_SID, TWILIO_TOKEN) if TWILIO_SID and TWILIO_TOKEN and TWILIO_FROM else None

# ── Global state ───────────────────────────────────────────────────────────────
parent_phone   = None             # Phone number for SMS alerts
alert_cooldown = {}               # Last alert timestamp per label (spam prevention)
alert_prefs    = {"crying": True} # Which labels trigger an SMS
api_key_header = APIKeyHeader(name="X-API-Key")

connected_clients: list[WebSocket] = []  # All active WebSocket connections

# ── App setup ──────────────────────────────────────────────────────────────────
app = FastAPI(title="CRY-GUARD API", version="2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Request models ─────────────────────────────────────────────────────────────

class PhoneRequest(BaseModel):
    """Request body for saving a phone number."""
    phone: str

class PrefsRequest(BaseModel):
    """Request body for updating SMS alert preferences."""
    crying: bool = True


# ── Helper functions ───────────────────────────────────────────────────────────

def send_sms(label: str):
    """
    Send an SMS alert to the parent's phone.
    Enforces a 60-second cooldown per label to prevent spam.

    Args:
        label -- classification label ("crying" or "background")
    """
    if not parent_phone:
        print("[SMS] No phone number set")
        return
    now = _time.time()
    if not alert_prefs.get(label, True):
        return
    if now - alert_cooldown.get(label, 0) < 60:
        return
    alert_cooldown[label] = now

    body = {"crying": "👶 Alert: Baby is crying!"}.get(label, "🚨 CRY-GUARD Alert")

    if not twilio_client:
        print("[SMS] Twilio is not configured.")
        return

    try:
        twilio_client.messages.create(body=body, from_=TWILIO_FROM, to=parent_phone)
        print(f"[SMS] Sent to {parent_phone}")
    except Exception as exc:
        print(f"[SMS] Failed: {exc}")


def verify_key(key: str = Depends(api_key_header)):
    """
    FastAPI dependency — validates the API key on every protected endpoint.
    Raises HTTP 403 if the key is wrong.
    """
    if key != API_KEY:
        raise HTTPException(status_code=403, detail="Forbidden")
    return key


async def broadcast(result: dict):
    """
    Push a classification result to all connected WebSocket clients.
    Automatically removes stale (closed) connections.
    """
    dead = []
    for ws in connected_clients:
        try:
            await ws.send_json(result)
        except Exception:
            dead.append(ws)
    for ws in dead:
        connected_clients.remove(ws)


# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    """Start the audio detection loop as a background task on server startup."""
    asyncio.create_task(detector.audio_loop(broadcast, send_sms))


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for the React frontend.
    Authenticates via ?api_key= query parameter.
    Keeps the connection alive until the client disconnects.
    """
    key = websocket.query_params.get("api_key")
    if key != API_KEY:
        await websocket.close(code=1008)
        return

    await websocket.accept()
    connected_clients.append(websocket)
    print(f"[WS] connected — total: {len(connected_clients)}")

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        if websocket in connected_clients:
            connected_clients.remove(websocket)
        print(f"[WS] disconnected — remaining: {len(connected_clients)}")


@app.post("/prefs")
async def set_prefs(req: PrefsRequest, key: str = Depends(verify_key)):
    """Update SMS alert preferences."""
    global alert_prefs
    alert_prefs = req.dict()
    return {"status": "ok"}


@app.post("/phone")
async def set_phone(req: PhoneRequest, key: str = Depends(verify_key)):
    """Save the parent's phone number for SMS alerts."""
    global parent_phone
    parent_phone = req.phone
    return {"status": "ok", "phone": parent_phone}


@app.post("/start")
async def start(key: str = Depends(verify_key)):
    """Start listening — resets the buffer and begins audio processing."""
    detector.buffer       = None
    detector.is_listening = True
    return {"status": "listening"}


@app.post("/stop")
async def stop(key: str = Depends(verify_key)):
    """Stop listening — halts processing and clears the buffer."""
    detector.is_listening = False
    detector.buffer       = None
    return {"status": "stopped"}


@app.get("/status")
async def status(key: str = Depends(verify_key)):
    """Return the current listening state."""
    return {"is_listening": detector.is_listening}
