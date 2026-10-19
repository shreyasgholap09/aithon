"""
Comprehensive Unit Tests for Geometry Utilities, Danger Zone Transitions,
Pose Landmark Ergonomics, and Incident Lifecycle Integrity.

Covers:
1. 2D and 3D angle calculations, zero-length vectors, identical points, NaN handling
2. Vertical and horizontal reference angles
3. IoU and IoA bounding box metrics, edge/containment cases, invalid box handling
4. Point-in-polygon containment, including boundary edges and vertices
5. Bottom-center foot-point calculation across coordinate formats
6. Normalized coordinate scaling to video frame dimensions
7. Danger zone entry, dwell, transfer, and exit transitions
8. Duplicate alert prevention across video frames
9. Pose landmark ergonomic analysis, distinguishing unsafe bending from squat lifting
10. Explicit UNKNOWN/UNAVAILABLE classification for missing/low-confidence landmarks (never SAFE)
11. Incident persistence, update, resolution, recurrence, and disappearance handling
"""

import math
import os
import sys
import unittest
import numpy as np

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from ai.geometry import (
    calculate_distance,
    calculate_angle_3points,
    calculate_angle_with_vertical,
    calculate_angle_with_horizontal,
    to_box_coords,
    box_intersection_and_areas,
    calculate_iou,
    calculate_ioa,
    get_bottom_center_point,
    point_in_polygon,
    scale_polygon_coordinates,
    validate_point,
    is_valid_number,
)
from ai.zone_detection import ZoneDetector
from ai.pose_detection import PoseDetector
from safety_engine.risk_engine import RiskEngine
from safety_engine.alert_manager import AlertManager


