"""
Fall Detection Module
Combines bounding box aspect ratio kinematics, vertical centroid velocity,
and multi-frame temporal persistence to detect falls reliably without single-frame noise.
"""

from typing import Dict, List, Tuple, Optional, Any
import time

class FallDetector:
    def __init__(
        self,
        velocity_threshold: float = 35.0,
        aspect_ratio_threshold: float = 1.25,
        confirmation_frames_needed: int = 3
    ):
        self.velocity_threshold = velocity_threshold
        self.aspect_ratio_threshold = aspect_ratio_threshold
        self.confirmation_frames_needed = confirmation_frames_needed
        # History map: worker_id -> list of (timestamp, y_centroid, aspect_ratio)
        self.history: Dict[str, List[Tuple[float, float, float]]] = {}
        # Consecutive fall frames counter: worker_id -> int
        self.consecutive_fall_frames: Dict[str, int] = {}

    def update_and_detect(
        self,
        worker_id: str,
        bbox: Tuple[int, int, int, int],
        simulated_override: Optional[Any] = None
    ) -> Tuple[str, float]:
        """
        Detects falls based on bounding box kinematics over time.
        Returns:
            fall_status: 'NONE' | 'POSSIBLE_FALL' | 'CONFIRMED_FALL'
            confidence: float
        """
        if simulated_override is not None:
            if isinstance(simulated_override, bool):
                return ("CONFIRMED_FALL" if simulated_override else "NONE"), 0.98
            st = str(simulated_override).upper()
            return st, 0.98

        x, y, w, h = bbox
        if h <= 0 or w <= 0:
            return "NONE", 0.0

        aspect_ratio = float(w) / float(h)
        y_centroid = y + h / 2.0
        now = time.time()

        if worker_id not in self.history:
            self.history[worker_id] = []

        history_list = self.history[worker_id]
        history_list.append((now, y_centroid, aspect_ratio))

        # Keep past 2 seconds of tracking
        history_list = [entry for entry in history_list if (now - entry[0]) <= 2.0]
        self.history[worker_id] = history_list

        # Frame indicates horizontal prostrate pose (width > height)
        is_frame_fallen = aspect_ratio > self.aspect_ratio_threshold

        # Downward velocity check
        has_downward_drop = False
        if len(history_list) >= 3:
            dt = history_list[-1][0] - history_list[0][0]
            dy = history_list[-1][1] - history_list[0][1]
            vel = (dy / dt) if dt > 0 else 0.0
            has_downward_drop = vel > self.velocity_threshold

        if is_frame_fallen:
            self.consecutive_fall_frames[worker_id] = self.consecutive_fall_frames.get(worker_id, 0) + 1
        else:
            self.consecutive_fall_frames[worker_id] = max(0, self.consecutive_fall_frames.get(worker_id, 0) - 1)

        consec = self.consecutive_fall_frames[worker_id]

        if consec >= self.confirmation_frames_needed or (has_downward_drop and consec >= 2):
            return "CONFIRMED_FALL", 0.96
        elif consec >= 1:
            return "POSSIBLE_FALL", 0.75
        else:
            return "NONE", 0.95
