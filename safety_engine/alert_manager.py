"""
Alert Manager & Incident Lifecycle Engine
Implements the full incident lifecycle state machine:
  CLEAR -> DETECTED -> ACTIVE -> RESOLVED

Ensures one continuous incident record per active violation,
preventing video frames from generating redundant duplicate records.
"""

import time
import uuid
from typing import Dict, List, Optional, Tuple, Any, Set

DEFAULT_CONFIRMATION_FRAMES = 2
DEFAULT_RESOLUTION_TIMEOUT = 3.0  # seconds without violation before resolving
DEFAULT_DISAPPEARANCE_TIMEOUT = 3.0  # seconds absent before marking NOT_OBSERVED

class ViolationLifecycle:
    def __init__(self, worker_id: str, violation_type: str, incident_id: str, location: str, severity: str):
        self.worker_id = worker_id
        self.violation_type = violation_type
        self.incident_id = incident_id
        self.location = location
        self.severity = severity
        self.state = "DETECTED"  # DETECTED -> ACTIVE -> RESOLVED -> CLEAR / NOT_OBSERVED
        self.first_detected_at = time.time()
        self.last_seen_at = time.time()
        self.consecutive_frames = 1
        self.resolved_at: Optional[float] = None

    @property
    def lifecycle_state(self) -> str:
        return self.state

    @lifecycle_state.setter
    def lifecycle_state(self, val: str):
        self.state = val