class TestGeometryUtilities(unittest.TestCase):
    """Tests 2D/3D joint angle math, bounding box overlap, polygon raycasting, and coordinate scaling."""

    def test_calculate_angle_3points_right_angle(self):
        # A=(0, 1), B=(0, 0), C=(1, 0) -> exactly 90 degrees
        angle = calculate_angle_3points((0.0, 1.0), (0.0, 0.0), (1.0, 0.0))
        self.assertAlmostEqual(angle, 90.0, places=2)

    def test_calculate_angle_3points_straight_line(self):
        # A=(-1, 0), B=(0, 0), C=(1, 0) -> 180 degrees
        angle = calculate_angle_3points((-1.0, 0.0), (0.0, 0.0), (1.0, 0.0))
        self.assertAlmostEqual(angle, 180.0, places=2)

    def test_calculate_angle_3points_acute_and_obtuse(self):
        # 45 degree acute angle
        angle_45 = calculate_angle_3points((1.0, 1.0), (0.0, 0.0), (1.0, 0.0))
        self.assertAlmostEqual(angle_45, 45.0, places=2)

        # 135 degree obtuse angle
        angle_135 = calculate_angle_3points((-1.0, 1.0), (0.0, 0.0), (1.0, 0.0))
        self.assertAlmostEqual(angle_135, 135.0, places=2)

    def test_calculate_angle_3points_zero_length_vector(self):
        # B coincides with A: vector BA has zero length -> should safely return 0.0
        angle = calculate_angle_3points((0.0, 0.0), (0.0, 0.0), (1.0, 0.0))
        self.assertEqual(angle, 0.0)

        # B coincides with C: vector BC has zero length -> safely returns 0.0
        angle2 = calculate_angle_3points((1.0, 0.0), (0.0, 0.0), (0.0, 0.0))
        self.assertEqual(angle2, 0.0)

    def test_calculate_angle_3points_identical_points(self):
        # All three points identical
        angle = calculate_angle_3points((2.0, 3.0), (2.0, 3.0), (2.0, 3.0))
        self.assertEqual(angle, 0.0)

    def test_calculate_angle_3points_3d(self):
        # 3D points: A=(0, 0, 1), B=(0, 0, 0), C=(0, 1, 0) -> 90 degrees
        angle_3d = calculate_angle_3points((0.0, 0.0, 1.0), (0.0, 0.0, 0.0), (0.0, 1.0, 0.0))
        self.assertAlmostEqual(angle_3d, 90.0, places=2)

    def test_calculate_angle_3points_nan_and_invalids(self):
        # Points containing NaN or non-numeric types
        self.assertEqual(calculate_angle_3points((float("nan"), 1.0), (0.0, 0.0), (1.0, 0.0)), 0.0)
        self.assertEqual(calculate_angle_3points((0.0, 1.0), None, (1.0, 0.0)), 0.0)

    def test_calculate_angle_with_vertical(self):
        # Purely vertical line: (0, 0) to (0, 10) -> 0 degrees from vertical
        self.assertAlmostEqual(calculate_angle_with_vertical(p1=(0.0, 0.0), p2=(0.0, 10.0)), 0.0, places=2)
        # Vector input: (0, -5) -> vertical -> 0 degrees
        self.assertAlmostEqual(calculate_angle_with_vertical(vector=(0.0, -5.0)), 0.0, places=2)
        # Purely horizontal line: (0, 0) to (10, 0) -> 90 degrees from vertical
        self.assertAlmostEqual(calculate_angle_with_vertical(p1=(0.0, 0.0), p2=(10.0, 0.0)), 90.0, places=2)
        # 45 degree tilt: (0, 0) to (10, 10) -> 45 degrees
        self.assertAlmostEqual(calculate_angle_with_vertical(p1=(0.0, 0.0), p2=(10.0, 10.0)), 45.0, places=2)

    def test_calculate_angle_with_horizontal(self):
        # Horizontal vector -> 0 degrees
        self.assertAlmostEqual(calculate_angle_with_horizontal((10.0, 0.0)), 0.0, places=2)
        # Vertical vector -> 90 degrees
        self.assertAlmostEqual(calculate_angle_with_horizontal((0.0, 10.0)), 90.0, places=2)
        # Two point segment
        self.assertAlmostEqual(calculate_angle_with_horizontal((0.0, 100.0), (200.0, 100.0)), 0.0, places=2)

    def test_to_box_coords(self):
        # xywh tuple
        self.assertEqual(to_box_coords((10, 20, 30, 40), format_hint="xywh"), (10.0, 20.0, 40.0, 60.0))
        # xyxy tuple
        self.assertEqual(to_box_coords((10, 20, 40, 60), format_hint="xyxy"), (10.0, 20.0, 40.0, 60.0))
        # dictionary
        self.assertEqual(to_box_coords({"x": 10, "y": 20, "w": 30, "h": 40}), (10.0, 20.0, 40.0, 60.0))
        # degenerate box (inverted coordinates or negative size)
        self.assertIsNone(to_box_coords((50, 50, 20, 20), format_hint="xyxy"))

    def test_calculate_iou_and_ioa(self):
        # Identical boxes: (0, 0, 10, 10)
        box1 = (0, 0, 10, 10)
        self.assertAlmostEqual(calculate_iou(box1, box1), 1.0, places=4)
        self.assertAlmostEqual(calculate_ioa(box1, box1), 1.0, places=4)

        # Disjoint boxes: (0, 0, 10, 10) and (20, 20, 30, 30)
        box2 = (20, 20, 30, 30)
        self.assertEqual(calculate_iou(box1, box2), 0.0)
        self.assertEqual(calculate_ioa(box1, box2), 0.0)

        # Partial overlap: (0, 0, 10, 10) and (5, 0, 15, 10)
        # Inter = 5 * 10 = 50. Union = 100 + 100 - 50 = 150. IoU = 50/150 = 1/3.
        box3 = (5, 0, 15, 10)
        self.assertAlmostEqual(calculate_iou(box1, box3), 1.0 / 3.0, places=4)
        # IoA of box1 in box3 = 50 / 100 = 0.50
        self.assertAlmostEqual(calculate_ioa(box1, box3), 0.50, places=4)

        # Subset containment: small box (2, 2, 8, 8) inside large box (0, 0, 10, 10)
        # Area small = 36. Inter = 36. IoA(small, large) = 36/36 = 1.0
        small_box = (2, 2, 8, 8)
        self.assertAlmostEqual(calculate_ioa(small_box, box1), 1.0, places=4)

    def test_point_in_polygon_interior_exterior(self):
        # Square polygon: (0, 0), (10, 0), (10, 10), (0, 10)
        poly = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
        self.assertTrue(point_in_polygon((5.0, 5.0), poly))
        self.assertFalse(point_in_polygon((15.0, 5.0), poly))
        self.assertFalse(point_in_polygon((-1.0, 5.0), poly))

    def test_point_in_polygon_boundary_and_vertices(self):
        poly = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
        # Points directly on boundary edges
        self.assertTrue(point_in_polygon((5.0, 0.0), poly, on_edge_inside=True))
        self.assertTrue(point_in_polygon((10.0, 5.0), poly, on_edge_inside=True))
        self.assertTrue(point_in_polygon((5.0, 10.0), poly, on_edge_inside=True))
        self.assertTrue(point_in_polygon((0.0, 5.0), poly, on_edge_inside=True))
        # Points exactly on vertices
        self.assertTrue(point_in_polygon((0.0, 0.0), poly, on_edge_inside=True))
        self.assertTrue(point_in_polygon((10.0, 10.0), poly, on_edge_inside=True))

    def test_get_bottom_center_point(self):
        # xywh: (100, 200, 60, 100) -> bottom center is (100 + 30, 200 + 100) = (130, 300)
        pt = get_bottom_center_point((100, 200, 60, 100), format_hint="xywh")
        self.assertEqual(pt, (130.0, 300.0))

        # xyxy: (100, 200, 160, 300) -> bottom center is (130, 300)
        pt2 = get_bottom_center_point((100, 200, 160, 300), format_hint="xyxy")
        self.assertEqual(pt2, (130.0, 300.0))

        # Dict format
        pt3 = get_bottom_center_point({"x": 100, "y": 200, "width": 60, "height": 100})
        self.assertEqual(pt3, (130.0, 300.0))

        # Default detection bbox [x1, y1, x2, y2]
        pt4 = get_bottom_center_point([100, 50, 200, 250])
        self.assertEqual(pt4, (150.0, 250.0))

    def test_scale_polygon_coordinates(self):
        norm_poly = [[0.1, 0.2], [0.8, 0.2], [0.8, 0.7], [0.1, 0.7]]
        scaled = scale_polygon_coordinates(norm_poly, frame_w=1000, frame_h=500)
        expected = [[100.0, 100.0], [800.0, 100.0], [800.0, 350.0], [100.0, 350.0]]
        self.assertEqual(scaled, expected)


