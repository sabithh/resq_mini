"""
pose_classifier.py

ResQ — Lightweight MLP classifier for aerial pose estimation.

Classifies normalized COCO-17 keypoints into:
  standing | sitting | lying | unknown

The classifier uses scikit-learn (fast, no GPU needed for inference).
Trained by `train_pose_classifier.py`.
"""
from __future__ import annotations

import numpy as np
from typing import Optional
from pathlib import Path
import pickle

# Class labels (index = class id)
POSE_CLASSES = ["standing", "sitting", "lying", "unknown"]

# Default model path (next to this file)
_DEFAULT_MODEL_PATH = Path(__file__).parent / "pose_classifier.pkl"


class PoseClassifier:
    """Wraps a trained sklearn MLP for pose classification from keypoints."""

    def __init__(self, model_path: str = None):
        self.model = None
        self.scaler = None
        self.available = False

        path = Path(model_path) if model_path else _DEFAULT_MODEL_PATH
        if path.exists():
            try:
                with open(path, "rb") as f:
                    bundle = pickle.load(f)
                self.model  = bundle["model"]
                self.scaler = bundle.get("scaler")  # StandardScaler, may be None
                self.available = True
                print(f"[PoseClassifier] Loaded model from {path}")
            except Exception as e:
                print(f"[PoseClassifier] Failed to load model: {e}")
        else:
            print(f"[PoseClassifier] No trained model at {path} — will use heuristic fallback")

    # ── Feature extraction ──────────────────────────────

    @staticmethod
    def extract_features(kpts: np.ndarray, bbox_w: float, bbox_h: float) -> Optional[np.ndarray]:
        """Convert raw keypoints to a normalised feature vector.

        Args:
            kpts:   shape (17, 3) — x, y, confidence for 17 COCO keypoints
            bbox_w: bounding-box width (for normalisation)
            bbox_h: bounding-box height (for normalisation)

        Returns:
            1-D feature array of length 51 (17 × 3: norm_x, norm_y, conf)
            or None if keypoints are too sparse.
        """
        kpts = np.asarray(kpts, dtype=np.float32)
        if kpts.ndim == 3:
            kpts = kpts[0]

        if kpts.shape[0] < 17:
            return None

        # Count visible keypoints (confidence > threshold)
        visible = (kpts[:, 2] > 0.15).sum()
        if visible < 5:
            return None

        # Normalize x, y relative to bounding box dimensions
        scale_x = max(bbox_w, 1.0)
        scale_y = max(bbox_h, 1.0)

        features = np.zeros(51, dtype=np.float32)
        for i in range(17):
            features[i * 3]     = kpts[i, 0] / scale_x   # normalised x
            features[i * 3 + 1] = kpts[i, 1] / scale_y   # normalised y
            features[i * 3 + 2] = kpts[i, 2]              # confidence (already 0-1)

        # Add derived geometric features
        # (appended after the 51 base features when training — kept here for compat)
        return features

    @staticmethod
    def extract_geometric_features(kpts: np.ndarray, bbox_w: float, bbox_h: float) -> Optional[np.ndarray]:
        """Extended features: base 51 + 8 geometric = 59 features total."""
        base = PoseClassifier.extract_features(kpts, bbox_w, bbox_h)
        if base is None:
            return None

        kpts = np.asarray(kpts, dtype=np.float32)
        if kpts.ndim == 3:
            kpts = kpts[0]

        import math
        scale_x = max(bbox_w, 1.0)
        scale_y = max(bbox_h, 1.0)

        # Midpoints
        def midpoint(i, j):
            return (kpts[i, :2] + kpts[j, :2]) / 2

        def dist(a, b):
            return math.sqrt((a[0] - b[0])**2 + (a[1] - b[1])**2)

        neck  = midpoint(5, 6)   # shoulders
        pelvis = midpoint(11, 12) # hips

        # Best ankle
        l_ank, r_ank = kpts[15], kpts[16]
        if l_ank[2] > 0.15 and r_ank[2] > 0.15:
            ankle = (l_ank[:2] + r_ank[:2]) / 2
        elif l_ank[2] > 0.15:
            ankle = l_ank[:2]
        elif r_ank[2] > 0.15:
            ankle = r_ank[:2]
        else:
            ankle = pelvis  # fallback

        diag = math.sqrt(bbox_w**2 + bbox_h**2)
        if diag == 0:
            diag = 1.0

        torso_len = dist(neck, pelvis) / diag
        leg_len   = dist(pelvis, ankle) / diag
        total_ext = torso_len + leg_len
        aspect    = bbox_w / max(bbox_h, 1.0)

        # Vertical spread of keypoints
        visible_mask = kpts[:, 2] > 0.15
        if visible_mask.any():
            vis_y  = kpts[visible_mask, 1]
            y_spread = (vis_y.max() - vis_y.min()) / scale_y
            vis_x  = kpts[visible_mask, 0]
            x_spread = (vis_x.max() - vis_x.min()) / scale_x
        else:
            y_spread = 0.0
            x_spread = 0.0

        # Neck-to-ankle angle from vertical
        dy = ankle[1] - neck[1]
        dx = ankle[0] - neck[0]
        angle_from_vertical = abs(math.atan2(dx, dy + 1e-6)) / math.pi  # 0 = vertical, 0.5 = horizontal

        geo = np.array([
            torso_len,
            leg_len,
            total_ext,
            aspect,
            y_spread,
            x_spread,
            angle_from_vertical,
            float(visible_mask.sum()) / 17.0,  # visibility ratio
        ], dtype=np.float32)

        return np.concatenate([base, geo])

    # ── Prediction ──────────────────────────────────────

    def predict(self, kpts: np.ndarray, bbox_w: float, bbox_h: float) -> str:
        """Classify pose from keypoints.

        Returns one of: 'standing', 'sitting', 'lying', 'unknown'
        """
        if not self.available:
            return "unknown"

        features = self.extract_geometric_features(kpts, bbox_w, bbox_h)
        if features is None:
            return "unknown"

        features = features.reshape(1, -1)

        if self.scaler is not None:
            features = self.scaler.transform(features)

        try:
            pred = self.model.predict(features)[0]
            if isinstance(pred, (int, np.integer)):
                return POSE_CLASSES[pred] if pred < len(POSE_CLASSES) else "unknown"
            return str(pred) if pred in POSE_CLASSES else "unknown"
        except Exception:
            return "unknown"

    def predict_proba(self, kpts: np.ndarray, bbox_w: float, bbox_h: float) -> dict:
        """Return class probabilities."""
        if not self.available:
            return {c: 0.0 for c in POSE_CLASSES}

        features = self.extract_geometric_features(kpts, bbox_w, bbox_h)
        if features is None:
            return {c: 0.0 for c in POSE_CLASSES}

        features = features.reshape(1, -1)
        if self.scaler is not None:
            features = self.scaler.transform(features)

        try:
            proba = self.model.predict_proba(features)[0]
            classes = self.model.classes_
            return {POSE_CLASSES[int(c)] if isinstance(c, (int, np.integer)) else str(c): float(p)
                    for c, p in zip(classes, proba)}
        except Exception:
            return {c: 0.0 for c in POSE_CLASSES}
