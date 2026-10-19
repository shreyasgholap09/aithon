"""
Danger-Zone Rules Evaluation Module
Evaluates worker boundary containment in automated machinery and robotic perimeters.
"""

from typing import List, Tuple, Dict, Any

DANGER_ZONE_SCORE = 35

def evaluate_zone(danger_zone_input: Any, location_name: str = "") -> Tuple[List[str], int, str, Dict[str, Any]]:
    """
    Evaluates worker boundary violation.
    Accepts:
        bool: True (entered) / False
        dict: {"entered": bool, "zone_id": str, "zone_name": str}

    Returns:
        violations (list): ['danger_zone_entry'] if inside prohibited zone
        score_impact (int): 35 points if inside prohibited zone
        severity (str): 'HIGH' if breach, else 'SAFE'
        zone_info (dict): standardized danger_zone payload
    """
    if isinstance(danger_zone_input, bool):
        entered = danger_zone_input
        zone_id = "ZONE_RESTRICTED" if entered else ""
        zone_name = location_name or "Restricted Hazard Perimeter"
    elif isinstance(danger_zone_input, dict):
        entered = bool(danger_zone_input.get("entered", False))
        zone_id = str(danger_zone_input.get("zone_id", "ZONE_RESTRICTED"))
        zone_name = str(danger_zone_input.get("zone_name", location_name or "Hazard Perimeter"))
    else:
        entered = False
        zone_id = ""
        zone_name = ""

    zone_info = {
        "entered": entered,
        "zone_id": zone_id,
        "zone_name": zone_name
    }

    if entered:
        return ["danger_zone_entry"], DANGER_ZONE_SCORE, "HIGH", zone_info
    return [], 0, "SAFE", zone_info
