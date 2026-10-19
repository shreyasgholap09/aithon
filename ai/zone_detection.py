"""
Danger-Zone & Geofencing Module
Defines restricted hazardous areas as configurable polygons in normalized [0.0, 1.0] coordinates,
dynamically scales to frame dimensions, and performs geometric intrusion and transition checks.
"""

import json
import os
import time
from typing import List, Tuple, Optional, Dict, Any, Union
from ai.geometry import (
    point_in_polygon,
    get_bottom_center_point,
    scale_polygon_coordinates,
    calculate_ioa,
    to_box_coords
)

DEFAULT_CONFIG_FILES = [
    os.path.join(os.path.dirname(__file__), "sample_danger_zones.json"),
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "sample_danger_zones.json")
]


class ZoneDetector:
    def __init__(
        self,
        normalized_zones: Optional[List[Dict[str, Any]]] = None,
        config_path: Optional[str] = None
    ):
        """
        Initializes the Danger Zone detector.
        Supports normalized polygon coordinates: [[x1, y1], [x2, y2], ...]
        and legacy norm_rect tuples: (nx, ny, nw, nh).
        """
        self.zones: List[Dict[str, Any]] = []
        self.config_path = config_path

        if normalized_zones is not None:
            self.zones = [self._normalize_zone_spec(z) for z in normalized_zones]
        elif config_path and os.path.exists(config_path):
            self.load_zones_from_file(config_path)
        else:
            # Attempt loading from default configuration files
            loaded = False
            for p in DEFAULT_CONFIG_FILES:
                if os.path.exists(p):
                    self.load_zones_from_file(p)
                    loaded = True
                    break
            if not loaded:
                # Default baseline zone for Robotic Cell 4
                self.zones = [
                    self._normalize_zone_spec({
                        "id": "ZONE_ROBOT_CELL_4",
                        "zone_id": "ZONE_ROBOT_CELL_4",
                        "name": "Robotic Cell 4 Perimeter",
                        "zone_name": "Robotic Cell 4 Perimeter",
                        "severity": "CRITICAL",
                        "polygon": [
                            [0.50, 0.25],
                            [0.95, 0.25],
                            [0.95, 0.90],
                            [0.50, 0.90]
                        ],
                        "max_dwell_seconds": 0.0,
                        "color_bgr": [0, 0, 240]
                    })
                ]

        # Transition & Dwell Tracker
        # worker_id -> {"current_zone": Optional[str], "entry_time": float, "last_transition": str, "dwell_seconds": float}
        self.worker_zone_states: Dict[str, Dict[str, Any]] = {}

    def _normalize_zone_spec(self, zone: Dict[str, Any]) -> Dict[str, Any]:
        """Normalizes zone specifications to have consistent ID, name, and polygon representation."""
        zid = zone.get("zone_id") or zone.get("id", "ZONE_RESTRICTED")
        zname = zone.get("zone_name") or zone.get("name", "Hazard Perimeter")
        severity = zone.get("severity", "HIGH")
        coord_mode = zone.get("coordinate_mode", "normalized")

        polygon = zone.get("polygon")
        if not polygon and "norm_rect" in zone:
            nx, ny, nw, nh = zone["norm_rect"]
            polygon = [
                [nx, ny],
                [nx + nw, ny],
                [nx + nw, ny + nh],
                [nx, ny + nh]
            ]
        elif not polygon and "rect" in zone:
            rx, ry, rw, rh = zone["rect"]
            polygon = [
                [rx, ry],
                [rx + rw, ry],
                [rx + rw, ry + rh],
                [rx, ry + rh]
            ]

        return {
            "id": zid,
            "zone_id": zid,
            "name": zname,
            "zone_name": zname,
            "severity": severity,
            "coordinate_mode": coord_mode,
            "polygon": polygon or [[0.5, 0.25], [0.95, 0.25], [0.95, 0.9], [0.5, 0.9]],
            "norm_rect": zone.get("norm_rect", (0.5, 0.25, 0.45, 0.65)),
            "max_dwell_seconds": float(zone.get("max_dwell_seconds", 0.0)),
            "required_ppe": zone.get("required_ppe", ["helmet", "vest"]),
            "color_bgr": zone.get("color_bgr", [0, 0, 240])
        }

    def load_zones_from_file(self, file_path: str) -> None:
        """Loads danger zones configuration from a JSON file."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                raw_zones = data.get("zones", [])
                coord_mode = data.get("coordinate_mode", "normalized")
                for rz in raw_zones:
                    if "coordinate_mode" not in rz:
                        rz["coordinate_mode"] = coord_mode
                self.zones = [self._normalize_zone_spec(z) for z in raw_zones]
                print(f"[ZoneDetector] Loaded {len(self.zones)} danger zones from {file_path}")
        except Exception as e:
            print(f"[ZoneDetector] Failed to load zones from {file_path}: {e}")

    def add_zone(self, zone_spec: Dict[str, Any]) -> None:
        """Dynamically registers or updates a danger zone."""
        normalized = self._normalize_zone_spec(zone_spec)
        # Update if ID already exists, else append
        for idx, z in enumerate(self.zones):
            if z["zone_id"] == normalized["zone_id"]:
                self.zones[idx] = normalized
                return
        self.zones.append(normalized)

    def get_pixel_polygon(
        self,
        zone: Dict[str, Any],
        frame_w: int,
        frame_h: int
    ) -> List[List[float]]:
        """Scales zone polygon to absolute frame dimensions."""
        poly = zone.get("polygon", [])
        mode = zone.get("coordinate_mode", "normalized")
        return scale_polygon_coordinates(poly, frame_w, frame_h, coordinate_mode=mode)

    def get_pixel_rect(
        self,
        zone: Dict[str, Any],
        frame_w: int,
        frame_h: int
    ) -> Tuple[int, int, int, int]:
        """Backward-compatible bounding rectangle of the danger zone in pixels."""
        poly = self.get_pixel_polygon(zone, frame_w, frame_h)
        if not poly:
            nx, ny, nw, nh = zone.get("norm_rect", (0.5, 0.25, 0.45, 0.65))
            return int(nx * frame_w), int(ny * frame_h), int(nw * frame_w), int(nh * frame_h)

        xs = [p[0] for p in poly]
        ys = [p[1] for p in poly]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        return int(min_x), int(min_y), int(max_x - min_x), int(max_y - min_y)

    def check_zone_intrusion(
        self,
        worker_bbox: Tuple[int, int, int, int],
        frame_shape: Tuple[int, int] = (720, 1280),
        simulated_override: Optional[bool] = None,
        worker_id: Optional[str] = None
    ) -> Tuple[bool, Optional[str], Optional[str], float]:
        """
        Evaluates whether a worker's ground anchor point (feet) or bounding box
        intersects any restricted danger zone.
        Returns:
            (is_inside, zone_id, zone_name, confidence)
        """
        if simulated_override is not None:
            if simulated_override:
                return True, "ZONE_ROBOT_CELL_4", "Robotic Cell 4 Perimeter", 0.96
            return False, None, None, 0.95

        frame_h, frame_w = frame_shape[:2]
        x, y, w, h = worker_bbox

        # 1. Primary test: Worker's foot contact point (bottom-center)
        foot_x, foot_y = get_bottom_center_point(worker_bbox, format_hint="xywh")

        active_zone = None
        current_time = time.time()

        for zone in self.zones:
            pixel_poly = self.get_pixel_polygon(zone, frame_w, frame_h)

            # Test point-in-polygon containment
            if point_in_polygon((foot_x, foot_y), pixel_poly):
                active_zone = zone
                break

            # Secondary test: Major bounding box overlap IoA (>40% of worker body inside zone)
            zx, zy, zw, zh = self.get_pixel_rect(zone, frame_w, frame_h)
            worker_rect = (x, y, x + w, y + h)
            zone_rect = (zx, zy, zx + zw, zy + zh)
            ioa_val = calculate_ioa(worker_rect, zone_rect)
            if ioa_val > 0.40:
                active_zone = zone
                break

        # 2. State Transition Tracking (Entry / Exit / Zone Transfer)
        w_key = str(worker_id or "default")
        state = self.worker_zone_states.setdefault(w_key, {
            "current_zone": None,
            "last_zone": None,
            "entry_time": 0.0,
            "last_transition": "NONE",
            "transition": "NONE",
            "dwell_seconds": 0.0
        })

        if active_zone:
            current_zid = active_zone["zone_id"]
            if state["current_zone"] is None:
                # Fresh entry into a hazard zone
                state["last_zone"] = None
                state["current_zone"] = current_zid
                state["entry_time"] = current_time
                state["last_transition"] = "ENTERED"
                state["transition"] = "ENTRY"
                state["dwell_seconds"] = 0.0
            elif state["current_zone"] != current_zid:
                # Transferred from one hazard zone to a different zone
                state["last_zone"] = state["current_zone"]
                state["current_zone"] = current_zid
                state["entry_time"] = current_time
                state["last_transition"] = "TRANSFERRED"
                state["transition"] = "TRANSFER"
                state["dwell_seconds"] = 0.0
            else:
                # Continued presence in same zone
                state["dwell_seconds"] = round(current_time - state["entry_time"], 1)
                state["last_transition"] = "DWELLING"
                state["transition"] = "INSIDE"

            return True, active_zone["zone_id"], active_zone["zone_name"], 0.95

        else:
            if state["current_zone"] is not None:
                # Worker exited hazard zone into safe area
                state["last_zone"] = state["current_zone"]
                state["current_zone"] = None
                state["entry_time"] = 0.0
                state["last_transition"] = "EXITED"
                state["transition"] = "EXIT"
                state["dwell_seconds"] = 0.0
            else:
                state["last_transition"] = "NONE"
                state["transition"] = "NONE"

            return False, None, None, 0.95

    def get_worker_state(self, worker_id: str) -> Dict[str, Any]:
        """Returns the current zone presence and dwell tracking for a specific worker."""
        st = self.worker_zone_states.get(str(worker_id), {
            "current_zone": None,
            "last_zone": None,
            "entry_time": 0.0,
            "last_transition": "NONE",
            "transition": "NONE",
            "dwell_seconds": 0.0
        })
        return {
            "current_zone": st.get("current_zone"),
            "last_zone": st.get("last_zone"),
            "entry_time": st.get("entry_time", 0.0),
            "last_transition": st.get("last_transition", "NONE"),
            "transition": st.get("transition", st.get("last_transition", "NONE")),
            "dwell_seconds": st.get("dwell_seconds", 0.0)
        }
