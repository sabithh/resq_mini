"""
train_pose_classifier.py

ResQ — Train the pose classifier on aerial pose data.

Workflow:
  1. Collect images with known poses (lying, standing, sitting)
  2. Run YOLOv8-pose to extract keypoints for each person
  3. Map each detection to ground-truth pose label
  4. Normalize keypoints → feature vectors
  5. Train a scikit-learn MLP classifier
  6. Save as pose_classifier.pkl

Data Folder Structure (expected):
  data/pose_dataset/
    lying/        ← images of people lying down (aerial view)
    standing/     ← images of people standing (aerial view)
    sitting/      ← images of people sitting (aerial view)

Each folder contains .jpg/.png images where the PRIMARY person in the
image has the pose indicated by the folder name.

Usage:
  python train_pose_classifier.py --data data/pose_dataset
  python train_pose_classifier.py --data data/pose_dataset --test-split 0.2

For C2A dataset integration:
  python train_pose_classifier.py --c2a-dir path/to/c2a --c2a-labels path/to/labels.csv
"""

import argparse
import sys
import pickle
from pathlib import Path

import numpy as np
import cv2


def collect_keypoints_from_folders(data_dir: str, pose_model_path: str = "yolov8m-pose.pt"):
    """Walk through pose-labeled folders, run YOLOv8-pose, extract features."""
    from ultralytics import YOLO
    from pose_classifier import PoseClassifier, POSE_CLASSES

    data_path = Path(data_dir)
    model = YOLO(pose_model_path)

    features_list = []
    labels_list   = []
    skipped       = 0

    for pose_label in ["standing", "sitting", "lying"]:
        folder = data_path / pose_label
        if not folder.exists():
            print(f"[train] Skipping missing folder: {folder}")
            continue

        images = list(folder.glob("*.jpg")) + list(folder.glob("*.png")) + list(folder.glob("*.jpeg"))
        print(f"[train] {pose_label}: {len(images)} images found")

        for img_path in images:
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
            boxes     = results[0].boxes

            if boxes is None or len(boxes) == 0:
                skipped += 1
                continue

            # Use the largest (most prominent) person detection
            box_areas = []
            for b in boxes.xyxy.cpu().numpy():
                x1, y1, x2, y2 = b
                box_areas.append((x2 - x1) * (y2 - y1))

            best_idx = np.argmax(box_areas)
            kpts = kpts_data[best_idx] if kpts_data.ndim == 3 else kpts_data

            x1, y1, x2, y2 = boxes.xyxy.cpu().numpy()[best_idx]
            bbox_w = x2 - x1
            bbox_h = y2 - y1

            feat = PoseClassifier.extract_geometric_features(kpts, bbox_w, bbox_h)
            if feat is None:
                skipped += 1
                continue

            features_list.append(feat)
            labels_list.append(pose_label)

    print(f"[train] Total samples: {len(features_list)}, skipped: {skipped}")
    return np.array(features_list), np.array(labels_list)


def collect_from_c2a(c2a_dir: str, c2a_labels: str, pose_model_path: str = "yolov8m-pose.pt"):
    """Extract pose features from C2A dataset using annotation labels.

    C2A annotations map poses: bent, kneeling, lying, sitting, upright
    We remap: bent/kneeling → sitting, upright → standing, lying → lying
    """
    from ultralytics import YOLO
    from pose_classifier import PoseClassifier
    import csv

    pose_map = {
        "upright":  "standing",
        "bent":     "sitting",
        "kneeling": "sitting",
        "sitting":  "sitting",
        "lying":    "lying",
    }

    model = YOLO(pose_model_path)
    c2a_path = Path(c2a_dir)

    features_list = []
    labels_list   = []
    skipped       = 0

    # Read label CSV (expected: filename, pose_label)
    label_lookup = {}
    with open(c2a_labels, "r") as f:
        reader = csv.reader(f)
        next(reader, None)  # skip header
        for row in reader:
            if len(row) >= 2:
                fname, pose = row[0].strip(), row[1].strip().lower()
                if pose in pose_map:
                    label_lookup[fname] = pose_map[pose]

    print(f"[train/c2a] {len(label_lookup)} labeled images loaded")

    for fname, label in label_lookup.items():
        img_path = c2a_path / fname
        if not img_path.exists():
            # Try common subdirectories
            for sub in ["images", "train", "val"]:
                candidate = c2a_path / sub / fname
                if candidate.exists():
                    img_path = candidate
                    break

        if not img_path.exists():
            skipped += 1
            continue

        img = cv2.imread(str(img_path))
        if img is None:
            skipped += 1
            continue

        results = model(img, verbose=False)
        if not results or results[0].keypoints is None:
            skipped += 1
            continue

        kpts_data = results[0].keypoints.data.cpu().numpy()
        boxes = results[0].boxes

        if boxes is None or len(boxes) == 0:
            skipped += 1
            continue

        # Process all detected persons
        for idx in range(len(boxes)):
            kpts = kpts_data[idx] if kpts_data.ndim == 3 else kpts_data
            x1, y1, x2, y2 = boxes.xyxy.cpu().numpy()[idx]
            bbox_w, bbox_h = x2 - x1, y2 - y1

            feat = PoseClassifier.extract_geometric_features(kpts, bbox_w, bbox_h)
            if feat is not None:
                features_list.append(feat)
                labels_list.append(label)
            else:
                skipped += 1

    print(f"[train/c2a] Total samples: {len(features_list)}, skipped: {skipped}")
    return np.array(features_list), np.array(labels_list)


