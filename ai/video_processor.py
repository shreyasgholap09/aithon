"""
Video Processing & Safety Telemetry Pipeline
Processes video frames through SafetyDetector and SafetyEngine,
strictly maintaining separation between LIVE_AI mode and SIMULATED demo mode.

Performance Architecture:
1. Decoupled Camera Capture: Background CameraReader thread grabs frames continuously (30 FPS);
   inference loop always receives the newest frame with zero buffering lag.
2. Inference Cadence Decoupling: Person tracking runs every frame; PPE inspection is decoupled
   at ~1.5 Hz with temporal caching (saving ~135ms on 70% of frames).
3. Payload Optimization: 640x360 downscaled frames at Q=55 reduce payload from 200 KB to ~48 KB.
4. Separate Video Stream from Telemetry: Safety alerts are sent instantly without carrying
   heavy video frames; video frames use backpressure dropping for slow consumers.
5. End-to-end telemetry profiling (FPS, latencies, breakdown) sent to debug panel.
"""

import argparse
import asyncio
import base64
import os
import sys
import time
from typing import Optional, Dict, Any, List, Tuple, Set

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from ai.camera_reader import CameraReader
from ai.detector import SafetyDetector
from ai.event_sender import EventSender
from ai.privacy_filter import PrivacyFilter
from safety_engine.risk_engine import RiskEngine
from safety_engine.webhook_dispatcher import WebhookDispatcher

DEMO_SCENARIOS = {
    "1": {
        "name": "Scenario 1: Fully Compliant Baseline",
        "worker_id": "W01",
        "location": "Assembly Line 1",
        "ppe": {"helmet": True, "vest": True},
        "posture": "SAFE",
        "fall_status": "NONE",
        "danger_zone": False
    },
    "2": {
        "name": "Scenario 2: Missing Hardhat Violation",
        "worker_id": "W02",
        "location": "Machine Zone A",
        "ppe": {"helmet": False, "vest": True},
        "posture": "SAFE",
        "fall_status": "NONE",
        "danger_zone": False
    },
    "3": {
        "name": "Scenario 3: Restricted Danger Zone Breach",
        "worker_id": "W03",
        "location": "Robotic Cell 4 Perimeter",
        "ppe": {"helmet": True, "vest": True},
        "posture": "SAFE",
        "fall_status": "NONE",
        "danger_zone": True
    },
    "4": {
        "name": "Scenario 4: Worker Fall Emergency",
        "worker_id": "W04",
        "location": "Loading Bay Ramp C",
        "ppe": {"helmet": True, "vest": True},
        "posture": "UNSAFE",
        "fall_status": "CONFIRMED_FALL",
        "danger_zone": False
    },
    "5": {
        "name": "Scenario 5: Ergonomic Strain & Missing Vest",
        "worker_id": "W05",
        "location": "Warehouse High-Rack 3",
        "ppe": {"helmet": False, "vest": False},
        "posture": "UNSAFE",
        "fall_status": "NONE",
        "danger_zone": False
    }
}

def resolve_source_config(source: Any = None, use_camera: bool = False) -> Tuple[str, str, Any]:
    """
    Resolves the execution source mode:
        source_mode: 'LIVE_AI' | 'CCTV_AI' | 'VIDEO_AI' | 'TEST_FIXTURE' | 'STANDBY'
        source_label: Human-readable label
        resolved_source: device index (int), stream URL, or file path
    """
    if source is not None and str(source).lower() == "sample":
        sample_path = os.path.join(PROJECT_ROOT, "ai", "test_sample.jpg")
        return "TEST_FIXTURE", "Test Fixture (Sample Image)", sample_path

    # IP CCTV Stream URL (rtsp://, http://, https://)
    if source is not None and isinstance(source, str) and (source.startswith("rtsp://") or source.startswith("http://") or source.startswith("https://")):
        return "CCTV_AI", f"IP CCTV Stream ({source})", source

    if source is not None and isinstance(source, str) and source.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp')):
        img_path = os.path.abspath(source) if os.path.exists(source) else os.path.join(PROJECT_ROOT, source)
        return "TEST_FIXTURE", f"Test Fixture ({os.path.basename(img_path)})", img_path

    if source is not None and isinstance(source, str) and (source.lower().endswith(('.mp4', '.avi', '.mov', '.mkv', '.webm')) or (os.path.isfile(source) and not source.isdigit())):
        vid_path = os.path.abspath(source) if os.path.exists(source) else os.path.join(PROJECT_ROOT, source)
        return "VIDEO_AI", f"Video File ({os.path.basename(vid_path)})", vid_path

    # Physical camera device explicitly requested via --camera or numeric device index (e.g. --source 0)
    if use_camera or (source is not None and (isinstance(source, int) or str(source).isdigit())):
        device_id = 0
        if source is not None:
            if isinstance(source, int):
                device_id = source
            elif str(source).isdigit():
                device_id = int(source)
        return "LIVE_AI", f"Physical Webcam (Device {device_id})", device_id

    # Default when no camera source argument is passed: start in STANDBY mode on-demand.
    # Physical camera hardware is NOT locked until requested by the user in the UI.
    return "STANDBY", "Camera Standby (On-Demand)", 0

