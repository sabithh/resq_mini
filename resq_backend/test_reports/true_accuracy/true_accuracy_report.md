# True Accuracy Report (Labeled)

- Dataset: `D:\PROJECTS\ResQ\resq_backend\data\SARD\search-and-rescue\valid`
- Images evaluated: 200
- IoU threshold: 0.5

## Micro Metrics
- Baseline: Precision=0.708, Recall=0.3865, F1=0.5, mAP50=0.1885
- Adaptive: Precision=0.7105, Recall=0.3913, F1=0.5047, mAP50=0.1905
- Delta: Precision=0.0025, Recall=0.0048, F1=0.0047, mAP50=0.002

## Per Class
- person: baseline(F1=0.5178, AP50=0.3771) -> adaptive(F1=0.5226, AP50=0.3809)
- wound: baseline(F1=0.0, AP50=0.0) -> adaptive(F1=0.0, AP50=0.0)

## Output Files
- `test_reports/true_accuracy/true_accuracy_report.json`
- `test_reports/true_accuracy/true_accuracy_summary.csv`
- `test_reports/true_accuracy/true_accuracy_report.md`