def train_classifier(X: np.ndarray, y: np.ndarray, test_split: float = 0.2):
    """Train a scikit-learn classifier on the extracted features."""
    from sklearn.model_selection import train_test_split
    from sklearn.preprocessing import StandardScaler
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics import classification_report, accuracy_score

    # Ensure float64 for sklearn compatibility
    X = np.asarray(X, dtype=np.float64)

    print(f"\n[train] Dataset shape: {X.shape}")
    print(f"[train] Classes: {np.unique(y, return_counts=True)}")

    # Split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_split, random_state=42, stratify=y
    )

    # Scale (helps with some classifiers, doesn't hurt RF)
    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s  = scaler.transform(X_test)

    # Train Random Forest (robust, fast, no numpy casting issues)
    clf = RandomForestClassifier(
        n_estimators=200,
        max_depth=20,
        min_samples_split=5,
        min_samples_leaf=2,
        random_state=42,
        n_jobs=-1,
        verbose=1,
    )

    print("\n[train] Training Random Forest classifier...")
    clf.fit(X_train_s, y_train)

    # Evaluate
    y_pred = clf.predict(X_test_s)
    acc = accuracy_score(y_test, y_pred)
    print(f"\n[train] ✅ Test Accuracy: {acc:.4f}")
    print("\n" + classification_report(y_test, y_pred))

    return clf, scaler


def save_model(clf, scaler, output_path: str = None):
    """Bundle model + scaler into a pickle file."""
    if output_path is None:
        output_path = str(Path(__file__).parent / "pose_classifier.pkl")

    bundle = {"model": clf, "scaler": scaler}
    with open(output_path, "wb") as f:
        pickle.dump(bundle, f)

    print(f"[train] Model saved → {output_path}")


