"""
prepare_dataset.py

Utility to merge external datasets (VisDrone, COCO, Medetec) into the
unified ResQ combined dataset structure.

Expected output structure:
resq_backend/data/combined_dataset/
  ├── images/
  │   ├── train/
  │   └── val/
  ├── labels/
  │   ├── train/
  │   └── val/
  └── dataset.yaml

Classes:
0: person
1: wound
"""

import os
import shutil
from pathlib import Path

def merge_yolo_dataset(source_dir, split, class_map, output_base="data/combined_dataset"):
    """
    Copies images and updates label IDs from a source directory to the combined dataset.
    
    Args:
        source_dir: Path to the source dataset (e.g., 'data/visdrone/train')
        split: 'train' or 'val'
        class_map: Dictionary mapping original class IDs to new class IDs. 
                   e.g., if VisDrone 'pedestrian' is 1 and 'people' is 2, 
                   and we want them both to be 0: {1: 0, 2: 0}
                   If a key is not in class_map, that label line is ignored.
    """
    src_images = Path(source_dir) / "images"
    src_labels = Path(source_dir) / "labels"
    
    dest_images = Path(output_base) / "images" / split
    dest_labels = Path(output_base) / "labels" / split
    
    os.makedirs(dest_images, exist_ok=True)
    os.makedirs(dest_labels, exist_ok=True)
    
    if not src_images.exists() or not src_labels.exists():
        print(f"Warning: Source images/labels not found in {source_dir}")
        return
        
    for img_path in src_images.glob("*.*"):
        if img_path.suffix.lower() not in ['.jpg', '.jpeg', '.png']:
            continue
            
        label_path = src_labels / f"{img_path.stem}.txt"
        
        if not label_path.exists():
            continue
            
        # Parse label
        new_lines = []
        with open(label_path, 'r') as f:
            for line in f:
                parts = line.strip().split()
                if not parts: continue
                
                orig_cls = int(parts[0])
                if orig_cls in class_map:
                    new_cls = class_map[orig_cls]
                    new_line = f"{new_cls} " + " ".join(parts[1:]) + "\n"
                    new_lines.append(new_line)
                    
        # Only copy if there are valid labels
        if new_lines:
            dest_img_path = dest_images / img_path.name
            dest_txt_path = dest_labels / label_path.name
            
            # Use symlinks if possible, otherwise copy to save space
            if not dest_img_path.exists():
                 shutil.copy2(img_path, dest_img_path)
                 
            with open(dest_txt_path, 'w') as f:
                f.writelines(new_lines)
                
    print(f"Merged {source_dir} -> {split} with mapped classes.")

if __name__ == "__main__":
    print("Dataset mapping instructions:")
    print("1. Download VisDrone to data/visdrone")
    print("2. Download Medetec wounds (convert to YOLO) to data/medetec")
    print("3. Modify this script to call merge_yolo_dataset with the correct class maps.")
    
    # Example usage (uncomment and adjust paths once downloaded):
    
    # Visdrone mapping (assuming 0:pedestrian, 1:people -> map both to 0:person)
    # class_map_visdrone = {0: 0, 1: 0} 
    # merge_yolo_dataset('data/visdrone/train', 'train', class_map_visdrone)
    # merge_yolo_dataset('data/visdrone/val', 'val', class_map_visdrone)

    # Medetec mapping (assuming 0:wound in source -> map to 1:wound)
    # class_map_medetec = {0: 1}
    # merge_yolo_dataset('data/medetec/train', 'train', class_map_medetec)
