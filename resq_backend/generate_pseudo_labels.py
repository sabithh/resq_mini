"""
generate_pseudo_labels.py

This script takes an aerial dataset that ONLY has bounding boxes (like VisDrone)
or no labels at all, and uses a pre-trained COCO pose model (yolov8m-pose.pt)
to generate YOLO-Pose formatted .txt files.

This is required because we need to train a model that understands BOTH
aerial perspectives (VisDrone) AND human keypoints (COCO). Co-training
requires all 'person' classes to have 17 keypoints.

Output Format (YOLO Pose):
<class_id> <x_center> <y_center> <width> <height> <px1> <py1> <vis1> ... <px17> <py17> <vis17>
"""

import os
import cv2
from pathlib import Path
from ultralytics import YOLO

def generate_keypoint_labels(image_dir, output_label_dir, model_path="yolov8m-pose.pt", conf_thresh=0.25):
    """
    Runs the pose model on all images in image_dir and writes YOLO-pose
    annotation files to output_label_dir.
    """
    image_dir = Path(image_dir)
    output_label_dir = Path(output_label_dir)
    os.makedirs(output_label_dir, exist_ok=True)
    
    # Load the COCO-trained pose model
    print(f"Loading pose model from {model_path}...")
    model = YOLO(model_path)
    
    valid_extensions = {'.jpg', '.jpeg', '.png'}
    image_files = [f for f in image_dir.rglob('*') if f.suffix.lower() in valid_extensions]
    
    print(f"Found {len(image_files)} images. Beginning pseudo-labeling...")
    
    success_count = 0
    
    for img_path in image_files:
        # Run inference
        results = model(img_path, conf=conf_thresh, verbose=False)
        result = results[0]
        
        # Prepare the output .txt path
        # If the image is in nested folders, flatten or recreate structure
        # Here we assume a flat folder for simplicity
        label_path = output_label_dir / f"{img_path.stem}.txt"
        
        lines = []
        
        # Check if any people/keypoints were found
        if result.boxes is not None and result.keypoints is not None:
            boxes = result.boxes.xywhn.cpu().numpy() # normalized xywh
            kpts_data = result.keypoints.data.cpu().numpy() # [N, 17, 3] (x, y, conf)
            
            # Get image dimensions for normalizing keypoints
            img_h, img_w = result.orig_shape
            
            for i in range(len(boxes)):
                # Class 0 is person
                cls_id = 0 
                
                # Bounding box (normalized)
                x_center, y_center, w, h = boxes[i]
                
                # Format the base bounding box string
                line = f"{cls_id} {x_center:.6f} {y_center:.6f} {w:.6f} {h:.6f}"
                
                # Get the 17 keypoints for this person
                person_kpts = kpts_data[i] if kpts_data.ndim == 3 else kpts_data
                
                # Append each keypoint (normalized x, normalized y, visibility)
                for j in range(17):
                    kx_px, ky_px, k_conf = person_kpts[j]
                    
                    # Normalize keypoint coordinates
                    kx_norm = kx_px / img_w
                    ky_norm = ky_px / img_h
                    
                    # Visibility flag (YOLO expects 1=occluded/unlabeled, 2=visible)
                    # We map YOLOv8's continuous confidence to visibility flags
                    vis = 2 if k_conf > 0.3 else (1 if k_conf > 0.0 else 0)
                    
                    # If visibility is 0, YOLO expects coordinates to be 0
                    if vis == 0:
                        kx_norm, ky_norm = 0.0, 0.0
                        
                    line += f" {kx_norm:.6f} {ky_norm:.6f} {vis}"
                    
                lines.append(line + "\n")
        
        # Write to file even if empty, so we know the image was processed
        # (YOLO treats empty txt files as background images)
        with open(label_path, 'w') as f:
            f.writelines(lines)
            
        if lines:
            success_count += 1
            
        if success_count % 100 == 0 and success_count > 0:
            print(f"Processed {success_count} images with human detections...")

    print(f"\nFinished! Generated keypoint labels for {success_count} images.")
    print(f"Labels saved to: {output_label_dir}")

if __name__ == "__main__":
    # --- Instructions ---
    # 1. Point `images_source` to your unzipped VisDrone (or other UAV) train images.
    # 2. Point `labels_destination` to where you want the new keypoint text files to go.
    
    # Example usage:
    # images_source = "data/visdrone/images/train"
    # labels_destination = "data/combined_dataset/labels/train"
    # generate_keypoint_labels(images_source, labels_destination, model_path="yolov8m-pose.pt")
    pass