"""
risk.py

Pose-aware risk assessment module for ResQ Drone system.

Logic goals:
- LOW    → clearly safe, standing, good visibility
- MEDIUM → uncertain, cluttered, seated, partial visibility
- HIGH   → lying / collapsed / high-risk posture
"""

from collections import defaultdict, deque

# History keyed by (drone_id, victim_id) -> deque of recent risk scores
_risk_history = defaultdict(lambda: deque(maxlen=10))

def compute_risk(victim: dict, drone_id: str = "DEFAULT", frame_width: int = None, frame_height: int = None) -> dict:
    area = victim["area"]
    confidence = victim["confidence"]
    pose = victim.get("pose", "unknown")
    pose_confidence = float(victim.get("pose_confidence", 0.0) or 0.0)
    aspect_ratio = victim.get("aspect_ratio", 0.0)

    # Aspect Ratio Fallback for Unknown Poses
    if pose == "unknown" and aspect_ratio > 1.5:
        pose = "lying"
        victim["pose"] = pose  # Update so the dashboard shows 'lying'

    risk = 0.0

    # Pose-based risk (MOST IMPORTANT)
    if pose == "lying":
        risk += 0.7  # Increased to ensure high priority
    elif pose in ["sitting", "collapsed"]: # Adding collapsed just in case
        risk += 0.4
    elif pose == "WOUND":
        risk += 0.9  # Wounds are critical!
    elif pose == "unknown":
        risk += 0.2

    # Penalize uncertain pose classification slightly.
    # This helps elevate ambiguous cases into MEDIUM instead of LOW.
    if pose != "WOUND":
        risk += (1.0 - max(0.0, min(pose_confidence, 1.0))) * 0.12

    # Area-based (small = far / buried)
    # Prefer frame-relative area so behavior is consistent across resolutions.
    frame_area = (frame_width * frame_height) if (frame_width and frame_height) else None
    if frame_area and frame_area > 0:
        area_ratio = area / float(frame_area)
        if area_ratio < 0.005:
            risk += 0.3
        elif area_ratio < 0.02:
            risk += 0.15
    else:
        if area < 12000:
            risk += 0.3
        elif area < 25000:
            risk += 0.15

    # Confidence-based (low confidence = harder to see = potential danger)
    risk += (1 - confidence) * 0.15

    # Clamp
    risk = min(risk, 1.0)

    # Temporal smoothing
    vid = victim.get("id")
    if vid is not None:
        history = _risk_history[(drone_id, vid)]
        history.append(risk)
        smoothed_risk = sum(history) / len(history)
        risk = smoothed_risk

    if risk >= 0.62:
        priority = "HIGH"
    elif risk >= 0.33:
        priority = "MEDIUM"
    else:
        priority = "LOW"

    victim["risk_score"] = round(risk, 3)
    victim["priority"] = priority
    return victim
