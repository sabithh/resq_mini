"""
True accuracy evaluation on labeled YOLO dataset.

Runs detector on a labeled image set and computes:
- per-class Precision / Recall / F1 (IoU 0.5)
- per-class AP50
- micro-averaged overall metrics

Also compares baseline vs adaptive detector mode.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import cv2
import numpy as np

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from detector import Detector


DATASET_IMAGES = BASE_DIR / "data" / "SARD" / "search-and-rescue" / "valid" / "images"
DATASET_LABELS = BASE_DIR / "data" / "SARD" / "search-and-rescue" / "valid" / "labels"
REPORT_DIR = BASE_DIR / "test_reports" / "true_accuracy"

CLASS_NAMES = {
    0: "person",
    1: "wound",
}


@dataclass
class PredItem:
    image: str
    cls: int
    conf: float
    box: List[int]


@dataclass
class GtItem:
    image: str
    cls: int
    box: List[int]


def iou_xyxy(a: List[int], b: List[int]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b

    inter_x1 = max(ax1, bx1)
    inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)

    inter_w = max(0, inter_x2 - inter_x1)
    inter_h = max(0, inter_y2 - inter_y1)
    inter = inter_w * inter_h
    if inter <= 0:
        return 0.0

    area_a = max(0, ax2 - ax1) * max(0, ay2 - ay1)
    area_b = max(0, bx2 - bx1) * max(0, by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def yolo_to_xyxy(cx: float, cy: float, w: float, h: float, img_w: int, img_h: int) -> List[int]:
    x1 = int((cx - w / 2.0) * img_w)
    y1 = int((cy - h / 2.0) * img_h)
    x2 = int((cx + w / 2.0) * img_w)
    y2 = int((cy + h / 2.0) * img_h)
    x1 = max(0, min(x1, img_w - 1))
    y1 = max(0, min(y1, img_h - 1))
    x2 = max(0, min(x2, img_w - 1))
    y2 = max(0, min(y2, img_h - 1))
    return [x1, y1, x2, y2]


def parse_label_file(label_path: Path, img_w: int, img_h: int) -> List[Tuple[int, List[int]]]:
    out = []
    if not label_path.exists():
        return out

    for line in label_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) < 5:
            continue
        try:
            cls = int(float(parts[0]))
            cx = float(parts[1])
            cy = float(parts[2])
            w = float(parts[3])
            h = float(parts[4])
        except ValueError:
            continue
        out.append((cls, yolo_to_xyxy(cx, cy, w, h, img_w, img_h)))
    return out


def detector_class(det: dict) -> int:
    return 1 if str(det.get("pose", "")).upper() == "WOUND" else 0


def safe_div(a: float, b: float) -> float:
    return a / b if b else 0.0


def compute_ap50(pred_flags: List[Tuple[float, int]], total_gt: int) -> float:
    """pred_flags entries: (confidence, is_tp 0/1)."""
    if total_gt == 0:
        return 0.0
    if not pred_flags:
        return 0.0

    pred_flags.sort(key=lambda x: x[0], reverse=True)

    tp_cum = []
    fp_cum = []
    tp = 0
    fp = 0
    for _, is_tp in pred_flags:
        if is_tp:
            tp += 1
        else:
            fp += 1
        tp_cum.append(tp)
        fp_cum.append(fp)

    recalls = [safe_div(tp_cum[i], total_gt) for i in range(len(tp_cum))]
    precisions = [safe_div(tp_cum[i], tp_cum[i] + fp_cum[i]) for i in range(len(tp_cum))]

    # VOC-style precision envelope + area under curve
    mrec = [0.0] + recalls + [1.0]
    mpre = [0.0] + precisions + [0.0]
    for i in range(len(mpre) - 2, -1, -1):
        mpre[i] = max(mpre[i], mpre[i + 1])

    ap = 0.0
    for i in range(1, len(mrec)):
        if mrec[i] != mrec[i - 1]:
            ap += (mrec[i] - mrec[i - 1]) * mpre[i]
    return ap


def evaluate_mode(images: List[Path], detector: Detector, adaptive: bool, iou_thr: float) -> dict:
    gts_by_image_class: Dict[Tuple[str, int], List[List[int]]] = defaultdict(list)
    preds_by_image_class: Dict[Tuple[str, int], List[PredItem]] = defaultdict(list)

    all_classes = set()

    for image_path in images:
        image = cv2.imread(str(image_path))
        if image is None:
            continue
        h, w = image.shape[:2]

        label_path = DATASET_LABELS / f"{image_path.stem}.txt"
        gts = parse_label_file(label_path, w, h)
        for cls, box in gts:
            gts_by_image_class[(image_path.name, cls)].append(box)
            all_classes.add(cls)

        try:
            dets = detector.detect(image, adaptive=adaptive)
        except Exception as exc:
            print(f"[WARN] detect failed for {image_path.name}: {exc}")
            dets = []

        for d in dets:
            cls = detector_class(d)
            box = d.get("bbox_xyxy")
            if not box or len(box) != 4:
                continue
            conf = float(d.get("confidence", 0.0))
            preds_by_image_class[(image_path.name, cls)].append(
                PredItem(image=image_path.name, cls=cls, conf=conf, box=box)
            )
            all_classes.add(cls)

    class_metrics = {}
    micro_tp = micro_fp = micro_fn = 0

    for cls in sorted(all_classes):
        class_name = CLASS_NAMES.get(cls, f"class_{cls}")

        total_gt = 0
        pred_flags: List[Tuple[float, int]] = []
        tp = fp = fn = 0

        image_names = set([k[0] for k in gts_by_image_class.keys()] + [k[0] for k in preds_by_image_class.keys()])
        for img_name in image_names:
            gt_boxes = list(gts_by_image_class.get((img_name, cls), []))
            pred_items = list(preds_by_image_class.get((img_name, cls), []))
            total_gt += len(gt_boxes)

            matched_gt = set()
            pred_items.sort(key=lambda p: p.conf, reverse=True)

            for pred in pred_items:
                best_iou = 0.0
                best_idx = -1
                for i, gt_box in enumerate(gt_boxes):
                    if i in matched_gt:
                        continue
                    iou = iou_xyxy(pred.box, gt_box)
                    if iou > best_iou:
                        best_iou = iou
                        best_idx = i

                if best_iou >= iou_thr and best_idx >= 0:
                    matched_gt.add(best_idx)
                    tp += 1
                    pred_flags.append((pred.conf, 1))
                else:
                    fp += 1
                    pred_flags.append((pred.conf, 0))

            fn += len(gt_boxes) - len(matched_gt)

        precision = safe_div(tp, tp + fp)
        recall = safe_div(tp, tp + fn)
        f1 = safe_div(2 * precision * recall, precision + recall)
        ap50 = compute_ap50(pred_flags, total_gt)

        class_metrics[class_name] = {
            "class_id": cls,
            "gt": total_gt,
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "ap50": round(ap50, 4),
        }

        micro_tp += tp
        micro_fp += fp
        micro_fn += fn

    micro_precision = safe_div(micro_tp, micro_tp + micro_fp)
    micro_recall = safe_div(micro_tp, micro_tp + micro_fn)
    micro_f1 = safe_div(2 * micro_precision * micro_recall, micro_precision + micro_recall)

    map50 = 0.0
    if class_metrics:
        map50 = float(np.mean([v["ap50"] for v in class_metrics.values()]))

    return {
        "images": len(images),
        "iou_threshold": iou_thr,
        "micro": {
            "tp": micro_tp,
            "fp": micro_fp,
            "fn": micro_fn,
            "precision": round(micro_precision, 4),
            "recall": round(micro_recall, 4),
            "f1": round(micro_f1, 4),
            "map50": round(map50, 4),
        },
        "classes": class_metrics,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run true labeled accuracy evaluation")
    parser.add_argument("--max-images", type=int, default=200, help="Maximum number of images to evaluate")
    parser.add_argument("--iou", type=float, default=0.5, help="IoU threshold")
    args = parser.parse_args()

    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    images = sorted(DATASET_IMAGES.glob("*.jpg")) + sorted(DATASET_IMAGES.glob("*.jpeg")) + sorted(DATASET_IMAGES.glob("*.png"))
    if not images:
        print(f"[ERROR] No images found in {DATASET_IMAGES}")
        return 1

    if args.max_images > 0:
        images = images[: args.max_images]

    detector = Detector()

    baseline = evaluate_mode(images, detector=detector, adaptive=False, iou_thr=args.iou)
    adaptive = evaluate_mode(images, detector=detector, adaptive=True, iou_thr=args.iou)

    report = {
        "dataset": str(DATASET_IMAGES.parent),
        "image_count": len(images),
        "iou_threshold": args.iou,
        "baseline": baseline,
        "adaptive": adaptive,
        "delta_micro": {
            "precision": round(adaptive["micro"]["precision"] - baseline["micro"]["precision"], 4),
            "recall": round(adaptive["micro"]["recall"] - baseline["micro"]["recall"], 4),
            "f1": round(adaptive["micro"]["f1"] - baseline["micro"]["f1"], 4),
            "map50": round(adaptive["micro"]["map50"] - baseline["micro"]["map50"], 4),
        },
    }

    out_json = REPORT_DIR / "true_accuracy_report.json"
    out_csv = REPORT_DIR / "true_accuracy_summary.csv"
    out_md = REPORT_DIR / "true_accuracy_report.md"

    out_json.write_text(json.dumps(report, indent=2), encoding="utf-8")

    with out_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["mode", "precision", "recall", "f1", "map50", "tp", "fp", "fn"])
        writer.writerow([
            "baseline",
            baseline["micro"]["precision"],
            baseline["micro"]["recall"],
            baseline["micro"]["f1"],
            baseline["micro"]["map50"],
            baseline["micro"]["tp"],
            baseline["micro"]["fp"],
            baseline["micro"]["fn"],
        ])
        writer.writerow([
            "adaptive",
            adaptive["micro"]["precision"],
            adaptive["micro"]["recall"],
            adaptive["micro"]["f1"],
            adaptive["micro"]["map50"],
            adaptive["micro"]["tp"],
            adaptive["micro"]["fp"],
            adaptive["micro"]["fn"],
        ])

    with out_md.open("w", encoding="utf-8") as f:
        f.write("# True Accuracy Report (Labeled)\n\n")
        f.write(f"- Dataset: `{DATASET_IMAGES.parent}`\n")
        f.write(f"- Images evaluated: {len(images)}\n")
        f.write(f"- IoU threshold: {args.iou}\n\n")

        f.write("## Micro Metrics\n")
        f.write(
            f"- Baseline: Precision={baseline['micro']['precision']}, Recall={baseline['micro']['recall']}, "
            f"F1={baseline['micro']['f1']}, mAP50={baseline['micro']['map50']}\n"
        )
        f.write(
            f"- Adaptive: Precision={adaptive['micro']['precision']}, Recall={adaptive['micro']['recall']}, "
            f"F1={adaptive['micro']['f1']}, mAP50={adaptive['micro']['map50']}\n"
        )
        f.write(
            f"- Delta: Precision={report['delta_micro']['precision']}, Recall={report['delta_micro']['recall']}, "
            f"F1={report['delta_micro']['f1']}, mAP50={report['delta_micro']['map50']}\n\n"
        )

        f.write("## Per Class\n")
        classes = sorted(set(list(baseline["classes"].keys()) + list(adaptive["classes"].keys())))
        for cls_name in classes:
            b = baseline["classes"].get(cls_name, {})
            a = adaptive["classes"].get(cls_name, {})
            if not b and not a:
                continue
            f.write(
                f"- {cls_name}: baseline(F1={b.get('f1', 0)}, AP50={b.get('ap50', 0)}) -> "
                f"adaptive(F1={a.get('f1', 0)}, AP50={a.get('ap50', 0)})\n"
            )

        f.write("\n## Output Files\n")
        f.write("- `test_reports/true_accuracy/true_accuracy_report.json`\n")
        f.write("- `test_reports/true_accuracy/true_accuracy_summary.csv`\n")
        f.write("- `test_reports/true_accuracy/true_accuracy_report.md`\n")

    print("[DONE] True accuracy evaluation complete")
    print(f"[DONE] JSON: {out_json}")
    print(f"[DONE] CSV: {out_csv}")
    print(f"[DONE] MD : {out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