class TestZoneTransitionsAndDwell(unittest.TestCase):
    """Tests multi-zone loading, normalized scaling, transitions (ENTRY, INSIDE, EXIT, TRANSFER), and duplicate suppression."""

    def setUp(self):
        self.zone_detector = ZoneDetector()

    def test_zone_entry_and_exit_transitions(self):
        # 1000x1000 frame
        # Inside ZONE_ROBOT_CELL_4: x in [500, 950], y in [250, 900]
        # Frame 1: Worker enters ZONE_ROBOT_CELL_4 (feet at (600 + 30, 400 + 120) = (630, 520))
        inside, zid, zname, _ = self.zone_detector.check_zone_intrusion(
            worker_bbox=(600, 400, 60, 120),
            frame_shape=(1000, 1000),
            worker_id="W_TEST_01"
        )
        self.assertTrue(inside)
        self.assertEqual(zid, "ZONE_ROBOT_CELL_4")
        st1 = self.zone_detector.get_worker_state("W_TEST_01")
        self.assertIn(st1["transition"], ("ENTRY", "ENTERED"))
        self.assertEqual(st1["current_zone"], "ZONE_ROBOT_CELL_4")

        # Frame 2: Worker remains inside -> transition becomes INSIDE (prevents repeated entry alert spam)
        inside2, zid2, _, _ = self.zone_detector.check_zone_intrusion(
            worker_bbox=(605, 405, 60, 120),
            frame_shape=(1000, 1000),
            worker_id="W_TEST_01"
        )
        self.assertTrue(inside2)
        st2 = self.zone_detector.get_worker_state("W_TEST_01")
        self.assertIn(st2["transition"], ("INSIDE", "DWELLING"))

        # Frame 3: Worker steps outside danger zone
        inside3, zid3, _, _ = self.zone_detector.check_zone_intrusion(
            worker_bbox=(100, 100, 50, 100),
            frame_shape=(1000, 1000),
            worker_id="W_TEST_01"
        )
        self.assertFalse(inside3)
        st3 = self.zone_detector.get_worker_state("W_TEST_01")
        self.assertIn(st3["transition"], ("EXIT", "EXITED"))
        self.assertEqual(st3["last_zone"], "ZONE_ROBOT_CELL_4")
        self.assertIsNone(st3["current_zone"])

    def test_zone_transfer_between_zones(self):
        # Worker starts inside DZ-02 (Forklift corridor: x in [50, 450], y in [550, 950])
        # Feet at (200 + 25, 600 + 100) = (225, 700) -> inside DZ-02
        inside1, zid1, _, _ = self.zone_detector.check_zone_intrusion(
            worker_bbox=(200, 600, 50, 100),
            frame_shape=(1000, 1000),
            worker_id="W_TRANSFER"
        )
        self.assertTrue(inside1)
        self.assertEqual(zid1, "DZ-02")
        self.assertIn(self.zone_detector.get_worker_state("W_TRANSFER")["transition"], ("ENTRY", "ENTERED"))

        # Worker moves directly into ZONE_ROBOT_CELL_4 (feet at (630, 600))
        inside2, zid2, _, _ = self.zone_detector.check_zone_intrusion(
            worker_bbox=(600, 500, 60, 100),
            frame_shape=(1000, 1000),
            worker_id="W_TRANSFER"
        )
        self.assertTrue(inside2)
        self.assertEqual(zid2, "ZONE_ROBOT_CELL_4")
        st2 = self.zone_detector.get_worker_state("W_TRANSFER")
        self.assertIn(st2["transition"], ("TRANSFER", "TRANSFERRED"))
        self.assertEqual(st2["last_zone"], "DZ-02")
        self.assertEqual(st2["current_zone"], "ZONE_ROBOT_CELL_4")


