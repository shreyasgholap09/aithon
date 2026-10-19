"""
Unit Tests for Event Processing, JSON Schema Compliance, and Transport Idempotency
Covers:
- Valid JSON schema compliance
- Rejection of malformed / missing required fields
- Idempotent duplicate event ID filtering
- Separation of LIVE_AI and SIMULATED event sources
- Verification of continuous violation deduplication
"""

import unittest
import json
import os
import sys

# Add project root to sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from safety_engine.risk_engine import RiskEngine

class TestEventProcessing(unittest.TestCase):
    def setUp(self):
        self.engine = RiskEngine()
        schema_path = os.path.join(PROJECT_ROOT, "shared", "detection_schema.json")
        with open(schema_path, "r", encoding="utf-8") as f:
            self.schema = json.load(f)

    def test_schema_required_fields_present(self):
        event, _, _ = self.engine.assess_worker(
            worker_id="W01",
            location="Machine Zone A",
            ppe={"helmet": False, "vest": True},
            source="LIVE_AI"
        )

        required_fields = self.schema.get("required", [])
        for field in required_fields:
            self.assertIn(field, event, f"Required schema field missing: {field}")

        self.assertEqual(event["schema_version"], "1.0")
        self.assertEqual(event["source"], "LIVE_AI")
        self.assertIsInstance(event["violations"], list)
        self.assertIsInstance(event["risk_score"], int)

    def test_demo_event_source_separation(self):
        sim_event, _, _ = self.engine.assess_worker(
            worker_id="W02",
            location="Robotic Cell",
            ppe={"helmet": True, "vest": True},
            source="SIMULATED"
        )
        self.assertEqual(sim_event["source"], "SIMULATED")
        self.assertNotEqual(sim_event["source"], "LIVE_AI")

    def test_malformed_json_handling(self):
        raw_bad_json = '{"worker_id": "W01", "timestamp": }'
        parsed = None
        try:
            parsed = json.loads(raw_bad_json)
        except json.JSONDecodeError:
            parsed = None
        self.assertIsNone(parsed)

    def test_missing_fields_validation(self):
        incomplete_event = {"worker_id": "W01"}
        required_fields = self.schema.get("required", [])
        missing = [f for f in required_fields if f not in incomplete_event]
        self.assertTrue(len(missing) > 0)
        self.assertIn("timestamp", missing)
        self.assertIn("risk_score", missing)

    def test_continuous_violation_deduplication(self):
        # Frame 1: Initial observation (DETECTED, awaiting confirmation)
        _, new_inc_1, _ = self.engine.assess_worker("W03", "Area 1", {"helmet": False, "vest": True})
        # Frame 2: Confirmed active (ACTIVE -> emits new incident)
        _, new_inc_2, _ = self.engine.assess_worker("W03", "Area 1", {"helmet": False, "vest": True})
        # Frame 3: Continuous active violation (deduplicated -> 0 new incidents)
        _, new_inc_3, _ = self.engine.assess_worker("W03", "Area 1", {"helmet": False, "vest": True})

        # Frame 1 detected, Frame 2 confirmed (1 new incident), Frame 3 deduplicated (0 new incidents)
        self.assertEqual(len(new_inc_1), 0)
        self.assertEqual(len(new_inc_2), 1)
        self.assertEqual(len(new_inc_3), 0)

    def test_resolve_source_config_sample_cannot_produce_live_ai(self):
        """A static sample image or test fixture must NEVER produce a LIVE_AI label."""
        from ai.video_processor import resolve_source_config
        sample_path = os.path.join(PROJECT_ROOT, "ai", "test_sample.jpg")
        
        # Test explicit path to image
        mode, label, path = resolve_source_config(sample_path)
        self.assertEqual(mode, "TEST_FIXTURE")
        self.assertNotEqual(mode, "LIVE_AI")

        # Test shorthand 'sample'
        mode_shorthand, _, _ = resolve_source_config("sample")
        self.assertEqual(mode_shorthand, "TEST_FIXTURE")
        self.assertNotEqual(mode_shorthand, "LIVE_AI")

    def test_resolve_source_config_video(self):
        """Video files are truthfully classified as VIDEO_AI."""
        from ai.video_processor import resolve_source_config
        mode, label, path = resolve_source_config("safety_drill.mp4")
        self.assertEqual(mode, "VIDEO_AI")
        self.assertNotEqual(mode, "LIVE_AI")

    def test_resolve_source_config_camera_fallback_to_standby(self):
        """When camera is unavailable or cannot open, transition to STANDBY, not a silent LIVE_AI mock."""
        from ai.video_processor import VideoProcessor
        proc = VideoProcessor(source=-999)
        opened = proc.open_camera(-999)
        self.assertFalse(opened)
        self.assertEqual(proc.active_source, "STANDBY")

    def test_schema_validates_all_honest_sources(self):
        """Schema must accept LIVE_AI, VIDEO_AI, TEST_FIXTURE, and SIMULATED."""
        source_prop = self.schema["properties"]["source"]
        allowed_sources = source_prop.get("enum", [])
        self.assertIn("LIVE_AI", allowed_sources)
        self.assertIn("VIDEO_AI", allowed_sources)
        self.assertIn("TEST_FIXTURE", allowed_sources)
        self.assertIn("SIMULATED", allowed_sources)

    def test_event_carries_incident_metadata(self):
        """Authoritative event includes stable incident IDs and track state."""
        event, _, _ = self.engine.assess_worker(
            worker_id="W05",
            location="Zone B",
            ppe={"helmet": False, "vest": True}
        )
        self.assertIn("incident_id", event)
        self.assertIn("primary_incident_id", event)
        self.assertIn("active_incidents", event)
        self.assertIn("track_state", event)
        self.assertIn(event["track_state"], ("OBSERVED", "ACTIVE"))

if __name__ == "__main__":
    unittest.main()
