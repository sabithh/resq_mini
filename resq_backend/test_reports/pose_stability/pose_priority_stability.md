# Pose/Priority Stability Report

This is a robustness consistency test (not absolute GT accuracy).

- Images evaluated: 120
- IoU threshold: 0.5

## Augmentation Summary
- gaussian_noise: match_rate=0.6056, pose_agreement=0.8372, priority_agreement=0.814
- gaussian_blur: match_rate=0.8028, pose_agreement=0.8596, priority_agreement=0.8596
- motion_blur: match_rate=0.7183, pose_agreement=0.8627, priority_agreement=0.8431
- low_light: match_rate=0.7183, pose_agreement=0.9608, priority_agreement=0.902

## Top Pose Flips
- lying -> standing: 16
- standing -> sitting: 4
- standing -> lying: 3
- sitting -> standing: 1

## Top Priority Flips
- HIGH -> LOW: 16
- LOW -> HIGH: 6
- LOW -> MEDIUM: 5
- MEDIUM -> LOW: 1
- HIGH -> MEDIUM: 1
