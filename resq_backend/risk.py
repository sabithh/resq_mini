"""
risk.py

Pose-aware risk assessment module for ResQ Drone system.

Logic goals:
- LOW  → clearly safe, standing, good visibility
- MEDIUM → uncertain, cluttered, partial visibility
- HIGH → lying / collapsed / high-risk posture
"""

def compute_risk(victim: dict) -> dict:
    area = victim["area"]
    confidence = victim["confidence"]
    pose = victim.get("pose", "unknown")

    risk = 0.0

    # Pose-based risk (MOST IMPORTANT)
    if pose == "lying":
        risk += 0.6
    elif pose == "unknown":
        risk += 0.2

    # Area-based (small = far / buried)
    if area < 15000:
        risk += 0.3
    elif area < 30000:
        risk += 0.15

    # Confidence-based
    risk += (1 - confidence) * 0.2

    # Clamp
    risk = min(risk, 1.0)

    if risk >= 0.7:
        priority = "HIGH"
    elif risk >= 0.4:
        priority = "MEDIUM"
    else:
        priority = "LOW"

    victim["risk_score"] = round(risk, 3)
    victim["priority"] = priority
    return victim
