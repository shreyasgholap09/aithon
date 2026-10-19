"""
Pose & Ergonomics Detection Module
Calculates worker spine angle, trunk bending inclination, and ergonomic hazard classification
using real geometric landmark calculations and exponential smoothing.

NOTE ON CLINICAL APPLICABILITY:
All angular thresholds in this module (e.g. 25° warning, 35° unsafe, 30° knee flexion)
are demonstration ergonomic heuristics derived from Rapid Entire Body Assessment (REBA) guidelines.
They are intended solely for workplace safety demonstration and automated hazard monitoring,
not for medical or clinical diagnostic evaluation.
"""

from typing import Tuple, Optional, Dict, Any, Union, List
import math
from ai.geometry import (
    calculate_angle_3points,
    calculate_angle_with_vertical,
    calculate_distance,
    to_point
)

# MediaPipe Pose landmark indices for standard reference
NOSE_IDX = 0
LEFT_EAR_IDX = 7
RIGHT_EAR_IDX = 8
LEFT_SHOULDER_IDX = 11
RIGHT_SHOULDER_IDX = 12
LEFT_HIP_IDX = 23
RIGHT_HIP_IDX = 24
LEFT_KNEE_IDX = 25
RIGHT_KNEE_IDX = 26
LEFT_ANKLE_IDX = 27
RIGHT_ANKLE_IDX = 28


