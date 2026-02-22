"""
detector.py

ResQ – Stable human detector with ByteTrack persistent IDs.
- YOLOv8 general detection  (filters to person class only)
- YOLOv8-Pose for lying / standing inference
- ByteTrack for cross-frame ID persistence
"""

from typing import List, Dict
import numpy as np
from ultralytics import YOLO


class Detector:
    def __init__(self, conf: float = 0.3):
        self.conf = conf
        self.detector   = YOLO("yolov8m.pt")
        self.pose_model = YOLO("yolov8m-pose.pt")
        self.PERSON_CLASS_ID = 0

        print("[Detector] ByteTrack + pose pipeline loaded")
        print(f"[Detector] Confidence threshold: {self.conf}")

    # --------------------------------------------------
    # MAIN DETECTION  (with ByteTrack)
    # --------------------------------------------------
    def detect(self, image: np.ndarray) -> List[Dict]:
        victims = []

        # track() instead of __call__ → persistent IDs via ByteTrack
        det_results = self.detector.track(
            image,
            conf=self.conf,
            persist=True,           # keep tracker state between calls
            tracker="bytetrack.yaml",
            verbose=False,
            classes=[self.PERSON_CLASS_ID]  # filter to persons only
        )

        if not det_results or det_results[0].boxes is None:
            return victims

        boxes   = det_results[0].boxes.xyxy.cpu().numpy()
        confs   = det_results[0].boxes.conf.cpu().numpy()
        # track IDs may be None if no track assigned yet
        ids_raw = det_results[0].boxes.id
        track_ids = ids_raw.cpu().numpy().astype(int) if ids_raw is not None else list(range(len(boxes)))

        h_img, w_img = image.shape[:2]

        for i, box in enumerate(boxes):
            x1, y1, x2, y2 = map(int, box)
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w_img, x2), min(h_img, y2)
            w, h   = x2 - x1, y2 - y1

            if w < 20 or h < 20:
                continue

            pose = "unknown"
            try:
                crop = image[y1:y2, x1:x2]
                if crop.size > 0:
                    pose_res = self.pose_model(crop, verbose=False)
                    if pose_res and pose_res[0].keypoints is not None:
                        pose = self._infer_pose(
                            pose_res[0].keypoints.data.cpu().numpy(), w, h
                        )
            except Exception:
                pass

            victims.append({
                "id":           int(track_ids[i]),   # ← persistent ByteTrack ID
                "confidence":   round(float(confs[i]), 3),
                "bbox_xyxy":    [x1, y1, x2, y2],
                "center":       [x1 + w // 2, y1 + h // 2],
                "area":         w * h,
                "aspect_ratio": round(w / h, 3) if h > 0 else 0.0,
                "pose":         pose
            })

        return victims

    # --------------------------------------------------
    # POSE INFERENCE (unchanged logic)
    # --------------------------------------------------
    def _infer_pose(self, kpts, w, h):
        if kpts is None:
            return "unknown"

        kpts = np.asarray(kpts)
        if kpts.ndim == 3:
            kpts = kpts[0]
        if kpts.shape[0] < 13:
            return "unknown"

        try:
            nose  = kpts[0]
            l_hip = kpts[11]
            r_hip = kpts[12]
        except Exception:
            return "unknown"

        if nose[2] < 0.5 or (l_hip[2] < 0.5 and r_hip[2] < 0.5):
            return "unknown"

        hip_y  = l_hip[1] if l_hip[2] > r_hip[2] else r_hip[1]
        head_y = nose[1]

        if abs(head_y - hip_y) < h * 0.35:
            return "lying"
        return "standing"
