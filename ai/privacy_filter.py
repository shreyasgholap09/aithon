"""
Privacy Filter Module for ErgoGuard AI (Layer 1 - Ingestion & Privacy)
Provides automated face blurring and skeleton-only anonymization before frames
are displayed, transmitted via WebSocket, or exported.

Privacy Modes:
- 'OFF': Full optical preview without privacy transformations.
- 'BLUR_FACES': Detects facial regions of all tracked workers and applies heavy Gaussian blurring.
- 'SKELETON_ONLY': Renders an anonymized dark silhouette canvas displaying only bounding boxes,
                   joint kinematics, and danger zone boundaries with zero optical facial/environmental data.

LIMITATIONS & DISCLAIMER:
Face blurring and automated privacy filtering are computer vision heuristics.
They significantly reduce visual identification but DO NOT guarantee complete, irreversible anonymity
under all optical angles, lighting variations, or partial occlusions.
"""

import os
from typing import List, Dict, Any, Optional, Tuple
import numpy as np

SUPPORTED_PRIVACY_MODES = ("OFF", "BLUR_FACES", "SKELETON_ONLY")

class PrivacyFilter:
    def __init__(self, mode: str = "OFF", blur_kernel_size: int = 45):
        """
        Initializes the privacy filter.
        Args:
            mode: Initial privacy mode ('OFF', 'BLUR_FACES', 'SKELETON_ONLY')
            blur_kernel_size: Odd integer kernel size for Gaussian blurring (default 45)
        """
        self.mode = mode.upper() if mode and mode.upper() in SUPPORTED_PRIVACY_MODES else "OFF"
        self.blur_kernel_size = blur_kernel_size if blur_kernel_size % 2 == 1 else blur_kernel_size + 1
        self._cv2 = None
        self._cascade = None
        self.faces_blurred_count = 0
        self.frames_processed = 0
        self.last_status = "INITIALIZED"
        self._init_cv2()

    def _init_cv2(self):
        try:
            import cv2
            self._cv2 = cv2
            # Check for optional OpenCV Haar cascade if available on disk
            cascade_candidates = [
                os.path.join(os.path.dirname(__file__), "models", "haarcascade_frontalface_default.xml"),
                getattr(getattr(cv2, "data", None), "haarcascades", "") + "haarcascade_frontalface_default.xml"
            ]
            for p in cascade_candidates:
                if p and os.path.exists(p):
                    try:
                        self._cascade = cv2.CascadeClassifier(p)
                        if not self._cascade.empty():
                            break
                    except Exception:
                        pass
        except ImportError:
            self._cv2 = None
            self.last_status = "OPENCV_UNAVAILABLE"

    def set_mode(self, mode: str) -> bool:
        """Sets active privacy mode safely."""
        norm = str(mode).upper().strip()
        if norm in SUPPORTED_PRIVACY_MODES:
            self.mode = norm
            self.last_status = f"MODE_SET_{norm}"
            return True
        return False

    def get_mode(self) -> str:
        return self.mode

    def apply(
        self,
        frame: Optional[np.ndarray],
        worker_detections: Optional[List[Dict[str, Any]]] = None
    ) -> Optional[np.ndarray]:
        """
        Applies active privacy filter to a copy of the input frame.
        The original input frame remains untouched in memory for uncompromised AI inference.
        """
        if frame is None or frame.size == 0 or self._cv2 is None:
            return frame

        self.frames_processed += 1

        if self.mode == "OFF":
            return frame

        h, w = frame.shape[:2]
        output_frame = frame.copy()

        # -------------------------------------------------------------
        # MODE: SKELETON_ONLY
        # -------------------------------------------------------------
        if self.mode == "SKELETON_ONLY":
            # Create high-contrast anonymized dark canvas
            canvas = np.zeros((h, w, 3), dtype=np.uint8)
            canvas[:] = (15, 18, 24)  # Deep slate background

            # Subtle grid lines
            canvas[::30, :, :] = (25, 30, 40)
            canvas[:, ::30, :] = (25, 30, 40)

            # Draw anonymized worker bounding boxes and center anchors
            if worker_detections:
                for det in worker_detections:
                    bx, by, bw, bh = det.get("bbox", (0, 0, 0, 0))
                    if bw > 0 and bh > 0:
                        risk_level = det.get("risk_level", "SAFE")
                        color = (0, 0, 255) if risk_level == "CRITICAL" else ((0, 165, 255) if risk_level in ("HIGH", "MEDIUM") else (0, 220, 0))
                        
                        # Anonymized wireframe box
                        self._cv2.rectangle(canvas, (bx, by), (bx + bw, by + bh), color, 2)
                        
                        # Kinetic center anchor
                        cx, cy = int(bx + bw / 2), int(by + bh / 2)
                        self._cv2.circle(canvas, (cx, cy), 5, (255, 255, 255), -1)
                        
                        # Head anchor indicator
                        head_y = int(by + bh * 0.15)
                        self._cv2.circle(canvas, (cx, head_y), 6, color, 2)

            self._cv2.putText(
                canvas,
                "PRIVACY-PRESERVING SKELETON DISPLAY (ANONYMIZED)",
                (15, 25),
                self._cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (0, 215, 255),
                1
            )
            return canvas

        # -------------------------------------------------------------
        # MODE: BLUR_FACES
        # -------------------------------------------------------------
        if self.mode == "BLUR_FACES":
            blurred_any = False

            # Strategy 1: Face detection via Haar Cascade if loaded
            if self._cascade is not None and not self._cascade.empty():
                try:
                    gray = self._cv2.cvtColor(output_frame, self._cv2.COLOR_BGR2GRAY)
                    faces = self._cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(30, 30))
                    for (fx, fy, fw, fh) in faces:
                        output_frame = self._blur_region(output_frame, fx, fy, fw, fh)
                        self.faces_blurred_count += 1
                        blurred_any = True
                except Exception:
                    pass

            # Strategy 2: Worker Bounding Box Geometric Head Localization
            # When full-body YOLO detects a person (x, y, w, h), the face region is
            # reliably located within the upper 28% vertical slice of the torso bbox.
            if worker_detections:
                for det in worker_detections:
                    bx, by, bw, bh = det.get("bbox", (0, 0, 0, 0))
                    if bw > 15 and bh > 30:
                        # Geometrically bounded facial ROI
                        fx = max(0, int(bx + bw * 0.15))
                        fy = max(0, by)
                        fw = max(10, min(int(bw * 0.70), w - fx))
                        fh = max(10, min(int(bh * 0.28), h - fy))
                        output_frame = self._blur_region(output_frame, fx, fy, fw, fh)
                        self.faces_blurred_count += 1
                        blurred_any = True

            # Privacy mode watermark badge
            self._cv2.putText(
                output_frame,
                "PRIVACY FILTER: FACE BLURRING ACTIVE",
                (15, 25),
                self._cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (0, 230, 180),
                2
            )
            return output_frame

        return output_frame

    def _blur_region(self, frame: np.ndarray, x: int, y: int, w: int, h: int) -> np.ndarray:
        """Applies heavy Gaussian blurring to specified rectangular ROI."""
        fh, fw = frame.shape[:2]
        x1 = max(0, min(x, fw - 1))
        y1 = max(0, min(y, fh - 1))
        x2 = max(x1 + 1, min(x + w, fw))
        y2 = max(y1 + 1, min(y + h, fh))

        roi = frame[y1:y2, x1:x2]
        if roi.size == 0 or roi.shape[0] < 3 or roi.shape[1] < 3:
            return frame

        k = self.blur_kernel_size
        k = k if k % 2 == 1 else k + 1
        # Heavy dual-pass Gaussian blur for irreversible anonymization
        blurred = self._cv2.GaussianBlur(roi, (k, k), 30)
        blurred = self._cv2.GaussianBlur(blurred, (k, k), 30)
        frame[y1:y2, x1:x2] = blurred
        return frame

    def get_diagnostics(self) -> Dict[str, Any]:
        """Returns runtime privacy filter status and diagnostics."""
        return {
            "mode": self.mode,
            "status": self.last_status,
            "supported_modes": list(SUPPORTED_PRIVACY_MODES),
            "faces_blurred_count": self.faces_blurred_count,
            "frames_processed": self.frames_processed,
            "disclaimer": "Automated privacy heuristics reduce visual identification but do not guarantee complete anonymity."
        }
