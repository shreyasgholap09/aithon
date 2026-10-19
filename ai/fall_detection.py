"""
Fall Detection Module
Multi-modal kinematic and geometric fall detection engine:
1. Bounding Box Aspect Ratio (w / h >= 1.0 indicates horizontal/prostrate orientation).
2. Dynamic Stature Collapse Ratio (h(t) / h_baseline < 0.55 indicates sudden vertical collapse).
3. Downward Centroid Velocity Gradient (dy / dt > 30 px/s over recent window).
4. Kinematic Spine/Torso Angle (spine_angle >= 65° indicates horizontal body plane).
5. Multi-stage temporal confirmation (NONE -> POSSIBLE_FALL -> CONFIRMED_FALL) and recovery.
"""

import time
from typing import Dict, List, Tuple, Optional, Any, Set


class FallDetector:
    def __init__(
        self,
        velocity_threshold: float = 30.0,
        aspect_ratio_threshold: float = 1.0,
        height_collapse_threshold: float = 0.55,
        confirmation_frames_needed: int = 3
    ):
        self.velocity_threshold = velocity_threshold
        self.aspect_ratio_threshold = aspect_ratio_threshold
        self.height_collapse_threshold = height_collapse_threshold
        self.confirmation_frames_needed = confirmation_frames_needed

        # History map: worker_id -> list of (timestamp, y_centroid, h, w, aspect_ratio)
        self.history: Dict[str, List[Tuple[float, float, float, float, float]]] = {}

        # Baseline upright height tracked per worker: worker_id -> float
        self.baseline_heights: Dict[str, float] = {}

        # Consecutive fall frames counter: worker_id -> int
        self.consecutive_fall_frames: Dict[str, int] = {}

        # Recovery frames counter: worker_id -> int
        self.consecutive_recovery_frames: Dict[str, int] = {}

        # Last detected state: worker_id -> str ('NONE' | 'POSSIBLE_FALL' | 'CONFIRMED_FALL')
        self.last_state: Dict[str, str] = {}

    def update_and_detect(
        self,
        worker_id: str,
        bbox: Tuple[int, int, int, int],
        spine_angle: Optional[float] = None,
        worker_landmarks: Optional[List[Any]] = None,
        simulated_override: Optional[Any] = None
    ) -> Tuple[str, float]:
        """
        Evaluates fall status using multi-feature kinematic and temporal tracking.
        Returns:
            (fall_status, confidence)
            fall_status: 'NONE' | 'POSSIBLE_FALL' | 'CONFIRMED_FALL'
        """
        # Explicit simulated override
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
        history_list.append((now, y_centroid, float(h), float(w), aspect_ratio))

        # Keep past 2.0 seconds of history
        history_list = [entry for entry in history_list if (now - entry[0]) <= 2.0]
        self.history[worker_id] = history_list

        # --- Indicator 1: Aspect Ratio Orientation ---
        # Upright: w/h ~ 0.35 - 0.50. Fallen / horizontal: w/h >= 1.0 (or width > height)
        is_horizontal_bbox = aspect_ratio >= self.aspect_ratio_threshold

        # --- Indicator 2: Upright Baseline & Height Collapse ---
        if aspect_ratio < 0.65:
            # Worker is clearly upright; record/update standing baseline height
            current_baseline = self.baseline_heights.get(worker_id, float(h))
            self.baseline_heights[worker_id] = max(current_baseline, float(h))

        baseline_h = self.baseline_heights.get(worker_id, float(h))
        height_ratio = float(h) / max(1.0, baseline_h)
        is_height_collapsed = height_ratio < self.height_collapse_threshold

        # --- Indicator 3: Downward Centroid Drop (Velocity) ---
        has_downward_drop = False
        if len(history_list) >= 2:
            # Inspect drop over the recent 0.15s - 0.6s window
            recent = [e for e in history_list if (now - e[0]) <= 0.6]
            if len(recent) >= 2:
                dt = recent[-1][0] - recent[0][0]
                dy = recent[-1][1] - recent[0][1]  # positive in screen coordinates = downward drop
                if dt >= 0.05:
                    vel = dy / dt
                    has_downward_drop = vel >= self.velocity_threshold

        # --- Indicator 4: Kinematic Spine / Torso Angle ---
        is_pose_horizontal = False
        if spine_angle is not None and spine_angle >= 65.0:
            is_pose_horizontal = True

        # Check MediaPipe Pose landmarks if available
        if worker_landmarks and len(worker_landmarks) >= 25:
            try:
                # Key landmarks: Left/Right Shoulders (11, 12), Left/Right Hips (23, 24)
                ls, rs = worker_landmarks[11], worker_landmarks[12]
                lh, rh = worker_landmarks[23], worker_landmarks[24]
                shoulder_y = (ls.y + rs.y) / 2.0
                hip_y = (lh.y + rh.y) / 2.0
                shoulder_x = (ls.x + rs.x) / 2.0
                hip_x = (lh.x + rh.x) / 2.0
                dy_torso = abs(shoulder_y - hip_y)
                dx_torso = abs(shoulder_x - hip_x)
                if dx_torso > dy_torso * 1.2:
                    is_pose_horizontal = True
            except Exception:
                pass

        # --- Indicator Fusion ---
        # Strong fall indicators:
        # A: Horizontal bounding box (w >= h)
        # B: Height collapse (h < 55% of baseline)
        # C: Downward velocity drop
        # D: Horizontal spine/torso angle
        fall_evidence_count = sum([
            1 if is_horizontal_bbox else 0,
            1 if is_height_collapsed else 0,
            1 if has_downward_drop else 0,
            1 if is_pose_horizontal else 0
        ])

        # Current frame strongly suggests a fall
        is_frame_fallen = is_horizontal_bbox or (is_height_collapsed and has_downward_drop) or (is_pose_horizontal and aspect_ratio > 0.85)

        # Recovery check: worker has stood back up (height >= 80% baseline and aspect ratio < 0.65)
        is_standing_upright = (height_ratio >= 0.78) and (aspect_ratio < 0.70)
        if is_standing_upright:
            self.consecutive_recovery_frames[worker_id] = self.consecutive_recovery_frames.get(worker_id, 0) + 1
            if self.consecutive_recovery_frames[worker_id] >= 3:
                self.consecutive_fall_frames[worker_id] = 0
                self.last_state[worker_id] = "NONE"
                return "NONE", 0.95
        else:
            self.consecutive_recovery_frames[worker_id] = 0

        # Update consecutive fall frames
        if is_frame_fallen:
            self.consecutive_fall_frames[worker_id] = self.consecutive_fall_frames.get(worker_id, 0) + 1
        else:
            self.consecutive_fall_frames[worker_id] = max(0, self.consecutive_fall_frames.get(worker_id, 0) - 1)

        consec = self.consecutive_fall_frames[worker_id]

        # Multi-stage State Transition
        if consec >= self.confirmation_frames_needed or (has_downward_drop and consec >= 2) or (fall_evidence_count >= 3 and consec >= 1):
            status = "CONFIRMED_FALL"
            conf = min(0.99, 0.85 + 0.04 * fall_evidence_count)
        elif consec >= 1 or fall_evidence_count >= 2:
            status = "POSSIBLE_FALL"
            conf = min(0.85, 0.65 + 0.05 * fall_evidence_count)
        else:
            status = "NONE"
            conf = 0.95

        self.last_state[worker_id] = status
        return status, conf

    def clean_stale_workers(self, active_worker_ids: Set[str]):
        """Prunes historical tracking for workers who have left optical view."""
        all_ids = list(self.history.keys())
        for wid in all_ids:
            if wid not in active_worker_ids:
                self.history.pop(wid, None)
                self.baseline_heights.pop(wid, None)
                self.consecutive_fall_frames.pop(wid, None)
                self.consecutive_recovery_frames.pop(wid, None)
                self.last_state.pop(wid, None)

    def reset(self):
        """Resets all internal tracking states."""
        self.history.clear()
        self.baseline_heights.clear()
        self.consecutive_fall_frames.clear()
        self.consecutive_recovery_frames.clear()
        self.last_state.clear()
