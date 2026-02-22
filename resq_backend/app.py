"""
app.py

ResQ Backend — Full Production Version
Features:
  - Multi-drone support (drone_id on every endpoint)
  - SQLite persistence (rescue state survives restarts)
  - ByteTrack persistent victim IDs
  - WebSocket live push (instant dashboard updates)
  - Configurable frame skip for video
  - Padded victim crops for better Telegram photos
  - Mission history (/history) and export (/export)
  - Telegram long-polling with callback handling
  - Thermal image support (/detect-thermal)
"""

from fastapi import FastAPI, File, UploadFile, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
from pathlib import Path
import cv2
import numpy as np
import shutil
import time
from datetime import datetime, timedelta
import threading
from threading import Lock
from copy import deepcopy
import requests
import json
import asyncio

from config import (
    BOT_TOKEN, CHAT_ID, BACKEND_HOST, BACKEND_PORT,
    FRAME_SKIP, CROP_PADDING, ALERT_COOLDOWN_MINUTES
)
from detector import Detector
from risk import compute_risk
from grid import assign_grid
from db import init_db, load_rescue_status, save_rescue_status, log_detection, get_history, get_mission_summary
from dashboard import get_dashboard_html
from dashboard_video import get_video_dashboard_html
from thermal_dashboard import get_thermal_dashboard_html
from thermal_processor import preprocess
from telegram_alert import send_telegram_alert

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"
telegram_offset = 0

# ──────────────────────────────────────────────────────
# APP SETUP
# ──────────────────────────────────────────────────────

app = FastAPI(title="ResQ Backend API", version="2.0")
BASE_DIR   = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"
VIDEO_DIR  = BASE_DIR / "videos"

STATIC_DIR.mkdir(exist_ok=True)
VIDEO_DIR.mkdir(exist_ok=True)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# ──────────────────────────────────────────────────────
# GLOBALS
# ──────────────────────────────────────────────────────

detector = Detector()

# rescue_status keyed by (drone_id, victim_id, (grid_row, grid_col))
rescue_status: dict = {}

# per-drone latest victims
drone_victims: dict = {}   # drone_id → list[victim]

latest_stream_frame = None
frame_lock = Lock()
streaming_active   = False
video_thread       = None
current_video_path = str(VIDEO_DIR / "current.mp4") if (VIDEO_DIR / "current.mp4").exists() else None

# asyncio event loop — captured at startup for thread-safe WS push
_loop: asyncio.AbstractEventLoop = None

# ──────────────────────────────────────────────────────
# STARTUP — load DB
# ──────────────────────────────────────────────────────

@app.on_event("startup")
async def on_startup():
    global rescue_status, _loop
    init_db()
    rescue_status = load_rescue_status()
    _loop = asyncio.get_event_loop()    # capture loop for thread-safe WS push
    threading.Thread(target=telegram_polling_worker, daemon=True).start()
    print("[ResQ] Backend v2.0 started — multi-drone + SQLite + WebSocket ready")

# ──────────────────────────────────────────────────────
# WEBSOCKET MANAGER
# ──────────────────────────────────────────────────────

class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []
        self._lock = Lock()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        with self._lock:
            self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        with self._lock:
            if ws in self.active:
                self.active.remove(ws)

    async def broadcast(self, data: dict):
        payload = json.dumps(data)
        dead = []
        for ws in list(self.active):
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

ws_manager = ConnectionManager()

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws_manager.connect(ws)
    try:
        # Send current state immediately on connect
        await ws.send_text(json.dumps(_build_status_payload()))
        while True:
            await ws.receive_text()   # keep alive (ping from client)
    except WebSocketDisconnect:
        ws_manager.disconnect(ws)

def _build_status_payload(drone_id: str = None) -> dict:
    """Build the victim list payload for WebSocket push."""
    victims_out = []
    for did, victims in drone_victims.items():
        if drone_id and did != drone_id:
            continue
        for v in victims:
            vv = deepcopy(v)
            key   = (did, vv["id"], tuple(vv["grid"]))
            state = rescue_status.get(key, {})
            vv["drone_id"] = did
            vv["rescued"]  = state.get("rescued", False)
            vv["onway"]    = state.get("onway",   False)
            vv["rescuer"]  = state.get("rescuer")
            victims_out.append(vv)
    return {"victims": victims_out, "drones": list(drone_victims.keys())}

