"""
thermal_processor.py

ResQ – Thermal Image Preprocessing Module

Prepares thermal/infrared camera images for YOLOv8 detection.
Thermal images often have very low contrast or unusual colormaps;
this module normalises them into a 3-channel image YOLO can work with.
"""

import cv2
import numpy as np


def preprocess(image: np.ndarray, mode: str = "clahe") -> np.ndarray:
    """
    Preprocess a thermal image for better YOLO detection.

    Args:
        image  : BGR numpy array (as loaded by cv2)
        mode   : one of "raw" | "clahe" | "false_color"

    Returns:
        Processed BGR numpy array, same HxW, 3-channel.
    """

    if mode == "raw":
        return image

    elif mode == "clahe":
        return _apply_clahe(image)

    elif mode == "false_color":
        return _normalize_false_color(image)

    else:
        return _apply_clahe(image)  # default


# --------------------------------------------------
# CLAHE – best for grayscale / near-IR images
# --------------------------------------------------

def _apply_clahe(image: np.ndarray) -> np.ndarray:
    """
    CLAHE (Contrast Limited Adaptive Histogram Equalization).
    Dramatically improves edges and outlines in low-contrast thermal imagery.
    Works on each channel independently then merges.
    """
    # Convert to grayscale then equalise, then back to BGR so YOLO gets 3 channels
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    eq = clahe.apply(gray)

    # Stack to 3-channel BGR
    rgb_eq = cv2.cvtColor(eq, cv2.COLOR_GRAY2BGR)
    return rgb_eq


# --------------------------------------------------
# FALSE-COLOR NORMALISE – for FLIR rainbow/iron palette images
# --------------------------------------------------

def _normalize_false_color(image: np.ndarray) -> np.ndarray:
    """
    Strips the false-color palette and re-maps to a clean high-contrast
    grayscale-to-BGR representation that YOLO handles better.

    Approach:
    1. Convert false-color FLIR image to HSV
    2. Extract the Value channel (intensity / heat proxy)
    3. Apply CLAHE on Value channel
    4. Convert back to BGR
    """
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    h, s, v = cv2.split(hsv)

    clahe = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(8, 8))
    v_eq = clahe.apply(v)

    # Recompose with desaturated hue (makes it more uniform for YOLO)
    s_flat = np.zeros_like(s)
    merged = cv2.merge([h, s_flat, v_eq])
    result = cv2.cvtColor(merged, cv2.COLOR_HSV2BGR)
    return result


# --------------------------------------------------
# UTILITY: save a side-by-side comparison image
# --------------------------------------------------

def make_comparison(original: np.ndarray, processed: np.ndarray) -> np.ndarray:
    """
    Joins original and processed images side by side for the dashboard preview.
    Both images are resized to the same height before joining.
    """
    h = max(original.shape[0], processed.shape[0])

    def _resize_h(img, target_h):
        ratio = target_h / img.shape[0]
        return cv2.resize(img, (int(img.shape[1] * ratio), target_h))

    left = _resize_h(original, h)
    right = _resize_h(processed, h)

    divider = np.full((h, 4, 3), (0, 255, 255), dtype=np.uint8)  # cyan divider

    return np.hstack([left, divider, right])
