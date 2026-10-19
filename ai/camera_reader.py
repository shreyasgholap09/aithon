"""
Threaded Camera Capture Module
Decouples camera I/O from AI model inference and network transmission.
Runs a background reader thread that continuously reads physical camera frames
into a thread-safe latest-frame buffer (size=1), discarding stale frames automatically.
Guarantees inference always receives the most recent frame with zero buffering latency.
"""

import os
import sys
import threading
import time
from typing import Tuple, Optional, Any
import numpy as np

class CameraReader:
    def __init__(self, source: Any = 0, target_fps: float = 30.0):
        self.source = source
        self.target_fps = target_fps
        self.running = False
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
        if self.running:
            return True

        try:
            import cv2
            self._cv2 = cv2
        except ImportError:
            print("[CameraReader] OpenCV not available.")
            return False

        device_id = 0
        is_device_index = False
        if isinstance(self.source, int):
            device_id = self.source
            is_device_index = True
        elif str(self.source).isdigit():
            device_id = int(self.source)
            is_device_index = True
        else:
            device_id = self.source

        try:
            # On Windows, DirectShow (CAP_DSHOW) avoids Microsoft Media Foundation (MSMF) locks and initializes 4x faster
            if is_device_index and sys.platform.startswith("win"):
                try:
                    self.cap = self._cv2.VideoCapture(device_id, self._cv2.CAP_DSHOW)
                except Exception:
                    self.cap = None

            if self.cap is None or not self.cap.isOpened():
                self.cap = self._cv2.VideoCapture(device_id)

            # Secondary fallback for laptops where device 0 is an IR/virtual camera and device 1 is RGB webcam
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
                print(f"[CameraReader] Could not open video source {device_id}. Camera device may be in use by another app or disconnected.")
                self.cap = None
                return False

            # Configure camera hardware properties where supported
            try:
                self.cap.set(self._cv2.CAP_PROP_BUFFERSIZE, 1)
                # Test if 1280x720 can be set without breaking frame capture
                orig_w = self.cap.get(self._cv2.CAP_PROP_FRAME_WIDTH)
                orig_h = self.cap.get(self._cv2.CAP_PROP_FRAME_HEIGHT)
                self.cap.set(self._cv2.CAP_PROP_FRAME_WIDTH, 1280)
                self.cap.set(self._cv2.CAP_PROP_FRAME_HEIGHT, 720)
                # Verify camera actually captures with chosen resolution
                ret, test_f = self.cap.read()
                if not ret or test_f is None:
                    # Revert to original resolution if custom resolution broke capture
                    self.cap.set(self._cv2.CAP_PROP_FRAME_WIDTH, orig_w)
                    self.cap.set(self._cv2.CAP_PROP_FRAME_HEIGHT, orig_h)
                if ret and test_f is not None:
                    with self.lock:
                        self.latest_frame = test_f
                        self.latest_timestamp = time.perf_counter()
                        self.frame_id = 1
            except Exception:
                pass


            self.running = True
            self._last_fps_calc_time = time.perf_counter()
            self._frame_counter = 0
            self.thread = threading.Thread(target=self._capture_loop, daemon=True, name="ErgoGuard-CameraReader")
            self.thread.start()
            print(f"[CameraReader] Dedicated camera thread started for device {device_id}.")
            return True

        except Exception as e:
            print(f"[CameraReader] Exception opening camera {device_id}: {e}")
            self.cap = None
            return False

    def _capture_loop(self):
        """Continuously reads frames and stores the latest into the buffer."""
        sleep_interval = 1.0 / max(1.0, self.target_fps)
        while self.running and self.cap is not None:
            ret, frame = self.cap.read()
            if not ret or frame is None:
                # Video file reached end or camera disconnected
                if isinstance(self.source, str) and not self.source.isdigit():
                    # Loop video file
                    try:
                        self.cap.set(self._cv2.CAP_PROP_POS_FRAMES, 0)
                        ret, frame = self.cap.read()
                    except Exception:
                        break
                if not ret or frame is None:
                    time.sleep(0.05)
                    continue

            now = time.perf_counter()
            with self.lock:
                self.latest_frame = frame
                self.latest_timestamp = now
                self.frame_id += 1

            self._frame_counter += 1
            dt = now - self._last_fps_calc_time
            if dt >= 1.0:
                self.capture_fps = round(self._frame_counter / dt, 1)
                self._frame_counter = 0
                self._last_fps_calc_time = now

            # Slight yield to avoid spinning 100% core
            time.sleep(0.005)

    def get_latest_frame(self) -> Tuple[Optional[np.ndarray], float, int]:
        """
        Thread-safe retrieval of newest frame without waiting.
        Returns: (frame, timestamp_of_capture, frame_id)
        """
        with self.lock:
            if self.latest_frame is None:
                return None, 0.0, 0
            return self.latest_frame.copy(), self.latest_timestamp, self.frame_id

    def read(self) -> Optional[np.ndarray]:
        """Convenience method returning latest frame or None."""
        frame, _, _ = self.get_latest_frame()
        return frame

    def stop(self):
        """Clean shutdown of capture thread and release of camera device."""
        self.running = False
        if self.thread is not None and self.thread.is_alive():
            self.thread.join(timeout=1.0)
            self.thread = None

        if self.cap is not None:
            try:
                self.cap.release()
                print("[CameraReader] Physical camera released cleanly.")
            except Exception:
                pass
            self.cap = None

        with self.lock:
            self.latest_frame = None
            self.latest_timestamp = 0.0
            self.capture_fps = 0.0
