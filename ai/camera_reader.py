"""
Threaded Camera & Video Capture Module (Layer 1 - Ingestion & Privacy)
Decouples camera/video I/O from AI model inference and network transmission.
Runs a background reader thread that continuously reads physical camera frames,
CCTV RTSP/HTTP streams, or prerecorded video files into a thread-safe latest-frame
buffer (size=1), discarding stale frames automatically.

Lifecycle States:
- STANDBY: Hardware unlocked and idle
- STARTING: Initializing device or establishing stream connection
- RUNNING: Active capture loop acquiring frames
- STOPPED: Capture terminated and device resources released
- ERROR: Capture device failed, in use, or stream unreachable
"""

import os
import sys
import threading
import time
from typing import Tuple, Optional, Any
import numpy as np

STATE_STANDBY = "STANDBY"
STATE_STARTING = "STARTING"
STATE_RUNNING = "RUNNING"
STATE_STOPPED = "STOPPED"
STATE_ERROR = "ERROR"

class CameraReader:
    def __init__(self, source: Any = 0, target_fps: float = 30.0):
        self.source = source
        self.target_fps = target_fps
        self.running = False
        self.state = STATE_STANDBY
        self.error_message: Optional[str] = None
        self.thread: Optional[threading.Thread] = None
        self.lock = threading.Lock()
        
        # Latest frame buffer (size = 1)
        self.latest_frame: Optional[np.ndarray] = None
        self.latest_timestamp: float = 0.0
        self.frame_id: int = 0
        
        # Capture metrics
        self.capture_fps: float = 0.0
        self._frame_counter: int = 0
        self._last_fps_calc_time: float = 0.0

        # Capture device
        self.cap = None
        self._cv2 = None

    def start(self) -> bool:
        """Starts background frame grabber thread."""
        if self.running and self.state == STATE_RUNNING:
            return True

        self.state = STATE_STARTING
        self.error_message = None

        try:
            import cv2
            self._cv2 = cv2
        except ImportError:
            self.state = STATE_ERROR
            self.error_message = "OpenCV (cv2) library not available in Python environment."
            print(f"[CameraReader] {self.error_message}")
            return False

        device_id = 0
        is_device_index = False
        is_network_stream = False

        if isinstance(self.source, int):
            device_id = self.source
            is_device_index = True
        elif str(self.source).isdigit():
            device_id = int(self.source)
            is_device_index = True
        elif isinstance(self.source, str) and (self.source.startswith("rtsp://") or self.source.startswith("http://") or self.source.startswith("https://")):
            device_id = self.source
            is_network_stream = True
        else:
            device_id = self.source

        try:
            # Configure network timeouts for IP CCTV streams
            if is_network_stream:
                os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp|timeout;5000000"
                print(f"[CameraReader] Connecting to IP CCTV stream: {device_id}...")
                self.cap = self._cv2.VideoCapture(device_id, self._cv2.CAP_FFMPEG)
            elif is_device_index and sys.platform.startswith("win"):
                # On Windows, DirectShow avoids Media Foundation locks
                try:
                    self.cap = self._cv2.VideoCapture(device_id, self._cv2.CAP_DSHOW)
                except Exception:
                    self.cap = None

            if self.cap is None or not self.cap.isOpened():
                self.cap = self._cv2.VideoCapture(device_id)

            # Secondary fallback for laptops where device 0 is an IR camera and device 1 is RGB webcam
            if (self.cap is None or not self.cap.isOpened()) and is_device_index and device_id == 0:
                print("[CameraReader] Device 0 unavailable. Probing device 1...")
                if sys.platform.startswith("win"):
                    try:
                        self.cap = self._cv2.VideoCapture(1, self._cv2.CAP_DSHOW)
                    except Exception:
                        self.cap = None
                if self.cap is None or not self.cap.isOpened():
                    self.cap = self._cv2.VideoCapture(1)
                if self.cap is not None and self.cap.isOpened():
                    device_id = 1
                    print("[CameraReader] Successfully connected to device 1.")

            if self.cap is None or not self.cap.isOpened():
                self.state = STATE_ERROR
                self.error_message = f"Could not open video source '{device_id}'. Camera may be in use by another app or stream unreachable."
                print(f"[CameraReader] {self.error_message}")
                self.cap = None
                return False

            # Configure camera hardware properties where supported
            try:
                self.cap.set(self._cv2.CAP_PROP_BUFFERSIZE, 1)
                orig_w = self.cap.get(self._cv2.CAP_PROP_FRAME_WIDTH)
                orig_h = self.cap.get(self._cv2.CAP_PROP_FRAME_HEIGHT)
                self.cap.set(self._cv2.CAP_PROP_FRAME_WIDTH, 1280)
                self.cap.set(self._cv2.CAP_PROP_FRAME_HEIGHT, 720)
                
                # Verify camera actually captures valid frames
                ret, test_f = self.cap.read()
                if not ret or test_f is None:
                    # Revert to original resolution if custom resolution broke capture
                    self.cap.set(self._cv2.CAP_PROP_FRAME_WIDTH, orig_w)
                    self.cap.set(self._cv2.CAP_PROP_FRAME_HEIGHT, orig_h)
                    ret, test_f = self.cap.read()

                if ret and test_f is not None:
                    with self.lock:
                        self.latest_frame = test_f
                        self.latest_timestamp = time.perf_counter()
                        self.frame_id = 1
            except Exception:
                pass

            self.running = True
            self.state = STATE_RUNNING
            self._last_fps_calc_time = time.perf_counter()
            self._frame_counter = 0
            self.thread = threading.Thread(target=self._capture_loop, daemon=True, name="ErgoGuard-CameraReader")
            self.thread.start()
            print(f"[CameraReader] Capture thread started for source '{device_id}'. State: {self.state}")
            return True

        except Exception as e:
            self.state = STATE_ERROR
            self.error_message = f"Exception opening video source '{device_id}': {e}"
            print(f"[CameraReader] {self.error_message}")
            if self.cap is not None:
                try:
                    self.cap.release()
                except Exception:
                    pass
            self.cap = None
            return False

    def _capture_loop(self):
        """Continuously reads frames and stores the latest into the buffer."""
        sleep_interval = 1.0 / max(1.0, self.target_fps)
        consecutive_read_failures = 0

        while self.running and self.cap is not None:
            ret, frame = self.cap.read()
            if not ret or frame is None:
                consecutive_read_failures += 1
                # Video file reached end -> Loop seamlessly
                if isinstance(self.source, str) and not self.source.isdigit() and not (self.source.startswith("rtsp://") or self.source.startswith("http")):
                    try:
                        self.cap.set(self._cv2.CAP_PROP_POS_FRAMES, 0)
                        ret, frame = self.cap.read()
                        if ret and frame is not None:
                            consecutive_read_failures = 0
                    except Exception:
                        break

                if not ret or frame is None:
                    if consecutive_read_failures > 60:
                        # Stream disconnected or camera unplugged
                        self.state = STATE_ERROR
                        self.error_message = "Stream interrupted or camera disconnected."
                        break
                    time.sleep(0.05)
                    continue

            consecutive_read_failures = 0
            now = time.perf_counter()
            with self.lock:
                self.latest_frame = frame
                self.latest_timestamp = now
                self.frame_id += 1

            # Track frame grabber FPS
            self._frame_counter += 1
            elapsed = now - self._last_fps_calc_time
            if elapsed >= 1.0:
                self.capture_fps = round(self._frame_counter / elapsed, 1)
                self._frame_counter = 0
                self._last_fps_calc_time = now

            time.sleep(max(0.001, sleep_interval * 0.4))

    def get_latest_frame(self) -> Tuple[Optional[np.ndarray], float, int]:
        """Thread-safe retrieval of latest frame."""
        with self.lock:
            if self.latest_frame is None:
                return None, 0.0, 0
            return self.latest_frame.copy(), self.latest_timestamp, self.frame_id

    def read(self) -> Optional[np.ndarray]:
        """Convenience accessor returning latest frame or None."""
        f, _, _ = self.get_latest_frame()
        return f

    def stop(self):
        """Cleanly terminates capture thread and releases camera/stream resources."""
        self.running = False
        self.state = STATE_STOPPED
        if self.thread is not None and self.thread.is_alive():
            try:
                self.thread.join(timeout=1.0)
            except Exception:
                pass
        self.thread = None

        if self.cap is not None:
            try:
                self.cap.release()
            except Exception:
                pass
            try:
                del self.cap
            except Exception:
                pass
            self.cap = None

        with self.lock:
            self.latest_frame = None

        print("[CameraReader] Video resources released cleanly. State: STOPPED.")
