"""
Build a pseudo-labeled pose dataset from SARD person boxes, then add blur variants.

Workflow:
1) Read SARD train/valid images + YOLO person boxes (class 0).
2) Run current pose model to predict keypoints.
3) Match predicted person boxes to GT person boxes by IoU.
4) Write YOLO-pose labels (class + box + 17 x/y/v keypoints).
5) Create blur variants for train split (gaussian + motion blur).
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path
from typing import List, Tuple

import cv2
import numpy as np
from ultralytics import YOLO


BASE_DIR = Path(__file__).resolve().parents[1]
SRC_ROOT = BASE_DIR / "data" / "SARD" / "search-and-rescue"
DST_ROOT = BASE_DIR / "data" / "sard_pose_blur_pseudo"


def motion_blur(image: np.ndarray, kernel_size: int = 13) -> np.ndarray:
    kernel = np.zeros((kernel_size, kernel_size), dtype=np.float32)
    kernel[kernel_size // 2, :] = 1.0 / kernel_size
    return cv2.filter2D(image, -1, kernel)


def gaussian_blur(image: np.ndarray, kernel_size: int = 7) -> np.ndarray:
    return cv2.GaussianBlur(image, (kernel_size, kernel_size), 0)


def iou_xyxy(a: Tuple[float, float, float, float], b: Tuple[float, float, float, float]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw = max(0.0, ix2 - ix1)
    ih = max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    denom = area_a + area_b - inter
    return inter / denom if denom > 0 else 0.0


def parse_sard_person_boxes(lbl_path: Path, w: int, h: int) -> List[Tuple[float, float, float, float, Tuple[float, float, float, float]]]:
    out = []
    if not lbl_path.exists():
        return out

    for raw in lbl_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        parts = raw.split()
        if len(parts) != 5:
            continue
        cls = int(float(parts[0]))
        if cls != 0:
            continue

        cx, cy, bw, bh = map(float, parts[1:5])
        x1 = max(0.0, (cx - bw / 2.0) * w)
        y1 = max(0.0, (cy - bh / 2.0) * h)
        x2 = min(float(w), (cx + bw / 2.0) * w)
        y2 = min(float(h), (cy + bh / 2.0) * h)
        out.append((cx, cy, bw, bh, (x1, y1, x2, y2)))
    return out


def build_pose_label_line(
    gt_box_norm: Tuple[float, float, float, float],
    pred_kpts: np.ndarray,
    img_w: int,
    img_h: int,
    kpt_conf_thr: float,
) -> str:
    cx, cy, bw, bh = gt_box_norm
    parts = ["0", f"{cx:.6f}", f"{cy:.6f}", f"{bw:.6f}", f"{bh:.6f}"]

    kpts = np.asarray(pred_kpts)
    if kpts.ndim == 3:
        kpts = kpts[0]
    if kpts.shape[0] < 17:
        # Fill unknown keypoints.
        for _ in range(17):
            parts.extend(["0.000000", "0.000000", "0"])
        return " ".join(parts)

    for i in range(17):
        x, y, c = float(kpts[i, 0]), float(kpts[i, 1]), float(kpts[i, 2])
        xn = min(1.0, max(0.0, x / max(1.0, img_w)))
        yn = min(1.0, max(0.0, y / max(1.0, img_h)))
        vis = 2 if c >= kpt_conf_thr else 0
        if vis == 0:
            xn, yn = 0.0, 0.0
        parts.extend([f"{xn:.6f}", f"{yn:.6f}", str(vis)])

    return " ".join(parts)


def write_split(
    split_name: str,
    pose_model: YOLO,
    iou_thr: float,
    kpt_conf_thr: float,
    augment_train: bool,
    imgsz: int,
    resume: bool,
):
    src_img_dir = SRC_ROOT / split_name / "images"
    src_lbl_dir = SRC_ROOT / split_name / "labels"
    dst_img_dir = DST_ROOT / "images" / ("train" if split_name == "train" else "val")
    dst_lbl_dir = DST_ROOT / "labels" / ("train" if split_name == "train" else "val")
    dst_img_dir.mkdir(parents=True, exist_ok=True)
    dst_lbl_dir.mkdir(parents=True, exist_ok=True)

    images = sorted(list(src_img_dir.glob("*.jpg")) + list(src_img_dir.glob("*.jpeg")) + list(src_img_dir.glob("*.png")))

    total_gt_boxes = 0
    total_matched = 0
    written_images = 0

    for idx, img_path in enumerate(images, start=1):
        dst_img = dst_img_dir / img_path.name
        dst_lbl = dst_lbl_dir / f"{img_path.stem}.txt"

        # Resume mode: keep already processed samples.
        if resume and dst_img.exists() and dst_lbl.exists():
            if augment_train and split_name == "train":
                g_name = f"{img_path.stem}__gblur{img_path.suffix}"
                m_name = f"{img_path.stem}__mblur{img_path.suffix}"
                g_ok = (dst_img_dir / g_name).exists() and (dst_lbl_dir / f"{Path(g_name).stem}.txt").exists()
                m_ok = (dst_img_dir / m_name).exists() and (dst_lbl_dir / f"{Path(m_name).stem}.txt").exists()
                if g_ok and m_ok:
                    continue
            else:
                continue

        image = cv2.imread(str(img_path))
        if image is None:
            continue
        h, w = image.shape[:2]

        gt_boxes = parse_sard_person_boxes(src_lbl_dir / f"{img_path.stem}.txt", w, h)
        total_gt_boxes += len(gt_boxes)

        pose_preds = pose_model.predict(image, conf=0.1, imgsz=imgsz, verbose=False, classes=[0])
        pred_boxes = []
        pred_kpts = []
        if pose_preds and pose_preds[0].boxes is not None and len(pose_preds[0].boxes) > 0:
            pred_boxes = pose_preds[0].boxes.xyxy.cpu().numpy().tolist()
            if pose_preds[0].keypoints is not None:
                pred_kpts = pose_preds[0].keypoints.data.cpu().numpy()

        # Match GT person boxes to predicted pose instances.
        used_pred = set()
        label_lines = []
        for gt_cx, gt_cy, gt_bw, gt_bh, gt_xyxy in gt_boxes:
            best_j = -1
            best_iou = 0.0
            for j, pb in enumerate(pred_boxes):
                if j in used_pred:
                    continue
                iou = iou_xyxy(gt_xyxy, tuple(map(float, pb)))
                if iou >= iou_thr and iou > best_iou:
                    best_iou = iou
                    best_j = j

            if best_j < 0 or best_j >= len(pred_kpts):
                continue

            used_pred.add(best_j)
            total_matched += 1
            line = build_pose_label_line((gt_cx, gt_cy, gt_bw, gt_bh), pred_kpts[best_j], w, h, kpt_conf_thr)
            label_lines.append(line)

        # Write original image and pseudo pose labels.
        shutil.copy2(img_path, dst_img)
        dst_lbl.write_text("\n".join(label_lines), encoding="utf-8")
        written_images += 1

        if augment_train and split_name == "train":
            g_img = gaussian_blur(image, kernel_size=7)
            g_name = f"{img_path.stem}__gblur{img_path.suffix}"
            cv2.imwrite(str(dst_img_dir / g_name), g_img)
            (dst_lbl_dir / f"{Path(g_name).stem}.txt").write_text("\n".join(label_lines), encoding="utf-8")

            m_img = motion_blur(image, kernel_size=13)
            m_name = f"{img_path.stem}__mblur{img_path.suffix}"
            cv2.imwrite(str(dst_img_dir / m_name), m_img)
            (dst_lbl_dir / f"{Path(m_name).stem}.txt").write_text("\n".join(label_lines), encoding="utf-8")
            written_images += 2

        if idx % 200 == 0:
            print(f"[{split_name}] processed {idx}/{len(images)}")

    return {
        "split": split_name,
        "source_images": len(images),
        "written_images": written_images,
        "gt_person_boxes": total_gt_boxes,
        "matched_pose_boxes": total_matched,
        "match_rate": round(total_matched / max(1, total_gt_boxes), 4),
    }


def write_yaml(dst_root: Path):
    yaml_path = dst_root / "dataset_pose_blur_pseudo.yaml"
    yaml_path.write_text(
        (
            f"path: {dst_root.as_posix()}\n"
            "train: images/train\n"
            "val: images/val\n"
            "names:\n"
            "  0: person\n"
            "kpt_shape: [17, 3]\n"
            # COCO17 symmetric pairs for flip augmentation.
            "flip_idx: [0, 2, 1, 4, 3, 6, 5, 8, 7, 10, 9, 12, 11, 14, 13, 16, 15]\n"
        ),
        encoding="utf-8",
    )
    return yaml_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Build SARD pseudo pose blur dataset")
    parser.add_argument("--pose-model", type=str, default="yolov8m-pose.pt", help="Pose model file or name")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite destination dataset")
    parser.add_argument("--resume", action="store_true", help="Resume and skip already processed outputs")
    parser.add_argument("--iou", type=float, default=0.35, help="IoU threshold for GT->pose matching")
    parser.add_argument("--kpt-conf", type=float, default=0.25, help="Keypoint visibility threshold")
    parser.add_argument("--imgsz", type=int, default=640, help="Pose inference image size for pseudo labeling")
    args = parser.parse_args()

    if DST_ROOT.exists() and args.overwrite:
        shutil.rmtree(DST_ROOT)
    if DST_ROOT.exists() and not args.overwrite and not args.resume:
        print(f"[ERROR] Destination exists: {DST_ROOT} (use --overwrite)")
        return 1

    pose_model = YOLO(args.pose_model)

    train_stats = write_split(
        split_name="train",
        pose_model=pose_model,
        iou_thr=args.iou,
        kpt_conf_thr=args.kpt_conf,
        augment_train=True,
        imgsz=args.imgsz,
        resume=args.resume,
    )
    val_stats = write_split(
        split_name="valid",
        pose_model=pose_model,
        iou_thr=args.iou,
        kpt_conf_thr=args.kpt_conf,
        augment_train=False,
        imgsz=args.imgsz,
        resume=args.resume,
    )
    yaml_path = write_yaml(DST_ROOT)

    print("[DONE] SARD pseudo pose blur dataset created")
    print(f"[DONE] train stats: {train_stats}")
    print(f"[DONE] val stats: {val_stats}")
    print(f"[DONE] yaml: {yaml_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
