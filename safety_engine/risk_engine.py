"""
Authoritative Risk Engine Module
Computes deterministic heuristic safety risk scores, evaluates categorical severity tiers,
and coordinates the incident lifecycle.

Scoring Policy:
- Missing Helmet: +25 pts
- Missing Vest:   +20 pts
- Unsafe Posture: +20 pts
- Danger Zone:    +35 pts
- Fall Detected:  +50 pts (Triggers automatic CRITICAL severity override)

Severity Thresholds:
- 0:       SAFE
- 1–30:    LOW
- 31–60:   MEDIUM
- 61–100:  HIGH
- Confirmed Fall: CRITICAL override
"""

from datetime import datetime, timezone
import uuid
from typing import Any, Dict, List, Optional, Tuple

from .ppe_rules import evaluate_ppe
from .posture_rules import evaluate_posture
from .fall_rules import evaluate_fall
from .zone_rules import evaluate_zone
from .alert_manager import AlertManager

class RiskEngine:
    def __init__(
        self,
        alert_manager: Optional[AlertManager] = None,
        weights: Optional[Dict[str, int]] = None
    ):
        self.alert_manager = alert_manager or AlertManager()
        self.weights = weights or {
            "helmet_missing": 25,
            "vest_missing": 20,
            "unsafe_posture": 20,
            "danger_zone_entry": 35,
            "fall_detected": 50
        }

    def assess_worker(
        self,
        worker_id: str,
        location: str,
        ppe: Dict[str, Any],
        posture: Any = "SAFE",
        fall_input: Any = "NONE",
        danger_zone_input: Any = False,
        spine_angle: float = 0.0,
        confidence: float = 0.90,
        source: str = "LIVE_AI",
        event_id: Optional[str] = None,
        is_observed: bool = True,
        now: Optional[float] = None
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Runs authoritative safety evaluation for a worker.
        Returns:
            telemetry_event: canonical event JSON conforming to detection_schema.json
            new_incidents: list of newly confirmed incident records
            resolved_incidents: list of newly resolved incident records
        """
        # 1. Rule Evaluations
        ppe_violations, ppe_score, ppe_sev, norm_ppe = evaluate_ppe(ppe)
        posture_violations, posture_score, posture_sev, norm_posture = evaluate_posture(posture, spine_angle)
        fall_violations, fall_score, fall_sev, norm_fall, is_fall_emergency = evaluate_fall(fall_input)
        zone_violations, zone_score, zone_sev, norm_zone = evaluate_zone(danger_zone_input, location)

        # 2. Collect current violations
        current_violations = ppe_violations + posture_violations + fall_violations + zone_violations

        # 3. Calculate bounded numerical risk score (0 to 100)
        raw_score = sum(self.weights.get(v, 20) for v in current_violations)
        risk_score = min(100, max(0, raw_score))

        # 4. Determine categorical Risk Level
        if is_fall_emergency or norm_fall == "CONFIRMED_FALL":
            risk_level = "CRITICAL"
        elif risk_score >= 61:
            risk_level = "HIGH"
        elif risk_score >= 31:
            risk_level = "MEDIUM"
        elif risk_score >= 1:
            risk_level = "LOW"
        else:
            risk_level = "SAFE"

        # 5. Update incident lifecycle
        new_incidents, resolved_incidents = self.alert_manager.update_violations(
            worker_id=worker_id,
            current_violations=current_violations,
            location=location,
            severity=risk_level,
            is_observed=is_observed,
            now=now
        )
        active_incidents = self.alert_manager.get_active_incidents(worker_id)
        primary_incident_id = active_incidents[0]["incident_id"] if active_incidents else None

        lifecycle_state = "ACTIVE" if current_violations else "CLEAR"
        if is_fall_emergency:
            lifecycle_state = "ACTIVE"

        # 6. Compose human-readable description
        details_parts = []
        if norm_fall == "CONFIRMED_FALL":
            details_parts.append("CRITICAL: Worker fall detected")
        elif norm_fall == "POSSIBLE_FALL":
            details_parts.append("Possible fall event under review")

        if norm_zone.get("entered"):
            details_parts.append(f"Restricted zone breach ({norm_zone.get('zone_name')})")

        if "helmet_missing" in current_violations:
            details_parts.append("Missing safety helmet")
        elif norm_ppe["helmet"]["status"] == "UNKNOWN":
            details_parts.append("Helmet status unverified")

        if "vest_missing" in current_violations:
            details_parts.append("Missing hi-vis vest")
        elif norm_ppe["vest"]["status"] == "UNKNOWN":
            details_parts.append("Vest status unverified")

        if norm_posture == "UNSAFE":
            details_parts.append("Ergonomic spine bend warning (>35°)")

        details = "; ".join(details_parts) if details_parts else "All monitored safety protocols compliant"

        # 7. Construct canonical event
        evt_id = event_id or f"evt-{worker_id}-{int(datetime.now(timezone.utc).timestamp() * 1000)}-{uuid.uuid4().hex[:6]}"
        telemetry_event = {
            "schema_version": "1.0",
            "event_id": evt_id,
            "incident_id": primary_incident_id,
            "primary_incident_id": primary_incident_id,
            "active_incidents": active_incidents,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": source,
            "lifecycle_state": lifecycle_state,
            "worker_id": worker_id,
            "track_state": self.alert_manager.worker_track_states.get(worker_id, "OBSERVED"),
            "location": location,
            "ppe": norm_ppe,
            "posture": norm_posture,
            "fall_status": norm_fall,
            "danger_zone": norm_zone,
            "violations": current_violations,
            "risk_score": risk_score,
            "risk_level": risk_level,
            "confidence": round(confidence, 2),
            "details": details
        }

        return telemetry_event, new_incidents, resolved_incidents
