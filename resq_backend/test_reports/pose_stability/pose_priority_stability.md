# Pose/Priority Stability Report

This is a robustness consistency test (not absolute GT accuracy).

- Images evaluated: 120
- IoU threshold: 0.5

## Augmentation Summary
- low_light: match_rate=0.4026, pose_agreement=0.871, priority_agreement=0.871
- motion_blur: match_rate=0.2857, pose_agreement=0.9091, priority_agreement=0.9091
- gaussian_blur: match_rate=0.8961, pose_agreement=0.9275, priority_agreement=0.9275
- gaussian_noise: match_rate=0.0779, pose_agreement=1.0, priority_agreement=1.0

## Top Pose Flips
- standing -> lying: 7
- lying -> standing: 4

## Top Priority Flips
- MEDIUM -> HIGH: 7
- HIGH -> MEDIUM: 4
