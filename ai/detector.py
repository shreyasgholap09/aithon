"""
Unified Worker Safety Detector Module
Orchestrates Person Detection & Tracking, PPE Verification,
Pose Estimation, Fall Kinematics, and Danger Zone intrusion.
Strictly distinguishes LIVE_AI from SIMULATED execution paths.

Performance Optimizations:
- Decouples PPE inference rate (every N frames / temporal cache) while keeping
  person tracking responsive on every frame.
- Skips PPE model execution completely when zero persons are in optical field of view.
- Provides precise stage-by-stage latency profiling metrics.
"""

import time
from typing import Dict, Any, List, Optional, Tuple
import numpy as np
from .person_tracking import PersonTracker
from .ppe_detection import PPEDetector
from .pose_detection import PoseDetector
from .fall_detection import FallDetector
from .zone_detection import ZoneDetector

class SafetyDetector:
    def __init__(self, ppe_interval_frames: int = 3, max_ppe_age_sec: float = 2.5):
        self.person_tracker = PersonTracker()
        self.ppe_detector = PPEDetector()
        self.pose_detector = PoseDetector()
        self.fall_detector = FallDetector()
        self.zone_detector = ZoneDetector()

        # PPE Decoupling & Caching
        self.ppe_interval_frames = ppe_interval_frames
        self.max_ppe_age_sec = max_ppe_age_sec
        self._frame_idx = 0
        self._cached_ppe: List[Dict[str, Any]] = []
        self._last_ppe_time = 0.0
        
        # Telemetry profiling metrics
        self.last_metrics = {
            "person_det_ms": 0.0,
            "ppe_det_ms": 0.0,
            "ppe_reused": False
        }

    def detect_live_workers(
        self,
        frame: Optional[np.ndarray],
        location: str = "Machine Zone A",
        source: str = "LIVE_AI"
    ) -> List[Dict[str, Any]]:
        """
        Runs genuine computer vision inference on an actual video frame.
        Returns a list of detected worker states.
        If zero persons are detected in the frame, returns []. Never fabricates a dummy worker.
        """
        if frame is None or frame.size == 0:
            self.last_metrics = {"person_det_ms": 0.0, "ppe_det_ms": 0.0, "ppe_reused": False}
            return []

        self._frame_idx += 1
        now = time.perf_counter()

        # 1. Detect and track real persons in the frame
        t0 = time.perf_counter()
        tracked_persons = self.person_tracker.detect_and_track(frame)
        person_det_ms = (time.perf_counter() - t0) * 1000.0

        if not tracked_persons:
            # When area is clear, skip PPE model forward pass entirely (saves ~135ms!)
            self.last_metrics = {
                "person_det_ms": round(person_det_ms, 1),
                "ppe_det_ms": 0.0,
                "ppe_reused": False
            }
            return []

        frame_h, frame_w = frame.shape[:2]

        # 2. Extract scene PPE detections with cadence decoupling
        need_fresh_ppe = (
            self._frame_idx % self.ppe_interval_frames == 1 or
            self._last_ppe_time == 0.0 or
            (now - self._last_ppe_time) > self.max_ppe_age_sec
        )

        ppe_det_ms = 0.0
        ppe_reused = True

        if need_fresh_ppe:
            t_ppe0 = time.perf_counter()
            self._cached_ppe = self.ppe_detector.detect_frame_ppe(frame)
            ppe_det_ms = (time.perf_counter() - t_ppe0) * 1000.0
            self._last_ppe_time = now
            ppe_reused = False

        frame_ppe = self._cached_ppe
        self.last_metrics = {
            "person_det_ms": round(person_det_ms, 1),
            "ppe_det_ms": round(ppe_det_ms, 1),
            "ppe_reused": ppe_reused
        }

        worker_detections = []
        all_worker_bboxes = [p["bbox"] for p in tracked_persons]

        for person in tracked_persons:
            w_id = person["worker_id"]
            x, y, w, h = person["bbox"]

            # Crop worker ROI safely
            x1 = max(0, min(x, frame_w - 1))
            y1 = max(0, min(y, frame_h - 1))
            x2 = max(x1 + 1, min(x + w, frame_w))
            y2 = max(y1 + 1, min(y + h, frame_h))
            worker_crop = frame[y1:y2, x1:x2]

            # 3. PPE Inspection with spatial cross-referencing and neighbor filtering
            other_bboxes = [ob for ob in all_worker_bboxes if ob != (x, y, w, h)]
            ppe_status, ppe_conf = self.ppe_detector.inspect_worker(
                worker_bbox=(x, y, w, h),
                frame_ppe_detections=frame_ppe,
                worker_crop=worker_crop,
                worker_id=w_id,
                other_worker_bboxes=other_bboxes
            )

            # 4. Posture analysis: uses real landmark keypoints when available;
            # Never fabricates posture from bounding-box aspect ratio.
            worker_landmarks = person.get("landmarks")
            if worker_landmarks:
                posture_status, smoothed_angle, pose_conf, _ = self.pose_detector.analyze_landmarks(
                    worker_landmarks,
                    worker_id=w_id,
                    frame_shape=(frame_h, frame_w)
                )
            else:
                posture_status, smoothed_angle, pose_conf, _, _ = self.pose_detector.detect_worker_pose(
                    frame,
                    worker_bbox=(x, y, w, h),
                    worker_id=w_id
                )

            # 5. Fall detection from temporal kinematics
            fall_status, fall_conf = self.fall_detector.update_and_detect(
                worker_id=w_id,
                bbox=(x, y, w, h),
                spine_angle=smoothed_angle,
                worker_landmarks=worker_landmarks
            )

            # 6. Danger zone intrusion check against configurable polygons
            entered, zone_id, zone_name, zone_conf = self.zone_detector.check_zone_intrusion(
                worker_bbox=(x, y, w, h),
                frame_shape=(frame_h, frame_w),
                worker_id=w_id
            )

            overall_confidence = float(np.mean([float(person.get("confidence", 0.88)), float(ppe_conf), float(pose_conf), float(fall_conf), float(zone_conf)]))

            worker_detections.append({
                "source": source,
                "worker_id": str(w_id),
                "bbox": (int(x), int(y), int(w), int(h)),
                "location": str(location),
                "ppe": ppe_status,
                "posture": str(posture_status),
                "spine_angle": float(smoothed_angle),
                "fall_status": str(fall_status),
                "danger_zone": {
                    "entered": bool(entered),
                    "zone_id": str(zone_id or ""),
                    "zone_name": str(zone_name or "")
                },
                "confidence": float(round(overall_confidence, 2))
            })

        return worker_detections

    def build_simulated_worker(
        self,
        scenario: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Builds an explicitly labeled SIMULATED demonstration event.
        Guaranteed to not touch or pollute the live AI inference state.
        """
        w_id = scenario.get("worker_id", "W01")
        location = scenario.get("location", "Machine Zone A")
        raw_fall = scenario.get("fall_status", scenario.get("fall_detected", False))
        is_fall = raw_fall in ["FALL_DETECTED", "CONFIRMED_FALL", "POSSIBLE_FALL", True]
        
        sim_bbox = (100, 240, 280, 95) if is_fall else tuple(scenario.get("bbox", (120, 100, 140, 280)))
        
        raw_ppe = scenario.get("ppe", {"helmet": True, "vest": True})
        ppe_status, ppe_conf = self.ppe_detector.inspect_worker(
            worker_bbox=sim_bbox,
            frame_ppe_detections=[],
            worker_crop=None,
            simulated_override=raw_ppe
        )

        raw_posture = scenario.get("posture", "HIGH_RISK" if is_fall else "SAFE")
        posture_status, angle, pose_conf = self.pose_detector.classify_posture(
            w_id,
            82.5 if is_fall else 0.0,
            simulated_override=raw_posture
        )

        fall_status, fall_conf = self.fall_detector.update_and_detect(
            w_id,
            sim_bbox,
            simulated_override=raw_fall,
            spine_angle=82.5 if is_fall else 0.0
        )

        raw_zone = scenario.get("danger_zone", False)
        entered, zone_id, zone_name, zone_conf = self.zone_detector.check_zone_intrusion(
            sim_bbox,
            simulated_override=raw_zone
        )

        return {
            "source": "SIMULATED",
            "worker_id": w_id,
            "bbox": sim_bbox,
            "location": location,
            "ppe": ppe_status,
            "posture": posture_status,
            "spine_angle": 82.5 if is_fall else angle,
            "fall_status": fall_status,
            "danger_zone": {
                "entered": entered,
                "zone_id": zone_id or "",
                "zone_name": zone_name or ""
            },
            "confidence": scenario.get("confidence", 0.95)
        }
