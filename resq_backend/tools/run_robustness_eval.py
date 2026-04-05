"""
Run robustness evaluation for ResQ detector on images in resq_backend/test.

What this script does:
1. Uses original images as reference predictions (proxy ground truth).
2. Creates perturbed variants (noise, blur, low/high light, etc.).
3. Runs detection on each variant.
4. Computes per-augmentation precision/recall/F1 against reference boxes.
5. Writes matrix/report files to resq_backend/test_reports.

Note:
- This is a robustness matrix, not absolute dataset accuracy, unless true labels are provided.
"""

from __future__ import annotations

import csv
import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Tuple

import cv2
import numpy as np

BASE_DIR = Path(__file__).resolve().parents[1]
TEST_DIR = BASE_DIR / "test"
REPORT_DIR = BASE_DIR / "test_reports"
AUG_DIR = REPORT_DIR / "augmented"

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from detector import Detector


@dataclass
class DetectionStats:
    mode: str
    image_name: str
    augmentation: str
    base_count: int
    pred_count: int
    tp: int
    fp: int
    fn: int
    precision: float
    recall: float
    f1: float
    mean_conf: float


def clip_uint8(img: np.ndarray) -> np.ndarray:
    return np.clip(img, 0, 255).astype(np.uint8)


def aug_identity(img: np.ndarray) -> np.ndarray:
    return img.copy()


def aug_gaussian_noise(img: np.ndarray, sigma: float = 18.0) -> np.ndarray:
    noise = np.random.normal(0, sigma, img.shape).astype(np.float32)
    return clip_uint8(img.astype(np.float32) + noise)


def aug_salt_pepper(img: np.ndarray, amount: float = 0.012) -> np.ndarray:
    out = img.copy()
    h, w = out.shape[:2]
    num = int(amount * h * w)
    ys = np.random.randint(0, h, num)
    xs = np.random.randint(0, w, num)
    out[ys, xs] = 255
    ys = np.random.randint(0, h, num)
    xs = np.random.randint(0, w, num)
    out[ys, xs] = 0
    return out


def aug_gaussian_blur(img: np.ndarray) -> np.ndarray:
    return cv2.GaussianBlur(img, (7, 7), 1.6)


