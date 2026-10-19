import unittest
import time
from ai.fall_detection import FallDetector

class TestFallDetector(unittest.TestCase):
    def setUp(self):
        self.detector = FallDetector(
            velocity_threshold=30.0,
            aspect_ratio_threshold=1.0,
            height_collapse_threshold=0.55,
            confirmation_frames_needed=2
        )

    def test_upright_worker_initialization(self):
        # A standing worker has w=100, h=250 (aspect ratio 0.4 < 1.0)
        status, conf = self.detector.update_and_detect("W01", (100, 100, 100, 250), spine_angle=12.0)
        self.assertEqual(status, "NONE")
        self.assertGreaterEqual(conf, 0.90)
        self.assertIn("W01", self.detector.baseline_heights)
        self.assertAlmostEqual(self.detector.baseline_heights["W01"], 250.0)

    def test_two_stage_fall_confirmation(self):
        # Establish baseline standing (w=100, h=250)
        self.detector.update_and_detect("W01", (100, 100, 100, 250), spine_angle=10.0)
        
        # Frame with partial evidence (horizontal box w=140, h=130, aspect ratio ~1.08, but upright spine angle 20°)
        # Has only 1 evidence factor (aspect ratio), consec=1 -> transitions to POSSIBLE_FALL
        status1, conf1 = self.detector.update_and_detect("W01", (100, 100, 140, 130), spine_angle=20.0)
        self.assertEqual(status1, "POSSIBLE_FALL")
        self.assertGreater(conf1, 0.60)
        
        # Next frame: second consecutive frame with collapsed height and horizontal aspect ratio
        status2, conf2 = self.detector.update_and_detect("W01", (100, 100, 140, 130), spine_angle=20.0)
        self.assertEqual(status2, "CONFIRMED_FALL")
        self.assertGreater(conf2, 0.85)

    def test_catastrophic_multi_evidence_fall(self):
        # Establish baseline standing
        self.detector.update_and_detect("W02", (100, 100, 100, 260), spine_angle=10.0)
        
        # Catastrophic fall: height collapse, wide horizontal box, 82° spine angle, downward centroid jump
        status, conf = self.detector.update_and_detect("W02", (100, 270, 270, 85), spine_angle=82.0)
        self.assertEqual(status, "CONFIRMED_FALL")
        self.assertGreater(conf, 0.90)

    def test_worker_recovery_when_standing_back_up(self):
        # Establish baseline
        self.detector.update_and_detect("W03", (100, 100, 100, 250), spine_angle=10.0)
        
        # Trigger confirmed fall
        self.detector.update_and_detect("W03", (100, 260, 250, 85), spine_angle=85.0)
        status_fall, _ = self.detector.update_and_detect("W03", (100, 260, 250, 85), spine_angle=85.0)
        self.assertEqual(status_fall, "CONFIRMED_FALL")
        
        # Worker stands back up (w=100, h=245, spine_angle=12.0)
        # Needs 3 recovery frames to return to NONE
        self.detector.update_and_detect("W03", (100, 105, 100, 245), spine_angle=12.0)
        self.detector.update_and_detect("W03", (100, 105, 100, 245), spine_angle=12.0)
        status_rec, _ = self.detector.update_and_detect("W03", (100, 105, 100, 245), spine_angle=12.0)
        self.assertEqual(status_rec, "NONE")

    def test_simulated_override(self):
        status, conf = self.detector.update_and_detect("W04", (100, 100, 100, 200), simulated_override=True)
        self.assertEqual(status, "CONFIRMED_FALL")
        self.assertEqual(conf, 0.98)

        status_false, conf_false = self.detector.update_and_detect("W04", (100, 100, 100, 200), simulated_override=False)
        self.assertEqual(status_false, "NONE")

    def test_stale_workers_cleanup(self):
        self.detector.update_and_detect("W99", (50, 50, 80, 200))
        self.assertIn("W99", self.detector.baseline_heights)
        self.detector.clean_stale_workers(active_worker_ids={"W01", "W02"})
        self.assertNotIn("W99", self.detector.baseline_heights)

    def test_reset(self):
        self.detector.update_and_detect("W01", (100, 100, 100, 200))
        self.detector.reset()
        self.assertEqual(len(self.detector.baseline_heights), 0)
        self.assertEqual(len(self.detector.last_state), 0)

if __name__ == "__main__":
    unittest.main()
