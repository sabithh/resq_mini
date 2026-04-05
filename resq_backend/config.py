"""
config.py

ResQ – Central configuration loaded from .env
All modules import from here instead of hardcoding credentials.
"""

import os
from pathlib import Path


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}

# Load .env if python-dotenv is available
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass  # .env already exported to environment, or running in Docker

# ── Telegram ───────────────────────────────────────────
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID", "")

if not BOT_TOKEN or not CHAT_ID:
    print("[Config] WARNING: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set in .env")

# ── Server ─────────────────────────────────────────────
BACKEND_HOST = os.environ.get("BACKEND_HOST", "0.0.0.0")
BACKEND_PORT = int(os.environ.get("BACKEND_PORT", "8000"))

# ── Detection tuning ───────────────────────────────────
FRAME_SKIP   = int(os.environ.get("FRAME_SKIP", "3"))    # process 1 in every N video frames
CROP_PADDING = int(os.environ.get("CROP_PADDING", "20")) # px padding around victim crop
ALERT_COOLDOWN_MINUTES = int(os.environ.get("ALERT_COOLDOWN_MINUTES", "1"))

# ── Video runtime tuning ───────────────────────────────
# Smaller infer size gives faster video inference on CPU.
VIDEO_INFER_IMGSZ = int(os.environ.get("VIDEO_INFER_IMGSZ", "960"))
VIDEO_ENABLE_WOUND_DETECTION = _env_bool("VIDEO_ENABLE_WOUND_DETECTION", True)
VIDEO_WRITE_INTERVAL_SEC = float(os.environ.get("VIDEO_WRITE_INTERVAL_SEC", "1.0"))

# MJPEG stream tuning to reduce CPU load while keeping usable quality.
STREAM_FPS = float(os.environ.get("STREAM_FPS", "12"))
STREAM_JPEG_QUALITY = int(os.environ.get("STREAM_JPEG_QUALITY", "80"))

# ── Model paths ───────────────────────────────────────
# Use fine-tuned aerial model when available, fall back to stock COCO
DETECTION_MODEL = os.environ.get("DETECTION_MODEL", "yolov8m-final-rescue.pt")
POSE_MODEL      = os.environ.get("POSE_MODEL", "yolov8m-pose.pt")
POSE_CLASSIFIER = os.environ.get("POSE_CLASSIFIER", "pose_classifier.pkl")
