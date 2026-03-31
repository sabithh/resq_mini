"""
Prepare an independent pose/priority labeling set.

Creates blind crop images and a GT template with empty labels so manual
annotation does not inherit model predictions.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

import cv2

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from detector import Detector


DATASET_IMAGES = BASE_DIR / "data" / "SARD" / "search-and-rescue" / "valid" / "images"
OUT_DIR = BASE_DIR / "test_reports" / "pose_eval_independent"


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare independent pose/priority labeling set")
    parser.add_argument("--target-victims", type=int, default=500, help="Target number of victims to collect")
    parser.add_argument("--max-images", type=int, default=700, help="Max images to scan")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing output files")
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    crops_dir = OUT_DIR / "crops"
    crops_dir.mkdir(parents=True, exist_ok=True)

    gt_path = OUT_DIR / "ground_truth_blind.json"
    pred_ref_path = OUT_DIR / "pred_reference_hidden.json"
    manifest_path = OUT_DIR / "manifest.json"

    if not args.overwrite and (gt_path.exists() or pred_ref_path.exists()):
        print(f"[ERROR] Output already exists in {OUT_DIR}. Use --overwrite to regenerate.")
        return 1

    all_images = sorted(DATASET_IMAGES.glob("*.jpg")) + sorted(DATASET_IMAGES.glob("*.jpeg")) + sorted(DATASET_IMAGES.glob("*.png"))
    if not all_images:
        print(f"[ERROR] No images found in {DATASET_IMAGES}")
        return 1

    random.seed(args.seed)
    random.shuffle(all_images)
    images = all_images[: args.max_images]

    detector = Detector()

    gt_entries = []
    pred_entries = []
    victim_idx = 0
    used_images = set()

    for i, img_path in enumerate(images, start=1):
        if victim_idx >= args.target_victims:
            break

        image = cv2.imread(str(img_path))
        if image is None:
            continue

        dets = detector.detect(image, adaptive=True)
        if not dets:
            continue

        h_img, w_img = image.shape[:2]
        for det in dets:
            if victim_idx >= args.target_victims:
                break

            pose = str(det.get("pose", "unknown")).lower()
            if pose == "wound":
                continue

            x1, y1, x2, y2 = [int(v) for v in det.get("bbox_xyxy", [0, 0, 0, 0])]
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w_img, x2), min(h_img, y2)
            if x2 - x1 < 12 or y2 - y1 < 12:
                continue

            crop = image[y1:y2, x1:x2]
            if crop.size == 0:
                continue

            victim_idx += 1
            used_images.add(img_path.name)
            crop_name = f"victim_{victim_idx:04d}.jpg"
            cv2.imwrite(str(crops_dir / crop_name), crop)

            # Blind annotation entry: labels intentionally empty.
            gt_entries.append({
                "entry_id": victim_idx,
                "crop_file": crop_name,
                "image_name": img_path.name,
                "bbox_xyxy": [x1, y1, x2, y2],
                "gt_pose": "",
                "gt_priority": "",
                "notes": "",
            })

            # Hidden prediction reference for auditing/debug only.
            pred_entries.append({
                "entry_id": victim_idx,
                "image_name": img_path.name,
                "bbox_xyxy": [x1, y1, x2, y2],
                "pred_pose": det.get("pose", "unknown"),
                "pred_pose_confidence": float(det.get("pose_confidence", 0.0) or 0.0),
                "pred_detector_confidence": float(det.get("confidence", 0.0) or 0.0),
            })

        if i % 50 == 0:
            print(f"[Progress] scanned_images={i}, victims_collected={victim_idx}")

    gt_path.write_text(json.dumps(gt_entries, indent=2), encoding="utf-8")
    pred_ref_path.write_text(json.dumps(pred_entries, indent=2), encoding="utf-8")

    manifest = {
        "dataset_images_total": len(all_images),
        "images_scanned": min(len(images), i if 'i' in locals() else 0),
        "images_with_selected_victims": len(used_images),
        "victims_collected": victim_idx,
        "target_victims": args.target_victims,
        "seed": args.seed,
        "paths": {
            "crops_dir": str(crops_dir),
            "ground_truth_blind": str(gt_path),
            "pred_reference_hidden": str(pred_ref_path),
        },
        "annotation_instructions": [
            "Fill gt_pose with one of: standing, sitting, lying.",
            "Fill gt_priority with one of: LOW, MEDIUM, HIGH.",
            "Do not open pred_reference_hidden.json until after labeling is complete.",
        ],
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"[DONE] Victims collected: {victim_idx}")
    print(f"[DONE] Crops: {crops_dir}")
    print(f"[DONE] Blind GT template: {gt_path}")
    print(f"[DONE] Hidden predictions: {pred_ref_path}")
    print(f"[DONE] Manifest: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
