from typing import List, Dict
import numpy as np
from ultralytics import YOLO

class Detector:
    def __init__(self, conf: float = 0.3):
        self.conf = conf
        self.detector = YOLO("yolov8s.pt")          # PERSON DETECTION
        self.pose_model = YOLO("yolov8s-pose.pt")  # POSE ONLY
        print("[Detector] Detection + Pose pipeline loaded")

    def detect(self, image: np.ndarray) -> List[Dict]:
        victims = []

        # 1️⃣ PERSON DETECTION (ROBUST)
        det_results = self.detector(image, conf=self.conf, verbose=False)

        if not det_results or det_results[0].boxes is None:
            return victims

        boxes = det_results[0].boxes.xyxy.cpu().numpy()
        confs = det_results[0].boxes.conf.cpu().numpy()

        h_img, w_img = image.shape[:2]

        for i, box in enumerate(boxes):
            x1, y1, x2, y2 = map(int, box)
            
            # Clamp to image bounds
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w_img, x2), min(h_img, y2)
            
            w, h = x2 - x1, y2 - y1
            
            # Skip invalid boxes
            if w < 20 or h < 20:
                continue

            pose = "unknown"

            # 2️⃣ POSE ON CROP (OPTIONAL, SAFE)
            try:
                crop = image[y1:y2, x1:x2]
                if crop.size > 0 and crop.shape[0] > 0 and crop.shape[1] > 0:
                    pose_res = self.pose_model(crop, verbose=False)
                    if pose_res and pose_res[0].keypoints is not None:
                        pose = self._infer_pose(pose_res[0].keypoints.data.cpu().numpy(), w, h)
            except Exception:
                # If pose estimation fails, keep pose as "unknown"
                pass

            victims.append({
                "id": i,
                "confidence": round(float(confs[i]), 3),
                "bbox_xyxy": [x1, y1, x2, y2],
                "center": [x1 + w // 2, y1 + h // 2],
                "area": w * h,
                "aspect_ratio": round(w / h, 3) if h > 0 else 0.0,
                "pose": pose
            })

        return victims

    def _infer_pose(self, kpts, w, h):
        """
        Robust pose inference.
        NEVER crashes.
        """

        # -----------------------------
        # 1. Validate keypoints
        # -----------------------------
        if kpts is None:
            return "unknown"

        kpts = np.asarray(kpts)

        # Handle weird shapes like (1,17,3)
        if kpts.ndim == 3:
            kpts = kpts[0]

        # Must have at least hips + nose
        if kpts.shape[0] < 13:
            return "unknown"

        # -----------------------------
        # 2. Extract safely
        # -----------------------------
        try:
            nose = kpts[0]
            l_hip = kpts[11]
            r_hip = kpts[12]
        except Exception:
            return "unknown"

        # Confidence checks
        if nose[2] < 0.5 or (l_hip[2] < 0.5 and r_hip[2] < 0.5):
            return "unknown"

        hip_y = l_hip[1] if l_hip[2] > r_hip[2] else r_hip[1]
        head_y = nose[1]

        # -----------------------------
        # 3. Pose logic
        # -----------------------------
        if abs(head_y - hip_y) < h * 0.35:
            return "lying"

        return "standing"
