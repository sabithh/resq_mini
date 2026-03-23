import cv2
import sys
from ultralytics import YOLO
from pose_classifier import PoseClassifier

img = cv2.imread('static/latest_annotated.jpg')
if img is None:
    print("Could not read static/latest_annotated.jpg")
    sys.exit(1)

import json
out = {"det": [], "pose": []}

# Check detection
det_model = YOLO('yolov8m.pt')
res_det = det_model(img, verbose=False, imgsz=1280)
if res_det:
    boxes = res_det[0].boxes.xyxy.cpu().numpy()
    confs = res_det[0].boxes.conf.cpu().numpy()
    for b, c in zip(boxes, confs):
        w, h = b[2]-b[0], b[3]-b[1]
        out["det"].append({"w": float(w), "h": float(h), "conf": float(c)})

# Check pose
pose_model = YOLO('yolov8m-pose.pt')
res_pose = pose_model(img, verbose=False)
clf = PoseClassifier('pose_classifier.pkl')

if res_pose and res_pose[0].keypoints is not None:
    kpts_data = res_pose[0].keypoints.data.cpu().numpy()
    boxes = res_pose[0].boxes.xyxy.cpu().numpy()
    for i, b in enumerate(boxes):
        w, h = b[2]-b[0], b[3]-b[1]
        k = kpts_data[i]
        pred = clf.predict(k, float(w), float(h))
        vis = sum(k[:, 2] > 0.15)
        out["pose"].append({"w": float(w), "h": float(h), "vis": int(vis), "pred": pred})

with open('output.json', 'w') as f:
    json.dump(out, f, indent=2)

