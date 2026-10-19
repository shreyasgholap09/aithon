"""
Unit Tests for Computer Vision Inference & Tracking Pipeline
Validates YOLOv8 person detection, centroid tracking, PPE inspection,
and hazard detection kinematics.
"""

import os
import unittest
import numpy as np

from ai.person_tracking import PersonTracker, CentroidTracker
from ai.ppe_detection import PPEDetector
from ai.pose_detection import PoseDetector
from ai.fall_detection import FallDetector
from ai.zone_detection import ZoneDetector
from ai.detector import SafetyDetector

class TestVisionPipeline(unittest.TestCase):
    def setUp(self):
        self.tracker = PersonTracker()
        self.ppe_detector = PPEDetector()
        self.pose_detector = PoseDetector()
        self.fall_detector = FallDetector()
        self.zone_detector = ZoneDetector()
        self.safety_detector = SafetyDetector()

    def test_blank_frame_returns_zero_workers(self):
        """In LIVE mode, an empty frame must report 0 workers truthfully — never fabricate a dummy worker."""
        blank = np.zeros((480, 640, 3), dtype=np.uint8)
        tracked = self.tracker.detect_and_track(blank)
        self.assertEqual(len(tracked), 0, "Blank frame should detect 0 persons")

    def test_none_frame_safety_detector(self):
        """None frame should cleanly return empty list without crashing."""
        self.assertEqual(self.safety_detector.detect_live_workers(None), [])

    def test_sample_image_detects_real_workers(self):
        """If sample image exists, verify actual inference detects people."""
        sample_path = os.path.join(os.path.dirname(__file__), "..", "ai", "test_sample.jpg")
        if os.path.exists(sample_path):
            import cv2
            img = cv2.imread(sample_path)
            tracked = self.tracker.detect_and_track(img)
            self.assertGreater(len(tracked), 0, "Real sample image should detect at least 1 person")
            self.assertTrue(tracked[0]["worker_id"].startswith("W"), "Worker ID must follow W01 format")
            self.assertGreater(tracked[0]["confidence"], 0.3, "Confidence should exceed threshold")

    def test_centroid_tracker_persistence(self):
        """CentroidTracker assigns sequential IDs and persists across small movements."""
        ct = CentroidTracker(max_distance=100.0)
        # Frame 1: worker at (100, 100, 50, 100)
        r1 = ct.update([(100, 100, 50, 100)])
        self.assertEqual(len(r1), 1)
        w_id = r1[0]["worker_id"]
        self.assertEqual(w_id, "W01")

        # Frame 2: worker moved slightly to (105, 102, 50, 100)
        r2 = ct.update([(105, 102, 50, 100)])
        self.assertEqual(len(r2), 1)
        self.assertEqual(r2[0]["worker_id"], "W01", "ID must persist across consecutive frames")

    def test_ppe_simulation_override(self):
        """PPEDetector honors explicit simulation overrides in demo mode."""
        sim_scenario = {"helmet": True, "vest": False}
        status, conf = self.ppe_detector.inspect_worker(
            worker_bbox=(100, 100, 50, 100),
            frame_ppe_detections=[],
            simulated_override=sim_scenario
        )
        self.assertEqual(status["helmet"]["status"], "PRESENT")
        self.assertEqual(status["vest"]["status"], "MISSING")
        self.assertGreaterEqual(conf, 0.90)

    def test_posture_smoothing_and_classification(self):
        """PoseDetector classifies SAFE vs UNSAFE and filters single-frame jumps."""
        # Upright worker
        st, angle, _ = self.pose_detector.classify_posture("W01", 10.0)
        self.assertEqual(st, "SAFE")

        # Sustained steep forward bend (>38 degrees)
        for _ in range(5):
            st, angle, _ = self.pose_detector.classify_posture("W01", 45.0)
        self.assertEqual(st, "UNSAFE")
        self.assertGreater(angle, 35.0)

    def test_fall_kinematics_detection(self):
        """FallDetector identifies prostrate aspect ratio (width > height)."""
        # Standing worker (aspect ratio ~0.4)
        status, _ = self.fall_detector.update_and_detect("W01", (100, 100, 40, 120))
        self.assertEqual(status, "NONE")

        # Fallen horizontal worker (aspect ratio = 140/50 = 2.8) over 3 frames
        for _ in range(3):
            status, conf = self.fall_detector.update_and_detect("W01", (100, 200, 140, 50))
        self.assertEqual(status, "CONFIRMED_FALL")

    def test_danger_zone_intrusion(self):
        """ZoneDetector correctly calculates normalized ground contact point intersection."""
        # Zone rect: (0.50, 0.25, 0.45, 0.65) on 1000x1000 frame -> px in [500, 950], py in [250, 900]
        # Worker feet outside zone: (100, 100, 50, 100) -> feet at (125, 200) -> False
        inside, zid, zname, _ = self.zone_detector.check_zone_intrusion(
            worker_bbox=(100, 100, 50, 100),
            frame_shape=(1000, 1000)
        )
        self.assertFalse(inside)

        # Worker feet inside zone: (600, 400, 60, 120) -> feet at (630, 520) -> True
        inside, zid, zname, _ = self.zone_detector.check_zone_intrusion(
            worker_bbox=(600, 400, 60, 120),
            frame_shape=(1000, 1000)
        )
        self.assertTrue(inside)
        self.assertEqual(zid, "ZONE_ROBOT_CELL_4")

    def test_decoupled_ppe_caching(self):
        """SafetyDetector reuses PPE results across interval frames and reports ppe_reused flag."""
        sample_path = os.path.join(os.path.dirname(__file__), "..", "ai", "test_sample.jpg")
        if os.path.exists(sample_path):
            import cv2
            img = cv2.imread(sample_path)
            # Frame 1: fresh PPE inference
            d1 = self.safety_detector.detect_live_workers(img)
            self.assertFalse(self.safety_detector.last_metrics["ppe_reused"])

            # Frame 2: cadence skips PPE model and reuses cached PPE
            d2 = self.safety_detector.detect_live_workers(img)
            self.assertTrue(self.safety_detector.last_metrics["ppe_reused"])
            self.assertEqual(self.safety_detector.last_metrics["ppe_det_ms"], 0.0)

    def test_camera_reader_lifecycle(self):
        """CameraReader initializes, releases cleanly, and maintains size=1 frame buffer."""
        from ai.camera_reader import CameraReader
        # Initialize with dummy or disconnected camera index
        reader = CameraReader(source=-999)
        started = reader.start()
        # Since index -999 does not exist, it should gracefully handle failure
        self.assertFalse(started)
        reader.stop()
        self.assertIsNone(reader.read())

    def test_ppe_high_confidence_present(self):
        """High-confidence model detections mark PPE as PRESENT after temporal confirmation."""
        worker_bbox = (100, 100, 100, 200)
        detections = [
            {"class": "Hardhat", "confidence": 0.88, "bbox": (120, 105, 40, 30)},
            {"class": "Safety Vest", "confidence": 0.85, "bbox": (110, 150, 70, 80)},
        ]
        w_id = "W_TEST_PRES"
        self.ppe_detector.inspect_worker(worker_bbox, detections, worker_id=w_id)
        status, conf = self.ppe_detector.inspect_worker(worker_bbox, detections, worker_id=w_id)
        self.assertEqual(status["helmet"]["status"], "PRESENT")
        self.assertEqual(status["vest"]["status"], "PRESENT")
        self.assertGreaterEqual(conf, 0.80)

    def test_ppe_empty_detections_yield_unknown_never_missing(self):
        """Empty detections must yield UNKNOWN, NEVER convert to MISSING."""
        worker_bbox = (100, 100, 100, 200)
        status, conf = self.ppe_detector.inspect_worker(worker_bbox, [], worker_id="W_TEST_EMPTY")
        self.assertEqual(status["helmet"]["status"], "UNKNOWN")
        self.assertEqual(status["vest"]["status"], "UNKNOWN")
        self.assertNotEqual(status["helmet"]["status"], "MISSING")
        self.assertNotEqual(status["vest"]["status"], "MISSING")

    def test_ppe_low_confidence_yields_unknown(self):
        """Detections below confidence threshold yield UNKNOWN."""
        worker_bbox = (100, 100, 100, 200)
        detections = [
            {"class": "Hardhat", "confidence": 0.20, "bbox": (120, 105, 40, 30)},
            {"class": "Safety Vest", "confidence": 0.25, "bbox": (110, 150, 70, 80)}
        ]
        status, _ = self.ppe_detector.inspect_worker(worker_bbox, detections, worker_id="W_TEST_LOW")
        self.assertEqual(status["helmet"]["status"], "UNKNOWN")
        self.assertEqual(status["vest"]["status"], "UNKNOWN")

    def test_ppe_explicit_missing_with_negative_class(self):
        """Negative PPE classes (e.g. NO-Hardhat) trigger MISSING only after confirmation."""
        worker_bbox = (100, 100, 100, 200)
        detections = [
            {"class": "NO-Hardhat", "confidence": 0.85, "bbox": (120, 105, 40, 30)}
        ]
        w_id = "W_TEST_EXP_MISS"
        # Frame 1: Pending confirmation
        self.ppe_detector.inspect_worker(worker_bbox, detections, worker_id=w_id)
        # Frame 2: Confirmed
        status, _ = self.ppe_detector.inspect_worker(worker_bbox, detections, worker_id=w_id)
        self.assertEqual(status["helmet"]["status"], "MISSING")

    def test_ppe_neighbor_spatial_rejection(self):
        """Detections physically closer to a neighboring worker are not claimed."""
        worker1_bbox = (100, 100, 80, 180)
        worker2_bbox = (300, 100, 80, 180)
        # Hardhat detection belongs to Worker 2
        detections = [
            {"class": "Hardhat", "confidence": 0.90, "bbox": (320, 105, 40, 30)}
        ]
        status, _ = self.ppe_detector.inspect_worker(
            worker_bbox=worker1_bbox,
            frame_ppe_detections=detections,
            other_worker_bboxes=[worker2_bbox],
            worker_id="W_TEST_N1"
        )
        self.assertEqual(status["helmet"]["status"], "UNKNOWN")

    def test_ppe_occluded_head_returns_unknown(self):
        """Severely occluded or degraded worker crop returns UNKNOWN."""
        worker_bbox = (100, 0, 80, 40)
        status, _ = self.ppe_detector.inspect_worker(worker_bbox, [], worker_id="W_TEST_OCC")
        self.assertEqual(status["helmet"]["status"], "UNKNOWN")

    def test_ppe_model_unavailable_reports_unknown(self):
        """When model is unavailable, reports UNKNOWN and does not invent classifications."""
        detector_unavail = PPEDetector(model_path="nonexistent_model.onnx")
        self.assertFalse(detector_unavail.is_available)
        status, _ = detector_unavail.inspect_worker((100, 100, 80, 180), [], worker_id="W_TEST_UNAV")
        self.assertEqual(status["helmet"]["status"], "UNKNOWN")
        self.assertEqual(status["vest"]["status"], "UNKNOWN")

    def test_ppe_hysteresis_and_recovery(self):
        """Single uncertain frame does not falsely toggle state, and recovers cleanly."""
        w_id = "W_TEST_RECOV"
        det_pres = [{"class": "Hardhat", "confidence": 0.90, "bbox": (120, 105, 40, 30)}]
        # 1. Establish PRESENT
        self.ppe_detector.inspect_worker((100, 100, 80, 180), det_pres, worker_id=w_id)
        st1, _ = self.ppe_detector.inspect_worker((100, 100, 80, 180), det_pres, worker_id=w_id)
        self.assertEqual(st1["helmet"]["status"], "PRESENT")

        # 2. Single uncertain frame (empty detections)
        st2, _ = self.ppe_detector.inspect_worker((100, 100, 80, 180), [], worker_id=w_id)
        self.assertNotEqual(st2["helmet"]["status"], "MISSING")

        # 3. Valid observation restored
        st3, _ = self.ppe_detector.inspect_worker((100, 100, 80, 180), det_pres, worker_id=w_id)
        self.assertEqual(st3["helmet"]["status"], "PRESENT")

if __name__ == "__main__":
    unittest.main()

