"""
Posture Rules Evaluation Module
Evaluates worker ergonomic posture to mitigate musculoskeletal injury hazards.
"""

from typing import List, Tuple

POSTURE_VIOLATION_SCORE = 20

def evaluate_posture(posture_state: str, spine_angle: float = 0.0) -> Tuple[List[str], int, str, str]:
    """
    Evaluates worker posture.
    Returns:
        violations (list): list of triggered violation keys
        score_impact (int): risk points contributed (0 or 20)
        severity (str): SAFE, MEDIUM, or HIGH
        normalized_state (str): 'SAFE', 'WARNING', 'UNSAFE', or 'UNKNOWN'
    """
    state_upper = str(posture_state).upper() if posture_state else "SAFE"
    violations = []
    score_impact = 0

    if state_upper == "UNSAFE" or spine_angle > 35.0:
        violations.append("unsafe_posture")
        score_impact = POSTURE_VIOLATION_SCORE
        severity = "HIGH"
        normalized_state = "UNSAFE"
    elif state_upper == "WARNING" or (25.0 <= spine_angle <= 35.0):
        severity = "MEDIUM"
        normalized_state = "WARNING"
    elif state_upper == "UNKNOWN":
        severity = "SAFE"
        normalized_state = "UNKNOWN"
    else:
        severity = "SAFE"
        normalized_state = "SAFE"

    return violations, score_impact, severity, normalized_state
