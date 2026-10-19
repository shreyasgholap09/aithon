"""
PPE Detection Module
Performs Personal Protective Equipment inspection using fine-tuned YOLOv8 PPE ONNX model
and secondary industrial color segmentation.
Detects Hardhat, NO-Hardhat, Safety Vest, NO-Safety Vest, Gloves, etc.
Distinguishes between PRESENT, MISSING, and UNKNOWN states.
Never defaults to compliant when evidence is absent.
"""

import os
from typing import Dict, Any, Tuple, Optional, List
import numpy as np

PPE_CLASSES = [
    'Fall-Detected', 'Gloves', 'Goggles', 'Hardhat', 'Mask',
    'NO-Gloves', 'NO-Goggles', 'NO-Hardhat', 'NO-Mask', 'NO-Safety Vest',
    'No_Harness', 'Person', 'Safety Vest'
]

class PPEDetector:
    def __init__(
        self,
        confidence_threshold: float = 0.35,
        nms_threshold: float = 0.45,
        confirmation_frames: int = 2,
        model_path: Optional[str] = None
    ):
        self.confidence_threshold = confidence_threshold
        self.nms_threshold = nms_threshold
        self.confirmation_frames = confirmation_frames
        self.net = None
        self.model_loaded = False
        self._cv2 = None
        # Temporal smoothing history per worker_id:
        # worker_id -> {"helmet_missing_consec": int, "vest_missing_consec": int, "last_helmet": str, "last_vest": str}
        self.worker_history: Dict[str, Dict[str, Any]] = {}
        self._init_model(model_path=model_path)

    @property
    def is_available(self) -> bool:
        return self.model_loaded and self.net is not None

    def _init_model(self, model_path: Optional[str] = None):
        try:
            import cv2
            self._cv2 = cv2
            threads = min(8, max(2, os.cpu_count() or 4))
            self._cv2.setNumThreads(threads)
            if model_path is None:
                base_dir = os.path.dirname(os.path.abspath(__file__))
                model_path = os.path.join(base_dir, "models", "ppe_yolov8.onnx")

            if os.path.exists(model_path):
                self.net = self._cv2.dnn.readNetFromONNX(model_path)
                self.model_loaded = True
                print(f"[PPEDetector] Loaded YOLOv8 PPE model from: {model_path}")
            else:
                self.model_loaded = False
                self.net = None
                print(f"[PPEDetector] PPE model not found at {model_path}. Capability reported as unavailable.")
        except Exception as e:
            self.model_loaded = False
            self.net = None
            print(f"[PPEDetector] Failed to load PPE model: {e}. Capability reported as unavailable.")

    def detect_frame_ppe(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """
        Runs full-frame inference to detect all PPE objects across the scene.
        """
        if not self.model_loaded or self.net is None or frame is None or frame.size == 0:
            return []

        h, w = frame.shape[:2]
        try:
            blob = self._cv2.dnn.blobFromImage(frame, 1.0 / 255.0, (640, 640), swapRB=True, crop=False)
            self.net.setInput(blob)
            preds = np.squeeze(self.net.forward()).T  # (8400, 17)

            boxes = []
            confidences = []
            class_ids = []
            x_factor = w / 640.0
            y_factor = h / 640.0

            for row in preds:
                scores = row[4:]
                idx = int(np.argmax(scores))
                score = float(scores[idx])
                if score >= self.confidence_threshold:
                    cx, cy, bw, bh = row[0:4]
                    x = int((cx - bw / 2.0) * x_factor)
                    y = int((cy - bh / 2.0) * y_factor)
                    boxes.append([x, y, int(bw * x_factor), int(bh * y_factor)])
                    confidences.append(score)
                    class_ids.append(idx)

            if len(boxes) == 0:
                return []

            indices = self._cv2.dnn.NMSBoxes(boxes, confidences, self.confidence_threshold, self.nms_threshold)
            results = []
            for i in indices:
                idx = i[0] if isinstance(i, (list, tuple, np.ndarray)) else i
                c_name = PPE_CLASSES[class_ids[idx]] if class_ids[idx] < len(PPE_CLASSES) else "Unknown"
                results.append({
                    "class_name": c_name,
                    "class": c_name,
                    "confidence": round(confidences[idx], 2),
                    "bbox": tuple(boxes[idx])
                })
            return results

        except Exception as err:
            print(f"[PPEDetector] Full frame error: {err}")
            return []

    def inspect_worker(
        self,
        worker_bbox: Tuple[int, int, int, int],
        frame_ppe_detections: List[Dict[str, Any]],
        worker_crop: Optional[np.ndarray] = None,
        simulated_override: Optional[Dict[str, Any]] = None,
        worker_id: Optional[str] = None,
        other_worker_bboxes: Optional[List[Tuple[int, int, int, int]]] = None
    ) -> Tuple[Dict[str, Dict[str, Any]], float]:
        """
        Inspects worker for helmet and vest compliance.
        Preserves UNKNOWN when evidence is absent or uncertain.
        Never converts UNKNOWN to MISSING.
        Labels secondary color fallback as heuristic without overriding model results.
        """
        # If simulated demo scenario
        if simulated_override is not None:
            norm = {}
            for item in ("helmet", "vest"):
                raw = simulated_override.get(item, True)
                if isinstance(raw, dict):
                    status = raw.get("status", "PRESENT")
                    conf = float(raw.get("confidence", 0.95))
                elif isinstance(raw, bool):
                    status = "PRESENT" if raw else "MISSING"
                    conf = 0.95
                else:
                    status = str(raw).upper()
                    conf = 0.90
                norm[item] = {"status": status, "confidence": conf, "method": "simulated"}
            return norm, 0.95

        wx, wy, ww, wh = worker_bbox

        # Check for invalid or degenerate worker bbox
        if ww <= 10 or wh <= 20:
            return {
                "helmet": {"status": "UNKNOWN", "confidence": 0.0, "method": "degraded_crop"},
                "vest": {"status": "UNKNOWN", "confidence": 0.0, "method": "degraded_crop"}
            }, 0.0

        # Check if head is occluded or truncated by top edge of frame
        head_occluded = wy < 5 or (worker_crop is not None and worker_crop.shape[0] < 35)

        head_top = wy - int(wh * 0.08)
        head_bottom = wy + int(wh * 0.35)
        torso_top = wy + int(wh * 0.18)
        torso_bottom = wy + int(wh * 0.75)

        helmet_status = "UNKNOWN"
        helmet_conf = 0.0
        helmet_method = "none"

        vest_status = "UNKNOWN"
        vest_conf = 0.0
        vest_method = "none"

        # Check model detections overlapping worker ROI
        for det in frame_ppe_detections:
            c_name = det.get("class_name") or det.get("class", "")
            conf = float(det.get("confidence", 0.0))
            if conf < self.confidence_threshold:
                continue

            dx, dy, dw, dh = det["bbox"]
            dcx = dx + dw // 2
            dcy = dy + dh // 2

            # Spatial association: detection center must be inside worker horizontal span
            if not (wx <= dcx <= wx + ww):
                continue

            # Ensure detection belongs to this worker rather than a closer neighboring worker
            if other_worker_bboxes:
                curr_dist_sq = (dcx - (wx + ww / 2.0)) ** 2 + (dcy - (wy + wh / 2.0)) ** 2
                is_neighbor = False
                for ob in other_worker_bboxes:
                    ox, oy, ow, oh = ob
                    if (ox, oy, ow, oh) == (wx, wy, ww, wh):
                        continue
                    other_dist_sq = (dcx - (ox + ow / 2.0)) ** 2 + (dcy - (oy + oh / 2.0)) ** 2
                    if other_dist_sq < curr_dist_sq:
                        is_neighbor = True
                        break
                if is_neighbor:
                    continue

            # Helmet check (head region)
            if not head_occluded and (head_top <= dcy <= head_bottom):
                if c_name == "Hardhat":
                    if conf > helmet_conf:
                        helmet_status = "PRESENT"
                        helmet_conf = conf
                        helmet_method = "model"
                elif c_name == "NO-Hardhat":
                    if conf > helmet_conf:
                        helmet_status = "MISSING"
                        helmet_conf = conf
                        helmet_method = "model"

            # Vest check (torso region)
            if torso_top <= dcy <= torso_bottom:
                if c_name == "Safety Vest":
                    if conf > vest_conf:
                        vest_status = "PRESENT"
                        vest_conf = conf
                        vest_method = "model"
                elif c_name == "NO-Safety Vest":
                    if conf > vest_conf:
                        vest_status = "MISSING"
                        vest_conf = conf
                        vest_method = "model"

        # Secondary heuristic color analysis: ONLY positive evidence indicator, never creates MISSING
        if worker_crop is not None and worker_crop.size > 0 and self._cv2 is not None:
            ch, cw = worker_crop.shape[:2]
            if ch >= 35 and cw >= 20:
                try:
                    # Head ROI color check (heuristic fallback only if model had no detection)
                    if helmet_status == "UNKNOWN" and not head_occluded:
                        head_roi = worker_crop[0:int(ch * 0.25), :]
                        if head_roi.size > 0:
                            hsv_head = self._cv2.cvtColor(head_roi, self._cv2.COLOR_BGR2HSV)
                            yellow_orange = (
                                self._cv2.inRange(hsv_head, np.array([16, 80, 80]), np.array([36, 255, 255])) |
                                self._cv2.inRange(hsv_head, np.array([5, 110, 100]), np.array([17, 255, 255])) |
                                self._cv2.inRange(hsv_head, np.array([0, 0, 185]), np.array([180, 45, 255]))
                            )
                            coverage = np.sum(yellow_orange > 0) / float(head_roi.shape[0] * head_roi.shape[1] + 1e-5)
                            if coverage > 0.08:
                                helmet_status = "PRESENT"
                                helmet_conf = min(0.85, round(0.55 + coverage, 2))
                                helmet_method = "heuristic_color"
                            # If coverage <= 0.08, status remains UNKNOWN (never MISSING!)

                    # Torso ROI color check (heuristic fallback only if model had no detection)
                    if vest_status == "UNKNOWN":
                        torso_roi = worker_crop[int(ch * 0.20):int(ch * 0.65), :]
                        if torso_roi.size > 0:
                            hsv_torso = self._cv2.cvtColor(torso_roi, self._cv2.COLOR_BGR2HSV)
                            hi_vis = (
                                self._cv2.inRange(hsv_torso, np.array([16, 90, 80]), np.array([36, 255, 255])) |
                                self._cv2.inRange(hsv_torso, np.array([5, 120, 100]), np.array([17, 255, 255]))
                            )
                            coverage_t = np.sum(hi_vis > 0) / float(torso_roi.shape[0] * torso_roi.shape[1] + 1e-5)
                            if coverage_t > 0.12:
                                vest_status = "PRESENT"
                                vest_conf = min(0.85, round(0.55 + coverage_t, 2))
                                vest_method = "heuristic_color"
                            # If coverage_t <= 0.12, status remains UNKNOWN (never MISSING!)

                except Exception:
                    pass

        # If model is unavailable and no heuristic match was found, explicitly report capability as unavailable/unknown
        if not self.model_loaded:
            if helmet_method == "none":
                helmet_status = "UNKNOWN"
                helmet_conf = 0.0
                helmet_method = "model_unavailable"
            if vest_method == "none":
                vest_status = "UNKNOWN"
                vest_conf = 0.0
                vest_method = "model_unavailable"

        # Temporal confirmation and hysteresis per tracked worker_id
        if worker_id is not None:
            if worker_id not in self.worker_history:
                self.worker_history[worker_id] = {
                    "helmet_missing_consec": 0,
                    "vest_missing_consec": 0,
                    "last_helmet": helmet_status,
                    "last_vest": vest_status
                }
            hist = self.worker_history[worker_id]

            # Helmet temporal smoothing: single frame missing remains UNKNOWN until confirmed
            if helmet_status == "MISSING":
                hist["helmet_missing_consec"] += 1
                if hist["helmet_missing_consec"] < self.confirmation_frames:
                    helmet_status = "UNKNOWN"
                    helmet_conf = 0.40
            else:
                hist["helmet_missing_consec"] = 0

            # Vest temporal smoothing: single frame missing remains UNKNOWN until confirmed
            if vest_status == "MISSING":
                hist["vest_missing_consec"] += 1
                if hist["vest_missing_consec"] < self.confirmation_frames:
                    vest_status = "UNKNOWN"
                    vest_conf = 0.40
            else:
                hist["vest_missing_consec"] = 0

            hist["last_helmet"] = helmet_status
            hist["last_vest"] = vest_status

        # Calculate overall confidence
        valid_confs = [c for c in (helmet_conf, vest_conf) if c > 0.0]
        overall_conf = round(float(np.mean(valid_confs)), 2) if valid_confs else 0.0

        return {
            "helmet": {
                "status": str(helmet_status),
                "confidence": float(round(helmet_conf, 2)),
                "method": str(helmet_method)
            },
            "vest": {
                "status": str(vest_status),
                "confidence": float(round(vest_conf, 2)),
                "method": str(vest_method)
            }
        }, float(overall_conf)
