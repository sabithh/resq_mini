"""
detector.py

ResQ – Stable human detector with ByteTrack persistent IDs.
- YOLOv8 detection  (aerial-finetuned or stock COCO, configurable)
- YOLOv8-Pose for keypoint extraction
- ML pose classifier with heuristic fallback
- ByteTrack for cross-frame ID persistence
"""

from typing import List, Dict
import numpy as np
import math
from pathlib import Path
from ultralytics import YOLO

from pose_classifier import PoseClassifier


class Detector:
    def __init__(self, conf: float = 0.15):
        self.conf = conf
        self.PERSON_CLASS_ID = 0

        # ── Load detection model ────────────────────────
        # Prefer aerial-finetuned, fall back to stock COCO
        from config import DETECTION_MODEL, POSE_MODEL, POSE_CLASSIFIER

        det_path = Path(__file__).parent / DETECTION_MODEL
        if det_path.exists():
            self.detector = YOLO(str(det_path))
            print(f"[Detector] Using aerial-finetuned model: {DETECTION_MODEL}")
        else:
            fallback = Path(__file__).parent / "yolov8m.pt"
            self.detector = YOLO(str(fallback))
            print(f"[Detector] Aerial model not found, using stock: yolov8m.pt")

        # ── Load pose model ─────────────────────────────
        pose_path = Path(__file__).parent / POSE_MODEL
        self.pose_model = YOLO(str(pose_path))

        # ── Load ML pose classifier ─────────────────────
        clf_path = Path(__file__).parent / POSE_CLASSIFIER
        self.pose_classifier = PoseClassifier(str(clf_path))

        print(f"[Detector] ByteTrack + pose pipeline loaded")
        print(f"[Detector] Confidence threshold: {self.conf}")
        print(f"[Detector] Pose classifier: {'ML-based' if self.pose_classifier.available else 'heuristic fallback'}")

    # --------------------------------------------------
    # MAIN DETECTION  (with ByteTrack)
    # --------------------------------------------------
    def detect(self, image: np.ndarray, conf: float = None) -> List[Dict]:
        victims = []

        # Use pose model for BOTH detection and tracking!
        # This prevents duplicate bounding boxes from a separate object detection model
        # and runs 2x faster by only using one YOLO pass instead of (Detection + Crop -> Pose).
        det_results = self.pose_model.track(
            image,
            conf=conf if conf is not None else self.conf,
            persist=True,
            tracker="bytetrack.yaml",
            verbose=False,
            imgsz=1280,
            classes=[self.PERSON_CLASS_ID]
        )

        if not det_results or det_results[0].boxes is None:
            return victims

        boxes   = det_results[0].boxes.xyxy.cpu().numpy()
        confs   = det_results[0].boxes.conf.cpu().numpy()
        # track IDs may be None if no track assigned yet
        ids_raw = det_results[0].boxes.id
        track_ids = ids_raw.cpu().numpy().astype(int) if ids_raw is not None else list(range(len(boxes)))
        
        # Keypoints are extracted simultaneously with the track
        kpts_list = det_results[0].keypoints.data.cpu().numpy() if det_results[0].keypoints is not None else [None] * len(boxes)

        h_img, w_img = image.shape[:2]

        for i, box in enumerate(boxes):
            x1, y1, x2, y2 = map(int, box)
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w_img, x2), min(h_img, y2)
            w, h   = x2 - x1, y2 - y1

            if w < 10 or h < 10:
                continue

            pose = "unknown"
            kpts = kpts_list[i] if i < len(kpts_list) else None

            if kpts is not None:
                try:
                    # Offset absolute image keypoints to be relative to the bounding box
                    # The ML classifier was trained on crops, so it expects (0,0) at the top-left of the box.
                    rel_kpts = kpts.copy()
                    # Only offset valid keypoints (confidence > 0)
                    valid_mask = rel_kpts[:, 2] > 0.0
                    rel_kpts[valid_mask, 0] -= x1
                    rel_kpts[valid_mask, 1] -= y1
                    
                    pose = self._classify_pose(rel_kpts, w, h)
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
    # POSE CLASSIFICATION — ML-first with heuristic fallback
    # --------------------------------------------------
    def _classify_pose(self, kpts, w, h) -> str:
        """Classify pose using ML/Heuristic hybrid approach.
        
        The ML model was trained on strictly top-down synthetic data, which 
        leads to low confidence / incorrect predictions on isometric views.
        We combine ML probabilities with aspect-ratio heuristics.
        """
        pose_ml = "unknown"
        prob_ml = 0.0
        
        # Try ML classifier first
        if self.pose_classifier.available:
            try:
                probs = self.pose_classifier.predict_proba(kpts, float(w), float(h))
                if probs:
                    pose_ml = max(probs, key=probs.get)
                    prob_ml = probs[pose_ml]
            except Exception:
                pass

        # Fallback: heuristic
        pose_he = self._infer_pose_heuristic(kpts, w, h)
        
        # Bounding box aspect ratio as a sanity check
        aspect = w / max(h, 1.0)
        
        # Rule 1: Horizontally long boxes are almost certainly lying or sitting
        if aspect > 1.35:
            return "lying"
            
        # Rule 2: Vertically tall boxes are very likely standing, or maybe sitting. 
        # Overrule the ML if it weakly predicts "lying" for a vertical box.
        if aspect < 0.6 and pose_ml == "lying":
            return pose_he # Fallback to heuristic standing/sitting

        # Rule 3: If ML is reasonably confident, trust it
        if prob_ml >= 0.55 and pose_ml != "unknown":
            return pose_ml
            
        # Rule 4: If ML is weak, trust the heuristic fallback
        return pose_he

    # --------------------------------------------------
    # HEURISTIC FALLBACK (Birds-Eye Euclidean Extension)
    # --------------------------------------------------
    def _infer_pose_heuristic(self, kpts, w, h):
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
        scale = math.sqrt(w**2 + h**2)
        if scale == 0: scale = 0.001

        # 2. Euclidean Physical Extensions
        torso = math.sqrt((neck_x - pelv_x)**2 + (neck_y - pelv_y)**2)
        legs  = math.sqrt((pelv_x - ank_x)**2  + (pelv_y - ank_y)**2)

        # 3. Total Extension Ratio
        extension = (torso + legs) / scale
        aspect = w / h if h > 0 else 1.0

        # 4. Angled / Aerial Heuristics
        # A. If box is significantly wider than tall, they are lying down.
        if aspect > 1.35:
            return "lying"
            
        # B. If box is tall (aspect < 0.8), they are likely standing. 
        if aspect < 0.8:
            return "standing"

        # C. For square-ish boxes, rely on extension.
        # If looking top-down at a standing person, torso+legs length is very small (foreshortening).
        # If lying down, extension is close to 1.0.
        if extension < 0.35:
            return "standing"

        if extension > 0.6:
            return "lying"

        return "sitting"
