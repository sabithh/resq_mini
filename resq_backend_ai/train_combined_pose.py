"""
train_combined_pose.py
Train the pose classifier on C2A real data + synthetic data combined.
"""
import json
import sys
import pickle
from pathlib import Path
from collections import Counter

import numpy as np
import cv2

C2A_POSE_MAP = {0: "sitting", 1: "sitting", 2: "lying", 3: "sitting", 4: "standing"}

BASE_DIR = Path(__file__).parent
C2A_ROOT = BASE_DIR / "data" / "C2A"
IMAGES_DIR = C2A_ROOT / "C2A_Dataset" / "new_dataset3"
ANNOTATIONS_DIR = C2A_ROOT / "Coco_annotation_pose"


def load_c2a_annotations():
    all_anns, img_lookup = [], {}
    for split in ["train", "val"]:
        f = ANNOTATIONS_DIR / f"{split}_annotations_with_pose_information.json"
        if not f.exists():
            continue
        data = json.load(open(f))
        for img in data.get("images", []):
            img_lookup[img["id"]] = {"file_name": img["file_name"], "split": split}
        for ann in data.get("annotations", []):
            pose_id = ann.get("pose")
            if pose_id is not None and pose_id in C2A_POSE_MAP:
                all_anns.append({"image_id": ann["image_id"], "bbox": ann["bbox"], "pose": C2A_POSE_MAP[pose_id]})
    return all_anns, img_lookup


def compute_iou(b1, b2):
    x1, y1 = max(b1[0], b2[0]), max(b1[1], b2[1])
    x2, y2 = min(b1[2], b2[2]), min(b1[3], b2[3])
    inter = max(0, x2-x1) * max(0, y2-y1)
    union = (b1[2]-b1[0])*(b1[3]-b1[1]) + (b2[2]-b2[0])*(b2[3]-b2[1]) - inter
    return inter / union if union > 0 else 0


def extract_c2a_features(anns, img_lookup, max_images=500):
    from ultralytics import YOLO
    from pose_classifier import PoseClassifier

    model = YOLO("yolov8m-pose.pt")
    img_anns = {}
    for a in anns:
        img_anns.setdefault(a["image_id"], []).append(a)

    features, labels, skipped = [], [], 0
    ids = list(img_anns.keys())[:max_images]
    print(f"[c2a] Processing {len(ids)} images...")

    for img_id in ids:
        info = img_lookup.get(img_id)
        if not info:
            skipped += 1; continue

        img_path = None
        for p in [IMAGES_DIR / info["split"] / "images" / info["file_name"],
                   IMAGES_DIR / "images" / info["file_name"]]:
            if p.exists():
                img_path = p; break
        if not img_path:
            skipped += 1; continue

        img = cv2.imread(str(img_path))
        if img is None:
            skipped += 1; continue

        results = model(img, verbose=False)
        if not results or results[0].keypoints is None or results[0].boxes is None:
            skipped += 1; continue

        kpts_data = results[0].keypoints.data.cpu().numpy()
        det_boxes = results[0].boxes.xyxy.cpu().numpy()

        for ann in img_anns[img_id]:
            cx, cy, cw, ch = ann["bbox"]
            c2a_box = [cx, cy, cx+cw, cy+ch]
            best_iou, best_idx = 0, -1
            for di in range(len(det_boxes)):
                iou = compute_iou(c2a_box, det_boxes[di])
                if iou > best_iou:
                    best_iou, best_idx = iou, di
            if best_idx >= 0 and best_iou > 0.2:
                kpts = kpts_data[best_idx] if kpts_data.ndim == 3 else kpts_data
                x1, y1, x2, y2 = det_boxes[best_idx]
                feat = PoseClassifier.extract_geometric_features(kpts, float(x2-x1), float(y2-y1))
                if feat is not None:
                    features.append(feat.astype(np.float64))
                    labels.append(ann["pose"])

    print(f"[c2a] Extracted {len(features)} real samples")
    return features, labels


def generate_synthetic(n=2000):
    from train_pose_classifier import generate_synthetic_data
    X, y = generate_synthetic_data(n)
    return [X[i] for i in range(len(X))], list(y)


if __name__ == "__main__":
    print("=" * 60)
    print("  ResQ — Combined C2A + Synthetic Pose Training")
    print("=" * 60)

    # 1. Get C2A real data
    anns, img_lookup = load_c2a_annotations()
    print(f"[c2a] {len(anns)} annotations, distribution: {dict(Counter(a['pose'] for a in anns))}")
    c2a_feat, c2a_lab = extract_c2a_features(anns, img_lookup, max_images=3000)

    # 2. Generate synthetic data
    print("\n[synthetic] Generating 1500 synthetic samples...")
    syn_feat, syn_lab = generate_synthetic(1500)

    # 3. Combine
    all_feat = c2a_feat + syn_feat
    all_lab = c2a_lab + syn_lab

    X = np.stack(all_feat).astype(np.float64)
    y = np.array(all_lab)

    print(f"\n[combined] Total: {X.shape[0]} samples")
    print(f"[combined] Distribution: {dict(Counter(y))}")
    print(f"[combined] Real C2A: {len(c2a_feat)}, Synthetic: {len(syn_feat)}")

    # 4. Train
    from sklearn.model_selection import train_test_split
    from sklearn.preprocessing import StandardScaler
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics import classification_report, accuracy_score

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

    scaler = StandardScaler()
    X_train = scaler.fit_transform(X_train)
    X_test = scaler.transform(X_test)

    clf = RandomForestClassifier(n_estimators=300, max_depth=25, min_samples_split=3,
                                  min_samples_leaf=2, random_state=42, n_jobs=-1, verbose=1)
    print("\n[train] Training RandomForest...")
    clf.fit(X_train, y_train)

    y_pred = clf.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    print(f"\n[train] ✅ Accuracy: {acc:.4f}")
    print("\n" + classification_report(y_test, y_pred))

    # 5. Save
    out = BASE_DIR / "pose_classifier.pkl"
    with open(out, "wb") as f:
        pickle.dump({"model": clf, "scaler": scaler}, f)
    print(f"\n[train] Model saved → {out}")
    print("✅ Pose classifier updated with real C2A + synthetic data!")
