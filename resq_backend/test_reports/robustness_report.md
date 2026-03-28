# ResQ Robustness Evaluation Report

- Scope: Test images in `resq_backend/test`
- Metric type: Proxy robustness vs original-image detections
- Modes: baseline vs adaptive blur-aware thresholding
- Important: This is not absolute ground-truth accuracy without labels

## Biggest F1 Improvements (Adaptive - Baseline)
- original: DeltaF1=0.0714 (baseline=0.9286, adaptive=1.0000), DeltaRecall=0.1333
- gaussian_noise: DeltaF1=0.0454 (baseline=0.8980, adaptive=0.9434), DeltaRecall=0.0467
- low_light: DeltaF1=0.0182 (baseline=0.9818, adaptive=1.0000), DeltaRecall=0.0000
- gaussian_blur: DeltaF1=0.0130 (baseline=0.7143, adaptive=0.7273), DeltaRecall=0.0158
- motion_blur: DeltaF1=0.0114 (baseline=0.7442, adaptive=0.7556), DeltaRecall=0.0145

## Biggest F1 Regressions
- motion_blur: DeltaF1=0.0114 (baseline=0.7442, adaptive=0.7556), DeltaRecall=0.0145
- salt_pepper: DeltaF1=0.0022 (baseline=0.9412, adaptive=0.9434), DeltaRecall=-0.0671
- high_contrast: DeltaF1=0.0000 (baseline=0.9630, adaptive=0.9630), DeltaRecall=0.0000
- high_light: DeltaF1=0.0000 (baseline=0.9630, adaptive=0.9630), DeltaRecall=0.0000
- low_contrast: DeltaF1=0.0000 (baseline=1.0000, adaptive=1.0000), DeltaRecall=0.0000

## Output Files
- `test_reports/accuracy_matrix_baseline.csv`
- `test_reports/accuracy_matrix_adaptive.csv`
- `test_reports/accuracy_matrix_comparison.csv`
- `test_reports/per_image_metrics_baseline.csv`
- `test_reports/per_image_metrics_adaptive.csv`
- `test_reports/augmented/baseline/` and `test_reports/augmented/adaptive/`
