"""
Geometry Utilities for ErgoGuard AI
Provides 2D/3D joint angle calculations, bounding-box IoU/IoA metrics,
ray-casting polygon containment, foot-point ground anchors, and robust input validation.
"""

import math
from typing import List, Tuple, Union, Dict, Any, Optional

try:
    import numpy as np
except ImportError:
    np = None


# ---------------------------------------------------------------------------
# Input Validation & Sanitization Helpers
# ---------------------------------------------------------------------------

def is_valid_number(val: Any) -> bool:
    """Returns True if val is a valid finite float or int (not NaN or inf)."""
    if val is None:
        return False
    if not isinstance(val, (int, float)):
        try:
            val = float(val)
        except (ValueError, TypeError):
            return False
    return not (math.isnan(val) or math.isinf(val))


def to_point(p: Any) -> Tuple[float, float, Optional[float]]:
    """
    Normalizes coordinates from tuple, list, or dict into (x, y, z_or_None).
    Raises ValueError on malformed or non-numeric points.
    """
    if p is None:
        raise ValueError("Point cannot be None")

    if isinstance(p, (tuple, list)):
        if len(p) < 2:
            raise ValueError(f"Point sequence must have at least 2 elements (x, y), got {p}")
        x, y = p[0], p[1]
        z = p[2] if len(p) > 2 else None
    elif isinstance(p, dict):
        if "x" not in p or "y" not in p:
            raise ValueError(f"Point dict must contain 'x' and 'y', got {p}")
        x, y = p["x"], p["y"]
        z = p.get("z")
    elif hasattr(p, "x") and hasattr(p, "y"):
        x, y = getattr(p, "x"), getattr(p, "y")
        z = getattr(p, "z", None)
    else:
        raise ValueError(f"Unsupported point format: {type(p)}")

    if not is_valid_number(x) or not is_valid_number(y):
        raise ValueError(f"Point coordinates must be valid finite numbers: ({x}, {y})")

    z_val = float(z) if (z is not None and is_valid_number(z)) else None
    return float(x), float(y), z_val


def validate_point(p: Any) -> bool:
    """Safe checker returning True if point is valid, False otherwise."""
    try:
        to_point(p)
        return True
    except (ValueError, TypeError):
        return False


# ---------------------------------------------------------------------------
# Point & Angle Calculations
# ---------------------------------------------------------------------------

def calculate_distance(
    p1: Union[Tuple[float, ...], List[float], Dict[str, float]],
    p2: Union[Tuple[float, ...], List[float], Dict[str, float]]
) -> float:
    """Calculates Euclidean distance between two 2D/3D points."""
    x1, y1, z1 = to_point(p1)
    x2, y2, z2 = to_point(p2)

    dx = x2 - x1
    dy = y2 - y1
    if z1 is not None and z2 is not None:
        dz = z2 - z1
        return math.sqrt(dx * dx + dy * dy + dz * dz)
    return math.sqrt(dx * dx + dy * dy)


def calculate_angle_3points(
    a: Any,
    b: Any,
    c: Any
) -> float:
    """
    Calculates interior angle in degrees at vertex b formed by rays b->a and b->c.
    Returns angle in degrees [0.0, 180.0].
    Handles zero-length vectors, collinear rays, 3D coordinates, and validates inputs.
    """
    try:
        ax, ay, az = to_point(a)
        bx, by, bz = to_point(b)
        cx, cy, cz = to_point(c)
    except (ValueError, TypeError):
        return 0.0

    v1x = ax - bx
    v1y = ay - by
    v2x = cx - bx
    v2y = cy - by

    has_z = az is not None and bz is not None and cz is not None
    v1z = (az - bz) if has_z else 0.0
    v2z = (cz - bz) if has_z else 0.0

    dot = v1x * v2x + v1y * v2y + v1z * v2z
    mag1 = math.sqrt(v1x * v1x + v1y * v1y + v1z * v1z)
    mag2 = math.sqrt(v2x * v2x + v2y * v2y + v2z * v2z)

    # Degenerate: overlapping or zero-length rays
    if mag1 == 0.0 or mag2 == 0.0:
        return 0.0

    cosine = dot / (mag1 * mag2)
    # Clamp to avoid floating point math domain errors outside [-1, 1]
    cosine = max(-1.0, min(1.0, cosine))
    angle = math.acos(cosine)
    return round(math.degrees(angle), 2)


def calculate_angle_with_vertical(
    p_top: Any = None,
    p_bottom: Optional[Any] = None,
    p1: Optional[Any] = None,
    p2: Optional[Any] = None,
    vector: Optional[Any] = None
) -> float:
    """
    Calculates the inclination angle of vector (p_bottom -> p_top) relative to the vertical line.
    0° = perfectly upright/vertical.
    90° = completely horizontal.
    Accepts two points (top, bottom / p1, p2) or a single direction vector.
    """
    try:
        top = p_top if p_top is not None else p1
        bottom = p_bottom if p_bottom is not None else p2
        if vector is not None:
            dx, dy, dz = to_point(vector)
            dy = abs(dy)
            dz = dz or 0.0
        elif bottom is not None and top is not None:
            tx, ty, tz = to_point(top)
            bx, by, bz = to_point(bottom)
            dx = tx - bx
            dy = abs(ty - by)  # Vertical displacement
            dz = (tz - bz) if (tz is not None and bz is not None) else 0.0
        elif top is not None:
            dx, dy, dz = to_point(top)
            dy = abs(dy)
            dz = dz or 0.0
        else:
            return 0.0
    except (ValueError, TypeError):
        return 0.0

    horizontal_dist = math.hypot(dx, dz)
    if horizontal_dist == 0.0 and dy == 0.0:
        return 0.0

    angle_rad = math.atan2(horizontal_dist, max(1e-6, dy))
    return round(math.degrees(angle_rad), 2)