def aug_motion_blur(img: np.ndarray, ksize: int = 13) -> np.ndarray:
    kernel = np.zeros((ksize, ksize), dtype=np.float32)
    kernel[ksize // 2, :] = 1.0
    kernel /= float(ksize)
    return cv2.filter2D(img, -1, kernel)


def aug_low_light(img: np.ndarray, factor: float = 0.45) -> np.ndarray:
    return clip_uint8(img.astype(np.float32) * factor)


def aug_high_light(img: np.ndarray, factor: float = 1.45) -> np.ndarray:
    return clip_uint8(img.astype(np.float32) * factor)


def aug_low_contrast(img: np.ndarray) -> np.ndarray:
    return clip_uint8((img.astype(np.float32) - 127.5) * 0.6 + 127.5)


def aug_high_contrast(img: np.ndarray) -> np.ndarray:
    return clip_uint8((img.astype(np.float32) - 127.5) * 1.4 + 127.5)


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


def greedy_match(base_boxes: List[List[int]], pred_boxes: List[List[int]], iou_thr: float = 0.5) -> Tuple[int, int, int]:
    if not base_boxes and not pred_boxes:
        return 0, 0, 0
    if not base_boxes:
        return 0, len(pred_boxes), 0
    if not pred_boxes:
        return 0, 0, len(base_boxes)

    candidates = []
    for bi, bb in enumerate(base_boxes):
        for pi, pb in enumerate(pred_boxes):
            iou = iou_xyxy(bb, pb)
            if iou >= iou_thr:
                candidates.append((iou, bi, pi))

    candidates.sort(reverse=True, key=lambda x: x[0])

    used_b = set()
    used_p = set()
    tp = 0
    for _, bi, pi in candidates:
        if bi in used_b or pi in used_p:
            continue
        used_b.add(bi)
        used_p.add(pi)
        tp += 1

    fp = len(pred_boxes) - tp
    fn = len(base_boxes) - tp
    return tp, fp, fn


def safe_div(a: float, b: float) -> float:
    return a / b if b else 0.0


def run_detector(detector: Detector, img: np.ndarray, adaptive: bool) -> List[Dict]:
    try:
        return detector.detect(img, adaptive=adaptive)
    except Exception as exc:
        print(f"[WARN] detection failed: {exc}")
        return []


def write_mode_outputs(mode_name: str, rows: List[DetectionStats], images: List[Path]) -> List[dict]:
    per_image_csv = REPORT_DIR / f"per_image_metrics_{mode_name}.csv"
    with per_image_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "mode",
            "image",
            "augmentation",
            "base_count",
            "pred_count",
            "tp",
            "fp",
            "fn",
            "precision",
            "recall",
            "f1",
            "mean_confidence",
        ])
        for r in rows:
            writer.writerow([
                r.mode,
                r.image_name,
                r.augmentation,
                r.base_count,
                r.pred_count,
                r.tp,
                r.fp,
                r.fn,
                f"{r.precision:.4f}",
                f"{r.recall:.4f}",
                f"{r.f1:.4f}",
                f"{r.mean_conf:.4f}",
            ])

    grouped: Dict[str, List[DetectionStats]] = {}
    for r in rows:
        grouped.setdefault(r.augmentation, []).append(r)

    matrix_csv = REPORT_DIR / f"accuracy_matrix_{mode_name}.csv"
    matrix_json = REPORT_DIR / f"accuracy_matrix_{mode_name}.json"
    matrix_rows = []

    with matrix_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "mode",
            "augmentation",
            "images",
            "base_total",
            "pred_total",
            "tp",
            "fp",
            "fn",
            "precision",
            "recall",
            "f1",
            "mean_confidence",
            "count_ratio_pred_to_base",
        ])

        for aug_name in sorted(grouped.keys()):
            aug_rows = grouped[aug_name]
            base_total = sum(x.base_count for x in aug_rows)
            pred_total = sum(x.pred_count for x in aug_rows)
            tp = sum(x.tp for x in aug_rows)
            fp = sum(x.fp for x in aug_rows)
            fn = sum(x.fn for x in aug_rows)
            precision = safe_div(tp, tp + fp)
            recall = safe_div(tp, tp + fn)
            f1 = safe_div(2 * precision * recall, precision + recall)
            mean_conf = float(np.mean([x.mean_conf for x in aug_rows])) if aug_rows else 0.0
            count_ratio = safe_div(pred_total, base_total) if base_total else 0.0

            writer.writerow([
                mode_name,
                aug_name,
                len(aug_rows),
                base_total,
                pred_total,
                tp,
                fp,
                fn,
                f"{precision:.4f}",
                f"{recall:.4f}",
                f"{f1:.4f}",
                f"{mean_conf:.4f}",
                f"{count_ratio:.4f}",
            ])

            matrix_rows.append(
                {
                    "mode": mode_name,
                    "augmentation": aug_name,
                    "images": len(aug_rows),
                    "base_total": base_total,
                    "pred_total": pred_total,
                    "tp": tp,
                    "fp": fp,
                    "fn": fn,
                    "precision": round(precision, 4),
                    "recall": round(recall, 4),
                    "f1": round(f1, 4),
                    "mean_confidence": round(mean_conf, 4),
                    "count_ratio_pred_to_base": round(count_ratio, 4),
                }
            )

    with matrix_json.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "note": "Proxy robustness matrix against original-image detections (not absolute labeled accuracy).",
                "mode": mode_name,
                "test_images": [p.name for p in images],
                "matrix": matrix_rows,
            },
            f,
            indent=2,
        )

    return matrix_rows


