"""
app.py

ResQ Backend – FINAL FIXED VERSION
Telegram Long-Polling + Image + Video + Live Dashboard
"""

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
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

from detector import Detector
from risk import compute_risk
from grid import assign_grid
from dashboard import get_dashboard_html
from dashboard_video import get_video_dashboard_html
from telegram_alert import send_telegram_alert

# --------------------------------------------------
# TELEGRAM CONFIG (LONG POLLING)
# --------------------------------------------------

BOT_TOKEN = "8492000668:AAFBC8eGDbnuK3GgpF1Jx8juk2kOGp_tCps"
CHAT_ID = "-5114857613"
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"
telegram_offset = 0

# --------------------------------------------------
# APP SETUP
# --------------------------------------------------

app = FastAPI(title="ResQ Backend API", version="FINAL")
BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"
VIDEO_DIR = BASE_DIR / "videos"

STATIC_DIR.mkdir(exist_ok=True)
VIDEO_DIR.mkdir(exist_ok=True)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Globals
detector = Detector()
latest_victims = []
video_victims_timeline = []
rescue_status = {}
latest_stream_frame = None
frame_lock = Lock()
streaming_active = False
video_thread = None
current_video_path = str(VIDEO_DIR / "current.mp4") if (VIDEO_DIR / "current.mp4").exists() else None

# Telegram worker (defined below)
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
                data = query.get("data", "")

                try:
                    action, vid, row, col = data.split(":")
                    key = (int(vid), (int(row), int(col)))
                except Exception:
                    continue

                if key not in rescue_status:
                    rescue_status[key] = {
                        "rescued": False,
                        "onway": False,
                        "rescuer": None,
                        "last_alert": None
                    }

                # Use same logic as elsewhere
                if action == "onway":
                    rescue_status[key]["onway"] = True
                    user = query["from"].get("first_name", "Responder")
                    rescue_status[key]["rescuer"] = user

                    # Announce
                    requests.post(
                        f"{TELEGRAM_API}/sendMessage",
                        json={
                            "chat_id": CHAT_ID,
                            "text": f"🚑 *ON THE WAY*\n{user} is responding to Victim ID {vid}",
                            "parse_mode": "Markdown"
                        },
                        timeout=5
                    )

                    # Update keyboard (remove onway)
                    msg_id = query["message"]["message_id"]
                    requests.post(
                        f"{TELEGRAM_API}/editMessageReplyMarkup",
                        json={
                            "chat_id": CHAT_ID,
                            "message_id": msg_id,
                            "reply_markup": {
                                "inline_keyboard": [
                                    [
                                        {"text": "✔️ Rescued", "callback_data": f"rescued:{vid}:{row}:{col}"}
                                    ],
                                    [
                                        {"text": "❗ False Alarm", "callback_data": f"false:{vid}:{row}:{col}"}
                                    ]
                                ]
                            }
                        },
                        timeout=5
                    )

                elif action == "rescued":
                    rescue_status[key]["rescued"] = True
                    rescue_status[key]["onway"] = False

                    requests.post(
                        f"{TELEGRAM_API}/sendMessage",
                        json={
                            "chat_id": CHAT_ID,
                            "text": f"✅ *RESCUED*\nVictim ID {vid} rescue confirmed.",
                            "parse_mode": "Markdown"
                        },
                        timeout=5
                    )

                    msg_id = query["message"]["message_id"]
                    requests.post(
                        f"{TELEGRAM_API}/editMessageReplyMarkup",
                        json={
                            "chat_id": CHAT_ID,
                            "message_id": msg_id,
                            "reply_markup": {"inline_keyboard": []}
                        },
                        timeout=5
                    )

                elif action == "false":
                    rescue_status[key]["rescued"] = True

                    requests.post(
                        f"{TELEGRAM_API}/sendMessage",
                        json={
                            "chat_id": CHAT_ID,
                            "text": f"❗ *FALSE ALARM*\nVictim ID {vid} marked false.",
                            "parse_mode": "Markdown"
                        },
                        timeout=5
                    )

                    msg_id = query["message"]["message_id"]
                    requests.post(
                        f"{TELEGRAM_API}/editMessageReplyMarkup",
                        json={
                            "chat_id": CHAT_ID,
                            "message_id": msg_id,
                            "reply_markup": {"inline_keyboard": []}
                        },
                        timeout=5
                    )

        except Exception as e:
            print("[Telegram] Poll error:", e)

        time.sleep(1)

threading.Thread(target=telegram_polling_worker, daemon=True).start()

# --------------------------------------------------
# IMAGE DETECTION
# --------------------------------------------------