class PoseDetector:
    def __init__(
        self,
        warning_angle: float = 25.0,
        critical_angle: float = 35.0,
        smoothing_factor: float = 0.30,
        min_landmark_confidence: float = 0.35,
        knee_straight_angle: float = 150.0
    ):
        """
        Initializes the PoseDetector with configurable demonstration ergonomic thresholds.
        """
        self.warning_angle = warning_angle
        self.critical_angle = critical_angle
        self.smoothing_factor = smoothing_factor
        self.min_landmark_confidence = min_landmark_confidence
        self.knee_straight_angle = knee_straight_angle

        # Temporal smoothing history per worker: worker_id -> smoothed_spine_angle
        self._smoothed_angles: Dict[str, float] = {}

    def calculate_spine_angle(
        self,
        shoulder_midpoint: Tuple[float, float],
        hip_midpoint: Tuple[float, float]
    ) -> float:
        """
        Calculates deviation angle of the torso segment from vertical (0° = perfectly upright).
        Uses calculate_angle_with_vertical from geometry utilities.
        """
        return calculate_angle_with_vertical(shoulder_midpoint, hip_midpoint)

    def analyze_landmarks(
        self,
        landmarks: Any,
        worker_id: str = "W01",
        frame_shape: Optional[Tuple[int, int]] = None
    ) -> Tuple[str, float, float, Dict[str, float]]:
        """
        Analyzes real pose estimation landmarks to evaluate worker ergonomics.
        
        Returns:
            posture_status: 'SAFE' | 'WARNING' | 'UNSAFE' | 'UNKNOWN'
            smoothed_trunk_angle: float
            confidence: float
            angles_breakdown: Dict[str, float] (trunk, neck, knee angles)
            
        Policy: If landmarks are missing, None, or below confidence threshold,
        returns UNKNOWN. Never classifies missing data as SAFE.
        """
        if not landmarks:
            return "UNKNOWN", 0.0, 0.0, {}

        # Parse landmarks from MediaPipe object, dict, or list
        points = self._extract_keypoints(landmarks, frame_shape)
        if not points:
            return "UNKNOWN", 0.0, 0.0, {}

        # Essential keypoints for spinal trunk inclination
        ls = points.get(LEFT_SHOULDER_IDX)
        rs = points.get(RIGHT_SHOULDER_IDX)
        lh = points.get(LEFT_HIP_IDX)
        rh = points.get(RIGHT_HIP_IDX)

        # Require at least one shoulder and one hip with sufficient confidence
        if not (ls or rs) or not (lh or rh):
            # Missing essential spinal landmarks -> UNKNOWN
            return "UNKNOWN", 0.0, 0.0, {}

        shoulder_pts = [p for p in (ls, rs) if p is not None]
        hip_pts = [p for p in (lh, rh) if p is not None]

        mid_shoulder = (
            sum(p[0] for p in shoulder_pts) / len(shoulder_pts),
            sum(p[1] for p in shoulder_pts) / len(shoulder_pts)
        )
        mid_hip = (
            sum(p[0] for p in hip_pts) / len(hip_pts),
            sum(p[1] for p in hip_pts) / len(hip_pts)
        )

        avg_conf = (
            sum(p[2] for p in shoulder_pts) / len(shoulder_pts) +
            sum(p[2] for p in hip_pts) / len(hip_pts)
        ) / 2.0

        if avg_conf < self.min_landmark_confidence:
            return "UNKNOWN", 0.0, 0.0, {}

        # 1. Trunk inclination angle from vertical
        raw_trunk_angle = calculate_angle_with_vertical(mid_shoulder, mid_hip)

        # 2. Neck flexion angle (if ear keypoints are detected)
        neck_angle = 0.0
        le = points.get(LEFT_EAR_IDX)
        re = points.get(RIGHT_EAR_IDX)
        ear_pts = [p for p in (le, re) if p is not None]
        if ear_pts:
            mid_ear = (
                sum(p[0] for p in ear_pts) / len(ear_pts),
                sum(p[1] for p in ear_pts) / len(ear_pts)
            )
            neck_angle = calculate_angle_with_vertical(mid_ear, mid_shoulder)

        # 3. Knee angles (flexion) for lifting evaluation
        lk = points.get(LEFT_KNEE_IDX)
        rk = points.get(RIGHT_KNEE_IDX)
        la = points.get(LEFT_ANKLE_IDX)
        ra = points.get(RIGHT_ANKLE_IDX)

        knee_angles = []
        if lh and lk and la:
            knee_angles.append(calculate_angle_3points((lh[0], lh[1]), (lk[0], lk[1]), (la[0], la[1])))
        if rh and rk and ra:
            knee_angles.append(calculate_angle_3points((rh[0], rh[1]), (rk[0], rk[1]), (ra[0], ra[1])))

        min_knee_angle = min(knee_angles) if knee_angles else 180.0

        # Classify ergonomic state
        status, smoothed_angle, conf = self.classify_posture(
            worker_id=worker_id,
            raw_angle=raw_trunk_angle,
            min_knee_angle=min_knee_angle
        )

        breakdown = {
            "trunk_angle": round(smoothed_angle, 1),
            "neck_angle": round(neck_angle, 1),
            "min_knee_angle": round(min_knee_angle, 1),
            "knee_angle": round(min_knee_angle, 1)
        }

        return status, smoothed_angle, round(conf, 2), breakdown

    def classify_posture(
        self,
        worker_id: str,
        raw_angle: float,
        simulated_override: Optional[str] = None,
        min_knee_angle: float = 180.0
    ) -> Tuple[str, float, float]:
        """
        Smooths angle over time and classifies ergonomic risk level.
        Returns:
            (posture_status, smoothed_angle, confidence)
        """
        if simulated_override is not None:
            state = str(simulated_override).upper()
            angle = 42.0 if state in ("UNSAFE", "UNSAFE_LIFTING") else (28.0 if state == "WARNING" else (12.0 if state == "SAFE" else 0.0))
            return state, angle, 0.95

        # Check for invalid angle (NaN, negative, or degenerate)
        if raw_angle is None or math.isnan(raw_angle) or raw_angle < 0.0:
            return "UNKNOWN", 0.0, 0.0

        # Exponential moving average smoothing
        prev = self._smoothed_angles.get(worker_id, raw_angle)
        smoothed = (self.smoothing_factor * raw_angle) + ((1.0 - self.smoothing_factor) * prev)
        self._smoothed_angles[worker_id] = smoothed

        if smoothed >= self.critical_angle:
            # Ergonomic lifting check: If knees are straight (> 150°), severe lumbar hazard
            if min_knee_angle >= self.knee_straight_angle:
                return "UNSAFE", round(smoothed, 1), 0.92
            else:
                # Squatting with bent knees is an acceptable ergonomic lift
                return "SAFE", round(smoothed, 1), 0.88
        elif smoothed >= self.warning_angle:
            if min_knee_angle < self.knee_straight_angle:
                return "SAFE", round(smoothed, 1), 0.90
            return "WARNING", round(smoothed, 1), 0.85
        else:
            return "SAFE", round(smoothed, 1), 0.95

    def _extract_keypoints(
        self,
        landmarks: Any,
        frame_shape: Optional[Tuple[int, int]]
    ) -> Dict[int, Tuple[float, float, float]]:
        """Parses landmark inputs into standard {idx: (x, y, visibility)} mapping."""
        points: Dict[int, Tuple[float, float, float]] = {}
        h, w = frame_shape[:2] if frame_shape else (1000, 1000)

        # Case 1: Dict input: {idx: (x, y, conf)} or {idx: {"x": ..., "y": ..., "visibility": ...}}
        if isinstance(landmarks, dict):
            for k, val in landmarks.items():
                try:
                    idx = int(k)
                    if isinstance(val, (tuple, list)):
                        x = float(val[0])
                        y = float(val[1])
                        c = float(val[2]) if len(val) > 2 else 1.0
                        points[idx] = (x, y, c)
                    elif isinstance(val, dict):
                        x = float(val.get("x", 0.0))
                        y = float(val.get("y", 0.0))
                        c = float(val.get("visibility", val.get("confidence", 1.0)))
                        points[idx] = (x, y, c)
                except (ValueError, TypeError, IndexError):
                    continue
            return points

        # Case 2: MediaPipe LandmarkList object
        if hasattr(landmarks, "landmark"):
            for idx, lm in enumerate(landmarks.landmark):
                vis = getattr(lm, "visibility", 1.0)
                px = lm.x * w if lm.x <= 1.0 else lm.x
                py = lm.y * h if lm.y <= 1.0 else lm.y
                points[idx] = (px, py, vis)
            return points

        # Case 3: List of points [(x, y, conf), ...] or [{"x": ..., "y": ..., "visibility": ...}, ...]
        if isinstance(landmarks, list):
            for idx, val in enumerate(landmarks):
                if isinstance(val, (tuple, list)) and len(val) >= 2:
                    c = float(val[2]) if len(val) > 2 else 1.0
                    points[idx] = (float(val[0]), float(val[1]), c)
                elif isinstance(val, dict):
                    x = float(val.get("x", 0.0))
                    y = float(val.get("y", 0.0))
                    c = float(val.get("visibility", val.get("confidence", 1.0)))
                    points[idx] = (x, y, c)
                elif hasattr(val, "x") and hasattr(val, "y"):
                    px = val.x * w if val.x <= 1.0 else val.x
                    py = val.y * h if val.y <= 1.0 else val.y
                    vis = getattr(val, "visibility", 1.0)
                    points[idx] = (px, py, vis)
            return points

        return {}
