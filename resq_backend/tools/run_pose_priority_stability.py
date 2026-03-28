"""
Pose/priority stability evaluation without leaked labels.

This evaluates how stable pose and priority predictions are when the same image
is perturbed (noise, blur, low light). It does not require manual GT labels.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

import cv2
import numpy as np

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from detector import Detector
from risk import compute_risk


DATASET_IMAGES = BASE_DIR / "data" / "SARD" / "search-and-rescue" / "valid" / "images"
REPORT_DIR = BASE_DIR / "test_reports" / "pose_stability"


@dataclass
class StableRow:
    augmentation: str
    originals: int
    matched: int
    unmatched: int
    pose_agree: int
    pose_flip: int
    pri_agree: int
    pri_flip: int


def iou_xyxy(a: List[int], b: List[int]) -> float:
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


def aug_gaussian_noise(img: np.ndarray, sigma: float = 20.0) -> np.ndarray:
    noise = np.random.normal(0, sigma, img.shape).astype(np.float32)
    out = img.astype(np.float32) + noise
    return np.clip(out, 0, 255).astype(np.uint8)


def aug_low_light(img: np.ndarray, factor: float = 0.45) -> np.ndarray:
    return np.clip(img.astype(np.float32) * factor, 0, 255).astype(np.uint8)


def aug_gaussian_blur(img: np.ndarray, k: int = 7) -> np.ndarray:
    return cv2.GaussianBlur(img, (k, k), 0)


def aug_motion_blur(img: np.ndarray, k: int = 13) -> np.ndarray:
    kernel = np.zeros((k, k), dtype=np.float32)
    kernel[k // 2, :] = 1.0 / k
    return cv2.filter2D(img, -1, kernel)


def people_only(victims: List[dict]) -> List[dict]:
    return [v for v in victims if str(v.get("pose", "")).upper() != "WOUND"]


def attach_priority(victims: List[dict], drone_id: str, w: int, h: int) -> List[dict]:
    out = []
    for v in victims:
        out.append(compute_risk(dict(v), drone_id=drone_id, frame_width=w, frame_height=h))
    return out


def evaluate(images: List[Path], detector: Detector, iou_thr: float) -> dict:
    augmentations = {
        "gaussian_noise": aug_gaussian_noise,
        "low_light": aug_low_light,
        "gaussian_blur": aug_gaussian_blur,
        "motion_blur": aug_motion_blur,
    }

    rows: List[StableRow] = []
    pose_flip_pairs = Counter()
    pri_flip_pairs = Counter()

    agg = defaultdict(lambda: {
        "originals": 0,
        "matched": 0,
        "unmatched": 0,
        "pose_agree": 0,
        "pose_flip": 0,
        "pri_agree": 0,
        "pri_flip": 0,
    })

    for idx, img_path in enumerate(images, start=1):
        image = cv2.imread(str(img_path))
        if image is None:
            continue

        h, w = image.shape[:2]
        base = detector.detect(image, adaptive=True)
        base = people_only(base)
        base = attach_priority(base, drone_id=f"stable-orig-{img_path.stem}", w=w, h=h)
        if not base:
            continue

        for aug_name, aug_fn in augmentations.items():
            aug_img = aug_fn(image)
            aug = detector.detect(aug_img, adaptive=True)
            aug = people_only(aug)
            aug = attach_priority(aug, drone_id=f"stable-{aug_name}-{img_path.stem}", w=w, h=h)

            used_aug = set()
            matched = 0
            pose_agree = 0
            pri_agree = 0

            for b in base:
                best_j = -1
                best_iou = 0.0
                for j, a in enumerate(aug):
                    if j in used_aug:
                        continue
                    cur_iou = iou_xyxy(b["bbox_xyxy"], a["bbox_xyxy"])
                    if cur_iou >= iou_thr and cur_iou > best_iou:
                        best_iou = cur_iou
                        best_j = j

                if best_j < 0:
                    continue

                matched += 1
                used_aug.add(best_j)
                a = aug[best_j]
                b_pose = str(b.get("pose", "unknown")).lower()
                a_pose = str(a.get("pose", "unknown")).lower()
                b_pri = str(b.get("priority", "LOW")).upper()
                a_pri = str(a.get("priority", "LOW")).upper()

                if b_pose == a_pose:
                    pose_agree += 1
                else:
                    pose_flip_pairs[(b_pose, a_pose)] += 1

                if b_pri == a_pri:
                    pri_agree += 1
                else:
                    pri_flip_pairs[(b_pri, a_pri)] += 1

            originals = len(base)
            unmatched = originals - matched
            pose_flip = matched - pose_agree
            pri_flip = matched - pri_agree

            row = StableRow(
                augmentation=aug_name,
                originals=originals,
                matched=matched,
                unmatched=unmatched,
                pose_agree=pose_agree,
                pose_flip=pose_flip,
                pri_agree=pri_agree,
                pri_flip=pri_flip,
            )
            rows.append(row)

            a = agg[aug_name]
            a["originals"] += originals
            a["matched"] += matched
            a["unmatched"] += unmatched
            a["pose_agree"] += pose_agree
            a["pose_flip"] += pose_flip
            a["pri_agree"] += pri_agree
            a["pri_flip"] += pri_flip

        if idx % 25 == 0:
            print(f"[Progress] Processed {idx}/{len(images)} images")

    summary_rows = []
    for aug_name, a in agg.items():
        matched = max(1, a["matched"])
        summary_rows.append({
            "augmentation": aug_name,
            "originals": a["originals"],
            "matched": a["matched"],
            "unmatched": a["unmatched"],
            "match_rate": round(a["matched"] / max(1, a["originals"]), 4),
            "pose_agreement": round(a["pose_agree"] / matched, 4),
            "pose_flip_rate": round(a["pose_flip"] / matched, 4),
            "priority_agreement": round(a["pri_agree"] / matched, 4),
            "priority_flip_rate": round(a["pri_flip"] / matched, 4),
        })

    summary_rows.sort(key=lambda x: x["pose_flip_rate"], reverse=True)

    return {
        "images_evaluated": len(images),
        "iou_threshold": iou_thr,
        "summary": summary_rows,
        "pose_flip_pairs": [
            {"from": k[0], "to": k[1], "count": v}
            for k, v in pose_flip_pairs.most_common()
        ],
        "priority_flip_pairs": [
            {"from": k[0], "to": k[1], "count": v}
            for k, v in pri_flip_pairs.most_common()
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Pose/priority stability evaluation")
    parser.add_argument("--max-images", type=int, default=120, help="Max images from validation set")
    parser.add_argument("--iou", type=float, default=0.5, help="IoU threshold for matching")
    args = parser.parse_args()

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    images = sorted(DATASET_IMAGES.glob("*.jpg")) + sorted(DATASET_IMAGES.glob("*.jpeg")) + sorted(DATASET_IMAGES.glob("*.png"))
    if not images:
        print(f"[ERROR] No images found in {DATASET_IMAGES}")
        return 1

    if args.max_images > 0:
        images = images[: args.max_images]

    detector = Detector()
    report = evaluate(images, detector=detector, iou_thr=args.iou)

    out_json = REPORT_DIR / "pose_priority_stability.json"
    out_csv = REPORT_DIR / "pose_priority_stability.csv"
    out_md = REPORT_DIR / "pose_priority_stability.md"

    out_json.write_text(json.dumps(report, indent=2), encoding="utf-8")

    with out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "augmentation",
            "originals",
            "matched",
            "unmatched",
            "match_rate",
            "pose_agreement",
            "pose_flip_rate",
            "priority_agreement",
            "priority_flip_rate",
        ])
        for s in report["summary"]:
            w.writerow([
                s["augmentation"],
                s["originals"],
                s["matched"],
                s["unmatched"],
                s["match_rate"],
                s["pose_agreement"],
                s["pose_flip_rate"],
                s["priority_agreement"],
                s["priority_flip_rate"],
            ])

    with out_md.open("w", encoding="utf-8") as f:
        f.write("# Pose/Priority Stability Report\n\n")
        f.write("This is a robustness consistency test (not absolute GT accuracy).\n\n")
        f.write(f"- Images evaluated: {report['images_evaluated']}\n")
        f.write(f"- IoU threshold: {report['iou_threshold']}\n\n")
        f.write("## Augmentation Summary\n")
        for s in report["summary"]:
            f.write(
                f"- {s['augmentation']}: match_rate={s['match_rate']}, "
                f"pose_agreement={s['pose_agreement']}, priority_agreement={s['priority_agreement']}\n"
            )

        f.write("\n## Top Pose Flips\n")
        for item in report["pose_flip_pairs"][:10]:
            f.write(f"- {item['from']} -> {item['to']}: {item['count']}\n")

        f.write("\n## Top Priority Flips\n")
        for item in report["priority_flip_pairs"][:10]:
            f.write(f"- {item['from']} -> {item['to']}: {item['count']}\n")

    print(f"[DONE] Wrote {out_json}")
    print(f"[DONE] Wrote {out_csv}")
    print(f"[DONE] Wrote {out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
