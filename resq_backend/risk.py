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

    # Pose + bleed-aware risk (exact policy requested):
    # - standing + no bleeding -> LOW
    # - standing + bleeding -> MEDIUM
    # - sitting -> MEDIUM
    # - sitting + bleeding -> HIGH
    # - lying (any) -> HIGH
    # - WOUND explicit -> HIGH
    raw_bleeding = bool(victim.get("bleeding", False))
    bleeding_conf = float(victim.get("bleeding_confidence", 0.0) or 0.0)

    # Pose-aware gating prevents weak color artifacts from escalating standing/sitting priority.
    if pose == "WOUND":
        bleeding = True
    elif pose == "standing":
        bleeding = raw_bleeding and bleeding_conf >= 0.68
    elif pose == "sitting":
        bleeding = raw_bleeding and bleeding_conf >= 0.58
    elif pose == "lying":
        bleeding = raw_bleeding and bleeding_conf >= 0.45
    else:
        bleeding = raw_bleeding and bleeding_conf >= 0.62

    if pose == "lying":
        risk = 0.9
    elif pose == "sitting":
        risk = 0.5 if not bleeding else 0.9
    elif pose == "standing":
        risk = 0.1 if not bleeding else 0.5
    elif pose == "WOUND":
        risk = 0.95
    elif pose == "collapsed":
        risk = 0.6
    else:  # unknown/fallback
        risk = 0.35

    # If effective bleeding is present (even if pose == standing/sitting), prefer urgency
    if bleeding:
        if pose == "standing":
            risk = max(risk, 0.5)
        elif pose == "sitting":
            risk = max(risk, 0.9)

    # Penalize uncertain pose classification slightly (non-wound/unknown) for edge cases.
    if not bleeding and pose not in ["WOUND", "lying"]:
        risk += (1.0 - max(0.0, min(pose_confidence, 1.0))) * 0.1

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

    # PriorityOverride rules (hard policy mapping).
    # Required behavior:
    # standing->LOW, standing+bleeding->MEDIUM
    # sitting->MEDIUM, sitting+bleeding->HIGH
    # lying or WOUND->HIGH
    if pose == "lying" or pose == "WOUND":
        priority = "HIGH"
    elif pose == "sitting" and bleeding:
        priority = "HIGH"
    elif pose == "sitting":
        priority = "MEDIUM"
    elif pose == "standing" and bleeding:
        priority = "MEDIUM"
    elif pose == "standing":
        priority = "LOW"
    elif pose == "collapsed":
        priority = "HIGH"
    else:
        # fallback to computed risk thresholds for non-standard poses
        if risk >= 0.62:
            priority = "HIGH"
        elif risk >= 0.33:
            priority = "MEDIUM"
        else:
            priority = "LOW"

    # Keep strict standing LOW mapping; only escalate unknown/other weak cases.
    if pose not in ["standing", "sitting", "lying", "WOUND"] and priority == "LOW" and (pose_confidence < 0.5 or confidence < 0.4):
        priority = "MEDIUM"

    victim["risk_score"] = round(risk, 3)
    victim["priority"] = priority
    return victim