class VideoProcessor:
    def __init__(self, source: Any = None, port: int = 8765, show_window: bool = True, use_camera: bool = False, privacy_mode: str = "OFF"):
        self.raw_source = source
        self.port = port
        self.show_window = show_window
        self.mode = "LIVE"  # "LIVE" or "DEMO"
        self.detector = SafetyDetector(ppe_interval_frames=3, max_ppe_age_sec=2.5)
        self.risk_engine = RiskEngine()
        self.event_sender = EventSender(port=port)
        self.event_sender.on_command_callback = self.handle_frontend_command
        self.event_sender.on_connect_callback = self._get_initial_state_payload
        self.privacy_filter = PrivacyFilter(mode=privacy_mode)
        self.webhook_dispatcher = WebhookDispatcher()
        self.active_demo_scenario: Optional[Dict[str, Any]] = None
        self.is_running = True
        self._loop = None

        # Resolved source configuration
        self.source_mode, self.source_label, self.resolved_source = resolve_source_config(source, use_camera)
        self.active_source = self.source_mode
        self.camera_reader: Optional[CameraReader] = None
        self.cv2 = None
        self.static_frame = None
        self.is_camera_open = False

        # Performance profiling telemetry
        self._inference_fps = 0.0
        self._inf_timestamps: List[float] = []

    def _get_initial_state_payload(self) -> Dict[str, Any]:
        """Provides instant synchronization payload for newly connected WebSocket clients."""
        reader_state = self.camera_reader.state if self.camera_reader else ("STANDBY" if self.active_source == "STANDBY" else "RUNNING")
        return {
            "type": "CAMERA_STATUS",
            "active": self.is_camera_open,
            "source": self.active_source,
            "pipeline_state": reader_state,
            "privacy_mode": self.privacy_filter.get_mode()
        }

    def _notify_camera_status(self, active: bool, error: Optional[str] = None):
        """Broadcasts camera hardware and pipeline state to connected frontend clients thread-safely."""
        reader_state = self.camera_reader.state if self.camera_reader else ("RUNNING" if active else "STANDBY")
        if error:
            reader_state = "ERROR"

        payload: Dict[str, Any] = {
            "type": "CAMERA_STATUS",
            "active": active,
            "source": self.active_source,
            "pipeline_state": reader_state,
            "privacy_mode": self.privacy_filter.get_mode()
        }
        if error:
            payload["error"] = error

        try:
            loop = getattr(self, "_loop", None)
            if loop is None or loop.is_closed():
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = asyncio.get_event_loop()
            if loop and loop.is_running():
                asyncio.run_coroutine_threadsafe(self.event_sender.broadcast_telemetry(payload), loop)
        except Exception:
            pass

    def open_camera(self, device_id: Optional[Any] = None) -> bool:
        """Acquires physical camera hardware device or CCTV stream via dedicated CameraReader thread."""
        self.release_camera()
        dev = device_id if device_id is not None else (
            self.resolved_source if (isinstance(self.resolved_source, int) or (isinstance(self.resolved_source, str) and self.resolved_source.startswith(("rtsp://", "http")))) else 0
        )

        self.camera_reader = CameraReader(source=dev, target_fps=30.0)
        success = self.camera_reader.start()
        if success:
            self.is_camera_open = True
            is_cctv = isinstance(dev, str) and (dev.startswith("rtsp://") or dev.startswith("http"))
            self.source_mode = "CCTV_AI" if is_cctv else "LIVE_AI"
            self.active_source = self.source_mode
            self.source_label = f"IP CCTV Stream ({dev})" if is_cctv else f"Physical Webcam (Device {dev})"
            print(f"[VideoProcessor] Camera reader started for source '{dev}'. State: RUNNING.")
            self._notify_camera_status(True)
            return True
        else:
            err_msg = self.camera_reader.error_message or f"Source '{dev}' not accessible"
            print(f"[VideoProcessor] Failed to start camera reader on source '{dev}': {err_msg}")
            print(f"[VideoProcessor] Operating in STANDBY. Alternatives: specify --source <video.mp4> or --source sample")
            self.camera_reader = None
            self.is_camera_open = False
            self.active_source = "STANDBY"
            self._notify_camera_status(False, err_msg)
            return False

    def release_camera(self):
        """Releases the camera hardware device cleanly."""
        if self.camera_reader is not None:
            self.camera_reader.stop()
            self.camera_reader = None
            print("[VideoProcessor] Camera reader stopped cleanly. Camera LED OFF.")
        self.is_camera_open = False
        self._notify_camera_status(False)

    def switch_source(self, new_source: Any):
        """Switches video input source cleanly without creating duplicate processing loops."""
        print(f"[VideoProcessor] Switching source to: {new_source}")
        self.release_camera()
        self.mode = "LIVE"
        self.active_demo_scenario = None
        self.source_mode, self.source_label, self.resolved_source = resolve_source_config(new_source)
        self.active_source = self.source_mode

        if self.source_mode in ("LIVE_AI", "CCTV_AI", "VIDEO_AI"):
            self.open_camera(self.resolved_source)
        elif self.source_mode == "TEST_FIXTURE":
            if self.cv2 is not None:
                self.static_frame = self.cv2.imread(self.resolved_source)
            self._notify_camera_status(True)
        elif self.source_mode == "STANDBY":
            self._notify_camera_status(False)

    def handle_frontend_command(self, cmd: str, data: Dict[str, Any]):
        """Receives mode toggles, scenario triggers, privacy modes, and camera commands from frontend."""
        print(f"[VideoProcessor] Received frontend command: {cmd}")
        if cmd.startswith("SCENARIO_"):
            scenario_key = cmd.replace("SCENARIO_", "")
            if scenario_key in DEMO_SCENARIOS:
                self.release_camera()
                self.mode = "DEMO"
                self.active_source = "SIMULATED"
                self.active_demo_scenario = DEMO_SCENARIOS[scenario_key]
                print(f"[VideoProcessor] Switched to DEMO mode: {self.active_demo_scenario['name']}")
        elif cmd == "START_CAMERA":
            print("[VideoProcessor] START_CAMERA command received. Activating webcam...")
            self.mode = "LIVE"
            self.active_demo_scenario = None
            self.open_camera(0)
        elif cmd == "STOP_CAMERA":
            print("[VideoProcessor] STOP_CAMERA command received. Deactivating webcam...")
            self.release_camera()
            self.active_source = "STANDBY"
        elif cmd == "SET_PRIVACY_MODE":
            mode = data.get("mode", "OFF")
            self.privacy_filter.set_mode(mode)
            print(f"[VideoProcessor] Privacy filter mode updated to: {self.privacy_filter.get_mode()}")
            self._notify_camera_status(self.is_camera_open)
        elif cmd == "SET_SOURCE":
            src = data.get("source")
            if src is not None:
                self.switch_source(src)
        elif cmd == "MODE_LIVE":
            self.mode = "LIVE"
            self.active_demo_scenario = None
            if self.source_mode in ("LIVE_AI", "CCTV_AI"):
                self.open_camera()
            else:
                self.active_source = self.source_mode
            print(f"[VideoProcessor] Switched to {self.active_source} mode.")
        elif cmd == "RESET":
            self.active_demo_scenario = None
            self.mode = "LIVE"
            self.release_camera()
            self.risk_engine.alert_manager.reset()
            self.active_source = self.source_mode
            print("[VideoProcessor] Alert manager reset. Operating in LIVE mode.")

    def _draw_scene_overlay(self, frame, detections, cv2):
        """Draws danger zone, worker boxes, tracker IDs, and safety status badges on frame."""
        h, w = frame.shape[:2]

        # 1. Draw Configured Polygonal Danger Zones
        for zone in self.detector.zone_detector.zones:
            poly_pts = self.detector.zone_detector.get_pixel_polygon(zone, w, h)
            if len(poly_pts) >= 3:
                import numpy as np
                pts_array = np.array(poly_pts, dtype=np.int32).reshape((-1, 1, 2))
                color = zone.get("color_bgr", [0, 0, 240])
                color_tuple = (int(color[0]), int(color[1]), int(color[2]))

                # Semi-transparent overlay
                overlay = frame.copy()
                cv2.fillPoly(overlay, [pts_array], color_tuple)
                cv2.addWeighted(overlay, 0.15, frame, 0.85, 0, frame)
                cv2.polylines(frame, [pts_array], isClosed=True, color=color_tuple, thickness=2)

                # Zone label
                label_x = int(min(p[0] for p in poly_pts)) + 10
                label_y = int(min(p[1] for p in poly_pts)) + 22
                z_title = zone.get("name") or zone.get("zone_name", "HAZARD ZONE")
                cv2.putText(frame, z_title.upper(), (label_x, label_y),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.48, color_tuple, 2)

        # 2. Draw Detected Workers
        for det in detections:
            bx, by, bw, bh = det["bbox"]
            risk_level = det.get("risk_level", "SAFE")

            if risk_level == "CRITICAL":
                box_color = (0, 0, 255)  # Bright Red
            elif risk_level in ("HIGH", "MEDIUM"):
                box_color = (0, 165, 255)  # Amber
            else:
                box_color = (0, 220, 0)  # Green

            # Bounding box
            cv2.rectangle(frame, (bx, by), (bx + bw, by + bh), box_color, 2)

            # Top label badge: Worker ID & Confidence
            w_id = det.get("worker_id", "W01")
            conf = int(det.get("confidence", 0.90) * 100)
            top_label = f"{w_id} ({conf}%)"
            (tw, th), _ = cv2.getTextSize(top_label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(frame, (bx, max(0, by - 22)), (bx + tw + 10, by), box_color, -1)
            cv2.putText(frame, top_label, (bx + 5, by - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

            # Sub-badges for PPE and Posture
            h_status = det.get("ppe", {}).get("helmet", {}).get("status", "UNKNOWN")
            v_status = det.get("ppe", {}).get("vest", {}).get("status", "UNKNOWN")
            fall = det.get("fall_status", "NONE")
            posture = det.get("posture", "SAFE")

            badge_y = by + 20
            h_txt = "Hardhat: OK" if h_status == "PRESENT" else ("NO Hardhat" if h_status == "MISSING" else "Hardhat: ?")
            h_col = (0, 200, 0) if h_status == "PRESENT" else ((0, 0, 255) if h_status == "MISSING" else (180, 180, 180))
            cv2.putText(frame, h_txt, (bx + 5, badge_y), cv2.FONT_HERSHEY_SIMPLEX, 0.45, h_col, 1)

            badge_y += 18
            v_txt = "Vest: OK" if v_status == "PRESENT" else ("NO Vest" if v_status == "MISSING" else "Vest: ?")
            v_col = (0, 200, 0) if v_status == "PRESENT" else ((0, 0, 255) if v_status == "MISSING" else (180, 180, 180))
            cv2.putText(frame, v_txt, (bx + 5, badge_y), cv2.FONT_HERSHEY_SIMPLEX, 0.45, v_col, 1)

            if fall == "CONFIRMED_FALL":
                badge_y += 18
                cv2.putText(frame, "EMERGENCY: FALL", (bx + 5, badge_y), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 255), 2)
            elif posture == "UNSAFE":
                badge_y += 18
                cv2.putText(frame, "POSTURE: STRAIN", (bx + 5, badge_y), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 165, 255), 1)

        # Mode stamp with honest source label
        if self.mode == "DEMO":
            mode_txt = f"DEMO: {self.active_demo_scenario.get('name', '')}"
            mode_col = (0, 255, 255)
        elif self.active_source == "LIVE_AI":
            mode_txt = "LIVE CAMERA AI"
            mode_col = (0, 255, 0)
        elif self.active_source == "VIDEO_AI":
            mode_txt = f"PRERECORDED VIDEO AI ({self.source_label})"
            mode_col = (255, 200, 0)
        elif self.active_source == "TEST_FIXTURE":
            mode_txt = "TEST FIXTURE (STATIC SAMPLE)"
            mode_col = (200, 200, 200)
        else:
            mode_txt = "CAMERA STANDBY"
            mode_col = (140, 140, 140)

        cv2.putText(frame, mode_txt, (15, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.60, mode_col, 2)
        cv2.putText(frame, f"Active Monitored Workers: {len(detections)}", (15, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)

    async def run(self):
        self._loop = asyncio.get_running_loop()
        # 1. Start WebSocket Server
        await self.event_sender.start()
        print("\n" + "=" * 70)
        print(" ErgoGuard AI — Intelligent Workplace Safety Platform")
        print(f" Transport: ws://127.0.0.1:{self.event_sender.port}")
        print(f" Source Mode: {self.source_mode} ({self.source_label})")
        print(" Commands: [C] Toggle Webcam, [L] Live Mode, [1-5] Scenarios, [Q] Quit")
        print("=" * 70 + "\n")

        try:
            import cv2 as _cv2
            self.cv2 = _cv2
        except Exception:
            print("[VideoProcessor] OpenCV not available. Running in headless event mode.")

        # Initialize source devices
        if self.cv2 is not None:
            if self.source_mode == "TEST_FIXTURE":
                if os.path.exists(self.resolved_source):
                    self.static_frame = self.cv2.imread(self.resolved_source)
                    self.active_source = "TEST_FIXTURE"
            elif self.source_mode == "VIDEO_AI":
                self.camera_reader = CameraReader(source=self.resolved_source, target_fps=30.0)
                success = self.camera_reader.start()
                if success:
                    self.is_camera_open = True
                    self.active_source = "VIDEO_AI"
                else:
                    print(f"[VideoProcessor] Failed to open video file: {self.resolved_source}")
                    self.active_source = "STANDBY"
            elif self.source_mode == "LIVE_AI":
                self.open_camera(self.resolved_source)
            elif self.source_mode == "STANDBY":
                self.active_source = "STANDBY"
                self.is_camera_open = False
                print("[VideoProcessor] Pipeline initialized in STANDBY. Webcam hardware unlocked and available on-demand.")

        while self.is_running:
            t_cycle_start = time.perf_counter()
            frame = None
            capture_ts = t_cycle_start

            # STANDBY Mode: Camera hardware unlocked and ready; broadcast lightweight telemetry heartbeat
            if self.active_source == "STANDBY" and self.mode != "DEMO":
                empty_telemetry = {
                    "schema_version": "1.0",
                    "event_id": f"evt-standby-idle-{int(time.time() * 1000)}",
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "source": "STANDBY",
                    "lifecycle_state": "CLEAR",
                    "worker_id": "NONE",
                    "location": "Machine Zone A",
                    "ppe": {
                        "helmet": {"status": "UNKNOWN", "confidence": 0.0},
                        "vest": {"status": "UNKNOWN", "confidence": 0.0}
                    },
                    "posture": "UNKNOWN",
                    "fall_status": "NONE",
                    "danger_zone": {"entered": False, "zone_id": "", "zone_name": ""},
                    "violations": [],
                    "risk_score": 0,
                    "risk_level": "SAFE",
                    "confidence": 1.0,
                    "details": "Camera in standby. Click 'Turn Camera On' to begin live AI monitoring."
                }
                await self.event_sender.broadcast_telemetry(empty_telemetry)
                await asyncio.sleep(0.15)
                continue

            # 1. Grab newest frame from CameraReader without buffering lag
            if self.camera_reader is not None and self.camera_reader.running:
                f, ts, fid = self.camera_reader.get_latest_frame()
                if f is not None:
                    frame = f
                    capture_ts = ts


            # 2. Grab static test fixture frame
            elif self.source_mode == "TEST_FIXTURE" and self.static_frame is not None and self.mode != "DEMO":
                frame = self.static_frame.copy()

            # 3. Clean fallback canvas if no camera input or standby
            if frame is None and self.cv2 is not None:
                import numpy as np
                frame = np.zeros((360, 640, 3), dtype=np.uint8)
                frame[::40, :, :] = (25, 25, 30)
                frame[:, ::40, :] = (25, 25, 30)
                standby_msg = "ErgoGuard AI - Camera Standby" if self.active_source == "STANDBY" else "Waiting for Video Stream..."
                self.cv2.putText(frame, standby_msg, (130, 170),
                                self.cv2.FONT_HERSHEY_SIMPLEX, 0.65, (140, 140, 160), 1)
                self.cv2.putText(frame, "Connect Webcam or run with --source <video/sample>", (100, 205),
                                self.cv2.FONT_HERSHEY_SIMPLEX, 0.5, (100, 100, 120), 1)

            # -------------------------------------------------------------
            # EXECUTION BRANCH: DEMO MODE vs LIVE/VIDEO/FIXTURE MODE
            # -------------------------------------------------------------
            frame_image_b64 = None
            analyzed_workers = []
            encode_ms = 0.0

            if self.mode == "DEMO" and self.active_demo_scenario is not None:
                # DEMO MODE: Build clearly labeled simulated event (Webcam is OFF)
                detection = self.detector.build_simulated_worker(self.active_demo_scenario)
                event, new_incidents, resolved_incidents = self.risk_engine.assess_worker(
                    worker_id=detection["worker_id"],
                    location=detection["location"],
                    ppe=detection["ppe"],
                    posture=detection["posture"],
                    fall_input=detection["fall_status"],
                    danger_zone_input=detection["danger_zone"],
                    confidence=detection["confidence"],
                    source="SIMULATED",
                    is_observed=True
                )
                event["bbox"] = detection["bbox"]
                analyzed_workers.append(event)

                display_frame = None
                if self.cv2 is not None and frame is not None:
                    display_frame = self.privacy_filter.apply(frame.copy(), analyzed_workers)
                    self._draw_scene_overlay(display_frame, analyzed_workers, self.cv2)
                    t_enc0 = time.perf_counter()
                    scaled = self.cv2.resize(display_frame, (640, 360), interpolation=self.cv2.INTER_LINEAR)
                    _, buf = self.cv2.imencode('.jpg', scaled, [int(self.cv2.IMWRITE_JPEG_QUALITY), 55])
                    frame_image_b64 = f"data:image/jpeg;base64,{base64.b64encode(buf).decode('utf-8')}"
                    encode_ms = (time.perf_counter() - t_enc0) * 1000.0

                metrics = {
                    "capture_fps": 30.0,
                    "inference_fps": round(self._inference_fps, 1),
                    "person_det_ms": 0.0,
                    "ppe_det_ms": 0.0,
                    "encode_ms": round(encode_ms, 1),
                    "tx_ms": round(self.event_sender.last_tx_ms, 1),
                    "e2e_latency_ms": round((time.perf_counter() - capture_ts) * 1000.0, 1),
                    "ppe_reused": False,
                    "active_source": "SIMULATED",
                    "privacy_mode": self.privacy_filter.get_mode(),
                    "pipeline_state": "RUNNING"
                }
                await self.event_sender.broadcast_video_frame(frame_image_b64, metrics=metrics)
                await self.event_sender.broadcast_telemetry(event)

            else:
                # REAL INFERENCE (LIVE_AI, VIDEO_AI, or TEST_FIXTURE)
                current_effective_source = self.active_source
                live_detections = []

                if frame is not None and self.active_source != "STANDBY":
                    live_detections = self.detector.detect_live_workers(
                        frame,
                        location="Machine Zone A",
                        source=current_effective_source
                    )

                det_metrics = self.detector.last_metrics
                visible_worker_ids = set()

                if not live_detections:
                    # Check if previously tracked workers have disappeared
                    stale_incidents = self.risk_engine.alert_manager.handle_disappeared_workers(set())
                    for inc in stale_incidents:
                        await self.event_sender.broadcast_telemetry({
                            "type": "INCIDENT_STALE",
                            "incident": inc,
                            "source": current_effective_source,
                            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                        })

                    display_frame = None
                    if self.cv2 is not None and frame is not None:
                        display_frame = self.privacy_filter.apply(frame.copy(), [])
                        self._draw_scene_overlay(display_frame, [], self.cv2)
                        t_enc0 = time.perf_counter()
                        scaled = self.cv2.resize(display_frame, (640, 360), interpolation=self.cv2.INTER_LINEAR)
                        _, buf = self.cv2.imencode('.jpg', scaled, [int(self.cv2.IMWRITE_JPEG_QUALITY), 55])
                        frame_image_b64 = f"data:image/jpeg;base64,{base64.b64encode(buf).decode('utf-8')}"
                        encode_ms = (time.perf_counter() - t_enc0) * 1000.0

                    empty_telemetry = {
                        "schema_version": "1.0",
                        "event_id": f"evt-{current_effective_source.lower()}-idle-{int(time.time() * 1000)}",
                        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        "source": current_effective_source,
                        "lifecycle_state": "CLEAR",
                        "worker_id": "NONE",
                        "location": "Machine Zone A",
                        "ppe": {
                            "helmet": {"status": "UNKNOWN", "confidence": 0.0},
                            "vest": {"status": "UNKNOWN", "confidence": 0.0}
                        },
                        "posture": "UNKNOWN",
                        "fall_status": "NONE",
                        "danger_zone": {"entered": False, "zone_id": "", "zone_name": ""},
                        "violations": [],
                        "risk_score": 0,
                        "risk_level": "SAFE",
                        "confidence": 1.0,
                        "details": "Area clear. No workers currently in optical field of view." if self.active_source != "STANDBY" else "Camera standby. Waiting for stream input."
                    }

                    pipeline_st = self.camera_reader.state if self.camera_reader else ("RUNNING" if self.active_source != "STANDBY" else "STANDBY")
                    metrics = {
                        "capture_fps": round(self.camera_reader.capture_fps if self.camera_reader else (30.0 if self.active_source == "TEST_FIXTURE" else 0.0), 1),
                        "inference_fps": round(self._inference_fps, 1),
                        "person_det_ms": det_metrics["person_det_ms"],
                        "ppe_det_ms": det_metrics["ppe_det_ms"],
                        "encode_ms": round(encode_ms, 1),
                        "tx_ms": round(self.event_sender.last_tx_ms, 1),
                        "e2e_latency_ms": round((time.perf_counter() - capture_ts) * 1000.0, 1),
                        "ppe_reused": det_metrics["ppe_reused"],
                        "active_source": current_effective_source,
                        "privacy_mode": self.privacy_filter.get_mode(),
                        "pipeline_state": pipeline_st
                    }
                    await self.event_sender.broadcast_video_frame(frame_image_b64, metrics=metrics)
                    await self.event_sender.broadcast_telemetry(empty_telemetry)

                else:
                    for det in live_detections:
                        w_id = det["worker_id"]
                        visible_worker_ids.add(w_id)
                        event, new_incidents, resolved_incidents = self.risk_engine.assess_worker(
                            worker_id=w_id,
                            location=det["location"],
                            ppe=det["ppe"],
                            posture=det["posture"],
                            fall_input=det["fall_status"],
                            danger_zone_input=det["danger_zone"],
                            spine_angle=det.get("spine_angle", 0.0),
                            confidence=det["confidence"],
                            source=current_effective_source,
                            is_observed=True
                        )
                        event["bbox"] = det["bbox"]
                        analyzed_workers.append(event)

                        # Broadcast newly confirmed incident records
                        for inc in new_incidents:
                            await self.event_sender.broadcast_telemetry({
                                "type": "INCIDENT_UPDATE",
                                "incident": inc,
                                "source": current_effective_source,
                                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                            })
                            if self.webhook_dispatcher.is_active():
                                asyncio.create_task(self.webhook_dispatcher.dispatch(inc))

                        # Broadcast resolved incident records
                        for inc in resolved_incidents:
                            await self.event_sender.broadcast_telemetry({
                                "type": "INCIDENT_RESOLVED",
                                "incident": inc,
                                "source": current_effective_source,
                                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                            })

                    # Handle workers who were active but disappeared from optical view
                    stale_incidents = self.risk_engine.alert_manager.handle_disappeared_workers(visible_worker_ids)
                    for inc in stale_incidents:
                        await self.event_sender.broadcast_telemetry({
                            "type": "INCIDENT_STALE",
                            "incident": inc,
                            "source": current_effective_source,
                            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                        })

                    display_frame = None
                    if self.cv2 is not None and frame is not None:
                        display_frame = self.privacy_filter.apply(frame.copy(), analyzed_workers)
                        self._draw_scene_overlay(display_frame, analyzed_workers, self.cv2)
                        t_enc0 = time.perf_counter()
                        scaled = self.cv2.resize(display_frame, (640, 360), interpolation=self.cv2.INTER_LINEAR)
                        _, buf = self.cv2.imencode('.jpg', scaled, [int(self.cv2.IMWRITE_JPEG_QUALITY), 55])
                        frame_image_b64 = f"data:image/jpeg;base64,{base64.b64encode(buf).decode('utf-8')}"
                        encode_ms = (time.perf_counter() - t_enc0) * 1000.0

                    pipeline_st = self.camera_reader.state if self.camera_reader else ("RUNNING" if self.active_source != "STANDBY" else "STANDBY")
                    metrics = {
                        "capture_fps": round(self.camera_reader.capture_fps if self.camera_reader else (30.0 if self.active_source == "TEST_FIXTURE" else 0.0), 1),
                        "inference_fps": round(self._inference_fps, 1),
                        "person_det_ms": det_metrics["person_det_ms"],
                        "ppe_det_ms": det_metrics["ppe_det_ms"],
                        "encode_ms": round(encode_ms, 1),
                        "tx_ms": round(self.event_sender.last_tx_ms, 1),
                        "e2e_latency_ms": round((time.perf_counter() - capture_ts) * 1000.0, 1),
                        "ppe_reused": det_metrics["ppe_reused"],
                        "active_source": current_effective_source,
                        "privacy_mode": self.privacy_filter.get_mode(),
                        "pipeline_state": pipeline_st
                    }

                    # Broadcast video frame payload
                    await self.event_sender.broadcast_video_frame(frame_image_b64, metrics=metrics)

                    # Broadcast clean, lightweight telemetry events
                    for ev in analyzed_workers:
                        await self.event_sender.broadcast_telemetry(ev)

            # Measure rolling inference FPS
            t_now = time.perf_counter()
            self._inf_timestamps.append(t_now)
            self._inf_timestamps = [t for t in self._inf_timestamps if (t_now - t) <= 2.0]
            if len(self._inf_timestamps) > 1:
                self._inference_fps = (len(self._inf_timestamps) - 1) / (self._inf_timestamps[-1] - self._inf_timestamps[0] + 1e-6)

            # Optional desktop window visualizer
            if self.show_window and self.cv2 is not None:
                vis_frame = display_frame if ('display_frame' in locals() and display_frame is not None) else frame
                if vis_frame is not None:
                    try:
                        self.cv2.imshow("ErgoGuard AI - Live Inference Pipeline", vis_frame)
                        key = self.cv2.waitKey(1) & 0xFF
                        if key == ord('q'):
                            break
                        elif key == ord('c'):
                            if self.camera_reader is None:
                                self.open_camera(0)
                            else:
                                self.release_camera()
                        elif key == ord('l'):
                            self.mode = "LIVE"
                            self.active_demo_scenario = None
                            if self.source_mode == "LIVE_AI":
                                self.open_camera()
                            else:
                                self.active_source = self.source_mode
                        elif key == ord('r'):
                            self.handle_frontend_command("RESET", {})
                        elif chr(key) in DEMO_SCENARIOS:
                            self.handle_frontend_command(f"SCENARIO_{chr(key)}", {})
                    except Exception:
                        pass

            await asyncio.sleep(0.01)

        self.release_camera()
        if self.cv2 is not None and self.show_window:
            try:
                self.cv2.destroyAllWindows()
            except Exception:
                pass

def main():
    parser = argparse.ArgumentParser(description="ErgoGuard AI High-Performance Video Pipeline")
    parser.add_argument("--camera", action="store_true", help="Explicitly activate physical PC webcam")
    parser.add_argument("--source", default=None, help="Camera index (e.g. 0), video file path, or 'sample'")
    parser.add_argument("--port", type=int, default=8765, help="WebSocket port (default 8765)")
    parser.add_argument("--nowin", action="store_true", help="Disable desktop OpenCV window")
    args = parser.parse_args()

    processor = VideoProcessor(source=args.source, port=args.port, show_window=not args.nowin, use_camera=args.camera)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(processor.run())
    except KeyboardInterrupt:
        print("\n[VideoProcessor] Pipeline stopped by user.")
    finally:
        processor.release_camera()

if __name__ == "__main__":
    main()