def calculate_angle_with_horizontal(
    p1: Any,
    p2: Optional[Any] = None
) -> float:
    """
    Calculates the angle of the segment (p1 -> p2) or vector (p1) relative to the horizontal axis.
    0° = parallel to the floor (fallen/prone).
    90° = vertical/upright.
    """
    try:
        if p2 is not None:
            x1, y1, _ = to_point(p1)
            x2, y2, _ = to_point(p2)
            dx = abs(x2 - x1)
            dy = abs(y2 - y1)
        else:
            dx, dy, _ = to_point(p1)
            dx = abs(dx)
            dy = abs(dy)
    except (ValueError, TypeError):
        return 0.0

    if dx == 0.0 and dy == 0.0:
        return 0.0

    angle_rad = math.atan2(dy, max(1e-6, dx))
    return round(math.degrees(angle_rad), 2)


# ---------------------------------------------------------------------------
# Bounding Box Coordinates & Overlap Metrics (IoU / IoA)
# ---------------------------------------------------------------------------

def to_box_coords(box: Any, format_hint: Optional[str] = None) -> Optional[Tuple[float, float, float, float]]:
    """
    Normalizes various bounding box representations into [x1, y1, x2, y2]
    where (x1, y1) is top-left and (x2, y2) is bottom-right.
    Accepts:
      - [x, y, w, h] (standard OpenCV / tracker format)
      - [x1, y1, x2, y2]
      - dict with xmin, ymin, xmax, ymax
      - dict with x, y, width, height (or w, h)
      - dict with left, top, right, bottom
    """
    if box is None:
        raise ValueError("Bounding box cannot be None")

    if isinstance(box, (list, tuple)):
        if len(box) != 4:
            raise ValueError(f"Box sequence must have 4 elements, got {len(box)}")
        v0, v1, v2, v3 = [float(v) if is_valid_number(v) else 0.0 for v in box]
        if format_hint == "xywh":
            x1, y1 = v0, v1
            x2, y2 = v0 + v2, v1 + v3
        elif format_hint == "xyxy":
            x1, y1, x2, y2 = v0, v1, v2, v3
            if x2 < x1 or y2 < y1:
                return None
        else:
            x1 = min(v0, v2)
            y1 = min(v1, v3)
            x2 = max(v0, v2)
            y2 = max(v1, v3)
        return float(x1), float(y1), float(x2), float(y2)

    if isinstance(box, dict):
        if "xmin" in box and "xmax" in box:
            x1 = float(box.get("xmin", 0.0))
            y1 = float(box.get("ymin", 0.0))
            x2 = float(box.get("xmax", 0.0))
            y2 = float(box.get("ymax", 0.0))
        elif "left" in box and "right" in box:
            x1 = float(box.get("left", 0.0))
            y1 = float(box.get("top", 0.0))
            x2 = float(box.get("right", 0.0))
            y2 = float(box.get("bottom", 0.0))
        elif "x1" in box and "x2" in box:
            x1 = float(box.get("x1", 0.0))
            y1 = float(box.get("y1", 0.0))
            x2 = float(box.get("x2", 0.0))
            y2 = float(box.get("y2", 0.0))
        else:
            x = float(box.get("x", box.get("left", 0.0)))
            y = float(box.get("y", box.get("top", 0.0)))
            w = float(box.get("width", box.get("w", 0.0)))
            h = float(box.get("height", box.get("h", 0.0)))
            x1, y1, x2, y2 = x, y, x + w, y + h

        return min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)

    if hasattr(box, "x1") and hasattr(box, "x2"):
        return float(box.x1), float(box.y1), float(box.x2), float(box.y2)

    raise ValueError(f"Unsupported box format: {type(box)}")


def box_intersection_and_areas(box_a: Any, box_b: Any) -> Dict[str, float]:
    """Computes intersection area, area of box_a, and area of box_b."""
    try:
        ax1, ay1, ax2, ay2 = to_box_coords(box_a)
        bx1, by1, bx2, by2 = to_box_coords(box_b)
    except (ValueError, TypeError):
        return {"inter_area": 0.0, "area_a": 0.0, "area_b": 0.0}

    inter_x1 = max(ax1, bx1)
    inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)

    inter_w = max(0.0, inter_x2 - inter_x1)
    inter_h = max(0.0, inter_y2 - inter_y1)
    inter_area = inter_w * inter_h

    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)

    return {"inter_area": inter_area, "area_a": area_a, "area_b": area_b}


