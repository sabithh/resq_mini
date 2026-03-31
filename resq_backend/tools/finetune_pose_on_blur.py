"""
Fine-tune YOLO pose model on blur-augmented dataset.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ultralytics import YOLO


BASE_DIR = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description="Fine-tune pose model for blur robustness")
    parser.add_argument("--model", type=str, default="yolov8m-pose.pt", help="Base pose model path")
    parser.add_argument(
        "--data",
        type=str,
        default=str((BASE_DIR / "data" / "combined_dataset_blur" / "dataset_blur.yaml").as_posix()),
        help="Dataset yaml path",
    )
    parser.add_argument("--epochs", type=int, default=20, help="Training epochs")
    parser.add_argument("--imgsz", type=int, default=960, help="Image size")
    parser.add_argument("--batch", type=int, default=8, help="Batch size")
    parser.add_argument("--device", type=str, default="", help="Device id, e.g. 0 or cpu")
    parser.add_argument("--workers", type=int, default=4, help="Data loader workers")
    parser.add_argument("--fraction", type=float, default=1.0, help="Fraction of dataset to use (0, 1]")
    parser.add_argument("--project", type=str, default="runs/pose_blur", help="Output project directory")
    parser.add_argument("--name", type=str, default="finetune", help="Run name")
    args = parser.parse_args()

    model_path = Path(args.model)
    if not model_path.is_absolute():
        model_path = BASE_DIR / args.model

    data_path = Path(args.data)
    if not data_path.is_absolute():
        data_path = BASE_DIR / args.data

    if not data_path.exists():
        print(f"[ERROR] Dataset YAML not found: {data_path}")
        return 1

    if not model_path.exists() and args.model.endswith(".pt"):
        # allow ultralytics to download known base models by filename
        model_ref = args.model
    else:
        model_ref = str(model_path)

    model = YOLO(model_ref)

    device_arg = args.device if args.device else None
    model.train(
        data=str(data_path),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        workers=args.workers,
        project=args.project,
        name=args.name,
        device=device_arg,
        fraction=max(0.05, min(args.fraction, 1.0)),
        close_mosaic=10,
        degrees=0.0,
        shear=0.0,
        perspective=0.0,
        fliplr=0.2,
    )

    print("[DONE] Blur fine-tuning completed")
    print(f"[DONE] Check weights in: {args.project}/{args.name}/weights")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
