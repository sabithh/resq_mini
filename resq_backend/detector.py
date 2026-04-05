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
import cv2
from ultralytics import YOLO

from pose_classifier import PoseClassifier


class Detector:
    def __init__(self, conf: float = 0.12):
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
    def _frame_quality_metrics(self, image: np.ndarray) -> tuple[float, float, float]:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        blur_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        mean_light = float(gray.mean())
        residual = cv2.absdiff(gray, cv2.GaussianBlur(gray, (3, 3), 0))
        noise_level = float(residual.std())
        return blur_var, mean_light, noise_level

    def _enhance_blurry_frame(self, image: np.ndarray) -> np.ndarray:
        """Apply lightweight deblur-friendly enhancement before inference."""
        # 1) Unsharp mask to recover local edges on blurred people silhouettes.
        blur = cv2.GaussianBlur(image, (0, 0), 1.2)
        sharpened = cv2.addWeighted(image, 1.65, blur, -0.65, 0)

        # 2) CLAHE on luminance channel to stabilize contrast after sharpening.
        lab = cv2.cvtColor(sharpened, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=2.2, tileGridSize=(8, 8))
        l_eq = clahe.apply(l)
        merged = cv2.merge([l_eq, a, b])
        return cv2.cvtColor(merged, cv2.COLOR_LAB2BGR)

    def _adaptive_confidence(self, image: np.ndarray) -> float:
        """Lower confidence threshold for blurry/dim frames to recover missed detections."""
        blur_var, mean_light, noise_level = self._frame_quality_metrics(image)

        conf = float(self.conf)

        if blur_var < 40.0:
            conf *= 0.55
        elif blur_var < 80.0:
            conf *= 0.70

        if mean_light < 45.0:
            conf *= 0.85

        if noise_level > 22.0:
            conf *= 0.82
        elif noise_level > 14.0:
            conf *= 0.90

        return max(0.05, min(conf, float(self.conf)))

    def _adaptive_preprocess(self, image: np.ndarray) -> np.ndarray:
        blur_var, _, noise_level = self._frame_quality_metrics(image)
        out = image
        if noise_level > 16.0:
            out = cv2.fastNlMeansDenoisingColored(out, None, 7, 7, 7, 21)
        if blur_var < 70.0:
            out = self._enhance_blurry_frame(out)
        return out

    def _heuristic_pose_from_keypoints(self, kpts: np.ndarray, w: int, h: int) -> tuple[str, float]:
        """Keypoint geometry fallback that is more stable under noisy ML probabilities."""
        if kpts is None or len(kpts) == 0:
            return self._fallback_aspect(w, h), 0.2

        kpts = np.asarray(kpts)
        if kpts.ndim == 3:
            kpts = kpts[0]
        if kpts.shape[0] < 17:
            return self._fallback_aspect(w, h), 0.2

        def get_pt(idx1, idx2):
            p1 = kpts[idx1] if kpts[idx1][2] > 0.3 else None
            p2 = kpts[idx2] if kpts[idx2][2] > 0.3 else None
            if p1 is None and p2 is None:
                return None
            if p1 is not None and p2 is not None:
                return ((p1[0] + p2[0]) / 2.0, (p1[1] + p2[1]) / 2.0)
            return p1[:2] if p1 is not None else p2[:2]

        neck = get_pt(5, 6)
        pelvis = get_pt(11, 12)
        knee = get_pt(13, 14)
        ankle = get_pt(15, 16)
        aspect = w / max(h, 1.0)

        def _joint_angle(a, b, c) -> float | None:
            if a is None or b is None or c is None:
                return None
            ba = np.array([a[0] - b[0], a[1] - b[1]], dtype=float)
            bc = np.array([c[0] - b[0], c[1] - b[1]], dtype=float)
            nba = float(np.linalg.norm(ba))
            nbc = float(np.linalg.norm(bc))
            if nba < 1e-6 or nbc < 1e-6:
                return None
            cosang = float(np.dot(ba, bc) / (nba * nbc))
            cosang = max(-1.0, min(1.0, cosang))
            return float(math.degrees(math.acos(cosang)))

        if not neck or not pelvis:
            return self._fallback_aspect(w, h), 0.25

        torso_dy = pelvis[1] - neck[1]
        torso_len = math.hypot(pelvis[0] - neck[0], torso_dy)
        if torso_len < 1.0:
            torso_len = 1.0
        torso_verticality = torso_dy / torso_len

        # More conservative lying trigger: seated people leaning back should not become lying.
        if torso_verticality < 0.28:
            return "lying", 0.65

        leg_dy = 0
        leg_len = 0
        knee_angle = None
        if ankle:
            leg_dy = ankle[1] - pelvis[1]
            leg_len = math.hypot(ankle[0] - pelvis[0], leg_dy)
            if knee:
                knee_angle = _joint_angle(pelvis, knee, ankle)
        elif knee:
            leg_dy = knee[1] - pelvis[1]
            leg_len = math.hypot(knee[0] - pelvis[0], leg_dy)

        if leg_len > 1.0:
            leg_verticality = leg_dy / leg_len
            if torso_verticality > 0.4 and leg_verticality > 0.4:
                # Favor sitting for ambiguous crops unless the body is clearly narrow/upright.
                if knee_angle is not None and knee_angle < 150.0:
                    return "sitting", 0.62
                return ("standing", 0.6) if aspect < 0.72 else ("sitting", 0.58)
            if torso_verticality > 0.4 and leg_verticality <= 0.4:
                return "sitting", 0.55

        if aspect < 0.72:
            return "standing", 0.5
        if aspect > 1.1:
            if torso_verticality > 0.4:
                return "sitting", 0.45
            return "lying", 0.5
        return "sitting", 0.4

    def _iou_xyxy(self, a: List[int], b: List[int]) -> float:
        ax1, ay1, ax2, ay2 = a
        bx1, by1, bx2, by2 = b
        ix1, iy1 = max(ax1, bx1), max(ay1, by1)
        ix2, iy2 = min(ax2, bx2), min(ay2, by2)
        iw, ih = max(0, ix2 - ix1), max(0, iy2 - iy1)
        inter = iw * ih
        if inter <= 0:
            return 0.0
        area_a = max(0, ax2 - ax1) * max(0, ay2 - ay1)
        area_b = max(0, bx2 - bx1) * max(0, by2 - by1)
        denom = area_a + area_b - inter
        return float(inter / denom) if denom > 0 else 0.0

    def _infer_bleeding_visual(self, image: np.ndarray, bbox_xyxy: List[int]) -> tuple[bool, float]:
        x1, y1, x2, y2 = bbox_xyxy
        crop = image[y1:y2, x1:x2]
        if crop is None or crop.size == 0:
            return False, 0.0

        # Ignore tiny crops where color cues are unstable.
        h, w = crop.shape[:2]
        if h < 20 or w < 20:
            return False, 0.0

        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
        mask1 = cv2.inRange(hsv, (0, 70, 40), (12, 255, 255))
        mask2 = cv2.inRange(hsv, (168, 70, 40), (180, 255, 255))
        red_mask = cv2.bitwise_or(mask1, mask2)

        # Remove isolated pixels and retain contiguous stain-like regions.
        kernel = np.ones((3, 3), np.uint8)
        red_mask = cv2.morphologyEx(red_mask, cv2.MORPH_OPEN, kernel, iterations=1)
        red_mask = cv2.morphologyEx(red_mask, cv2.MORPH_CLOSE, kernel, iterations=1)

        red_ratio = float((red_mask > 0).mean())
        if red_ratio < 0.02:
            return False, min(1.0, red_ratio * 2.0)

        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats((red_mask > 0).astype(np.uint8), connectivity=8)
        comp_areas = [int(stats[i, cv2.CC_STAT_AREA]) for i in range(1, num_labels)]
        crop_area = float(h * w)
        largest_comp_ratio = (max(comp_areas) / crop_area) if comp_areas else 0.0
        medium_comp_count = sum(1 for a in comp_areas if (a / crop_area) >= 0.01)

        red_pixels = hsv[red_mask > 0]
        sat_mean = float(red_pixels[:, 1].mean()) if len(red_pixels) > 0 else 0.0
        val_mean = float(red_pixels[:, 2].mean()) if len(red_pixels) > 0 else 0.0

        # Reject patterns that usually indicate clothing/thermal palettes rather than blood-like stains.
        if red_ratio > 0.22 or largest_comp_ratio > 0.14:
            return False, min(1.0, red_ratio * 1.5)
        if sat_mean < 95.0:
            return False, min(1.0, red_ratio * 1.5)
        if val_mean > 215.0 and red_ratio > 0.06:
            return False, min(1.0, red_ratio * 1.4)

        # Prefer localized clustered red regions.
        if 0.02 <= red_ratio <= 0.14 and largest_comp_ratio <= 0.09 and medium_comp_count >= 1:
            score = min(1.0, 0.45 + red_ratio * 2.5 + min(0.2, largest_comp_ratio * 1.5))
            return True, score

        return False, min(1.0, red_ratio * 2.0)

    def detect(
        self,
        image: np.ndarray,
        conf: float = None,
        adaptive: bool = False,
        imgsz: int = 1280,
        detect_wounds: bool = True,
    ) -> List[Dict]:
        people = []
        wounds = []
        if conf is not None:
            effective_conf = conf
        elif adaptive:
            effective_conf = self._adaptive_confidence(image)
        else:
            effective_conf = self.conf

        try:
            infer_imgsz = int(imgsz)
        except (TypeError, ValueError):
            infer_imgsz = 1280
        infer_imgsz = max(320, min(infer_imgsz, 1920))

        inference_image = self._adaptive_preprocess(image) if adaptive else image
        # Run wounds at a lower threshold to recover subtle bleeding cues.
        det_conf = max(0.02, effective_conf * 0.45)

        # Run Pose Model for People (Class 0)
        # This guarantees we get high-quality person detection (including lying down)
        # and native keypoint extraction in a single pass.
        pose_results = self.pose_model.track(
            inference_image,
            conf=effective_conf,
            persist=True,
            tracker="bytetrack.yaml",
            verbose=False,
            imgsz=infer_imgsz,
            classes=[0]  # Only people
        )

        # Run Detection Model for wounds only.
        # Wounds are then associated with people as bleeding evidence.
        det_results = None
        if detect_wounds:
            det_results = self.detector.track(
                inference_image,
                conf=det_conf,
                persist=True,
                tracker="bytetrack.yaml",
                verbose=False,
                imgsz=infer_imgsz,
                classes=[1]
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

                if w < 6 or h < 6:
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
                        pose = self._fallback_aspect(w, h)
                        pose_confidence = 0.25
                else:
                    aspect = w / max(h, 1.0)
                    if aspect > 1.2:
                        pose = "lying"
                    elif aspect < 0.8:
                        pose = "standing"
                    else:
                        pose = "sitting"
                    pose_confidence = 0.35

                person_box = [x1, y1, x2, y2]
                bleeding_flag, bleeding_conf = self._infer_bleeding_visual(image, person_box)

                people.append({
                    "id": int(track_ids[i]),
                    "confidence": round(float(confs[i]), 3),
                    "bbox_xyxy": person_box,
                    "center": [x1 + w // 2, y1 + h // 2],
                    "area": w * h,
                    "aspect_ratio": round(w / h, 3) if h > 0 else 0.0,
                    "pose": pose,
                    "pose_confidence": round(float(pose_confidence), 3),
                    "bleeding": bool(bleeding_flag),
                    "bleeding_confidence": round(float(bleeding_conf), 3),
                })

        # 2. Process wounds
        if detect_wounds and det_results and det_results[0].boxes is not None:
            boxes = det_results[0].boxes.xyxy.cpu().numpy()
            confs = det_results[0].boxes.conf.cpu().numpy()
            ids_raw = det_results[0].boxes.id
            base_ids = ids_raw.cpu().numpy().astype(int) if ids_raw is not None else np.arange(len(boxes))

            for i, box in enumerate(boxes):
                x1, y1, x2, y2 = map(int, box)
                x1, y1 = max(0, x1), max(0, y1)
                x2, y2 = min(w_img, x2), min(h_img, y2)
                w, h = x2 - x1, y2 - y1

                if w < 10 or h < 10:
                    continue

                wounds.append({
                    "id": int(base_ids[i] + 10000),
                    "confidence": round(float(confs[i]), 3),
                    "bbox_xyxy": [x1, y1, x2, y2],
                    "center": [x1 + w // 2, y1 + h // 2],
                    "area": w * h,
                    "aspect_ratio": round(w / h, 3) if h > 0 else 0.0,
                    "pose": "WOUND",
                    "pose_confidence": 1.0,
                })

        # 3. Associate wounds to nearest overlapping person as bleeding evidence.
        standalone_wounds = []
        for wv in wounds:
            best_idx = -1
            best_score = 0.0
            wcx, wcy = wv["center"]
            for idx, pv in enumerate(people):
                cur_iou = self._iou_xyxy(wv["bbox_xyxy"], pv["bbox_xyxy"])
                px1, py1, px2, py2 = pv["bbox_xyxy"]
                center_inside = (px1 <= wcx <= px2 and py1 <= wcy <= py2)
                score = cur_iou + (0.2 if center_inside else 0.0)
                if score > best_score:
                    best_score = score
                    best_idx = idx

            if best_idx >= 0 and best_score >= 0.08:
                people[best_idx]["bleeding"] = True
                people[best_idx]["bleeding_confidence"] = max(
                    float(people[best_idx].get("bleeding_confidence", 0.0)),
                    float(wv.get("confidence", 0.0)),
                )
            else:
                standalone_wounds.append(wv)

        return people + standalone_wounds

    # --------------------------------------------------
    # POSE CLASSIFICATION — ML-first with heuristic fallback
    # --------------------------------------------------
    def _fallback_aspect(self, w, h):
        aspect = w / max(h, 1.0)
        if aspect > 1.3: return "lying"
        if aspect < 0.72: return "standing"
        return "sitting"

    def _classify_pose(self, kpts, w, h) -> tuple[str, float]:
        """Classify pose using keypoint geometry (Y coordinates, angles)."""
        heuristic_pose, heuristic_conf = self._heuristic_pose_from_keypoints(kpts, w, h)

        if kpts is None or len(kpts) == 0:
            return heuristic_pose, heuristic_conf

        kpts = np.asarray(kpts)
        if kpts.ndim == 3:
            kpts = kpts[0]
        if kpts.shape[0] < 17:
            return heuristic_pose, heuristic_conf

        # ML prediction when trained classifier is available, then fuse with heuristic.
        if self.pose_classifier.available:
            try:
                pred = self.pose_classifier.predict(kpts, w, h)
                if pred != "unknown":
                    probs = self.pose_classifier.predict_proba(kpts, w, h)
                    conf = float(probs.get(pred, 0.0)) if isinstance(probs, dict) else 0.0
                    margin = 1.0
                    if isinstance(probs, dict) and probs:
                        vals = sorted([float(v) for v in probs.values()], reverse=True)
                        if len(vals) >= 2:
                            margin = vals[0] - vals[1]

                    # Improve robustness by requiring stronger agreement before downgrading pose.
                    if pred == heuristic_pose:
                        return pred, max(conf, heuristic_conf)

                    # Strong anti-standing-bias rule: seated/crouched bodies are often misread as standing.
                    if pred == "standing" and heuristic_pose == "sitting":
                        if conf < 0.72 or margin < 0.22:
                            return "sitting", max(heuristic_conf, 0.56)

                    # Guard against false lying when confidence margin is weak.
                    if pred == "lying" and heuristic_pose in ["standing", "sitting"]:
                        if conf < 0.72 and margin < 0.25 and heuristic_conf >= 0.5:
                            return heuristic_pose, max(heuristic_conf, 0.52)

                    # If geometry strongly indicates lying, prefer it unless ML is very sure otherwise.
                    if heuristic_pose == "lying" and heuristic_conf >= 0.62 and conf < 0.8:
                        return "lying", heuristic_conf

                    # If classifier is very confident, trust it.
                    if conf >= 0.75:
                        return pred, conf

                    # If heuristic is stronger, prefer heuristic.
                    if heuristic_conf > conf + 0.15:
                        return heuristic_pose, heuristic_conf

                    # Moderate confidence: blend with heuristic for stability
                    blended = max(conf, heuristic_conf, 0.45)
                    return pred, blended
            except Exception:
                pass

        # Apply fallback improvement: when heuristics disagree but one is much higher
        if heuristic_conf >= 0.7:
            return heuristic_pose, heuristic_conf

        return heuristic_pose, heuristic_conf
