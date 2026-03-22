import numpy as np
import pickle
from pose_classifier import PoseClassifier
import warnings
warnings.filterwarnings('ignore')

with open('pose_classifier.pkl', 'rb') as f:
    bundle = pickle.load(f)
model = bundle['model']
scaler = bundle['scaler']

# STANDING: vertical box
k_st = np.zeros((17, 3))
k_st[:, 0] = 25
k_st[:, 1] = np.linspace(10, 90, 17)
k_st[:, 2] = 0.9
f_st = PoseClassifier.extract_geometric_features(k_st, 50, 100)
print('Stand predict (relative kpts, vertical):', model.predict(scaler.transform([f_st]))[0])

# LYING: horizontal box
k_ly = np.zeros((17, 3))
k_ly[:, 0] = np.linspace(10, 190, 17)
k_ly[:, 1] = 25
k_ly[:, 2] = 0.9
f_ly = PoseClassifier.extract_geometric_features(k_ly, 200, 50)
print('Lying predict (relative kpts, horizontal):', model.predict(scaler.transform([f_ly]))[0])

# STANDING: absolute coords (untouched)
k_sta = np.zeros((17, 3))
k_sta[:, 0] = 1025
k_sta[:, 1] = np.linspace(1010, 1090, 17)
k_sta[:, 2] = 0.9
f_sta = PoseClassifier.extract_geometric_features(k_sta, 50, 100)
print('Stand predict (absolute kpts, vertical):', model.predict(scaler.transform([f_sta]))[0])

# LYING: absolute coords (untouched)
k_lya = np.zeros((17, 3))
k_lya[:, 0] = np.linspace(1010, 1190, 17)
k_lya[:, 1] = 1025
k_lya[:, 2] = 0.9
f_lya = PoseClassifier.extract_geometric_features(k_lya, 200, 50)
print('Lying predict (absolute kpts, horizontal):', model.predict(scaler.transform([f_lya]))[0])
