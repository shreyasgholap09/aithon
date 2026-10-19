"""
Unit tests for Layer 1 (Ingestion & Privacy) and Layer 5 (Webhook Dispatcher).
Covers:
- PrivacyFilter (OFF, BLUR_FACES, SKELETON_ONLY)
- CameraReader lifecycle states and IP CCTV configuration
- WebhookDispatcher sanitization, activation, and dispatch
- Source resolution (Webcam, CCTV, Video, Test Fixture, Standby)
"""

import unittest
import numpy as np
import os
import sys

# Ensure repository root is on sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from ai.privacy_filter import PrivacyFilter
from ai.camera_reader import CameraReader
from ai.video_processor import resolve_source_config
from safety_engine.webhook_dispatcher import WebhookDispatcher


class TestPrivacyFilter(unittest.TestCase):
    def setUp(self):
        # Create dummy test frame (480x640x3)
        self.frame = np.ones((480, 640, 3), dtype=np.uint8) * 128
        self.detections = [
            {
                "worker_id": "W01",
                "bbox": [100, 100, 200, 350],
                "confidence": 0.95
            }
        ]

    def test_filter_off_returns_identical_frame(self):
        pf = PrivacyFilter(mode="OFF")
        filtered = pf.apply(self.frame, self.detections)
        self.assertEqual(filtered.shape, self.frame.shape)
        np.testing.assert_array_equal(filtered, self.frame)

    def test_filter_blur_faces_modifies_head_region(self):
        pf = PrivacyFilter(mode="BLUR_FACES")
        # Add high frequency noise in head region
        frame_noisy = self.frame.copy()
        frame_noisy[100:180, 120:220] = np.random.randint(0, 255, (80, 100, 3), dtype=np.uint8)
        filtered = pf.apply(frame_noisy, self.detections)
        self.assertEqual(filtered.shape, self.frame.shape)
        # Verify the head region was altered (blurred)
        self.assertFalse(np.array_equal(filtered[100:180, 120:220], frame_noisy[100:180, 120:220]))

    def test_filter_skeleton_only_creates_anonymized_wireframe(self):
        pf = PrivacyFilter(mode="SKELETON_ONLY")
        filtered = pf.apply(self.frame, self.detections)
        self.assertEqual(filtered.shape, self.frame.shape)
        # Background should be dark/anonymized (majority pixels <= 30)
        self.assertLess(np.mean(filtered[:50, :50]), 40)

    def test_mode_switching_and_unknown_fallback(self):
        pf = PrivacyFilter(mode="INVALID_MODE")
        self.assertEqual(pf.get_mode(), "OFF")
        pf.set_mode("BLUR_FACES")
        self.assertEqual(pf.get_mode(), "BLUR_FACES")
        pf.set_mode("SKELETON_ONLY")
        self.assertEqual(pf.get_mode(), "SKELETON_ONLY")


class TestSourceResolution(unittest.TestCase):
    def test_resolve_standby_default(self):
        mode, label, src = resolve_source_config(None, use_camera=False)
        self.assertEqual(mode, "STANDBY")
        self.assertIn("Standby", label)

    def test_resolve_cctv_stream_urls(self):
        rtsp_url = "rtsp://admin:pass@192.168.1.100:554/live"
        mode, label, src = resolve_source_config(rtsp_url)
        self.assertEqual(mode, "CCTV_AI")
        self.assertEqual(src, rtsp_url)
        self.assertIn("IP CCTV Stream", label)

        http_url = "http://192.168.1.50:8080/video"
        mode, label, src = resolve_source_config(http_url)
        self.assertEqual(mode, "CCTV_AI")
        self.assertEqual(src, http_url)

    def test_resolve_webcam(self):
        mode, label, src = resolve_source_config(0, use_camera=True)
        self.assertEqual(mode, "LIVE_AI")
        self.assertEqual(src, 0)

    def test_resolve_video_file(self):
        mode, label, src = resolve_source_config("safety_feed.mp4")
        self.assertEqual(mode, "VIDEO_AI")


class TestCameraReader(unittest.TestCase):
    def test_initial_state_standby(self):
        reader = CameraReader(source="non_existent_stream.mp4")
        self.assertEqual(reader.state, "STANDBY")
        self.assertFalse(reader.running)

    def test_invalid_source_transitions_to_error(self):
        # A nonexistent video file should transition cleanly to ERROR state without network lag
        reader = CameraReader(source="non_existent_feed_9999.mp4", target_fps=30.0)
        success = reader.start()
        self.assertFalse(success)
        self.assertEqual(reader.state, "ERROR")
        self.assertIsNotNone(reader.error_message)
        reader.stop()
        self.assertEqual(reader.state, "STOPPED")


class TestWebhookDispatcher(unittest.TestCase):
    def test_disabled_by_default(self):
        dispatcher = WebhookDispatcher()
        self.assertFalse(dispatcher.is_active())

    def test_active_only_when_enabled_and_endpoint_configured(self):
        dispatcher = WebhookDispatcher(endpoint_url="https://hooks.example.com/safety", enabled=True)
        self.assertTrue(dispatcher.is_active())

        dispatcher_no_url = WebhookDispatcher(endpoint_url="", enabled=True)
        self.assertFalse(dispatcher_no_url.is_active())

    def test_payload_sanitization(self):
        dispatcher = WebhookDispatcher()
        raw_payload = {
            "incident_id": "INC-101",
            "worker_id": "W02",
            "severity": "CRITICAL",
            "frame": b"raw_binary_video_frame_data",
            "image": "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEASABIAAD...",
            "risk_score": 85.5
        }
        sanitized = dispatcher.sanitize_payload(raw_payload)
        self.assertEqual(sanitized["incident_id"], "INC-101")
        self.assertEqual(sanitized["worker_id"], "W02")
        self.assertEqual(sanitized["risk_score"], 85.5)
        self.assertNotIn("frame", sanitized)
        self.assertNotIn("image", sanitized)
        self.assertEqual(sanitized["_dispatcher"], "ErgoGuard_Enterprise_Webhook_v1")


if __name__ == "__main__":
    unittest.main()