def calculate_iou(box_a: Any, box_b: Any) -> float:
    """
    Calculates Intersection over Union (IoU) between two bounding boxes.
    Returns float in range [0.0, 1.0].
    """
    areas = box_intersection_and_areas(box_a, box_b)
    inter_area = areas["inter_area"]
    union_area = areas["area_a"] + areas["area_b"] - inter_area
    if union_area <= 0.0:
        return 0.0
    return round(inter_area / union_area, 4)


def calculate_ioa(box_a: Any, box_b: Any) -> float:
    """
    Calculates Intersection over Area (IoA) of box_a covered by box_b.
    Returns float in range [0.0, 1.0] (1.0 means box_a is 100% inside box_b).
    """
    areas = box_intersection_and_areas(box_a, box_b)
    area_a = areas["area_a"]
    if area_a <= 0.0:
        return 0.0
    return round(areas["inter_area"] / area_a, 4)


# ---------------------------------------------------------------------------
# Foot Point & Polygon Geometry
# ---------------------------------------------------------------------------

def get_bottom_center_point(
    bbox: Union[List[float], Tuple[float, float, float, float], Dict[str, float]],
    format_hint: Optional[str] = None
) -> Tuple[float, float]:
    """
    Extracts the bottom-center point (worker feet location on the ground plane).
    Supports:
      - (x, y, w, h)
      - (x1, y1, x2, y2)
      - Dicts
    """
    if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
        v0, v1, v2, v3 = [float(v) if is_valid_number(v) else 0.0 for v in bbox]
        if format_hint == "xywh":
            return round(v0 + v2 / 2.0, 1), round(v1 + v3, 1)
        elif format_hint == "xyxy":
            return round((v0 + v2) / 2.0, 1), round(v3, 1)
        else:
            if v2 < v0 or v3 < v1:
                return round(v0 + v2 / 2.0, 1), round(v1 + v3, 1)
            else:
                return round((v0 + v2) / 2.0, 1), round(v3, 1)

    try:
        coords = to_box_coords(bbox)
        if coords is not None:
            x1, y1, x2, y2 = coords
            return round((x1 + x2) / 2.0, 1), round(y2, 1)
        return 0.0, 0.0
    except Exception:
        return 0.0, 0.0


def point_in_polygon(
    point: Any,
    polygon: List[Any],
    on_edge_inside: bool = True
) -> bool:
    """
    Determines whether a 2D point (x, y) lies inside or on the boundary of a 2D polygon.
    Uses ray-casting algorithm with boundary tolerance check.
    Works for convex and concave polygons.
    """
    try:
        px, py, _ = to_point(point)
    except (ValueError, TypeError):
        return False

    if not polygon or len(polygon) < 3:
        return False

    # Extract vertex coordinates
    pts = []
    for p in polygon:
        try:
            vx, vy, _ = to_point(p)
            pts.append((vx, vy))
        except (ValueError, TypeError):
            continue

    n = len(pts)
    if n < 3:
        return False

    # 1. Boundary check: point lies directly on a segment
    if on_edge_inside:
        for i in range(n):
            p1x, p1y = pts[i]
            p2x, p2y = pts[(i + 1) % n]
            # Cross product to check collinearity
            cross = (py - p1y) * (p2x - p1x) - (px - p1x) * (p2y - p1y)
            if abs(cross) <= 1e-5:
                # Check bounding box of segment
                if min(p1x, p2x) - 1e-5 <= px <= max(p1x, p2x) + 1e-5 and \
                   min(p1y, p2y) - 1e-5 <= py <= max(p1y, p2y) + 1e-5:
                    return True

    # 2. Standard ray-casting algorithm
    inside = False
    p1x, p1y = pts[0]
    for i in range(1, n + 1):
        p2x, p2y = pts[i % n]
        if py > min(p1y, p2y):
            if py <= max(p1y, p2y):
                if px <= max(p1x, p2x):
                    if p1y != p2y:
                        xinters = (py - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    else:
                        xinters = p1x
                    if p1x == p2x or px <= xinters:
                        inside = not inside
        p1x, p1y = p2x, p2y

    return inside


def scale_polygon_coordinates(
    polygon: List[Any],
    frame_w: Optional[int] = None,
    frame_h: Optional[int] = None,
    coordinate_mode: str = "normalized",
    frame_width: Optional[int] = None,
    frame_height: Optional[int] = None
) -> List[List[float]]:
    """
    Scales polygon vertices from normalized [0.0, 1.0] coordinates to absolute pixel coordinates.
    """
    fw = frame_w if frame_w is not None else (frame_width if frame_width is not None else 1280)
    fh = frame_h if frame_h is not None else (frame_height if frame_height is not None else 720)
    resolved = []
    for vertex in polygon:
        try:
            vx, vy, _ = to_point(vertex)
            if coordinate_mode == "normalized":
                resolved.append([round(vx * fw, 1), round(vy * fh, 1)])
            else:
                resolved.append([round(vx, 1), round(vy, 1)])
        except (ValueError, TypeError):
            continue
    return resolved
