"""
Build a blur-augmented pose dataset from combined_dataset.

Creates:
  data/combined_dataset_blur/
    images/train, images/val
    labels/train, labels/val
    dataset_blur.yaml

Train split includes originals + blurred variants.
Val split keeps originals for fair validation.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import cv2
import numpy as np


BASE_DIR = Path(__file__).resolve().parents[1]
SRC_DATASET = BASE_DIR / "data" / "combined_dataset"
DST_DATASET = BASE_DIR / "data" / "combined_dataset_blur"


def motion_blur(image: np.ndarray, kernel_size: int = 13) -> np.ndarray:
    kernel = np.zeros((kernel_size, kernel_size), dtype=np.float32)
    kernel[kernel_size // 2, :] = 1.0 / kernel_size
    return cv2.filter2D(image, -1, kernel)


def gaussian_blur(image: np.ndarray, kernel_size: int = 7) -> np.ndarray:
    return cv2.GaussianBlur(image, (kernel_size, kernel_size), 0)


def copy_original_and_labels(src_img: Path, src_lbl: Path, dst_img: Path, dst_lbl: Path):
    shutil.copy2(src_img, dst_img)
    if src_lbl.exists():
        shutil.copy2(src_lbl, dst_lbl)


def build_train_split(src_img_dir: Path, src_lbl_dir: Path, dst_img_dir: Path, dst_lbl_dir: Path):
    dst_img_dir.mkdir(parents=True, exist_ok=True)
    dst_lbl_dir.mkdir(parents=True, exist_ok=True)

    images = sorted(list(src_img_dir.glob("*.jpg")) + list(src_img_dir.glob("*.jpeg")) + list(src_img_dir.glob("*.png")))
    count = 0
    for idx, src_img in enumerate(images, start=1):
        src_lbl = src_lbl_dir / f"{src_img.stem}.txt"

        # Original
        out_img = dst_img_dir / src_img.name
        out_lbl = dst_lbl_dir / f"{src_img.stem}.txt"
        copy_original_and_labels(src_img, src_lbl, out_img, out_lbl)
        count += 1

        image = cv2.imread(str(src_img))
        if image is None:
            continue

        # Gaussian blur variant
        g_img = gaussian_blur(image, kernel_size=7)
        g_name = f"{src_img.stem}__gblur{src_img.suffix}"
        cv2.imwrite(str(dst_img_dir / g_name), g_img)
        if src_lbl.exists():
            shutil.copy2(src_lbl, dst_lbl_dir / f"{Path(g_name).stem}.txt")
        count += 1

        # Motion blur variant
        m_img = motion_blur(image, kernel_size=13)
        m_name = f"{src_img.stem}__mblur{src_img.suffix}"
        cv2.imwrite(str(dst_img_dir / m_name), m_img)
        if src_lbl.exists():
            shutil.copy2(src_lbl, dst_lbl_dir / f"{Path(m_name).stem}.txt")
        count += 1

        if idx % 200 == 0:
            print(f"[Train] Processed {idx}/{len(images)} source images")

    return len(images), count


def build_val_split(src_img_dir: Path, src_lbl_dir: Path, dst_img_dir: Path, dst_lbl_dir: Path):
    dst_img_dir.mkdir(parents=True, exist_ok=True)
    dst_lbl_dir.mkdir(parents=True, exist_ok=True)

    images = sorted(list(src_img_dir.glob("*.jpg")) + list(src_img_dir.glob("*.jpeg")) + list(src_img_dir.glob("*.png")))
    for src_img in images:
        src_lbl = src_lbl_dir / f"{src_img.stem}.txt"
        copy_original_and_labels(
            src_img,
            src_lbl,
            dst_img_dir / src_img.name,
            dst_lbl_dir / f"{src_img.stem}.txt",
        )

    return len(images)


def write_dataset_yaml(dataset_root: Path):
    yaml_path = dataset_root / "dataset_blur.yaml"
    yaml_content = (
        f"path: {dataset_root.as_posix()}\n"
        "train: images/train\n"
        "val: images/val\n"
        "names:\n"
        "  0: person\n"
        "  1: wound\n"
        "kpt_shape: [17, 3]\n"
    )
    yaml_path.write_text(yaml_content, encoding="utf-8")
    return yaml_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Build blur-augmented pose dataset")
    parser.add_argument("--overwrite", action="store_true", help="Delete destination dataset before rebuild")
    args = parser.parse_args()

    if not SRC_DATASET.exists():
        print(f"[ERROR] Missing source dataset: {SRC_DATASET}")
        return 1

    if DST_DATASET.exists() and args.overwrite:
        shutil.rmtree(DST_DATASET)

    if DST_DATASET.exists() and not args.overwrite:
        print(f"[ERROR] Destination already exists: {DST_DATASET} (use --overwrite)")
        return 1

    train_src_img = SRC_DATASET / "images" / "train"
    train_src_lbl = SRC_DATASET / "labels" / "train"
    val_src_img = SRC_DATASET / "images" / "val"
    val_src_lbl = SRC_DATASET / "labels" / "val"

    train_dst_img = DST_DATASET / "images" / "train"
    train_dst_lbl = DST_DATASET / "labels" / "train"
    val_dst_img = DST_DATASET / "images" / "val"
    val_dst_lbl = DST_DATASET / "labels" / "val"

    src_train_count, dst_train_count = build_train_split(train_src_img, train_src_lbl, train_dst_img, train_dst_lbl)
    dst_val_count = build_val_split(val_src_img, val_src_lbl, val_dst_img, val_dst_lbl)
    yaml_path = write_dataset_yaml(DST_DATASET)

    print("[DONE] Blur dataset ready")
    print(f"[DONE] Source train images: {src_train_count}")
    print(f"[DONE] Destination train images: {dst_train_count}")
    print(f"[DONE] Destination val images: {dst_val_count}")
    print(f"[DONE] Dataset YAML: {yaml_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