def generate_synthetic_data(n_samples: int = 2000):
    """Generate synthetic keypoint data for bootstrapping when no real dataset is available.

    Creates realistic keypoint distributions for standing, sitting, and lying poses
    as seen from an aerial/overhead drone camera. This allows the classifier to work
    out of the box while real data is being collected.
    """
    from pose_classifier import PoseClassifier

    rng = np.random.default_rng(42)
    features = []
    labels   = []

    # COCO keypoint order:
    # 0:nose 1:l_eye 2:r_eye 3:l_ear 4:r_ear
    # 5:l_shoulder 6:r_shoulder 7:l_elbow 8:r_elbow
    # 9:l_wrist 10:r_wrist 11:l_hip 12:r_hip
    # 13:l_knee 14:r_knee 15:l_ankle 16:r_ankle

    for _ in range(n_samples):
        pose = rng.choice(["standing", "sitting", "lying"])

        # Base bounding box size (pixels)
        if pose == "standing":
            # From overhead: person is compact, roughly equal w/h or taller
            bbox_w = rng.uniform(40, 100)
            bbox_h = rng.uniform(60, 160)

            # Keypoints clustered vertically
            cx, cy = bbox_w / 2, bbox_h / 2
            kpts = np.zeros((17, 3), dtype=np.float32)

            # Head at top
            kpts[0] = [cx + rng.normal(0, 3), cy - bbox_h * 0.35 + rng.normal(0, 3), rng.uniform(0.5, 0.95)]
            kpts[1] = [cx - 3 + rng.normal(0, 2), cy - bbox_h * 0.37, rng.uniform(0.3, 0.9)]
            kpts[2] = [cx + 3 + rng.normal(0, 2), cy - bbox_h * 0.37, rng.uniform(0.3, 0.9)]
            kpts[3] = [cx - 6, cy - bbox_h * 0.33, rng.uniform(0.2, 0.7)]
            kpts[4] = [cx + 6, cy - bbox_h * 0.33, rng.uniform(0.2, 0.7)]

            # Shoulders
            shoulder_spread = rng.uniform(10, 25)
            kpts[5] = [cx - shoulder_spread / 2, cy - bbox_h * 0.2, rng.uniform(0.6, 0.95)]
            kpts[6] = [cx + shoulder_spread / 2, cy - bbox_h * 0.2, rng.uniform(0.6, 0.95)]

            # Elbows
            kpts[7] = [cx - shoulder_spread * 0.7, cy - bbox_h * 0.05, rng.uniform(0.4, 0.9)]
            kpts[8] = [cx + shoulder_spread * 0.7, cy - bbox_h * 0.05, rng.uniform(0.4, 0.9)]

            # Wrists
            kpts[9]  = [cx - shoulder_spread * 0.6, cy + bbox_h * 0.05, rng.uniform(0.3, 0.85)]
            kpts[10] = [cx + shoulder_spread * 0.6, cy + bbox_h * 0.05, rng.uniform(0.3, 0.85)]

            # Hips
            hip_spread = rng.uniform(8, 18)
            kpts[11] = [cx - hip_spread / 2, cy + bbox_h * 0.1, rng.uniform(0.5, 0.9)]
            kpts[12] = [cx + hip_spread / 2, cy + bbox_h * 0.1, rng.uniform(0.5, 0.9)]

            # Knees
            kpts[13] = [cx - hip_spread * 0.4, cy + bbox_h * 0.25, rng.uniform(0.4, 0.9)]
            kpts[14] = [cx + hip_spread * 0.4, cy + bbox_h * 0.25, rng.uniform(0.4, 0.9)]

            # Ankles
            kpts[15] = [cx - hip_spread * 0.3, cy + bbox_h * 0.38, rng.uniform(0.3, 0.85)]
            kpts[16] = [cx + hip_spread * 0.3, cy + bbox_h * 0.38, rng.uniform(0.3, 0.85)]

        elif pose == "lying":
            # From overhead: person is spread out horizontally, wide bbox
            bbox_w = rng.uniform(100, 250)
            bbox_h = rng.uniform(40, 100)

            cx, cy = bbox_w / 2, bbox_h / 2
            kpts = np.zeros((17, 3), dtype=np.float32)

            # Body stretched horizontally
            direction = rng.choice([-1, 1])  # left or right

            # Head at one end
            kpts[0] = [cx - direction * bbox_w * 0.35, cy + rng.normal(0, 5), rng.uniform(0.4, 0.9)]
            kpts[1] = [cx - direction * bbox_w * 0.37, cy - 3, rng.uniform(0.2, 0.8)]
            kpts[2] = [cx - direction * bbox_w * 0.37, cy + 3, rng.uniform(0.2, 0.8)]
            kpts[3] = [cx - direction * bbox_w * 0.33, cy - 5, rng.uniform(0.1, 0.6)]
            kpts[4] = [cx - direction * bbox_w * 0.33, cy + 5, rng.uniform(0.1, 0.6)]

            # Shoulders
            kpts[5] = [cx - direction * bbox_w * 0.2, cy - rng.uniform(5, 15), rng.uniform(0.5, 0.9)]
            kpts[6] = [cx - direction * bbox_w * 0.2, cy + rng.uniform(5, 15), rng.uniform(0.5, 0.9)]

            # Elbows
            kpts[7] = [cx - direction * bbox_w * 0.05, cy - rng.uniform(8, 20), rng.uniform(0.3, 0.85)]
            kpts[8] = [cx - direction * bbox_w * 0.05, cy + rng.uniform(8, 20), rng.uniform(0.3, 0.85)]

            # Wrists
            kpts[9]  = [cx + direction * bbox_w * 0.05, cy - rng.uniform(5, 15), rng.uniform(0.2, 0.8)]
            kpts[10] = [cx + direction * bbox_w * 0.05, cy + rng.uniform(5, 15), rng.uniform(0.2, 0.8)]

            # Hips
            kpts[11] = [cx + direction * bbox_w * 0.1, cy - rng.uniform(5, 12), rng.uniform(0.4, 0.9)]
            kpts[12] = [cx + direction * bbox_w * 0.1, cy + rng.uniform(5, 12), rng.uniform(0.4, 0.9)]

            # Knees
            kpts[13] = [cx + direction * bbox_w * 0.25, cy - rng.uniform(3, 10), rng.uniform(0.3, 0.85)]
            kpts[14] = [cx + direction * bbox_w * 0.25, cy + rng.uniform(3, 10), rng.uniform(0.3, 0.85)]

            # Ankles
            kpts[15] = [cx + direction * bbox_w * 0.38, cy - rng.uniform(2, 8), rng.uniform(0.2, 0.8)]
            kpts[16] = [cx + direction * bbox_w * 0.38, cy + rng.uniform(2, 8), rng.uniform(0.2, 0.8)]

            # Random 90-degree rotation to simulate vertical/diagonal lying
            if rng.choice([True, False]):
                bbox_w, bbox_h = bbox_h, bbox_w
                for i in range(17):
                    dx = kpts[i, 0] - cx
                    dy = kpts[i, 1] - cy
                    kpts[i, 0] = cx - dy
                    kpts[i, 1] = cy + dx


        elif pose == "sitting":
            # From overhead: moderate spread, knees bent closer to body
            bbox_w = rng.uniform(50, 120)
            bbox_h = rng.uniform(50, 120)

            cx, cy = bbox_w / 2, bbox_h / 2
            kpts = np.zeros((17, 3), dtype=np.float32)

            # Head
            kpts[0] = [cx + rng.normal(0, 4), cy - bbox_h * 0.25, rng.uniform(0.5, 0.9)]
            kpts[1] = [cx - 3, cy - bbox_h * 0.28, rng.uniform(0.3, 0.8)]
            kpts[2] = [cx + 3, cy - bbox_h * 0.28, rng.uniform(0.3, 0.8)]
            kpts[3] = [cx - 6, cy - bbox_h * 0.22, rng.uniform(0.2, 0.6)]
            kpts[4] = [cx + 6, cy - bbox_h * 0.22, rng.uniform(0.2, 0.6)]

            # Shoulders wider
            shoulder_spread = rng.uniform(12, 30)
            kpts[5] = [cx - shoulder_spread / 2, cy - bbox_h * 0.1, rng.uniform(0.5, 0.9)]
            kpts[6] = [cx + shoulder_spread / 2, cy - bbox_h * 0.1, rng.uniform(0.5, 0.9)]

            # Elbows bent forward
            kpts[7] = [cx - shoulder_spread * 0.8, cy + bbox_h * 0.05, rng.uniform(0.4, 0.85)]
            kpts[8] = [cx + shoulder_spread * 0.8, cy + bbox_h * 0.05, rng.uniform(0.4, 0.85)]

            # Wrists (in lap area)
            kpts[9]  = [cx - rng.uniform(5, 15), cy + bbox_h * 0.1, rng.uniform(0.3, 0.8)]
            kpts[10] = [cx + rng.uniform(5, 15), cy + bbox_h * 0.1, rng.uniform(0.3, 0.8)]

            # Hips
            kpts[11] = [cx - rng.uniform(5, 12), cy + bbox_h * 0.15, rng.uniform(0.4, 0.85)]
            kpts[12] = [cx + rng.uniform(5, 12), cy + bbox_h * 0.15, rng.uniform(0.4, 0.85)]

            # Knees bent — close to hips (sitting = compact)
            kpts[13] = [cx - rng.uniform(8, 20), cy + bbox_h * 0.2, rng.uniform(0.3, 0.8)]
            kpts[14] = [cx + rng.uniform(8, 20), cy + bbox_h * 0.2, rng.uniform(0.3, 0.8)]

            # Ankles close to body
            kpts[15] = [cx - rng.uniform(5, 15), cy + bbox_h * 0.28, rng.uniform(0.2, 0.75)]
            kpts[16] = [cx + rng.uniform(5, 15), cy + bbox_h * 0.28, rng.uniform(0.2, 0.75)]

        # Add noise to ALL keypoints
        noise = rng.normal(0, 2, kpts[:, :2].shape)
        kpts[:, :2] += noise.astype(np.float32)

        # Randomly make some keypoints invisible (simulate occlusion)
        occlude_count = rng.integers(0, 5)
        occlude_indices = rng.choice(17, size=occlude_count, replace=False)
        for idx in occlude_indices:
            kpts[idx, 2] = rng.uniform(0, 0.1)

        feat = PoseClassifier.extract_geometric_features(kpts, float(bbox_w), float(bbox_h))
        if feat is not None:
            features.append(feat.astype(np.float64))
            labels.append(pose)

    print(f"[synthetic] Generated {len(features)} synthetic samples")
    if len(features) == 0:
        return np.zeros((0, 59), dtype=np.float64), np.array([], dtype=str)
    return np.stack(features).astype(np.float64), np.array(labels)


