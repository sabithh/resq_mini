# ResQ Mini 🚨

An AI-powered disaster rescue assistant system that detects and prioritizes human victims from disaster-scene images in real time.

## Overview

ResQ Mini is a two-component rescue coordination system designed to assist first responders during disaster scenarios. A Flutter mobile app acts as a field unit — capturing images on-site — while a FastAPI backend acts as the control unit, running YOLOv8-based AI models to detect victims, assess their risk levels, and display results on a control-room dashboard.

---

## System Architecture

```
┌─────────────────────────┐        POST /detect        ┌──────────────────────────────┐
│   Flutter Mobile App    │  ─────────────────────────▶ │   FastAPI Backend (Laptop)   │
│   (resq_app)            │                              │   (resq_backend)             │
│                         │                              │                              │
│  • Capture images       │                              │  • YOLOv8 victim detection   │
│  • Live camera feed     │                              │  • Risk & priority scoring   │
│  • Send to backend      │                              │  • Grid-based spatial map    │
│  • View results         │ ◀───────────────────────── │  • Annotated image output    │
└─────────────────────────┘        JSON response        └──────────────────────────────┘
                                                                      │
                                                                      ▼
                                                         http://localhost:8000/dashboard
                                                         (Control Room Web Dashboard)
```

---

## Project Structure

```
resq_mini/
├── resq_app/               # Flutter mobile application (field unit)
│   ├── lib/                # Dart source code
│   ├── android/            # Android-specific config
│   ├── ios/                # iOS-specific config
│   └── pubspec.yaml        # Flutter dependencies
│
└── resq_backend/           # Python FastAPI backend (control unit)
    ├── app.py              # Main FastAPI application & API endpoints
    ├── detector.py         # YOLOv8 victim detection module
    ├── risk.py             # Risk scoring & priority assessment logic
    ├── grid.py             # 10×10 spatial grid mapping
    ├── dashboard.py        # Control-room dashboard HTML generator
    ├── static/             # Served images (latest & annotated)
    ├── requirements.txt    # Python dependencies
    └── yolov8*-pose.pt     # Pre-downloaded YOLO model weights
```

---

## Features

### 🤖 AI Backend (`resq_backend`)
- **Victim Detection** – YOLOv8 detects persons in uploaded images
- **Risk Priority Assessment** – Each victim is scored `HIGH / MEDIUM / LOW` based on:
  - Bounding box area (small → possible partial burial)
  - Pose aspect ratio (unusual posture → distress indicator)
  - Detection confidence (low confidence → unclear visibility)
- **Grid Mapping** – Victim positions mapped to a 10×10 coordinate grid
- **Annotated Images** – Color-coded bounding boxes (🔴 HIGH · 🟡 MEDIUM · 🟢 LOW)
- **Control-Room Dashboard** – Web UI at `/dashboard` for rescue operators
- **RESTful API** – Easy integration with any client (Flutter, web, etc.)

### 📱 Mobile App (`resq_app`)
- Flutter-based field unit app
- Captures and uploads images to the backend via camera or gallery
- Displays AI-generated results returned from the backend

---

## Getting Started

### Backend Setup

**Requirements:** Python 3.9+

```bash
cd resq_backend

# Create a virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start the server
python app.py
# OR
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

Server runs at `http://localhost:8000`

| Endpoint | Method | Description |
|---|---|---|
| `/` | GET | API health check |
| `/detect` | POST | Upload image for victim detection |
| `/status` | GET | Latest victim detection state |
| `/latest` | GET | Last processed raw image |
| `/latest/annotated` | GET | Last annotated image with bounding boxes |
| `/dashboard` | GET | Control-room web dashboard |

---

### Flutter App Setup

**Requirements:** Flutter SDK 3.x+

```bash
cd resq_app

flutter pub get
flutter run
```

> Make sure the backend IP is correctly configured in the Flutter app to point to your laptop's local IP address.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Mobile App | Flutter / Dart |
| Backend API | FastAPI + Uvicorn |
| AI Detection | YOLOv8 (Ultralytics) |
| Image Processing | OpenCV, NumPy |
| Model Variants | YOLOv8n-pose, YOLOv8s-pose, YOLOv8s |

---

## License

[Add your license here]
