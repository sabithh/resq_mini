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

def compute_risk(victim: dict, drone_id: str = "DEFAULT") -> dict:
    # --- HYBRID AI OVERRIDE ---
    if "override_priority" in victim:
        victim["priority"] = victim["override_priority"]
        victim["risk_score"] = victim.get("override_risk", 0.9)
        return victim

    area = victim["area"]
    confidence = victim["confidence"]
    pose = victim.get("pose", "unknown")
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

    # Area-based (small = far / buried)
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

    if risk >= 0.65:
        priority = "HIGH"
    elif risk >= 0.35:
        priority = "MEDIUM"
    else:
        priority = "LOW"

    victim["risk_score"] = round(risk, 3)
    victim["priority"] = priority
    return victim
