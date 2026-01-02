"""
app.py

Main FastAPI application for ResQ backend.
Handles image input from Flutter, runs AI processing,
stores victim status, and powers the control-room dashboard.
"""

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
from pathlib import Path
import cv2
import numpy as np

from detector import Detector
from risk import compute_risk
from grid import assign_grid
from dashboard import get_dashboard_html

# --------------------------------------------------
# App setup
# --------------------------------------------------

app = FastAPI(title="ResQ Backend API", version="1.0.0")

BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"
STATIC_DIR.mkdir(exist_ok=True)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# --------------------------------------------------
# Initialize AI components
# --------------------------------------------------

detector = Detector()

# --------------------------------------------------
# GLOBAL STATE (for dashboard)
# --------------------------------------------------

latest_victims = []   # stores latest detection results

# --------------------------------------------------
# Utility: draw dashboard annotations
# --------------------------------------------------

def draw_dashboard(image: np.ndarray, victims: list) -> None:
    """
    Draw bounding boxes, priority labels, and grid info
    and save to static/latest_annotated.jpg
    """
    output = image.copy()

    for v in victims:
        x1, y1, x2, y2 = v["bbox_xyxy"]

        if v["priority"] == "HIGH":
            color = (0, 0, 255)
        elif v["priority"] == "MEDIUM":
            color = (0, 255, 255)
        else:
            color = (0, 255, 0)

        cv2.rectangle(output, (x1, y1), (x2, y2), color, 2)

        label = f"ID:{v['id']} {v['priority']} Pose:{v['pose']}"
        cv2.putText(
            output,
            label,
            (x1, max(y1 - 10, 20)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            color,
            2
        )

    cv2.imwrite(str(STATIC_DIR / "latest_annotated.jpg"), output)

# --------------------------------------------------
# API endpoints
# --------------------------------------------------

@app.get("/")
async def root():
    return {"status": "ResQ Backend running"}


@app.post("/detect")
async def detect_victims(file: UploadFile = File(...)):
    """
    Receives an image from Flutter phone,
    performs victim detection, priority estimation,
    grid mapping, and updates dashboard.
    """
    global latest_victims

    try:
        # Read image bytes
        image_bytes = await file.read()
        np_arr = np.frombuffer(image_bytes, np.uint8)
        image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

        if image is None:
            raise ValueError("Invalid image data")

        # Save original image
        cv2.imwrite(str(STATIC_DIR / "latest.jpg"), image)

        h, w = image.shape[:2]

        # -------------------------
        # Detection
        # -------------------------
        detections = detector.detect(image)

        victims = []
        for d in detections:
            v = compute_risk(d)
            v = assign_grid(v, w, h)
            victims.append(v)

        # Sort victims by priority (HIGH → LOW)
        priority_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
        victims.sort(key=lambda x: priority_order[x["priority"]])

        # Store for dashboard
        latest_victims = victims

        # Draw annotated image
        draw_dashboard(image, victims)

        return {
            "count": len(victims),
            "victims": victims,
            "image_url": "/static/latest.jpg",
            "annotated_image_url": "/static/latest_annotated.jpg"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/status")
def get_status():
    """
    Provides latest victim data for dashboard UI
    """
    return {
        "victims": latest_victims
    }


@app.get("/latest")
async def latest_image():
    path = STATIC_DIR / "latest.jpg"
    if not path.exists():
        raise HTTPException(status_code=404, detail="No image available")
    return FileResponse(path)


@app.get("/latest/annotated")
async def latest_annotated_image():
    path = STATIC_DIR / "latest_annotated.jpg"
    if not path.exists():
        raise HTTPException(status_code=404, detail="No annotated image available")
    return FileResponse(path)


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    """
    Professional control-room dashboard
    """
    return get_dashboard_html()

# --------------------------------------------------
# Run server
# --------------------------------------------------

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
