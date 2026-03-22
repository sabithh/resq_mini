"""
finetune_aerial.py

ResQ — Fine-tune YOLOv8 on aerial/drone datasets for improved person detection.

Supported datasets:
  - VisDrone-DET  (auto-downloaded by Ultralytics)
  - SARD          (manual download, YOLO format)
  - C2A           (Kaggle, YOLO format)

Usage:
  # Quick start — fine-tune on VisDrone (auto-download ~3 GB)
  python finetune_aerial.py

  # Custom dataset folder (must have YOLO format)
  python finetune_aerial.py --data path/to/dataset.yaml

  # Validate only (skip training)
  python finetune_aerial.py --validate --weights yolov8m-aerial.pt

GPU recommended (8 GB+ VRAM). For CPU or Colab see README.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# ── Defaults ────────────────────────────────────────────
DEFAULT_BASE_MODEL   = "yolov8m.pt"
DEFAULT_OUTPUT_NAME  = "yolov8m-aerial"
DEFAULT_EPOCHS       = 50
DEFAULT_BATCH        = 8
DEFAULT_IMG_SIZE     = 640
DEFAULT_PATIENCE     = 10


def build_visdrone_yaml() -> str:
    """Return the built-in Ultralytics VisDrone dataset descriptor.

    Ultralytics ships with a ready-made 'VisDrone.yaml' that auto-downloads
    the dataset on first use.  We wrap it here so the user doesn't need
    to locate it manually.
    """
    return "VisDrone.yaml"


def build_combined_yaml(extra_dirs: list[str], output_path: str = "aerial_combined.yaml") -> str:
    """Create a merged YAML config pointing to multiple YOLO-format dataset dirs.

    Each dir must follow the standard layout:
      dir/
        images/train/  images/val/
        labels/train/  labels/val/

    The generated YAML uses Ultralytics multi-path syntax.
    """
    import yaml

    train_paths = []
    val_paths   = []

    for d in extra_dirs:
        p = Path(d)
        ti = p / "images" / "train"
        vi = p / "images" / "val"
        if ti.exists():
            train_paths.append(str(ti.resolve()))
        if vi.exists():
            val_paths.append(str(vi.resolve()))

    if not train_paths:
        print("[finetune] ERROR: No valid train image dirs found in extra_dirs.")
        sys.exit(1)

    cfg = {
        "train": train_paths if len(train_paths) > 1 else train_paths[0],
        "val":   val_paths   if len(val_paths)   > 1 else (val_paths[0] if val_paths else train_paths[0]),
        "nc":    1,
        "names": ["person"],
    }

    with open(output_path, "w") as f:
        yaml.dump(cfg, f, default_flow_style=False)

    print(f"[finetune] Combined dataset YAML written to {output_path}")
    return output_path


def train(args):
    from ultralytics import YOLO

    model = YOLO(args.base_model)
    print(f"[finetune] Base model : {args.base_model}")
    print(f"[finetune] Dataset    : {args.data}")
    print(f"[finetune] Epochs     : {args.epochs}")
    print(f"[finetune] Batch size : {args.batch}")
    print(f"[finetune] Image size : {args.imgsz}")

    # ── Train ───────────────────────────────────────────
    results = model.train(
        data=args.data,
        epochs=args.epochs,
        batch=args.batch,
        imgsz=args.imgsz,
        patience=args.patience,
        name=args.output_name,
        project="runs/aerial",
        exist_ok=True,
        # Aerial-optimised augmentations
        augment=True,
        mosaic=1.0,              # helpful for small-object aerial scenes
        mixup=0.15,
        scale=0.7,               # aggressive scale jitter for altitude sim
        fliplr=0.5,
        flipud=0.2,              # overhead images can be upside-down
        degrees=15.0,            # slight rotation for angled drone shots
        hsv_h=0.015,
        hsv_s=0.5,
        hsv_v=0.3,
        # Filter to person class only (class 0 in COCO / VisDrone "pedestrian")
        classes=[0],
        verbose=True,
    )

    # ── Save best weights next to this script ───────────
    best_pt = Path("runs") / "aerial" / args.output_name / "weights" / "best.pt"
    dst     = Path(__file__).parent / f"{args.output_name}.pt"
    if best_pt.exists():
        import shutil
        shutil.copy2(best_pt, dst)
        print(f"\n[finetune] ✅ Best model saved → {dst}")
    else:
        print("[finetune] ⚠️  best.pt not found — check runs/aerial/ for results.")

    return results


def validate(args):
    from ultralytics import YOLO

    weights = args.weights or str(Path(__file__).parent / f"{args.output_name}.pt")
    print(f"[validate] Evaluating {weights} on {args.data}")

    model   = YOLO(weights)
    metrics = model.val(data=args.data, imgsz=args.imgsz, batch=args.batch)

    print(f"\n[validate] mAP50    : {metrics.box.map50:.4f}")
    print(f"[validate] mAP50-95 : {metrics.box.map:.4f}")
    return metrics


# ── CLI ─────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(description="Fine-tune YOLOv8 for aerial person detection")

    p.add_argument("--data",        default=None,
                   help="Dataset YAML path (default: VisDrone.yaml auto-download)")
    p.add_argument("--extra-dirs",  nargs="*", default=[],
                   help="Extra dataset dirs (YOLO format) to merge with VisDrone")
    p.add_argument("--base-model",  default=DEFAULT_BASE_MODEL,
                   help="Base YOLO weights to start from")
    p.add_argument("--output-name", default=DEFAULT_OUTPUT_NAME)
    p.add_argument("--epochs",      type=int, default=DEFAULT_EPOCHS)
    p.add_argument("--batch",       type=int, default=DEFAULT_BATCH)
    p.add_argument("--imgsz",       type=int, default=DEFAULT_IMG_SIZE)
    p.add_argument("--patience",    type=int, default=DEFAULT_PATIENCE)
    p.add_argument("--validate",    action="store_true",
                   help="Run validation only (skip training)")
    p.add_argument("--weights",     default=None,
                   help="Weights file for --validate mode")

    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()

    # Resolve dataset
    if args.data is None:
        if args.extra_dirs:
            args.data = build_combined_yaml(args.extra_dirs)
        else:
            args.data = build_visdrone_yaml()

    if args.validate:
        validate(args)
    else:
        train(args)
        print("\n[finetune] Done.  Use the trained model in ResQ:")
        print(f"  export DETECTION_MODEL={args.output_name}.pt")
        print("  python app.py")
