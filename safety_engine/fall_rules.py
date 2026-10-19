"""
Fall Rules Evaluation Module
Evaluates slip, trip, and fall hazards with temporal state distinction.
Confirmed falls immediately escalate to CRITICAL emergency severity tier.
"""

from typing import List, Tuple, Any

FALL_VIOLATION_SCORE = 50

def evaluate_fall(fall_input: Any) -> Tuple[List[str], int, str, str, bool]:
    """
    Evaluates fall status.
    Accepts:
        bool: True (CONFIRMED_FALL) / False (NONE)
        str: 'NONE', 'POSSIBLE_FALL', 'CONFIRMED_FALL'

    Returns:
        violations (list): ['fall_detected'] if confirmed fall
        score_impact (int): 50 points if confirmed fall, 20 if possible fall
        severity (str): 'CRITICAL', 'MEDIUM', or 'SAFE'
        fall_status (str): 'NONE', 'POSSIBLE_FALL', 'CONFIRMED_FALL'
        is_emergency (bool): True if critical emergency override applies
    """
    if isinstance(fall_input, bool):
        fall_status = "CONFIRMED_FALL" if fall_input else "NONE"
    else:
        fall_status = str(fall_input).upper() if fall_input else "NONE"

    if fall_status == "CONFIRMED_FALL":
        return ["fall_detected"], FALL_VIOLATION_SCORE, "CRITICAL", fall_status, True
    elif fall_status == "POSSIBLE_FALL":
        return [], 20, "MEDIUM", fall_status, False
    else:
        return [], 0, "SAFE", "NONE", False
