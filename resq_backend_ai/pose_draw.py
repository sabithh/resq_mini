import cv2
import numpy as np

SKELETON = [
    (5, 7), (7, 9),
    (6, 8), (8, 10),
    (5, 6),
    (11, 13), (13, 15),
    (12, 14), (14, 16),
    (11, 12),
    (5, 11), (6, 12)
]

def draw_skeleton(image, keypoints, conf_thresh=0.5):
    """
    SAFE skeleton drawing.
    Will NEVER crash.
    """

    # ---------- HARD VALIDATION ----------
    if keypoints is None:
        return False

    keypoints = np.asarray(keypoints)

    if keypoints.shape != (17, 3):
        return False

    drawn = False

    try:
        for p1, p2 in SKELETON:
            x1, y1, c1 = keypoints[p1]
            x2, y2, c2 = keypoints[p2]

            if (
                c1 > conf_thresh and c2 > conf_thresh and
                not np.isnan([x1, y1, x2, y2]).any()
            ):
                cv2.line(
                    image,
                    (int(x1), int(y1)),
                    (int(x2), int(y2)),
                    (0, 255, 255),
                    2
                )
                drawn = True
    except Exception as e:
        print("⚠️ Skeleton draw error:", e)
        return False

    # ---------- FALLBACK MARK ----------
    if not drawn:
        try:
            cx = int(np.nanmean(keypoints[:, 0]))
            cy = int(np.nanmean(keypoints[:, 1]))
            cv2.circle(image, (cx, cy), 5, (0, 0, 255), -1)
            drawn = True
        except Exception:
            pass

    return drawn