class TestPoseLandmarkErgonomics(unittest.TestCase):
    """Tests ergonomic pose landmark analysis, joint angle calculation, and missing data safety handling."""

    def setUp(self):
        self.pose_detector = PoseDetector()

    def test_upright_posture_safe(self):
        # Upright worker landmarks:
        # Shoulders at (300, 150) & (340, 150) -> Mid-shoulder at (320, 150)
        # Hips at (300, 300) & (340, 300) -> Mid-hip at (320, 300)
        # Vertical spine vector (0, 150) -> trunk angle 0.0 degrees (SAFE)
        landmarks = [
            {"x": 320, "y": 100, "z": 0.0, "visibility": 0.95},  # 0: nose
            *([{"x": 0, "y": 0, "z": 0.0, "visibility": 0.0}] * 10),
            {"x": 300, "y": 150, "z": 0.0, "visibility": 0.95},  # 11: left shoulder
            {"x": 340, "y": 150, "z": 0.0, "visibility": 0.95},  # 12: right shoulder
            *([{"x": 0, "y": 0, "z": 0.0, "visibility": 0.0}] * 10),
            {"x": 300, "y": 300, "z": 0.0, "visibility": 0.95},  # 23: left hip
            {"x": 340, "y": 300, "z": 0.0, "visibility": 0.95},  # 24: right hip
            {"x": 300, "y": 450, "z": 0.0, "visibility": 0.95},  # 25: left knee
            {"x": 340, "y": 450, "z": 0.0, "visibility": 0.95},  # 26: right knee
            {"x": 300, "y": 600, "z": 0.0, "visibility": 0.95},  # 27: left ankle
            {"x": 340, "y": 600, "z": 0.0, "visibility": 0.95},  # 28: right ankle
        ]
        status, trunk_angle, conf, breakdown = self.pose_detector.analyze_landmarks(landmarks, frame_shape=(720, 1280))
        self.assertEqual(status, "SAFE")
        self.assertAlmostEqual(trunk_angle, 0.0, delta=2.0)
        self.assertGreater(conf, 0.8)

    def test_unsafe_bending_hazardous(self):
        # Hazardous forward bending with straight legs:
        # Mid-hip at (320, 300). Mid-shoulder bent forward at (450, 200).
        # Trunk angle = angle with vertical of vector (130, -100) -> ~52.4 degrees (> 35 deg threshold)
        # Knees straight: hip (320, 300), knee (320, 450), ankle (320, 600) -> straight knees
        landmarks = [
            {"x": 480, "y": 170, "z": 0.0, "visibility": 0.95},  # 0: nose
            *([{"x": 0, "y": 0, "z": 0.0, "visibility": 0.0}] * 10),
            {"x": 450, "y": 200, "z": 0.0, "visibility": 0.95},  # 11: left shoulder
            {"x": 450, "y": 200, "z": 0.0, "visibility": 0.95},  # 12: right shoulder
            *([{"x": 0, "y": 0, "z": 0.0, "visibility": 0.0}] * 10),
            {"x": 320, "y": 300, "z": 0.0, "visibility": 0.95},  # 23: left hip
            {"x": 320, "y": 300, "z": 0.0, "visibility": 0.95},  # 24: right hip
            {"x": 320, "y": 450, "z": 0.0, "visibility": 0.95},  # 25: left knee
            {"x": 320, "y": 450, "z": 0.0, "visibility": 0.95},  # 26: right knee
            {"x": 320, "y": 600, "z": 0.0, "visibility": 0.95},  # 27: left ankle
            {"x": 320, "y": 600, "z": 0.0, "visibility": 0.95},  # 28: right ankle
        ]
        status, trunk_angle, conf, breakdown = self.pose_detector.analyze_landmarks(landmarks, frame_shape=(720, 1280))
        self.assertEqual(status, "UNSAFE")
        self.assertGreater(trunk_angle, 35.0)

    def test_ergonomic_squat_lifting_safe(self):
        # Ergonomic squat: moderate trunk lean (~28 deg) with deeply bent knees (knee angle ~90 deg -> flexion 90 deg)
        # Hip at (320, 350), Shoulder at (370, 250) (vector 50, -100 -> ~26.5 deg)
        # Hip (320, 350), Knee forward (380, 420), Ankle back at (320, 490) -> bent knee
        landmarks = [
            {"x": 390, "y": 210, "z": 0.0, "visibility": 0.95},  # 0: nose
            *([{"x": 0, "y": 0, "z": 0.0, "visibility": 0.0}] * 10),
            {"x": 370, "y": 250, "z": 0.0, "visibility": 0.95},  # 11
            {"x": 370, "y": 250, "z": 0.0, "visibility": 0.95},  # 12
            *([{"x": 0, "y": 0, "z": 0.0, "visibility": 0.0}] * 10),
            {"x": 320, "y": 350, "z": 0.0, "visibility": 0.95},  # 23
            {"x": 320, "y": 350, "z": 0.0, "visibility": 0.95},  # 24
            {"x": 380, "y": 420, "z": 0.0, "visibility": 0.95},  # 25: knee bent
            {"x": 380, "y": 420, "z": 0.0, "visibility": 0.95},  # 26
            {"x": 320, "y": 490, "z": 0.0, "visibility": 0.95},  # 27: ankle
            {"x": 320, "y": 490, "z": 0.0, "visibility": 0.95},  # 28
        ]
        status, trunk_angle, conf, breakdown = self.pose_detector.analyze_landmarks(landmarks, frame_shape=(720, 1280))
        # Squat lifting with bent knees is classified as SAFE (or compliant squat)
        self.assertEqual(status, "SAFE")
        self.assertIn("knee_angle", breakdown)

    def test_missing_landmarks_explicitly_returns_unknown(self):
        # Empty or None landmarks MUST return UNKNOWN / UNAVAILABLE — never SAFE!
        res_none_status, _, conf1, _ = self.pose_detector.analyze_landmarks(None)
        self.assertIn(res_none_status, ("UNKNOWN", "UNAVAILABLE"))
        self.assertEqual(conf1, 0.0)

        res_empty_status, _, conf2, _ = self.pose_detector.analyze_landmarks([])
        self.assertIn(res_empty_status, ("UNKNOWN", "UNAVAILABLE"))
        self.assertEqual(conf2, 0.0)

    def test_low_confidence_landmarks_explicitly_returns_unknown(self):
        # Landmarks with visibility below threshold (e.g. 0.10) must return UNKNOWN
        low_conf_landmarks = [
            {"x": 320, "y": 100, "z": 0.0, "visibility": 0.1},
            *([{"x": 0, "y": 0, "z": 0.0, "visibility": 0.0}] * 10),
            {"x": 300, "y": 150, "z": 0.0, "visibility": 0.1},
            {"x": 340, "y": 150, "z": 0.0, "visibility": 0.1},
            *([{"x": 0, "y": 0, "z": 0.0, "visibility": 0.0}] * 10),
            {"x": 300, "y": 300, "z": 0.0, "visibility": 0.1},
            {"x": 340, "y": 300, "z": 0.0, "visibility": 0.1},
            {"x": 300, "y": 450, "z": 0.0, "visibility": 0.1},
            {"x": 340, "y": 450, "z": 0.0, "visibility": 0.1},
            {"x": 300, "y": 600, "z": 0.0, "visibility": 0.1},
            {"x": 340, "y": 600, "z": 0.0, "visibility": 0.1},
        ]
        status, _, conf, _ = self.pose_detector.analyze_landmarks(low_conf_landmarks)
        self.assertIn(status, ("UNKNOWN", "UNAVAILABLE"))
        self.assertEqual(conf, 0.0)