async def _push_update():
    """Push current state to all WebSocket clients."""
    await ws_manager.broadcast(_build_status_payload())

# ──────────────────────────────────────────────────────
# TELEGRAM LONG POLLING
# ──────────────────────────────────────────────────────

def telegram_polling_worker():
    global telegram_offset
    print("[Telegram] Long polling started")

    while True:
        try:
            resp = requests.get(
                f"{TELEGRAM_API}/getUpdates",
                params={"offset": telegram_offset, "timeout": 5},
                timeout=10
            ).json()

            for update in resp.get("result", []):
                telegram_offset = update["update_id"] + 1

                if "callback_query" not in update:
                    continue

                query = update["callback_query"]
                data  = query.get("data", "")

                try:
                    action, drone_id, vid, row, col = data.split(":")
                    key = (drone_id, int(vid), (int(row), int(col)))
                except Exception:
                    continue

                if key not in rescue_status:
                    rescue_status[key] = {
                        "rescued": False, "onway": False,
                        "rescuer": None, "last_alert": None
                    }

                s = rescue_status[key]

                if action == "onway":
                    s["onway"]   = True
                    user         = query["from"].get("first_name", "Responder")
                    s["rescuer"] = user
                    save_rescue_status(drone_id, int(vid), (int(row), int(col)), s)

                    requests.post(f"{TELEGRAM_API}/sendMessage", json={
                        "chat_id": CHAT_ID,
                        "text": f"🚑 *ON THE WAY*\n{user} responding to Victim {vid} [{drone_id}]",
                        "parse_mode": "Markdown"
                    }, timeout=5)

                    msg_id = query["message"]["message_id"]
                    requests.post(f"{TELEGRAM_API}/editMessageReplyMarkup", json={
                        "chat_id": CHAT_ID, "message_id": msg_id,
                        "reply_markup": {"inline_keyboard": [
                            [{"text": "✔️ Rescued",    "callback_data": f"rescued:{drone_id}:{vid}:{row}:{col}"}],
                            [{"text": "❗ False Alarm", "callback_data": f"false:{drone_id}:{vid}:{row}:{col}"}]
                        ]}
                    }, timeout=5)

                elif action == "rescued":
                    s["rescued"] = True
                    s["onway"]   = False
                    save_rescue_status(drone_id, int(vid), (int(row), int(col)), s)

                    requests.post(f"{TELEGRAM_API}/sendMessage", json={
                        "chat_id": CHAT_ID,
                        "text": f"✅ *RESCUED*\nVictim {vid} [{drone_id}] confirmed rescued.",
                        "parse_mode": "Markdown"
                    }, timeout=5)
                    _clear_keyboard(query["message"]["message_id"])

                elif action == "false":
                    s["rescued"] = True
                    save_rescue_status(drone_id, int(vid), (int(row), int(col)), s)

                    requests.post(f"{TELEGRAM_API}/sendMessage", json={
                        "chat_id": CHAT_ID,
                        "text": f"❗ *FALSE ALARM*\nVictim {vid} [{drone_id}] marked false.",
                        "parse_mode": "Markdown"
                    }, timeout=5)
                    _clear_keyboard(query["message"]["message_id"])

        except Exception as e:
            print("[Telegram] Poll error:", e)

        time.sleep(1)


def _clear_keyboard(msg_id: int):
    requests.post(f"{TELEGRAM_API}/editMessageReplyMarkup", json={
        "chat_id": CHAT_ID, "message_id": msg_id,
        "reply_markup": {"inline_keyboard": []}
    }, timeout=5)

# ──────────────────────────────────────────────────────
# SHARED HELPERS
# ──────────────────────────────────────────────────────