class AlertManager:
    def __init__(
        self,
        confirmation_frames: int = DEFAULT_CONFIRMATION_FRAMES,
        resolution_timeout: float = DEFAULT_RESOLUTION_TIMEOUT,
        disappearance_timeout: float = DEFAULT_DISAPPEARANCE_TIMEOUT
    ):
        self.confirmation_frames = confirmation_frames
        self.resolution_timeout = resolution_timeout
        self.disappearance_timeout = disappearance_timeout
        # Map: (worker_id, violation_type) -> ViolationLifecycle
        self._active_lifecycles: Dict[Tuple[str, str], ViolationLifecycle] = {}
        # Track last valid observation timestamp per worker_id
        self.track_last_observed: Dict[str, float] = {}
        self.worker_track_states: Dict[str, str] = {}  # worker_id -> "OBSERVED" | "NOT_OBSERVED"
        self.total_incidents_created = 0
        self.total_incidents_resolved = 0

    def update_violations(
        self,
        worker_id: str,
        current_violations: List[str],
        location: str,
        severity: str,
        is_observed: bool = True,
        now: Optional[float] = None
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Updates the lifecycle for all violation types for a given worker.
        Returns:
            new_incidents: list of newly confirmed incident dictionaries to persist
            resolved_incidents: list of newly resolved incident dictionaries to update
        """
        t_now = now if now is not None else time.time()
        new_incidents = []
        resolved_incidents = []

        if is_observed:
            self.track_last_observed[worker_id] = t_now
            self.worker_track_states[worker_id] = "OBSERVED"

        current_set = set(current_violations)

        # 1. Process active violations in current frame
        for v in current_set:
            key = (worker_id, v)
            if key not in self._active_lifecycles:
                # First time detected - assign unique stable incident ID for this specific violation
                inc_id = f"inc-{worker_id}-{v}-{int(t_now * 1000)}-{uuid.uuid4().hex[:6]}"
                lifecycle = ViolationLifecycle(worker_id, v, inc_id, location, severity)
                lifecycle.first_detected_at = t_now
                lifecycle.last_seen_at = t_now
                self._active_lifecycles[key] = lifecycle

                # If confirmation is 1 or fall emergency, confirm immediately
                if self.confirmation_frames <= 1 or v == "fall_detected":
                    lifecycle.state = "ACTIVE"
                    self.total_incidents_created += 1
                    new_incidents.append(self._to_incident_dict(lifecycle))
            else:
                lifecycle = self._active_lifecycles[key]
                lifecycle.last_seen_at = t_now
                lifecycle.consecutive_frames += 1

                # If worker returned after being unobserved / stale, reactivate existing incident
                if lifecycle.state == "NOT_OBSERVED":
                    lifecycle.state = "ACTIVE"

                # Transition from DETECTED -> ACTIVE once confirmation threshold met
                elif lifecycle.state == "DETECTED" and lifecycle.consecutive_frames >= self.confirmation_frames:
                    lifecycle.state = "ACTIVE"
                    self.total_incidents_created += 1
                    new_incidents.append(self._to_incident_dict(lifecycle))

        # 2. Check for resolved violations ONLY if worker was observed in this frame
        # (Worker absence does not constitute resolution!)
        if is_observed:
            to_remove = []
            for key, lifecycle in self._active_lifecycles.items():
                w_id, v_type = key
                if w_id == worker_id and v_type not in current_set:
                    if (t_now - lifecycle.last_seen_at) >= self.resolution_timeout:
                        lifecycle.state = "RESOLVED"
                        lifecycle.resolved_at = t_now
                        self.total_incidents_resolved += 1
                        resolved_incidents.append(self._to_incident_dict(lifecycle))
                        to_remove.append(key)

            for k in to_remove:
                del self._active_lifecycles[k]

        return new_incidents, resolved_incidents

    def handle_disappeared_workers(
        self,
        visible_worker_ids: Optional[Set[str]] = None,
        now: Optional[float] = None,
        active_worker_ids: Optional[Set[str]] = None,
        current_time: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        Policy: A worker leaving camera view does NOT resolve hazards.
        Instead, active incidents for unobserved workers transition to NOT_OBSERVED
        after the disappearance timeout.
        """
        vis_ids = visible_worker_ids if visible_worker_ids is not None else (active_worker_ids or set())
        t_now = now if now is not None else (current_time if current_time is not None else time.time())
        stale_incidents = []

        for key, lifecycle in self._active_lifecycles.items():
            w_id, v_type = key
            if w_id not in vis_ids:
                last_seen = self.track_last_observed.get(w_id, lifecycle.last_seen_at)
                elapsed = t_now - last_seen
                if elapsed >= self.disappearance_timeout:
                    if lifecycle.state in ("ACTIVE", "DETECTED"):
                        lifecycle.state = "NOT_OBSERVED"
                        self.worker_track_states[w_id] = "NOT_OBSERVED"
                        stale_incidents.append(self._to_incident_dict(lifecycle))

        return stale_incidents

    @property
    def active_incidents(self) -> Dict[Tuple[str, str], ViolationLifecycle]:
        """Provides access to currently tracked violation lifecycles."""
        return self._active_lifecycles

    def get_active_incidents(self, worker_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Returns currently active confirmed incident dictionaries."""
        results = []
        for (w_id, v_type), lifecycle in self._active_lifecycles.items():
            if worker_id is None or w_id == worker_id:
                if lifecycle.state in ("ACTIVE", "DETECTED", "NOT_OBSERVED"):
                    results.append(self._to_incident_dict(lifecycle))
        return results

    def _to_incident_dict(self, lifecycle: ViolationLifecycle) -> Dict[str, Any]:
        return {
            "incident_id": lifecycle.incident_id,
            "worker_id": lifecycle.worker_id,
            "violation": lifecycle.violation_type,
            "location": lifecycle.location,
            "severity": lifecycle.severity,
            "lifecycle_state": lifecycle.state,
            "first_detected_at": lifecycle.first_detected_at,
            "last_seen_at": lifecycle.last_seen_at,
            "resolved_at": lifecycle.resolved_at
        }

    def get_active_worker_violations(self, worker_id: str) -> List[str]:
        """Returns currently active confirmed violations for a worker."""
        active = []
        for (w_id, v_type), lifecycle in self._active_lifecycles.items():
            if w_id == worker_id and lifecycle.state == "ACTIVE":
                active.append(v_type)
        return active

    def reset(self):
        """Resets all tracked incident lifecycles."""
        self._active_lifecycles.clear()
        self.track_last_observed.clear()
        self.worker_track_states.clear()
        self.total_incidents_created = 0
        self.total_incidents_resolved = 0
