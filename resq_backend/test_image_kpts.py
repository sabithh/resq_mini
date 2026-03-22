import cv2
import numpy as np
import sys
from detector import Detector
import warnings
warnings.filterwarnings('ignore')

img_path = r'C:\Users\mxsab\.gemini\antigravity\brain\47048f4c-e59b-4546-9852-8f13e532b6f6\media__1774159797232.jpg'
img = cv2.imread(img_path)
if img is not None:
    print(f"Loaded image: {img.shape}")
    det = Detector()
    results = det.detect(img)
    for r in results:
        print(f"ID: {r.get('id')}, pose: {r.get('pose')}, bbox: {r.get('bbox_xyxy')}, aspect: {r.get('aspect_ratio')}")
else:
    print('Failed to load image')