# ── CLI ─────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(description="Train pose classifier for ResQ")

    p.add_argument("--data", default=None,
                   help="Path to pose dataset folder (lying/standing/sitting subfolders)")
    p.add_argument("--c2a-dir", default=None,
                   help="Path to C2A dataset images")
    p.add_argument("--c2a-labels", default=None,
                   help="Path to C2A labels CSV (filename, pose)")
    p.add_argument("--synthetic", action="store_true",
                   help="Generate and use synthetic training data (no real images needed)")
    p.add_argument("--synthetic-samples", type=int, default=3000,
                   help="Number of synthetic samples to generate per class")
    p.add_argument("--pose-model", default="yolov8m-pose.pt",
                   help="YOLOv8-pose model for keypoint extraction")
    p.add_argument("--test-split", type=float, default=0.2)
    p.add_argument("--output", default=None,
                   help="Output path for trained model (default: pose_classifier.pkl)")
    p.add_argument("--test", action="store_true",
                   help="Test existing model on the dataset (skip training)")

    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()

    X, y = None, None

    # Collect data from available sources
    all_X, all_y = [], []

    if args.synthetic or (args.data is None and args.c2a_dir is None):
        print("[train] Using synthetic data (use --data or --c2a-dir for real data)")
        X_syn, y_syn = generate_synthetic_data(args.synthetic_samples)
        all_X.append(X_syn)
        all_y.append(y_syn)

    if args.data:
        X_real, y_real = collect_keypoints_from_folders(args.data, args.pose_model)
        if len(X_real) > 0:
            all_X.append(X_real)
            all_y.append(y_real)

    if args.c2a_dir and args.c2a_labels:
        X_c2a, y_c2a = collect_from_c2a(args.c2a_dir, args.c2a_labels, args.pose_model)
        if len(X_c2a) > 0:
            all_X.append(X_c2a)
            all_y.append(y_c2a)

    if not all_X:
        print("[train] ERROR: No data collected. Provide --data, --c2a-dir, or --synthetic")
        sys.exit(1)

    X = np.concatenate(all_X).astype(np.float64)
    y = np.concatenate(all_y)

    if args.test:
        # Load and evaluate existing model
        from pose_classifier import PoseClassifier
        classifier = PoseClassifier(args.output)
        if not classifier.available:
            print("[test] ERROR: No model found to test")
            sys.exit(1)

        from sklearn.metrics import classification_report, accuracy_score
        from sklearn.preprocessing import StandardScaler

        preds = []
        for i in range(len(X)):
            # Reconstruct kpts from features (first 51 values)
            feat = X[i]
            # We can pass features directly through the model
            feat_reshaped = feat.reshape(1, -1)
            if classifier.scaler is not None:
                feat_reshaped = classifier.scaler.transform(feat_reshaped)
            pred = classifier.model.predict(feat_reshaped)[0]
            preds.append(pred)

        acc = accuracy_score(y, preds)
        print(f"\n[test] Accuracy: {acc:.4f}")
        print(classification_report(y, preds))
    else:
        clf, scaler = train_classifier(X, y, args.test_split)
        save_model(clf, scaler, args.output)
        print("\n[train] ✅ Pose classifier ready!  It will be auto-loaded by detector.py")