class TestIncidentLifecycleEdgeCases(unittest.TestCase):
    """Tests incident creation, persistence, recurrence, and worker disappearance."""

    def setUp(self):
        self.alert_manager = AlertManager(confirmation_frames=2, resolution_timeout=1.0, disappearance_timeout=2.0)
        self.risk_engine = RiskEngine(alert_manager=self.alert_manager)

    def test_incident_persistence_retains_stable_id(self):
        # Frame 1: Detection -> DETECTED
        t0 = 1000.0
        self.alert_manager.update_violations("W20", ["helmet_missing"], "Zone A", "LOW", now=t0)
        active = self.alert_manager.get_active_incidents("W20")
        self.assertEqual(len(active), 1)
        orig_id = active[0]["incident_id"]

        # Frame 2: Confirmed -> ACTIVE
        self.alert_manager.update_violations("W20", ["helmet_missing"], "Zone A", "LOW", now=t0 + 0.1)
        active2 = self.alert_manager.get_active_incidents("W20")
        self.assertEqual(len(active2), 1)
        self.assertEqual(active2[0]["incident_id"], orig_id)
        self.assertEqual(active2[0]["lifecycle_state"], "ACTIVE")

        # Frame 3: Violation still ongoing -> maintains exact same ID
        self.alert_manager.update_violations("W20", ["helmet_missing"], "Zone A", "LOW", now=t0 + 0.2)
        active3 = self.alert_manager.get_active_incidents("W20")
        self.assertEqual(active3[0]["incident_id"], orig_id)

    def test_incident_resolution_and_recurrence_creates_new_id(self):
        t0 = 2000.0
        # 1. Occurrence & Confirmation
        self.alert_manager.update_violations("W21", ["vest_missing"], "Zone B", "LOW", now=t0)
        self.alert_manager.update_violations("W21", ["vest_missing"], "Zone B", "LOW", now=t0 + 0.1)
        inc1 = self.alert_manager.get_active_incidents("W21")[0]
        id_1 = inc1["incident_id"]

        # 2. Worker puts vest on (observed=True, violation clear for > 1.0s timeout)
        _, resolved = self.alert_manager.update_violations("W21", [], "Zone B", "LOW", is_observed=True, now=t0 + 1.5)
        self.assertEqual(len(resolved), 1)
        self.assertEqual(resolved[0]["lifecycle_state"], "RESOLVED")
        self.assertEqual(len(self.alert_manager.get_active_incidents("W21")), 0)

        # 3. Recurrence later: vest removed again -> must generate fresh distinct incident_id
        _, new_inc = self.alert_manager.update_violations("W21", ["vest_missing"], "Zone B", "LOW", now=t0 + 5.0)
        self.alert_manager.update_violations("W21", ["vest_missing"], "Zone B", "LOW", now=t0 + 5.1)
        inc2 = self.alert_manager.get_active_incidents("W21")[0]
        id_2 = inc2["incident_id"]

        self.assertNotEqual(id_1, id_2, "Recurring violation must receive a new distinct incident ID")

    def test_worker_disappearance_does_not_resolve_incident(self):
        t0 = 3000.0
        # Worker has violation
        self.alert_manager.update_violations("W22", ["danger_zone_entry"], "Zone C", "MEDIUM", now=t0)
        self.alert_manager.update_violations("W22", ["danger_zone_entry"], "Zone C", "MEDIUM", now=t0 + 0.1)

        # Worker is no longer detected / camera cannot see worker
        stale = self.alert_manager.handle_disappeared_workers(visible_worker_ids=set(), now=t0 + 3.0)
        self.assertEqual(len(stale), 1)
        self.assertEqual(stale[0]["lifecycle_state"], "NOT_OBSERVED")
        # Must NOT be marked as RESOLVED!
        self.assertNotEqual(stale[0]["lifecycle_state"], "RESOLVED")


if __name__ == "__main__":
    unittest.main()