def draw_dashboard(image, victims):
    output = image.copy()

    for v in victims:
        x1, y1, x2, y2 = v["bbox_xyxy"]
        priority = v.get("priority", "LOW")

        color = (0, 255, 0)
        if priority == "HIGH":
            color = (0, 0, 255)
        elif priority == "MEDIUM":
            color = (0, 255, 255)

        cv2.rectangle(output, (x1, y1), (x2, y2), color, 2)
        label = f"ID:{v['id']} {v['pose']} {priority}"
        cv2.putText(output, label, (x1, max(y1 - 10, 20)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

    cv2.imwrite(str(STATIC_DIR / "latest_annotated.jpg"), output)


def crop_victim(image, bbox, victim_id):
    x1, y1, x2, y2 = bbox
    x1 = max(0, int(x1))
    y1 = max(0, int(y1))
    x2 = max(0, int(x2))
    y2 = max(0, int(y2))

    if x2 <= x1 or y2 <= y1:
        return None

    crop = image[y1:y2, x1:x2]
    if crop.size == 0:
        return None

    path = STATIC_DIR / f"victim_{victim_id}.jpg"
    cv2.imwrite(str(path), crop)
    return str(path)

@app.post("/detect")
async def detect_image(file: UploadFile = File(...)):
    global latest_victims

    image = cv2.imdecode(np.frombuffer(await file.read(), np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise HTTPException(400, "Invalid image")

    h, w = image.shape[:2]
    victims = []

    for d in detector.detect(image):
        v = assign_grid(compute_risk(d), w, h)
        victims.append(v)

    latest_victims = victims
    draw_dashboard(image, victims)

    now = datetime.utcnow()

    for v in victims:
        if v["priority"] in ["HIGH", "MEDIUM"]:
            key = (v["id"], tuple(v["grid"]))
            entry = rescue_status.setdefault(key, {
                "rescued": False,
                "onway": False,
                "rescuer": None,
                "last_alert": None
            })

            if not entry["rescued"] and (
                entry["last_alert"] is None or
                (now - entry["last_alert"]) > timedelta(minutes=1)
            ):
                crop_path = crop_victim(image, v["bbox_xyxy"], v["id"])
                if crop_path and send_telegram_alert(v, crop_path):
                    entry["last_alert"] = now

    return {"count": len(victims), "victims": victims}

# --------------------------------------------------
# VIDEO UPLOAD
# --------------------------------------------------

@app.post("/upload-video")
async def upload_video(file: UploadFile = File(...)):
    global current_video_path, streaming_active
    streaming_active = False

    path = VIDEO_DIR / "current.mp4"
    with open(path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    current_video_path = str(path)
    return {"status": "uploaded"}

# --------------------------------------------------
# VIDEO WORKER (FPS AWARE)
# --------------------------------------------------

def video_worker():
    global streaming_active, latest_stream_frame, latest_victims

    cap = cv2.VideoCapture(current_video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    delay = 1 / fps if fps > 0 else 0.03

    while streaming_active and cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        victims = []
        h, w = frame.shape[:2]

        for d in detector.detect(frame):
            victims.append(assign_grid(compute_risk(d), w, h))

        latest_victims = victims
        draw_dashboard(frame, victims)

        with frame_lock:
            latest_stream_frame = frame.copy()

        time.sleep(delay)

    cap.release()
    streaming_active = False

# --------------------------------------------------
# STREAM CONTROLS
# --------------------------------------------------

@app.post("/start-stream")
def start_stream():
    global streaming_active, video_thread

    if not current_video_path:
        raise HTTPException(400, "No video uploaded")

    if streaming_active:
        return {"status": "already running"}

    streaming_active = True
    video_thread = threading.Thread(target=video_worker, daemon=True)
    video_thread.start()
    return {"status": "started"}

@app.post("/restart-stream")
def restart_stream():
    global streaming_active, video_thread
    streaming_active = False
    time.sleep(0.2)
    streaming_active = True
    video_thread = threading.Thread(target=video_worker, daemon=True)
    video_thread.start()
    return {"status": "restarted"}

@app.post("/stop-stream")
def stop_stream():
    global streaming_active
    streaming_active = False
    return {"status": "stopped"}

# --------------------------------------------------
# STATUS + DASHBOARDS
# --------------------------------------------------

@app.get("/status")
def status():
    enriched = []
    for v in latest_victims:
        vv = deepcopy(v)
        key = (vv["id"], tuple(vv["grid"]))
        state = rescue_status.get(key, {})
        vv["rescued"] = state.get("rescued", False)
        vv["onway"] = state.get("onway", False)
        vv["rescuer"] = state.get("rescuer")
        enriched.append(vv)
    return {"victims": enriched}

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    return get_dashboard_html()

@app.get("/dashboard/video", response_class=HTMLResponse)
def dashboard_video():
    return get_video_dashboard_html()

# --------------------------------------------------
# MJPEG STREAM
# --------------------------------------------------

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

# --------------------------------------------------
# RUN
# --------------------------------------------------

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