def draw_annotations(image: np.ndarray, victims: list) -> np.ndarray:
    output = image.copy()
    for v in victims:
        x1, y1, x2, y2 = v["bbox_xyxy"]
        priority = v.get("priority", "LOW")
        color = (0, 255, 0)
        if priority == "HIGH":   color = (0, 0, 255)
        elif priority == "MEDIUM": color = (0, 165, 255)
        cv2.rectangle(output, (x1, y1), (x2, y2), color, 2)
        label = f"ID:{v['id']} {v['pose']} {priority}"
        cv2.putText(output, label, (x1, max(y1 - 10, 20)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
    return output


def crop_victim(image: np.ndarray, bbox: list, victim_id: int, pad: int = CROP_PADDING):
    """Crop victim with padding, save to static/, return path."""
    x1, y1, x2, y2 = bbox
    h_img, w_img = image.shape[:2]
    x1 = max(0, int(x1) - pad)
    y1 = max(0, int(y1) - pad)
    x2 = min(w_img, int(x2) + pad)
    y2 = min(h_img, int(y2) + pad)

    if x2 <= x1 or y2 <= y1:
        return None
    crop = image[y1:y2, x1:x2]
    if crop.size == 0:
        return None
    path = STATIC_DIR / f"victim_{victim_id}.jpg"
    cv2.imwrite(str(path), crop)
    return str(path)


def handle_alerts(image: np.ndarray, victims: list, drone_id: str, mode: str = "rgb"):
    """Send Telegram alerts for HIGH/MEDIUM victims and persist to DB."""
    now = datetime.utcnow()
    cooldown = timedelta(minutes=ALERT_COOLDOWN_MINUTES)

    for v in victims:
        log_detection(v, drone_id=drone_id, mode=mode)

        if v["priority"] not in ("HIGH", "MEDIUM"):
            continue

        key   = (drone_id, v["id"], tuple(v["grid"]))
        entry = rescue_status.setdefault(key, {
            "rescued": False, "onway": False,
            "rescuer": None, "last_alert": None
        })

        if entry["rescued"]:
            continue
        if entry["last_alert"] and (now - entry["last_alert"]) < cooldown:
            continue

        crop_path = crop_victim(image, v["bbox_xyxy"], v["id"])
        if crop_path and send_telegram_alert(v, crop_path, drone_id=drone_id):
            entry["last_alert"] = now
            save_rescue_status(drone_id, v["id"], tuple(v["grid"]), entry)

# ──────────────────────────────────────────────────────
# IMAGE DETECTION
# ──────────────────────────────────────────────────────

@app.post("/detect")
async def detect_image(
    file: UploadFile = File(...),
    drone_id: str = "DRONE_1"
):
    image = cv2.imdecode(np.frombuffer(await file.read(), np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise HTTPException(400, "Invalid image")

    h, w = image.shape[:2]
    victims = [assign_grid(compute_risk(d), w, h) for d in detector.detect(image)]

    drone_victims[drone_id] = victims

    annotated = draw_annotations(image, victims)
    cv2.imwrite(str(STATIC_DIR / "latest_annotated.jpg"), annotated)

    handle_alerts(image, victims, drone_id=drone_id, mode="rgb")
    await _push_update()

    return {"count": len(victims), "victims": victims, "drone_id": drone_id}

# ──────────────────────────────────────────────────────
# THERMAL DETECTION
# ──────────────────────────────────────────────────────

@app.post("/detect-thermal")
async def detect_thermal(
    file: UploadFile = File(...),
    mode: str = "clahe",
    drone_id: str = "DRONE_1"
):
    image = cv2.imdecode(np.frombuffer(await file.read(), np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise HTTPException(400, "Invalid image — could not decode")

    cv2.imwrite(str(STATIC_DIR / "thermal_original.jpg"), image)
    processed = preprocess(image, mode=mode)

    h, w = processed.shape[:2]
    victims = [assign_grid(compute_risk(d), w, h) for d in detector.detect(processed)]

    drone_victims[drone_id] = victims

    annotated = draw_annotations(processed, victims)
    cv2.imwrite(str(STATIC_DIR / "thermal_annotated.jpg"), annotated)

    handle_alerts(image, victims, drone_id=drone_id, mode=mode)
    await _push_update()

    return {"count": len(victims), "victims": victims,
            "preprocessing_mode": mode, "drone_id": drone_id}

# ──────────────────────────────────────────────────────
# VIDEO UPLOAD
# ──────────────────────────────────────────────────────

@app.post("/upload-video")
async def upload_video(file: UploadFile = File(...)):
    global current_video_path, streaming_active
    streaming_active = False

    path = VIDEO_DIR / "current.mp4"
    with open(path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    current_video_path = str(path)
    return {"status": "uploaded"}

# ──────────────────────────────────────────────────────
# VIDEO WORKER — frame skip aware
# ──────────────────────────────────────────────────────

def video_worker(drone_id: str = "DRONE_1"):
    global streaming_active, latest_stream_frame

    cap   = cv2.VideoCapture(current_video_path)
    fps   = cap.get(cv2.CAP_PROP_FPS)
    delay = 1 / fps if fps > 0 else 0.03
    frame_count = 0

    while streaming_active and cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        frame_count += 1

        # Frame skip — only run inference every FRAME_SKIP frames
        if frame_count % FRAME_SKIP == 0:
            h, w = frame.shape[:2]
            victims = [assign_grid(compute_risk(d), w, h) for d in detector.detect(frame)]
            drone_victims[drone_id] = victims
            annotated = draw_annotations(frame, victims)
            cv2.imwrite(str(STATIC_DIR / "latest_annotated.jpg"), annotated)
            handle_alerts(frame, victims, drone_id=drone_id, mode="video")
            # Push WebSocket update from thread using the captured event loop
            if _loop and not _loop.is_closed():
                asyncio.run_coroutine_threadsafe(_push_update(), _loop)

        with frame_lock:
            latest_stream_frame = frame.copy()

        time.sleep(delay)

    cap.release()
    streaming_active = False

# ──────────────────────────────────────────────────────
# STREAM CONTROLS
# ──────────────────────────────────────────────────────

@app.post("/start-stream")
def start_stream(drone_id: str = "DRONE_1"):
    global streaming_active, video_thread
    if not current_video_path:
        raise HTTPException(400, "No video uploaded")
    if streaming_active:
        return {"status": "already running"}
    streaming_active = True
    video_thread = threading.Thread(target=video_worker, args=(drone_id,), daemon=True)
    video_thread.start()
    return {"status": "started"}

@app.post("/restart-stream")
def restart_stream(drone_id: str = "DRONE_1"):
    global streaming_active, video_thread
    streaming_active = False
    time.sleep(0.2)
    streaming_active = True
    video_thread = threading.Thread(target=video_worker, args=(drone_id,), daemon=True)
    video_thread.start()
    return {"status": "restarted"}

@app.post("/stop-stream")
def stop_stream():
    global streaming_active
    streaming_active = False
    return {"status": "stopped"}

# ──────────────────────────────────────────────────────
# STATUS
# ──────────────────────────────────────────────────────

@app.get("/status")
def status(drone_id: str = None):
    return _build_status_payload(drone_id=drone_id)

@app.get("/drones")
def list_drones():
    return {"drones": list(drone_victims.keys())}

# ──────────────────────────────────────────────────────
# HISTORY & EXPORT
# ──────────────────────────────────────────────────────

@app.get("/history")
def history(limit: int = 50):
    return {"events": get_history(limit)}

@app.get("/export")
def export_report():
    summary = get_mission_summary()
    return JSONResponse(
        content=summary,
        headers={"Content-Disposition": "attachment; filename=resq_mission_report.json"}
    )

# ──────────────────────────────────────────────────────
# DASHBOARDS
# ──────────────────────────────────────────────────────

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    return get_dashboard_html()

@app.get("/dashboard/video", response_class=HTMLResponse)
def dashboard_video():
    return get_video_dashboard_html()

@app.get("/dashboard/thermal", response_class=HTMLResponse)
def dashboard_thermal():
    return get_thermal_dashboard_html()

# ──────────────────────────────────────────────────────
# MJPEG STREAM
# ──────────────────────────────────────────────────────

@app.get("/video-stream")
def video_stream():
    def generate():
        while True:
            with frame_lock:
                if latest_stream_frame is None:
                    continue
                _, jpg = cv2.imencode(".jpg", latest_stream_frame)
            yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpg.tobytes() + b"\r\n"
            time.sleep(0.03)

    return StreamingResponse(
        generate(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )

# ──────────────────────────────────────────────────────
# RUN
# ──────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run(app, host=BACKEND_HOST, port=BACKEND_PORT)