def main() -> int:
    np.random.seed(42)

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    AUG_DIR.mkdir(parents=True, exist_ok=True)

    images = sorted(TEST_DIR.glob("*.jpg")) + sorted(TEST_DIR.glob("*.jpeg")) + sorted(TEST_DIR.glob("*.png"))
    if not images:
        print(f"[ERROR] No images found in {TEST_DIR}")
        return 1

    detector = Detector()

    augmentations: Dict[str, Callable[[np.ndarray], np.ndarray]] = {
        "original": aug_identity,
        "gaussian_noise": aug_gaussian_noise,
        "salt_pepper": aug_salt_pepper,
        "gaussian_blur": aug_gaussian_blur,
        "motion_blur": aug_motion_blur,
        "low_light": aug_low_light,
        "high_light": aug_high_light,
        "low_contrast": aug_low_contrast,
        "high_contrast": aug_high_contrast,
    }

    mode_flags = {
        "baseline": False,
        "adaptive": True,
    }

    mode_matrix: Dict[str, List[dict]] = {}

    for mode_name, adaptive_flag in mode_flags.items():
        mode_rows: List[DetectionStats] = []

        for aug_name, aug_fn in augmentations.items():
            mode_aug_dir = AUG_DIR / mode_name / aug_name
            mode_aug_dir.mkdir(parents=True, exist_ok=True)

            for img_path in images:
                image = cv2.imread(str(img_path))
                if image is None:
                    print(f"[WARN] Could not read {img_path.name}")
                    continue

                base = run_detector(detector, image, adaptive=adaptive_flag)
                base_boxes = [d.get("bbox_xyxy", []) for d in base if d.get("bbox_xyxy")]

                variant = aug_fn(image)
                cv2.imwrite(str(mode_aug_dir / img_path.name), variant)

                pred = run_detector(detector, variant, adaptive=adaptive_flag)
                pred_boxes = [d.get("bbox_xyxy", []) for d in pred if d.get("bbox_xyxy")]
                confidences = [float(d.get("confidence", 0.0)) for d in pred]

                tp, fp, fn = greedy_match(base_boxes, pred_boxes, iou_thr=0.5)
                prec = safe_div(tp, tp + fp)
                rec = safe_div(tp, tp + fn)
                f1 = safe_div(2 * prec * rec, prec + rec)
                mean_conf = float(np.mean(confidences)) if confidences else 0.0

                mode_rows.append(
                    DetectionStats(
                        mode=mode_name,
                        image_name=img_path.name,
                        augmentation=aug_name,
                        base_count=len(base_boxes),
                        pred_count=len(pred_boxes),
                        tp=tp,
                        fp=fp,
                        fn=fn,
                        precision=prec,
                        recall=rec,
                        f1=f1,
                        mean_conf=mean_conf,
                    )
                )

        mode_matrix[mode_name] = write_mode_outputs(mode_name, mode_rows, images)

    # Keep legacy filenames pointing to adaptive results for convenience.
    shutil.copyfile(REPORT_DIR / "per_image_metrics_adaptive.csv", REPORT_DIR / "per_image_metrics.csv")
    shutil.copyfile(REPORT_DIR / "accuracy_matrix_adaptive.csv", REPORT_DIR / "accuracy_matrix.csv")
    shutil.copyfile(REPORT_DIR / "accuracy_matrix_adaptive.json", REPORT_DIR / "accuracy_matrix.json")

    baseline_by_aug = {x["augmentation"]: x for x in mode_matrix["baseline"]}
    adaptive_by_aug = {x["augmentation"]: x for x in mode_matrix["adaptive"]}

    comparison_csv = REPORT_DIR / "accuracy_matrix_comparison.csv"
    with comparison_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "augmentation",
            "baseline_f1",
            "adaptive_f1",
            "delta_f1",
            "baseline_recall",
            "adaptive_recall",
            "delta_recall",
            "baseline_precision",
            "adaptive_precision",
            "delta_precision",
        ])

        for aug in sorted(baseline_by_aug.keys()):
            b = baseline_by_aug[aug]
            a = adaptive_by_aug.get(aug, b)
            writer.writerow([
                aug,
                f"{b['f1']:.4f}",
                f"{a['f1']:.4f}",
                f"{(a['f1'] - b['f1']):.4f}",
                f"{b['recall']:.4f}",
                f"{a['recall']:.4f}",
                f"{(a['recall'] - b['recall']):.4f}",
                f"{b['precision']:.4f}",
                f"{a['precision']:.4f}",
                f"{(a['precision'] - b['precision']):.4f}",
            ])

    improved = []
    for aug, b in baseline_by_aug.items():
        a = adaptive_by_aug.get(aug, b)
        improved.append((a["f1"] - b["f1"], aug, b, a))
    improved.sort(reverse=True, key=lambda x: x[0])

    report_md = REPORT_DIR / "robustness_report.md"
    with report_md.open("w", encoding="utf-8") as f:
        f.write("# ResQ Robustness Evaluation Report\n\n")
        f.write("- Scope: Test images in `resq_backend/test`\n")
        f.write("- Metric type: Proxy robustness vs original-image detections\n")
        f.write("- Modes: baseline vs adaptive blur-aware thresholding\n")
        f.write("- Important: This is not absolute ground-truth accuracy without labels\n\n")

        f.write("## Biggest F1 Improvements (Adaptive - Baseline)\n")
        for delta, aug, b, a in improved[:5]:
            f.write(
                f"- {aug}: DeltaF1={delta:.4f} (baseline={b['f1']:.4f}, adaptive={a['f1']:.4f}), "
                f"DeltaRecall={(a['recall'] - b['recall']):.4f}\n"
            )

        f.write("\n## Biggest F1 Regressions\n")
        for delta, aug, b, a in improved[-5:]:
            f.write(
                f"- {aug}: DeltaF1={delta:.4f} (baseline={b['f1']:.4f}, adaptive={a['f1']:.4f}), "
                f"DeltaRecall={(a['recall'] - b['recall']):.4f}\n"
            )

        f.write("\n## Output Files\n")
        f.write("- `test_reports/accuracy_matrix_baseline.csv`\n")
        f.write("- `test_reports/accuracy_matrix_adaptive.csv`\n")
        f.write("- `test_reports/accuracy_matrix_comparison.csv`\n")
        f.write("- `test_reports/per_image_metrics_baseline.csv`\n")
        f.write("- `test_reports/per_image_metrics_adaptive.csv`\n")
        f.write("- `test_reports/augmented/baseline/` and `test_reports/augmented/adaptive/`\n")

    print("[DONE] Evaluation completed.")
    print(f"[DONE] Comparison: {comparison_csv}")
    print(f"[DONE] Report: {report_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
