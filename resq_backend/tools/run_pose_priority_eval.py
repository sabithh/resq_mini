"""
run_pose_priority_eval.py

ResQ — Pose Classification & Priority Accuracy Evaluation

Step 1: Run this script with --annotate to detect all victims and save
        annotated crops to test_reports/pose_eval/crops/ for manual labelling.

Step 2: Fill in the ground truth JSON at test_reports/pose_eval/ground_truth.json
        (the script creates a skeleton with predicted labels — correct them!)

Step 3: Run this script without --annotate to evaluate pose and priority accuracy.

Outputs
-------
  test_reports/pose_eval/
    ├── ground_truth.json           — GT labels (edit this after step 1)
    ├── predictions.json            — Raw detector output
    ├── pose_confusion_matrix.csv   — Pose confusion matrix
    ├── priority_confusion_matrix.csv
    ├── pose_accuracy_report.csv    — Per-class P/R/F1 for pose
    ├── priority_accuracy_report.csv
    ├── full_report.json            — Combined JSON
    └── crops/                      — Annotated victim crops for labelling
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

BASE_DIR = Path(__file__).resolve().parents[1]
TEST_DIR  = BASE_DIR / "test"
REPORT_DIR = BASE_DIR / "test_reports" / "pose_eval"

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from detector import Detector
from risk import compute_risk
from grid import assign_grid

POSE_CLASSES     = ["standing", "sitting", "lying"]
PRIORITY_CLASSES = ["LOW", "MEDIUM", "HIGH"]

# ──────────────────────────────────────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────────────────────────────────────

def safe_div(a: float, b: float) -> float:
    return a / b if b else 0.0


def iou_xyxy(a, b) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw = max(0, ix2 - ix1)
    ih = max(0, iy2 - iy1)
    inter = iw * ih
    if inter == 0:
        return 0.0
    area_a = max(0, ax2 - ax1) * max(0, ay2 - ay1)
    area_b = max(0, bx2 - bx1) * max(0, by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def confusion_matrix(gt_labels: List[str], pred_labels: List[str], classes: List[str]) -> Dict:
    """Returns a dict-of-dicts confusion matrix."""
    cm: Dict[str, Dict[str, int]] = {c: {c2: 0 for c2 in classes} for c in classes}
    for gt, pred in zip(gt_labels, pred_labels):
        if gt in cm and pred in cm:
            cm[gt][pred] += 1
    return cm


def class_metrics_from_cm(cm: Dict, classes: List[str]) -> Dict:
    """Compute per-class Precision / Recall / F1 from confusion matrix."""
    results = {}
    for cls in classes:
        tp = cm[cls][cls]
        fp = sum(cm[other][cls] for other in classes if other != cls)
        fn = sum(cm[cls][other] for other in classes if other != cls)
        precision = safe_div(tp, tp + fp)
        recall    = safe_div(tp, tp + fn)
        f1        = safe_div(2 * precision * recall, precision + recall)
        support   = sum(cm[cls].values())
        results[cls] = {
            "tp": tp, "fp": fp, "fn": fn,
            "precision": round(precision, 4),
            "recall":    round(recall,    4),
            "f1":        round(f1,        4),
            "support":   support,
        }
    return results


def macro_avg(class_metrics: Dict, classes: List[str]) -> Dict:
    valid = [c for c in classes if class_metrics[c]["support"] > 0]
    if not valid:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}
    return {
        "precision": round(float(np.mean([class_metrics[c]["precision"] for c in valid])), 4),
        "recall":    round(float(np.mean([class_metrics[c]["recall"]    for c in valid])), 4),
        "f1":        round(float(np.mean([class_metrics[c]["f1"]        for c in valid])), 4),
    }


def weighted_avg(class_metrics: Dict, classes: List[str]) -> Dict:
    total_support = sum(class_metrics[c]["support"] for c in classes)
    if total_support == 0:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}
    return {
        "precision": round(sum(class_metrics[c]["precision"] * class_metrics[c]["support"] for c in classes) / total_support, 4),
        "recall":    round(sum(class_metrics[c]["recall"]    * class_metrics[c]["support"] for c in classes) / total_support, 4),
        "f1":        round(sum(class_metrics[c]["f1"]        * class_metrics[c]["support"] for c in classes) / total_support, 4),
    }


def overall_accuracy(gt_labels: List[str], pred_labels: List[str]) -> float:
    correct = sum(g == p for g, p in zip(gt_labels, pred_labels))
    return round(safe_div(correct, len(gt_labels)), 4)

# ──────────────────────────────────────────────────────────────────────────────
# DETECT & ANNOTATE
# ──────────────────────────────────────────────────────────────────────────────

def run_detection(images: List[Path], detector: Detector) -> List[dict]:
    """Run detector on all images, return flat list of victim dicts with image_name."""
    all_victims = []
    for img_path in images:
        image = cv2.imread(str(img_path))
        if image is None:
            print(f"[WARN] Cannot read {img_path.name}")
            continue
        h, w = image.shape[:2]
        victims = detector.detect(image, adaptive=True)
        for v in victims:
            v = compute_risk(v, drone_id="EVAL", frame_width=w, frame_height=h)
            v = assign_grid(v, w, h)
            v["image_name"] = img_path.name
        all_victims.extend(victims)
        print(f"[Detect] {img_path.name} → {len(victims)} victims")
    return all_victims


def save_crops(images_dir: Path, victims: List[dict], crops_dir: Path, pad: int = 20):
    """Save annotated crops for each victim for manual labelling."""
    crops_dir.mkdir(parents=True, exist_ok=True)
    by_image: Dict[str, List[dict]] = defaultdict(list)
    for v in victims:
        by_image[v["image_name"]].append(v)

    for img_name, vics in by_image.items():
        image = cv2.imread(str(images_dir / img_name))
        if image is None:
            continue
        h_img, w_img = image.shape[:2]
        for v in vics:
            x1, y1, x2, y2 = v["bbox_xyxy"]
            x1c = max(0, x1 - pad)
            y1c = max(0, y1 - pad)
            x2c = min(w_img, x2 + pad)
            y2c = min(h_img, y2 + pad)
            crop = image[y1c:y2c, x1c:x2c].copy()

            # Draw color
            priority = v.get("priority", "LOW")
            color = (0, 255, 0)
            if priority == "HIGH":   color = (0, 0, 255)
            elif priority == "MEDIUM": color = (0, 165, 255)

            pose = v.get("pose", "unknown")
            label = f"ID:{v['id']} POSE:{pose}({v.get('pose_confidence',0):.2f}) PRI:{priority}"
            cv2.putText(crop, label, (5, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)
            cv2.rectangle(crop, (0, 0), (crop.shape[1]-1, crop.shape[0]-1), color, 2)

            stem = Path(img_name).stem
            fname = f"{stem}_id{v['id']}_pred_{pose}_{priority}.jpg"
            cv2.imwrite(str(crops_dir / fname), crop)

    print(f"[Crops] Saved annotated crops to {crops_dir}")

# ──────────────────────────────────────────────────────────────────────────────
# GROUND TRUTH
# ──────────────────────────────────────────────────────────────────────────────

def build_gt_skeleton(victims: List[dict], gt_path: Path):
    """
    Create a ground truth skeleton JSON pre-filled with predicted labels.
    User must manually correct 'gt_pose' and 'gt_priority' fields.
    """
    entries = []
    for v in victims:
        entries.append({
            "image_name":   v["image_name"],
            "victim_id":    v["id"],
            "bbox_xyxy":    v["bbox_xyxy"],
            "gt_pose":      v.get("pose", "unknown"),    # ← EDIT THIS
            "gt_priority":  v.get("priority", "LOW"),    # ← EDIT THIS
            "_pred_pose":     v.get("pose", "unknown"),  # reference (don't edit)
            "_pred_priority": v.get("priority", "LOW"),  # reference (don't edit)
            "_pose_confidence": round(float(v.get("pose_confidence", 0.0)), 3),
            "_risk_score":  round(float(v.get("risk_score", 0.0)), 3),
        })

    with gt_path.open("w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2)
    print(f"[GT] Ground truth skeleton saved to {gt_path}")
    print(f"[GT] → Open that file, look at the crops in test_reports/pose_eval/crops/")
    print(f"[GT] → Correct 'gt_pose' and 'gt_priority' for each victim, then re-run without --annotate")

# ──────────────────────────────────────────────────────────────────────────────
# EVALUATION
# ──────────────────────────────────────────────────────────────────────────────

def match_preds_to_gt(
    gt_entries: List[dict],
    pred_victims: List[dict],
    iou_thr: float = 0.5,
) -> List[dict]:
    """
    Match each GT entry to the best overlapping prediction.
    Returns list of matched pairs with gt_pose, pred_pose, gt_priority, pred_priority.
    """
    matches = []
    by_image_pred: Dict[str, List[dict]] = defaultdict(list)
    for v in pred_victims:
        by_image_pred[v["image_name"]].append(v)

    for entry in gt_entries:
        img    = entry["image_name"]
        gt_box = entry["bbox_xyxy"]
        gt_pose = entry.get("gt_pose", "unknown").lower()
        gt_pri  = entry.get("gt_priority", "LOW").upper()

        if gt_pose not in POSE_CLASSES:
            gt_pose = "sitting"  # default unknown to sitting
        if gt_pri not in PRIORITY_CLASSES:
            gt_pri = "LOW"

        preds = by_image_pred.get(img, [])
        best_iou = 0.0
        best_pred = None
        for p in preds:
            iou = iou_xyxy(gt_box, p["bbox_xyxy"])
            if iou > best_iou:
                best_iou = iou
                best_pred = p

        if best_pred and best_iou >= iou_thr:
            pred_pose = best_pred.get("pose", "unknown").lower()
            pred_pri  = best_pred.get("priority", "LOW").upper()
            if pred_pose not in POSE_CLASSES:
                pred_pose = "sitting"
            if pred_pri not in PRIORITY_CLASSES:
                pred_pri = "LOW"

            matches.append({
                "image":        img,
                "victim_id":    entry["victim_id"],
                "gt_pose":      gt_pose,
                "pred_pose":    pred_pose,
                "gt_priority":  gt_pri,
                "pred_priority": pred_pri,
                "iou":          round(best_iou, 3),
                "pose_confidence": round(float(best_pred.get("pose_confidence", 0.0)), 3),
                "risk_score":   round(float(best_pred.get("risk_score", 0.0)), 3),
                "matched":      True,
            })
        else:
            # No prediction matched → undetected victim
            matches.append({
                "image":        img,
                "victim_id":    entry["victim_id"],
                "gt_pose":      gt_pose,
                "pred_pose":    "UNDETECTED",
                "gt_priority":  gt_pri,
                "pred_priority": "UNDETECTED",
                "iou":          0.0,
                "pose_confidence": 0.0,
                "risk_score":   0.0,
                "matched":      False,
            })

    return matches


def write_confusion_csv(cm: Dict, classes: List[str], path: Path, label: str):
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([f"{label} (Predicted →)"] + classes)
        for gt_cls in classes:
            writer.writerow([gt_cls] + [cm[gt_cls].get(pred_cls, 0) for pred_cls in classes])


def write_class_metrics_csv(metrics: Dict, classes: List[str], macro: Dict, weighted: Dict, accuracy: float, path: Path):
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["class", "precision", "recall", "f1", "support", "tp", "fp", "fn"])
        for cls in classes:
            m = metrics.get(cls, {})
            writer.writerow([cls, m.get("precision", 0), m.get("recall", 0), m.get("f1", 0),
                              m.get("support", 0), m.get("tp", 0), m.get("fp", 0), m.get("fn", 0)])
        writer.writerow([])
        writer.writerow(["macro avg", macro["precision"], macro["recall"], macro["f1"], "", "", "", ""])
        writer.writerow(["weighted avg", weighted["precision"], weighted["recall"], weighted["f1"], "", "", "", ""])
        writer.writerow(["overall accuracy", accuracy, "", "", "", "", "", ""])


def print_confusion_matrix(cm: Dict, classes: List[str], title: str):
    print("\n" + "─"*50)
    print(" " + title)
    print("─"*50)
    col_label = "GT \ Pred"
    header = col_label.ljust(12) + "".join(c.ljust(12) for c in classes)
    print(header)
    for gt_cls in classes:
        row = gt_cls.ljust(12) + "".join(str(cm[gt_cls].get(pred_cls, 0)).ljust(12) for pred_cls in classes)
        print(row)


def print_class_metrics(metrics: Dict, classes: List[str], macro: Dict, weighted: Dict, accuracy: float, title: str):
    print("\n" + "─"*60)
    print(" " + title)
    print("─"*60)
    print("Class".ljust(12) + "Precision".rjust(12) + "Recall".rjust(10) + "F1".rjust(10) + "Support".rjust(10))
    for cls in classes:
        m = metrics.get(cls, {})
        print(cls.ljust(12)
              + f"{m.get('precision', 0):>12.4f}"
              + f"{m.get('recall', 0):>10.4f}"
              + f"{m.get('f1', 0):>10.4f}"
              + f"{m.get('support', 0):>10}")
    print("─"*60)
    print("macro avg".ljust(12) + f"{macro['precision']:>12.4f}" + f"{macro['recall']:>10.4f}" + f"{macro['f1']:>10.4f}")
    print("weighted".ljust(12)  + f"{weighted['precision']:>12.4f}" + f"{weighted['recall']:>10.4f}" + f"{weighted['f1']:>10.4f}")
    print(f"\n  Overall Accuracy: {accuracy:.4f} ({accuracy*100:.1f}%)")

# ──────────────────────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="Pose & Priority accuracy evaluation for ResQ")
    parser.add_argument("--annotate", action="store_true",
                        help="Run detection, save crops, and create GT skeleton. Do this first.")
    parser.add_argument("--iou", type=float, default=0.5,
                        help="IoU threshold for matching predictions to GT boxes (default: 0.5)")
    parser.add_argument("--gt", type=str, default=None,
                        help="Path to ground_truth.json (default: test_reports/pose_eval/ground_truth.json)")
    parser.add_argument("--fail-on-leak", action="store_true",
                        help="Exit with error if GT appears copied from predictions")
    parser.add_argument("--strict-gt", action="store_true",
                        help="Fail when GT labels are missing/invalid instead of auto-defaulting")
    args = parser.parse_args()

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    crops_dir = REPORT_DIR / "crops"
    gt_path = Path(args.gt) if args.gt else REPORT_DIR / "ground_truth.json"
    pred_path = REPORT_DIR / "predictions.json"

    images = sorted(TEST_DIR.glob("*.jpg")) + sorted(TEST_DIR.glob("*.jpeg")) + sorted(TEST_DIR.glob("*.png"))
    if not images:
        print(f"[ERROR] No test images found in {TEST_DIR}")
        return 1

    print(f"[ResQ] Pose & Priority Evaluation — {len(images)} images")
    print(f"[ResQ] IoU threshold: {args.iou}")

    detector = Detector()

    # ── MODE 1: Annotate (detect + save crops + GT skeleton) ─────────────────
    if args.annotate:
        print("\n[Annotate Mode] Running detection on all test images...")
        victims = run_detection(images, detector)

        # Save predictions
        with pred_path.open("w", encoding="utf-8") as f:
            json.dump(victims, f, indent=2, default=str)
        print(f"[Detect] Predictions saved to {pred_path}")

        save_crops(TEST_DIR, victims, crops_dir)

        if not gt_path.exists():
            build_gt_skeleton(victims, gt_path)
        else:
            print(f"[GT] ground_truth.json already exists at {gt_path} — not overwriting.")
            print(f"[GT] Delete it and re-run --annotate if you want a fresh skeleton.")

        print("\n✅ Annotation step complete!")
        print(f"   → Review crops in:       {crops_dir}")
        print(f"   → Edit ground truth at:  {gt_path}")
        print(f"     Correct 'gt_pose' and 'gt_priority' for each victim")
        print(f"   → Then run without --annotate to evaluate")
        return 0

    # ── MODE 2: Evaluate ─────────────────────────────────────────────────────
    if not gt_path.exists():
        print(f"[ERROR] No ground truth file found at {gt_path}")
        print(f"        Run with --annotate first to create it.")
        return 1

    with gt_path.open(encoding="utf-8") as f:
        gt_entries = json.load(f)
    print(f"[GT] Loaded {len(gt_entries)} ground truth entries from {gt_path}")

    # Keep evaluation aligned to current test folder content.
    valid_image_names = {p.name for p in images}
    filtered_gt = [e for e in gt_entries if e.get("image_name", "") in valid_image_names]
    dropped_gt = len(gt_entries) - len(filtered_gt)
    if dropped_gt > 0:
        print(f"[GT] Ignoring {dropped_gt} stale GT entries not present in current test folder")
    gt_entries = filtered_gt
    if not gt_entries:
        print("[ERROR] No valid GT entries remain after filtering to current test images")
        return 1

    # Detect label leakage when GT is still identical to scaffolded predictions.
    comparable = [
        e for e in gt_entries
        if "_pred_pose" in e and "_pred_priority" in e
    ]
    if comparable:
        pose_same = sum(
            1
            for e in comparable
            if str(e.get("gt_pose", "")).lower() == str(e.get("_pred_pose", "")).lower()
        )
        pri_same = sum(
            1
            for e in comparable
            if str(e.get("gt_priority", "")).upper() == str(e.get("_pred_priority", "")).upper()
        )
        pose_ratio = pose_same / max(1, len(comparable))
        pri_ratio = pri_same / max(1, len(comparable))
        if pose_ratio >= 0.95 and pri_ratio >= 0.95:
            msg = (
                f"[WARN] Possible label leakage: gt_pose==_pred_pose {pose_same}/{len(comparable)}, "
                f"gt_priority==_pred_priority {pri_same}/{len(comparable)}."
            )
            print(msg)
            print("[WARN] This score is likely optimistic unless GT was manually corrected.")
            if args.fail_on_leak:
                print("[ERROR] Failing because --fail-on-leak is enabled.")
                return 2

    # Re-run detection (or load from cache)
    if pred_path.exists():
        print(f"[Detect] Loading cached predictions from {pred_path}")
        with pred_path.open(encoding="utf-8") as f:
            pred_victims = json.load(f)
    else:
        print("[Detect] No cache found — running detection...")
        pred_victims = run_detection(images, detector)
        with pred_path.open("w", encoding="utf-8") as f:
            json.dump(pred_victims, f, indent=2, default=str)

    # Validate GT labels in strict mode.
    if args.strict_gt:
        invalid = []
        for idx, e in enumerate(gt_entries, start=1):
            gt_pose = str(e.get("gt_pose", "")).lower().strip()
            gt_pri = str(e.get("gt_priority", "")).upper().strip()
            if gt_pose not in POSE_CLASSES or gt_pri not in PRIORITY_CLASSES:
                invalid.append({
                    "index": idx,
                    "image_name": e.get("image_name", ""),
                    "victim_id": e.get("victim_id", e.get("entry_id", "")),
                    "gt_pose": e.get("gt_pose", ""),
                    "gt_priority": e.get("gt_priority", ""),
                })
        if invalid:
            print(f"[ERROR] Strict GT validation failed: {len(invalid)} invalid entries.")
            for row in invalid[:10]:
                print(
                    f"  - idx={row['index']} image={row['image_name']} victim={row['victim_id']} "
                    f"gt_pose={row['gt_pose']} gt_priority={row['gt_priority']}"
                )
            if len(invalid) > 10:
                print(f"  ... and {len(invalid) - 10} more")
            return 3

    # Match GT → predictions
    matches = match_preds_to_gt(gt_entries, pred_victims, iou_thr=args.iou)

    matched   = [m for m in matches if m["matched"]]
    unmatched = [m for m in matches if not m["matched"]]

    print(f"\n[Match] {len(matched)} matched | {len(unmatched)} undetected (FN)")

    if not matched:
        print("[ERROR] No matches found. Check IoU threshold or GT bounding boxes.")
        return 1

    # ── Pose accuracy ─────────────────────────────────────────────────────────
    gt_poses   = [m["gt_pose"]   for m in matched]
    pred_poses = [m["pred_pose"] for m in matched]

    pose_cm      = confusion_matrix(gt_poses, pred_poses, POSE_CLASSES)
    pose_metrics = class_metrics_from_cm(pose_cm, POSE_CLASSES)
    pose_macro   = macro_avg(pose_metrics, POSE_CLASSES)
    pose_weighted= weighted_avg(pose_metrics, POSE_CLASSES)
    pose_acc     = overall_accuracy(gt_poses, pred_poses)

    # ── Priority accuracy ─────────────────────────────────────────────────────
    gt_pris   = [m["gt_priority"]   for m in matched]
    pred_pris = [m["pred_priority"] for m in matched]

    pri_cm      = confusion_matrix(gt_pris, pred_pris, PRIORITY_CLASSES)
    pri_metrics = class_metrics_from_cm(pri_cm, PRIORITY_CLASSES)
    pri_macro   = macro_avg(pri_metrics, PRIORITY_CLASSES)
    pri_weighted= weighted_avg(pri_metrics, PRIORITY_CLASSES)
    pri_acc     = overall_accuracy(gt_pris, pred_pris)

    # ── Print results ─────────────────────────────────────────────────────────
    print_confusion_matrix(pose_cm, POSE_CLASSES, "POSE CONFUSION MATRIX (GT rows, Pred cols)")
    print_class_metrics(pose_metrics, POSE_CLASSES, pose_macro, pose_weighted, pose_acc, "POSE CLASSIFICATION ACCURACY")

    print_confusion_matrix(pri_cm, PRIORITY_CLASSES, "PRIORITY CONFUSION MATRIX (GT rows, Pred cols)")
    print_class_metrics(pri_metrics, PRIORITY_CLASSES, pri_macro, pri_weighted, pri_acc, "PRIORITY ASSIGNMENT ACCURACY")

    # ── Per-image breakdown ───────────────────────────────────────────────────
    print(f"\n{'─'*70}")
    print(" PER-IMAGE BREAKDOWN")
    print(f"{'─'*70}")
    by_image: Dict[str, List[dict]] = defaultdict(list)
    for m in matched:
        by_image[m["image"]].append(m)
    for img, ms in sorted(by_image.items()):
        p_correct = sum(1 for m in ms if m["gt_pose"] == m["pred_pose"])
        r_correct = sum(1 for m in ms if m["gt_priority"] == m["pred_priority"])
        print(f"  {Path(img).stem[:20]:<22}  "
              f"Pose: {p_correct}/{len(ms)} correct ({p_correct/len(ms)*100:.0f}%)  "
              f"Priority: {r_correct}/{len(ms)} correct ({r_correct/len(ms)*100:.0f}%)")

    # ── Save CSVs ─────────────────────────────────────────────────────────────
    write_confusion_csv(pose_cm, POSE_CLASSES,     REPORT_DIR / "pose_confusion_matrix.csv",     "Pose")
    write_confusion_csv(pri_cm,  PRIORITY_CLASSES, REPORT_DIR / "priority_confusion_matrix.csv", "Priority")
    write_class_metrics_csv(pose_metrics, POSE_CLASSES,     pose_macro, pose_weighted, pose_acc, REPORT_DIR / "pose_accuracy_report.csv")
    write_class_metrics_csv(pri_metrics,  PRIORITY_CLASSES, pri_macro,  pri_weighted,  pri_acc,  REPORT_DIR / "priority_accuracy_report.csv")

    # Per-victim detail CSV
    detail_csv = REPORT_DIR / "per_victim_results.csv"
    with detail_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["image", "victim_id", "gt_pose", "pred_pose", "pose_correct",
                         "gt_priority", "pred_priority", "priority_correct",
                         "iou", "pose_confidence", "risk_score"])
        for m in matches:
            writer.writerow([
                m["image"], m["victim_id"],
                m["gt_pose"], m["pred_pose"], m["gt_pose"] == m["pred_pose"],
                m["gt_priority"], m["pred_priority"], m["gt_priority"] == m["pred_priority"],
                m["iou"], m["pose_confidence"], m["risk_score"],
            ])

    # Full JSON report
    full_report = {
        "test_images": len(images),
        "gt_entries": len(gt_entries),
        "matched": len(matched),
        "undetected_fn": len(unmatched),
        "iou_threshold": args.iou,
        "pose": {
            "overall_accuracy": pose_acc,
            "macro_avg": pose_macro,
            "weighted_avg": pose_weighted,
            "per_class": pose_metrics,
            "confusion_matrix": pose_cm,
        },
        "priority": {
            "overall_accuracy": pri_acc,
            "macro_avg": pri_macro,
            "weighted_avg": pri_weighted,
            "per_class": pri_metrics,
            "confusion_matrix": pri_cm,
        },
        "per_victim_matches": matches,
    }
    with (REPORT_DIR / "full_report.json").open("w", encoding="utf-8") as f:
        json.dump(full_report, f, indent=2, default=str)

    print(f"\n{'═'*60}")
    print(f"  SUMMARY")
    print(f"{'═'*60}")
    print(f"  Pose     Overall Accuracy : {pose_acc:.4f} ({pose_acc*100:.1f}%)")
    print(f"  Pose     Macro F1         : {pose_macro['f1']:.4f}")
    print(f"  Pose     Weighted F1      : {pose_weighted['f1']:.4f}")
    print(f"  Priority Overall Accuracy : {pri_acc:.4f} ({pri_acc*100:.1f}%)")
    print(f"  Priority Macro F1         : {pri_macro['f1']:.4f}")
    print(f"  Priority Weighted F1      : {pri_weighted['f1']:.4f}")
    print(f"{'═'*60}")
    print(f"\n[DONE] Reports saved to {REPORT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
