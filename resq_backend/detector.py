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
        effective_conf = self.conf if conf is None else conf

        # Run Pose Model for People (Class 0)
        # This guarantees we get high-quality person detection (including lying down)
        # and native keypoint extraction in a single pass.
        pose_results = self.pose_model.track(
            image,
            conf=effective_conf,
            persist=True,
            tracker="bytetrack.yaml",
            verbose=False,
            imgsz=1280,
            classes=[0]  # Only people
        )

        # Run Detection Model for Wounds (Class 1)
        # This catches our custom wound annotations without interfering with person tracking.
        det_results = self.detector.track(
            image,
            conf=effective_conf,
            persist=True,
            tracker="bytetrack.yaml",
            verbose=False,
            imgsz=1280,
            classes=[1]  # Only wounds
        )

        h_img, w_img = image.shape[:2]

        # 1. Process People & Poses
        if pose_results and pose_results[0].boxes is not None:
            boxes = pose_results[0].boxes.xyxy.cpu().numpy()
            confs = pose_results[0].boxes.conf.cpu().numpy()
            ids_raw = pose_results[0].boxes.id
            track_ids = ids_raw.cpu().numpy().astype(int) if ids_raw is not None else list(range(len(boxes)))
            
            kpts_list = pose_results[0].keypoints.data.cpu().numpy() if (hasattr(pose_results[0], 'keypoints') and pose_results[0].keypoints is not None) else [None] * len(boxes)

            for i, box in enumerate(boxes):
                x1, y1, x2, y2 = map(int, box)
                x1, y1 = max(0, x1), max(0, y1)
                x2, y2 = min(w_img, x2), min(h_img, y2)
                w, h = x2 - x1, y2 - y1

                if w < 10 or h < 10:
                    continue

                pose = "unknown"
                pose_confidence = 0.0
                kpts = kpts_list[i] if i < len(kpts_list) else None

                if kpts is not None and len(kpts) > 0:
                    try:
                        # Offset absolute image keypoints to be relative to the bounding box
                        rel_kpts = kpts.copy()
                        valid_mask = rel_kpts[:, 2] > 0.0
                        rel_kpts[valid_mask, 0] -= x1
                        rel_kpts[valid_mask, 1] -= y1

                        pose, pose_confidence = self._classify_pose(rel_kpts, w, h)
                    except Exception:
                        pass
                else:
                    aspect = w / max(h, 1.0)
                    if aspect > 1.2:
                        pose = "lying"
                    elif aspect < 0.8:
                        pose = "standing"

                victims.append({
                    "id": int(track_ids[i]),
                    "confidence": round(float(confs[i]), 3),
                    "bbox_xyxy": [x1, y1, x2, y2],
                    "center": [x1 + w // 2, y1 + h // 2],
                    "area": w * h,
                    "aspect_ratio": round(w / h, 3) if h > 0 else 0.0,
                    "pose": pose,
                    "pose_confidence": round(float(pose_confidence), 3)
                })

        # 2. Process Wounds
        if det_results and det_results[0].boxes is not None:
            boxes = det_results[0].boxes.xyxy.cpu().numpy()
            confs = det_results[0].boxes.conf.cpu().numpy()
            ids_raw = det_results[0].boxes.id
            # Offset wound IDs by 10000 so they don't collide with person IDs in ByteTrack
            track_ids = (ids_raw.cpu().numpy().astype(int) + 10000) if ids_raw is not None else [x + 10000 for x in range(len(boxes))]

            for i, box in enumerate(boxes):
                x1, y1, x2, y2 = map(int, box)
                x1, y1 = max(0, x1), max(0, y1)
                x2, y2 = min(w_img, x2), min(h_img, y2)
                w, h = x2 - x1, y2 - y1

                if w < 10 or h < 10:
                    continue

                victims.append({
                    "id": int(track_ids[i]), 
                    "confidence": round(float(confs[i]), 3),
                    "bbox_xyxy": [x1, y1, x2, y2],
                    "center": [x1 + w // 2, y1 + h // 2],
                    "area": w * h,
                    "aspect_ratio": round(w / h, 3) if h > 0 else 0.0,
                    "pose": "WOUND",
                    "pose_confidence": 1.0
                })

        return victims

    # --------------------------------------------------
    # POSE CLASSIFICATION — ML-first with heuristic fallback
    # --------------------------------------------------
    def _fallback_aspect(self, w, h):
        aspect = w / max(h, 1.0)
        if aspect > 1.3: return "lying"
        if aspect < 0.8: return "standing"
        return "sitting"

    def _classify_pose(self, kpts, w, h) -> tuple[str, float]:
        """Classify pose using keypoint geometry (Y coordinates, angles)."""
        if kpts is None or len(kpts) == 0:
            return self._fallback_aspect(w, h), 0.2
            
        kpts = np.asarray(kpts)
        if kpts.ndim == 3: kpts = kpts[0]
        if kpts.shape[0] < 17:
            return self._fallback_aspect(w, h), 0.2

        # ML-first prediction when trained classifier is available.
        if self.pose_classifier.available:
            try:
                pred = self.pose_classifier.predict(kpts, w, h)
                if pred != "unknown":
                    probs = self.pose_classifier.predict_proba(kpts, w, h)
                    conf = float(probs.get(pred, 0.0)) if isinstance(probs, dict) else 0.0
                    return pred, conf
            except Exception:
                pass

        def get_pt(idx1, idx2):
            p1 = kpts[idx1] if kpts[idx1][2] > 0.3 else None
            p2 = kpts[idx2] if kpts[idx2][2] > 0.3 else None
            if p1 is None and p2 is None: return None
            if p1 is not None and p2 is not None:
                return ((p1[0]+p2[0])/2.0, (p1[1]+p2[1])/2.0)
            return p1[:2] if p1 is not None else p2[:2]

        neck   = get_pt(5, 6)
        pelvis = get_pt(11, 12)
        knee   = get_pt(13, 14)
        ankle  = get_pt(15, 16)
        
        aspect = w / max(h, 1.0)
        
        if not neck or not pelvis:
            return self._fallback_aspect(w, h), 0.25
            
        # Torso logic
        torso_dy = pelvis[1] - neck[1]
        torso_len = math.hypot(pelvis[0] - neck[0], torso_dy)
        if torso_len < 1.0: torso_len = 1.0
        
        # 1.0 = vertical, 0.0 = horizontal
        torso_verticality = torso_dy / torso_len  
        
        # 1. LYING
        if torso_verticality < 0.35:
            return "lying", 0.65

        # 2. SITTING vs STANDING
        leg_dy = 0
        leg_len = 0
        if ankle:
            leg_dy = ankle[1] - pelvis[1]
            leg_len = math.hypot(ankle[0] - pelvis[0], leg_dy)
        elif knee:
            leg_dy = knee[1] - pelvis[1]
            leg_len = math.hypot(knee[0] - pelvis[0], leg_dy)
            
        if leg_len > 1.0:
            leg_verticality = leg_dy / leg_len
            # Both torso and legs point clearly down
            if torso_verticality > 0.4 and leg_verticality > 0.4:
                return ("standing", 0.6) if aspect < 0.85 else ("sitting", 0.55)
            # Torso upright but legs are horizontal/tucked/pointed sideways
            elif torso_verticality > 0.4 and leg_verticality <= 0.4:
                return "sitting", 0.55
        
        # 3. Fallback without valid leg data
        if aspect < 0.85:
            return "standing", 0.5
        elif aspect > 1.1:
            if torso_verticality > 0.4:
                return "sitting", 0.45
            else:
                return "lying", 0.5

        return "sitting", 0.4
