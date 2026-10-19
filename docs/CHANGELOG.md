# Changelog — ErgoGuard AI Geometry & Incident Lifecycle Improvements

All notable changes made to the ErgoGuard AI platform to integrate selective geometry code and hazard detection capabilities from the GitHub reference repository are documented below.

---

## [2.1.0] - 2026-10-19

### 1. Unified Computational Geometry Engine
- **Added `ai/geometry.py`**:
  - Implemented `calculate_distance`: Euclidean 2D and 3D distance between points.
  - Implemented `calculate_angle_3points`: Interior joint angle with zero-length vector validation, identical points handling, cosine clamping to $[-1.0, 1.0]$, and 3D landmark support.
  - Implemented `calculate_angle_with_vertical`: Angular inclination from vertical upright posture for trunk and neck flexion analysis.
  - Implemented `calculate_angle_with_horizontal`: Angle relative to the floor plane for fall detection.
  - Implemented `to_box_coords`: Normalizes bounding boxes (`[x, y, w, h]`, `[x1, y1, x2, y2]`, and dictionary formats) into canonical bounds with degenerate box rejection.
  - Implemented `calculate_iou` & `calculate_ioa`: Exact Intersection over Union and Intersection over Area metrics.
  - Implemented `get_bottom_center_point`: Computes foot ground contact point $(x + w/2, y + h)$ across bounding box representations.
  - Implemented `point_in_polygon`: Ray-casting algorithm with collinear cross-product boundary edge and vertex inclusion (`on_edge_inside=True`).
  - Implemented `scale_polygon_coordinates`: Transforms normalized $[0.0, 1.0]$ coordinates to active frame dimensions.
- **Added `engine/geometry.js` & `frontend/src/utils/geometry.js`**:
  - Client-side mirror providing `toPoint`, `angleAt`, `angleFromVertical`, `toBoxCoords`, `boxIntersectionAndAreas`, `iou`, `ioa`, `pointInPolygon`, and `getBottomCenterPoint`.
- **Added `tests/geometry.test.js`**:
  - 37 automated JavaScript unit tests covering right angles, obtuse/acute angles, vertical orientation, IoU/IoA edge cases, polygon containment, and foot point extraction.

### 2. Configurable Polygonal Danger Zones
- **Added `sample_danger_zones.json` & `ai/sample_danger_zones.json`**:
  - Configured 3 non-overlapping industrial zones: `ZONE_ROBOT_CELL_4` (Robotic Cell 4 Perimeter), `DZ-02` (Forklift Transit Corridor), and `DZ-03` (Chemical Storage / Solvent Area).
  - Specified normalized polygon vertices $[0.0, 1.0]$ with required PPE, severity tiers, dwell time thresholds, and BGR HUD colors.
- **Refactored `ai/zone_detection.py` (`ZoneDetector`)**:
  - Dynamically loads multiple polygonal zones from JSON or runtime specifications.
  - Uses `get_bottom_center_point` as the primary ground anchor and secondary IoA ($> 0.40$) body overlap check.
  - Tracks spatial state transitions per worker: `ENTRY` (`ENTERED`), `INSIDE` (`DWELLING`), `TRANSFER` (`TRANSFERRED`), and `EXIT` (`EXITED`).
  - Prevents repeated frame alert generation by emitting breach alerts only on state transitions.
- **Updated `ai/video_processor.py`**:
  - Replaced hardcoded rectangle with dynamic polygonal rendering (`cv2.fillPoly` semi-transparent wash + `cv2.polylines` border + zone names).

### 3. Landmark Ergonomic Posture Detection
- **Refactored `ai/pose_detection.py` (`PoseDetector`)**:
  - Calculates real spinal trunk inclination using vertical angle of vector connecting mid-hip to mid-shoulder.
  - Evaluates knee flexion angle using hip, knee, and ankle keypoints.
  - Differentiates safe squat lifting ($< 150^\circ$ knee flexion) from hazardous straight-legged bending ($> 150^\circ$ knee straightness + $> 35^\circ$ trunk flexion).
  - Explicitly returns `UNKNOWN` or `UNAVAILABLE` when key landmarks are missing or visibility $< 0.50$. **Never classifies missing data as SAFE**.
  - Documented REBA demonstration thresholds vs clinical medical diagnoses.
- **Refactored `ai/detector.py` (`SafetyDetector`)**:
  - Removed naive bounding-box aspect ratio fake spine angles; routes actual landmarks to `pose_detector.analyze_landmarks`.

### 4. Incident Lifecycle & Safety Bug Fixes
- **Fixed `ai/fall_detection.py`**:
  - Verified `Any` import in typing header.
- **Fixed `safety_engine/alert_manager.py`**:
  - Added missing `Set` import from typing.
  - Enforced stable incident IDs (`inc-{worker_id}-{violation}-{timestamp}-{uuid}`).
  - Active violations continuously update existing incident records rather than creating duplicate incidents per frame.
  - Resolved violations generate a brand new distinct incident ID upon recurrence.
  - Worker disappearance transitions active incidents to `NOT_OBSERVED` after disappearance timeout; never falsely marks them `RESOLVED`.
- **Fixed `ai/ppe_detection.py`**:
  - Explicitly represents PPE status as `PRESENT`, `MISSING`, or `UNKNOWN`.
  - When detection fails or model is unavailable, reports `UNKNOWN` with confidence `0.0`. Never assumes PPE is present.
- **Updated `frontend/src/pages/Dashboard.jsx`**:
  - Geofence boundary card displays specific breached zone name and ID in real time.
  - Camera access lifecycle supports DirectShow on Windows with graceful error handling and dual-mode fallback.

### 5. Automated Testing Suite
- **Added `tests/test_geometry.py`**:
  - 25 comprehensive Python unit tests covering geometry math, zone transitions, pose landmark classification, squat vs bend discrimination, missing landmark safety handling, and incident persistence/recurrence.
- **Configured `pytest.ini`**:
  - Standardized test discovery to `tests/` and excluded `scratch/` and `node_modules/`.
- **Executed Test Results**:
  - Full Python suite: **68 passed out of 68 tests (100% pass rate)**.
  - JavaScript suite: **37 passed out of 37 tests (100% pass rate)**.
  - Frontend production build: **Successfully compiled with Vite in 10.94s**.

### 6. Documentation
- Created `docs/GEOMETRY_AND_ZONES.md`
- Created `docs/SAFETY_RULES.md`
- Created `docs/ARCHITECTURE.md`
- Created `docs/TESTING.md`
- Created `docs/CHANGELOG.md`
- Updated `README.md`
