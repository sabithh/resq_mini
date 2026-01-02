# ResQ-Drone Simulator Backend

AI-based victim detection, priority assessment, and control-room visualization system built with FastAPI.

## Overview

ResQ-Drone Simulator is a rescue assistance system that detects human victims from disaster-scene images using YOLO (Ultralytics YOLOv8), estimates their urgency using visual risk indicators, and maps locations to a grid system. The system provides a control-room style dashboard for rescue operators to make informed decisions.

## Features

- **Victim Detection**: YOLOv8-based detection of human victims (persons) in images
- **Visual Risk Assessment**: Priority calculation using:
  - Bounding box area (smaller = partial burial indicator)
  - Aspect ratio (unusual posture = distress indicator)
  - Detection confidence (low = unclear visibility = danger indicator)
- **Grid Mapping**: Spatial organization of victims using 10×10 grid coordinates
- **Annotated Visualization**: Images with color-coded bounding boxes (Red=High, Orange=Medium, Green=Low priority)
- **Control Room Dashboard**: Web-based interface for viewing results and uploading images
- **RESTful API**: FastAPI endpoints for integration with mobile Flutter app

## Project Structure

```
resq_backend/
├── app.py              # Main FastAPI application
├── detector.py         # YOLO detection module
├── risk.py             # Risk assessment and priority logic
├── grid.py             # Grid mapping functionality
├── dashboard.py        # Dashboard UI HTML generator
├── static/                    # Static files directory
│   ├── latest.jpg            # Last processed image
│   └── latest_annotated.jpg  # Annotated image with bounding boxes
├── requirements.txt    # Python dependencies
└── README.md           # This file
```

## Installation

1. Create a virtual environment (recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Running the Server

```bash
python app.py
```

Or using uvicorn directly:
```bash
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

The server will start on `http://localhost:8000`

### API Endpoints

- `GET /` - Root endpoint, returns API status
- `POST /detect` - Upload an image for victim detection
  - Request: multipart/form-data with `file` field
  - Response: JSON with:
    - `detections`: List of detected victims with bbox, confidence, area, aspect_ratio
    - `risk_assessment`: Risk levels and priority items
    - `grid_data`: Grid mapping with coordinates
    - `image_url`: Original image URL
    - `annotated_image_url`: Image with bounding boxes and labels
- `GET /dashboard` - Serve the control room dashboard UI
- `GET /latest` - Get the latest processed image
- `GET /latest/annotated` - Get the latest annotated image with bounding boxes
- `GET /static/{filename}` - Serve static files

### Dashboard

Access the web dashboard at:
```
http://localhost:8000/dashboard
```

Upload images through the web interface to see:
- Annotated images with color-coded bounding boxes
- Risk assessment with priority levels
- Grid location mapping
- Detailed detection information

## Configuration

### YOLO Model Setup

The system uses Ultralytics YOLOv8 by default. The model will be automatically downloaded on first use.

You can specify a different model:
```python
# In app.py, modify:
detector = Detector(model_name="yolov8s.pt")  # or yolov8m.pt, yolov8l.pt, yolov8x.pt
```

Available models (faster to slower, more accurate):
- `yolov8n.pt` - Nano (fastest, default)
- `yolov8s.pt` - Small
- `yolov8m.pt` - Medium
- `yolov8l.pt` - Large
- `yolov8x.pt` - Extra Large (most accurate)

### Risk Assessment Parameters

The risk calculator uses visual indicators. You can adjust thresholds in `risk.py`:
```python
# Modify thresholds (0-1 scale)
self.thresholds = {
    RiskLevel.HIGH: 0.6,    # Adjust for more/less high priority
    RiskLevel.MEDIUM: 0.3,  # Adjust for more/less medium priority
    RiskLevel.LOW: 0.0,
}

# Adjust risk factor weights
risk_score = (
    0.5 * area_risk +      # 50% weight on area (partial burial)
    0.3 * confidence_risk + # 30% weight on confidence (visibility)
    0.2 * aspect_risk       # 20% weight on aspect ratio (posture)
)
```

### Grid Size

Adjust grid dimensions in `grid.py`:
```python
grid_mapper = GridMapper(grid_size=(20, 20))  # 20x20 grid
```

## System Architecture

### Field Unit (Mobile - Flutter App)
- Captures images from disaster scene
- Sends images to backend via POST `/detect`

### Control Unit (Laptop - Backend)
- Receives images from mobile app
- Performs YOLO detection (persons only)
- Calculates risk using visual indicators
- Maps victims to grid coordinates
- Displays results on dashboard

## How It Works

1. **Image Acquisition**: Mobile app captures and sends image
2. **Victim Detection**: YOLOv8 detects all persons in the image
3. **Risk Assessment**: For each victim, calculates risk based on:
   - **Area**: Smaller bounding box → higher risk (partial burial)
   - **Aspect Ratio**: Unusual width/height → higher risk (distress posture)
   - **Confidence**: Lower confidence → higher risk (unclear visibility)
4. **Grid Mapping**: Maps each victim's center point to a 10×10 grid cell
5. **Visualization**: Draws color-coded bounding boxes on image:
   - 🔴 Red: High priority
   - 🟠 Orange: Medium priority
   - 🟢 Green: Low priority

## Dependencies

- **ultralytics**: YOLOv8 object detection
- **fastapi**: Modern web framework for building APIs
- **uvicorn**: ASGI server for running FastAPI
- **opencv-python**: Image processing and annotation
- **numpy**: Numerical computations
- **pillow**: Image handling

## License

[Add your license here]

## Contributing

[Add contribution guidelines here]

