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
    # POSE INFERENCE (Birds-Eye Euclidean Extension)
    # --------------------------------------------------
    def _infer_pose(self, kpts, w, h):
        if kpts is None:
            return "unknown"

        kpts = np.asarray(kpts)
        if kpts.ndim == 3:
            kpts = kpts[0]
        if kpts.shape[0] < 17:  # Need ankles (15, 16)
            return "unknown"

        try:
            # Shoulders (5, 6) -> Neck
            l_sh = kpts[5]
            r_sh = kpts[6]
            if l_sh[2] < 0.2 and r_sh[2] < 0.2: return "unknown"
            
            # Hips (11, 12) -> Pelvis
            l_hp = kpts[11]
            r_hp = kpts[12]
            if l_hp[2] < 0.2 and r_hp[2] < 0.2: return "unknown"

            # Ankles (15, 16)
            l_an = kpts[15]
            r_an = kpts[16]

            # Midpoints
            neck_x, neck_y = (l_sh[0]+r_sh[0])/2, (l_sh[1]+r_sh[1])/2
            pelv_x, pelv_y = (l_hp[0]+r_hp[0])/2, (l_hp[1]+r_hp[1])/2
            
            # Use the most confident ankle, or average if both good
            if l_an[2] > 0.2 and r_an[2] > 0.2:
                ank_x, ank_y = (l_an[0]+r_an[0])/2, (l_an[1]+r_an[1])/2
            elif l_an[2] > 0.2:
                ank_x, ank_y = l_an[0], l_an[1]
            elif r_an[2] > 0.2:
                ank_x, ank_y = r_an[0], r_an[1]
            else:
                ank_x, ank_y = pelv_x, pelv_y # Fallback: Leg length 0 (foreshortened)

        except Exception:
            return "unknown"

        # 1. Bounding box diagonal as relative scale
        import math
        scale = math.sqrt(w**2 + h**2)
        if scale == 0: scale = 0.001

        # 2. Euclidean Physical Extensions
        torso = math.sqrt((neck_x - pelv_x)**2 + (neck_y - pelv_y)**2)
        legs  = math.sqrt((pelv_x - ank_x)**2  + (pelv_y - ank_y)**2)

        # 3. Total Extension Ratio
        extension = (torso + legs) / scale

        # 4. Angled / Birds-Eye Heuristics
        # A. If body is stretched across > 45% of its bounding box diagonal, it is lying down
        if extension > 0.45:
            return "lying"

        # B. If legs are occluded/missing (extension is small) but the box is extremely wide
        # this indicates someone lying horizontally where the tracker only caught their upper body
        if w > h * 1.35:
            return "lying"

        return "standing"
