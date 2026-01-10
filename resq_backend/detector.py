from typing import List, Dict
import numpy as np
from ultralytics import YOLO

class Detector:
    def __init__(self, conf: float = 0.3):
        """
        Final stable detector for ResQ.
        - Robust human detection
        - Correct lying / standing pose inference
        - Filters non-human objects safely
        """
        self.conf = conf
        self.detector = YOLO("yolov8s.pt")          # General detector
        self.pose_model = YOLO("yolov8s-pose.pt")  # Pose model
        self.PERSON_CLASS_ID = 0                   # COCO: person

        print("[Detector] Stable human + pose pipeline loaded")
        print(f"[Detector] Confidence threshold: {self.conf}")

    # --------------------------------------------------
    # MAIN DETECTION
    # --------------------------------------------------
    def detect(self, image: np.ndarray) -> List[Dict]:
        victims = []

        # 1️⃣ DETECTION (DO NOT restrict classes here)
        det_results = self.detector(
            image,
            conf=self.conf,
            verbose=False
        )

        if not det_results or det_results[0].boxes is None:
            return victims

        boxes = det_results[0].boxes.xyxy.cpu().numpy()
        confs = det_results[0].boxes.conf.cpu().numpy()
        classes = det_results[0].boxes.cls.cpu().numpy()

        h_img, w_img = image.shape[:2]

        for i, box in enumerate(boxes):

            # 2️⃣ FILTER NON-HUMANS SAFELY
            if int(classes[i]) != self.PERSON_CLASS_ID:
                continue

            x1, y1, x2, y2 = map(int, box)

            # Clamp to image bounds
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w_img, x2), min(h_img, y2)

            w, h = x2 - x1, y2 - y1

            # Skip tiny / invalid boxes
            if w < 20 or h < 20:
                continue

            pose = "unknown"

            # 3️⃣ POSE ESTIMATION (STABLE)
            try:
                crop = image[y1:y2, x1:x2]
                if crop.size > 0:
                    pose_res = self.pose_model(crop, verbose=False)
                    if pose_res and pose_res[0].keypoints is not None:
                        pose = self._infer_pose(
                            pose_res[0].keypoints.data.cpu().numpy(),
                            w,
                            h
                        )
            except Exception:
                pass  # Never crash

            victims.append({
                "id": i,  # frame-local ID
                "confidence": round(float(confs[i]), 3),
                "bbox_xyxy": [x1, y1, x2, y2],
                "center": [x1 + w // 2, y1 + h // 2],
                "area": w * h,
                "aspect_ratio": round(w / h, 3) if h > 0 else 0.0,
                "pose": pose
            })

        return victims

    # --------------------------------------------------
    # POSE INFERENCE (ORIGINAL & CORRECT)
    # --------------------------------------------------
    def _infer_pose(self, kpts, w, h):
        """
        Robust pose inference.
        This logic is intentionally simple and stable.
        """

        if kpts is None:
            return "unknown"

        kpts = np.asarray(kpts)

        # Handle shapes like (1,17,3)
        if kpts.ndim == 3:
            kpts = kpts[0]

        # Must have at least nose + hips
        if kpts.shape[0] < 13:
            return "unknown"

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

        # 🔥 ORIGINAL LOGIC (WORKS BEST)
        if abs(head_y - hip_y) < h * 0.35:
            return "lying"

        return "standing"
