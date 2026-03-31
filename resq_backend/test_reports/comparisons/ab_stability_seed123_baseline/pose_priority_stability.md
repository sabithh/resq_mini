# Pose/Priority Stability Report

This is a robustness consistency test (not absolute GT accuracy).

- Images evaluated: 120
- IoU threshold: 0.5

## Augmentation Summary
- motion_blur: match_rate=0.7183, pose_agreement=0.902, priority_agreement=0.7255
- gaussian_blur: match_rate=0.8028, pose_agreement=0.9649, priority_agreement=0.7368
- gaussian_noise: match_rate=0.5915, pose_agreement=0.9762, priority_agreement=0.8095
- low_light: match_rate=0.7324, pose_agreement=1.0, priority_agreement=0.9231

## Top Pose Flips
- standing -> sitting: 2
- standing -> lying: 2
- lying -> standing: 2
- lying -> sitting: 1
- sitting -> standing: 1

## Top Priority Flips
- MEDIUM -> LOW: 19
- LOW -> MEDIUM: 13
- HIGH -> MEDIUM: 5
- MEDIUM -> HIGH: 2
- LOW -> HIGH: 2
