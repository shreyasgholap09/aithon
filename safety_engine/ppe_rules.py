"""
PPE Rules Evaluation Module
Evaluates Personal Protective Equipment compliance (Head protection and High-Visibility Vest).
Distinguishes verified compliant, verified missing, and unverified/unknown states.
"""

from typing import Dict, Any, List, Tuple

# Configurable violation scores
HELMET_VIOLATION_SCORE = 25
VEST_VIOLATION_SCORE = 20

def evaluate_ppe(ppe_detections: Dict[str, Any]) -> Tuple[List[str], int, str, Dict[str, Any]]:
    """
    Evaluates helmet and vest compliance.
    Supports both structured format:
      {"helmet": {"status": "PRESENT"|"MISSING"|"UNKNOWN", "confidence": float}}
    and legacy boolean format:
      {"helmet": True, "vest": False}

    Returns:
        violations (list): list of violation string keys
        score_impact (int): risk points contributed (0 to 45)
        severity (str): SAFE, LOW, MEDIUM, or HIGH
        normalized_ppe (dict): standardized PPE status object
    """
    violations = []
    score_impact = 0

    normalized_ppe = {}
    for item in ("helmet", "vest"):
        raw = ppe_detections.get(item, {"status": "UNKNOWN", "confidence": 0.5})
        if isinstance(raw, bool):
            status = "PRESENT" if raw else "MISSING"
            confidence = 0.90
        elif isinstance(raw, dict):
            status = str(raw.get("status", "UNKNOWN")).upper()
            confidence = float(raw.get("confidence", 0.5))
        elif isinstance(raw, str):
            status = raw.upper()
            confidence = 0.85
        else:
            status = "UNKNOWN"
            confidence = 0.0

        normalized_ppe[item] = {"status": status, "confidence": round(confidence, 2)}

    # Helmet evaluation
    if normalized_ppe["helmet"]["status"] == "MISSING":
        violations.append("helmet_missing")
        score_impact += HELMET_VIOLATION_SCORE

    # Vest evaluation
    if normalized_ppe["vest"]["status"] == "MISSING":
        violations.append("vest_missing")
        score_impact += VEST_VIOLATION_SCORE

    # Severity tier from PPE alone
    if len(violations) >= 2:
        severity = "HIGH"
    elif len(violations) == 1:
        severity = "MEDIUM" if "helmet_missing" in violations else "LOW"
    else:
        severity = "SAFE"

    return violations, score_impact, severity, normalized_ppe
