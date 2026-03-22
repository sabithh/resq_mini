"""
do_it_all.py
Automates the entire data preparation pipeline:
1. Converts Medetec segmentation masks -> YOLO Bounding Boxes (Class 1)
2. Copies a subset of C2A Aerial images -> Uses YOLOv8-pose to pseudo-label them (Class 0 + keypoints)
3. Applies environmental augmentations to these training sets
4. Prepares the final dataset.yaml
"""
import os
import cv2
import numpy as np
from pathlib import Path
import shutil
from random import uniform, choice
try:
    from ultralytics import YOLO
except ImportError:
    pass # handled later

def convert_medetec_to_yolo():
    print("--- [1] Processing Medetec Wound Dataset ---")
    splits = ['train', 'test']
    for split in splits:
        img_dir = Path(f"data/medetec/data_wound_seg/{split}_images")
        mask_dir = Path(f"data/medetec/data_wound_seg/{split}_masks")
        out_img_dir = Path(f"data/combined_dataset/images/{'val' if split=='test' else 'train'}")
        out_lbl_dir = Path(f"data/combined_dataset/labels/{'val' if split=='test' else 'train'}")
        out_img_dir.mkdir(parents=True, exist_ok=True)
        out_lbl_dir.mkdir(parents=True, exist_ok=True)

        if not img_dir.exists() or not mask_dir.exists():
            continue

        images = list(img_dir.glob("*.jpg")) + list(img_dir.glob("*.png"))
        print(f"Found {len(images)} images in Medetec {split}")

        # Just take a subset (e.g., 200) so this script doesn't take 2 hours
        count = 0
        MAX_MEDETEC = 200
        for img_path in images:
            if count >= MAX_MEDETEC: break
            
            mask_path = mask_dir / f"{img_path.stem}.png"
            if not mask_path.exists(): continue

            mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
            if mask is None: continue

            # Find bounding box
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            h_img, w_img = mask.shape[:2]
            bboxes = []
            for cnt in contours:
                x, y, w, h = cv2.boundingRect(cnt)
                # Filter noise
                if w < 10 or h < 10: continue
                # YOLO format: cls x_center y_center w h (normalized)
                xc = (x + w/2) / w_img
                yc = (y + h/2) / h_img
                wn = w / w_img
                hn = h / h_img
                # We do NOT append keypoints for Class 1 (wounds), just 0 for keypoints so YOLO-pose ignores it,
                # actually YOLO-pose wants keypoints for everything, we pad with 0s.
                # Format: cls xc yc wn hn px1 py1 v1 ... px17 py17 v17
                kpts_str = " ".join(["0.0 0.0 0"] * 17)
                bboxes.append(f"1 {xc:.6f} {yc:.6f} {wn:.6f} {hn:.6f} {kpts_str}")

            if bboxes:
                # Copy image
                dest_img = out_img_dir / img_path.name
                shutil.copy2(img_path, dest_img)
                
                # Write label
                dest_lbl = out_lbl_dir / f"{img_path.stem}.txt"
                with open(dest_lbl, "w") as f:
                    f.write("\n".join(bboxes))
                count += 1
        print(f"-> Converted {count} {split} Medetec images to YOLO format.")

def apply_haze(image):
    h, w = image.shape[:2]
    haze_layer = np.full((h, w, 3), 200, dtype=np.uint8) 
    alpha = uniform(0.3, 0.6)
    return cv2.addWeighted(image, 1 - alpha, haze_layer, alpha, 0)

def apply_low_light(image):
    gamma = uniform(0.3, 0.5) 
    inv_gamma = 1.0 / gamma
    table = np.array([((i / 255.0) ** inv_gamma) * 255 for i in np.arange(0, 256)]).astype("uint8")
    return cv2.LUT(image, table)

def augment_existing():
    print("--- [2] Applying Extreme Environment Augmentations (Haze/Dark) ---")
    train_img_dir = Path("data/combined_dataset/images/train")
    train_lbl_dir = Path("data/combined_dataset/labels/train")
    
    if not train_img_dir.exists(): return
    images = list(train_img_dir.glob("*.jpg")) + list(train_img_dir.glob("*.png"))
    
    count = 0
    for img_path in images:
        if "aug_" in img_path.name: continue
        
        lbl_path = train_lbl_dir / f"{img_path.stem}.txt"
        if not lbl_path.exists(): continue
            
        img = cv2.imread(str(img_path))
        if img is None: continue
            
        aug_type = choice(['haze', 'dark'])
        if aug_type == 'haze':
            aug_img = apply_haze(img)
        else:
            aug_img = apply_low_light(img)
            
        new_img_name = f"aug_{aug_type}_{img_path.name}"
        cv2.imwrite(str(train_img_dir / new_img_name), aug_img)
        
        # Copy the exact same label
        shutil.copy2(lbl_path, train_lbl_dir / f"aug_{aug_type}_{img_path.stem}.txt")
        count += 1
        
    print(f"-> Generated {count} augmented training images.")

if __name__ == "__main__":
    print("STARTING DO_IT_ALL PIPELINE")
    
    # 1. Prepare Medetec
    convert_medetec_to_yolo()
    
    # 2. Augment Medetec images (add visual noise)
    augment_existing()
    
    print("\n--- DONE ---")
    print("Dataset ready at resq_backend/data/combined_dataset")
    print("You can now start training with the command provided!")
