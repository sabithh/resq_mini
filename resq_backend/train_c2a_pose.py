"""
train_c2a_pose.py

Train the pose classifier on the C2A dataset using COCO-format annotations.
C2A pose labels: 0=Bent, 1=Kneeling, 2=Lying, 3=Sitting, 4=Upright

Usage:
  python train_c2a_pose.py
"""
import json
import sys
import pickle
from pathlib import Path

import numpy as np
import cv2

# C2A pose mapping → our pose classes
C2A_POSE_MAP = {
    0: "sitting",    # Bent → sitting
    1: "sitting",    # Kneeling → sitting
    2: "lying",      # Lying → lying
    3: "sitting",    # Sitting → sitting
    4: "standing",   # Upright → standing
}

BASE_DIR = Path(__file__).parent
C2A_ROOT = BASE_DIR / "data" / "C2A"
IMAGES_DIR = C2A_ROOT / "C2A_Dataset" / "new_dataset3"
ANNOTATIONS_DIR = C2A_ROOT / "Coco_annotation_pose"


def load_annotations():
    """Load train + val annotations from COCO JSON files."""
    all_annotations = []
    image_lookup = {}

    for split in ["train", "val"]:
        ann_file = ANNOTATIONS_DIR / f"{split}_annotations_with_pose_information.json"
        if not ann_file.exists():
            print(f"[c2a] Skipping {ann_file} (not found)")
            continue

        with open(ann_file, "r") as f:
            data = json.load(f)

        # Build image id → filename map
        for img in data.get("images", []):
            image_lookup[img["id"]] = {
                "file_name": img["file_name"],
                "split": split,
            }

        for ann in data.get("annotations", []):
            pose_id = ann.get("pose")
            if pose_id is None or pose_id not in C2A_POSE_MAP:
                continue

            all_annotations.append({
                "image_id": ann["image_id"],
                "bbox": ann["bbox"],  # COCO format: [x, y, w, h]
                "pose": C2A_POSE_MAP[pose_id],
            })

    return all_annotations, image_lookup


def extract_features(annotations, image_lookup, max_images=500):
    """Run YOLOv8-pose on C2A images and extract keypoint features."""
    from ultralytics import YOLO
    from pose_classifier import PoseClassifier

    pose_model_path = "yolov8m-pose.pt"
    print(f"[c2a] Loading pose model: {pose_model_path}")
    model = YOLO(pose_model_path)

    # Group annotations by image
    img_anns = {}
    for ann in annotations:
        img_id = ann["image_id"]
        if img_id not in img_anns:
            img_anns[img_id] = []
        img_anns[img_id].append(ann)

    features = []
    labels = []
    skipped = 0
    processed = 0

    # Limit images for speed
    image_ids = list(img_anns.keys())[:max_images]
    print(f"[c2a] Processing {len(image_ids)} images (of {len(img_anns)} total)...")

    for img_id in image_ids:
        img_info = image_lookup.get(img_id)
        if img_info is None:
            skipped += 1
            continue

        fname = img_info["file_name"]
        split = img_info["split"]

        # Try finding the image in various locations
        candidates = [
            IMAGES_DIR / split / "images" / fname,
            IMAGES_DIR / "images" / fname,
            IMAGES_DIR / fname,
        ]
        
        img_path = None
        for c in candidates:
            if c.exists():
                img_path = c
                break

        if img_path is None:
            skipped += 1
            continue

        img = cv2.imread(str(img_path))
        if img is None:
            skipped += 1
            continue

        # Run pose estimation
        results = model(img, verbose=False)
        if not results or results[0].keypoints is None:
            skipped += 1
            continue

        kpts_data = results[0].keypoints.data.cpu().numpy()
        boxes = results[0].boxes

        if boxes is None or len(boxes) == 0:
            skipped += 1
            continue

        det_boxes = boxes.xyxy.cpu().numpy()

        # Match C2A annotations to YOLO detections by IOU
        for ann in img_anns[img_id]:
            cx, cy, cw, ch = ann["bbox"]  # COCO: x, y, w, h
            c2a_box = [cx, cy, cx + cw, cy + ch]

            # Find best matching detection
            best_iou = 0
            best_idx = -1
            for di in range(len(det_boxes)):
                iou = compute_iou(c2a_box, det_boxes[di])
                if iou > best_iou:
                    best_iou = iou
                    best_idx = di

            if best_idx >= 0 and best_iou > 0.3:
                kpts = kpts_data[best_idx] if kpts_data.ndim == 3 else kpts_data
                x1, y1, x2, y2 = det_boxes[best_idx]
                bbox_w = float(x2 - x1)
                bbox_h = float(y2 - y1)

                feat = PoseClassifier.extract_geometric_features(kpts, bbox_w, bbox_h)
                if feat is not None:
                    features.append(feat.astype(np.float64))
                    labels.append(ann["pose"])
                else:
                    skipped += 1
            else:
                skipped += 1

        processed += 1
        if processed % 50 == 0:
            print(f"  [{processed}/{len(image_ids)}] samples: {len(features)}, skipped: {skipped}")

    print(f"[c2a] Done! {len(features)} samples, {skipped} skipped")
    return features, labels


def compute_iou(box1, box2):
    """Compute IoU between two [x1,y1,x2,y2] boxes."""
    x1 = max(box1[0], box2[0])
    y1 = max(box1[1], box2[1])
    x2 = min(box1[2], box2[2])
    y2 = min(box1[3], box2[3])

    inter = max(0, x2 - x1) * max(0, y2 - y1)
    area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
    area2 = (box2[2] - box2[0]) * (box2[3] - box2[1])
    union = area1 + area2 - inter

    return inter / union if union > 0 else 0


def train_and_save(features, labels):
    """Train RandomForest on extracted features and save."""
    from sklearn.model_selection import train_test_split
    from sklearn.preprocessing import StandardScaler
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics import classification_report, accuracy_score

    X = np.stack(features).astype(np.float64)
    y = np.array(labels)

    print(f"\n[train] Dataset: {X.shape}")
    print(f"[train] Classes: {np.unique(y, return_counts=True)}")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    scaler = StandardScaler()
    X_train = scaler.fit_transform(X_train)
    X_test = scaler.transform(X_test)

    clf = RandomForestClassifier(
        n_estimators=200, max_depth=20,
        min_samples_split=5, min_samples_leaf=2,
        random_state=42, n_jobs=-1, verbose=1
    )

    print("\n[train] Training RandomForest...")
    clf.fit(X_train, y_train)

    y_pred = clf.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    print(f"\n[train] ✅ Accuracy: {acc:.4f}")
    print("\n" + classification_report(y_test, y_pred))

    # Save
    out = BASE_DIR / "pose_classifier.pkl"
    with open(out, "wb") as f:
        pickle.dump({"model": clf, "scaler": scaler}, f)
    print(f"[train] Model saved → {out}")


if __name__ == "__main__":
    print("=" * 60)
    print("  ResQ — C2A Pose Classifier Training")
    print("=" * 60)

    anns, img_lookup = load_annotations()
    print(f"[c2a] {len(anns)} annotations loaded, {len(img_lookup)} images")

    # Count pose distribution
    from collections import Counter
    pose_dist = Counter(a["pose"] for a in anns)
    print(f"[c2a] Pose distribution: {dict(pose_dist)}")

    features, labels = extract_features(anns, img_lookup, max_images=300)

    if len(features) < 10:
        print("[c2a] ERROR: Too few samples extracted. Check image paths.")
        sys.exit(1)

    train_and_save(features, labels)
    print("\n✅ Done! pose_classifier.pkl is updated with real C2A data.")
