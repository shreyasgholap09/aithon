# ErgoGuard AI — Intelligent Workplace Safety & Compliance Platform

[![Track: Industrial Automation & Robotics](https://img.shields.io/badge/Track-Industrial_Automation_%26_Robotics-blue.svg)](https://github.com)
[![Tech: React + Vite](https://img.shields.io/badge/Frontend-React_18_%7C_Vite-61dafb.svg)](https://react.dev)
[![AI Engine: Python + OpenCV](https://img.shields.io/badge/Engine-Python_3.14_%7C_OpenCV-3776ab.svg)](https://python.org)
[![Storage: IndexedDB](https://img.shields.io/badge/Storage-Browser_IndexedDB-orange.svg)](https://developer.mozilla.org)
[![Tests: 105 Passing](https://img.shields.io/badge/Tests-105%2F105_Passing-brightgreen.svg)](docs/TESTING.md)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

ErgoGuard AI is an AI-assisted workplace safety monitoring and compliance platform designed for modern manufacturing plants, automated robotic cells, and logistics warehouses. It evaluates computer vision video streams, inspects Personal Protective Equipment (PPE) compliance, evaluates ergonomic posture risks, detects dangerous worker falls, monitors virtual polygon-based restricted danger zones, and computes an auditable real-time risk score with persistent browser-side audit storage in IndexedDB.

---

## 🚀 Key Features

1. **Computational Geometry Core**: 2D and 3D joint angle calculations with cosine clamping, vertical inclination, floor horizontal angles, bounding box IoU & IoA metrics, and robust point-in-polygon ray-casting with boundary edge inclusion.
2. **Configurable Polygonal Danger Zones**: Replaces rigid rectangular boxes with multi-zone normalized polygon geofences (`sample_danger_zones.json`). Features foot contact ground anchor calculation (`bottom-center`) and zone transition tracking (`ENTRY`, `INSIDE`, `TRANSFER`, `EXIT`).
3. **Ergonomic Posture Detection**: Analyzes real joint landmarks (trunk inclination, knee flexion, neck flexion). Distinguishes hazardous straight-legged bending from compliant squat lifting. Explicitly returns `UNKNOWN`/`UNAVAILABLE` when landmarks are missing or low confidence—**never classifies missing data as SAFE**.
4. **PPE Compliance Inspection**: Automated YOLOv8 inspection of safety helmets (hard hats) and high-visibility vests with explicit `PRESENT`, `MISSING`, and `UNKNOWN` states.
5. **Instant Fall Emergency Escalation**: Kinematic vertical velocity and aspect-ratio inversion analysis with automatic `CRITICAL` severity override.
6. **Robust Incident Lifecycle State Machine**: Enforces stable incident IDs (`inc-{worker_id}-{violation}-{timestamp}-{uuid}`), updates ongoing violations without duplicate alert spam, creates fresh IDs upon violation recurrence, and transitions unobserved workers to `NOT_OBSERVED` rather than prematurely marking them safe.
7. **DirectShow Windows Camera Access**: Resilient camera reader supporting DirectShow on Windows (`cv2.CAP_DSHOW`), dual-mode fallback (Python backend or browser local camera preview), and automatic camera lock resolution.
8. **Real-Time Safety Dashboard**: Interactive HUD overlays with dynamic polygon visualization, active worker states, longitudinal analytics, and persistent IndexedDB audit logging.

---

## 📐 Architecture & Workflow

```
[ Camera / Video Feed / Test Scenarios ]
                   │
                   ▼
         ┌───────────────────┐
         │  Python AI Module │ (ai/detector.py)
         │  - Person Tracker │ (ai/person_tracking.py)
         │  - PPE Inspection │ (ai/ppe_detection.py)
         │  - Pose Angles    │ (ai/pose_detection.py)
         │  - Fall Tracker   │ (ai/fall_detection.py)
         │  - Zone Boundary  │ (ai/zone_detection.py)
         │  - Geometry Core  │ (ai/geometry.py)
         └─────────┬─────────┘
                   │ Raw Detections & Tracking Records
                   ▼
         ┌───────────────────┐
         │   Safety Engine   │ (safety_engine/risk_engine.py)
         │  - Heuristic Rules│ (ppe, posture, fall, zone)
         │  - Risk Scoring   │ (0–100% scale + CRITICAL override)
         │  - Alert Manager  │ (CLEAR -> DETECTED -> ACTIVE -> RESOLVED)
         └─────────┬─────────┘
                   │ Canonical JSON Stream (shared/detection_schema.json)
                   ▼
         ┌───────────────────┐
         │WebSocket Transport│ (ai/event_sender.py • ws://localhost:8765)
         └─────────┬─────────┘
                   │ Stream
                   ▼
         ┌───────────────────┐
         │  React Dashboard  │ (frontend/)
         │  - Live Safety HUD│ (frontend/src/pages/Dashboard.jsx)
         │  - Incidents Log  │ (frontend/src/pages/Incidents.jsx)
         │  - Analytics Graph│ (frontend/src/pages/Analytics.jsx)
         └─────────┬─────────┘
                   │ Persistent Browser Storage
                   ▼
         ┌───────────────────┐
         │ Browser IndexedDB │ (ErgoGuardDB • survives F5 refreshes)
         └───────────────────┘
```

Detailed architectural diagrams and telemetry contracts are available in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

---

## 🛠️ Windows Setup & Run Instructions

### 1. Prerequisites
- **Operating System:** Windows 10 / 11
- **Node.js:** v18+ (tested on Node v22.14.0)
- **Python:** 3.10 – 3.14 (tested on Python 3.14.3)
- **Webcam:** Optional (built-in DirectShow camera, video file, or test fixture)

### 2. Launch Frontend (React + Vite)
```powershell
# From project root:
cd frontend
npm install
npm run dev
```
Open **`http://localhost:5173`** in your browser.

### 3. Launch Python AI Backend
In a separate PowerShell window:
```powershell
# Install Python dependencies:
pip install -r ai/requirements.txt

# Run with physical webcam:
python ai/video_processor.py --camera

# OR run with a video file:
python ai/video_processor.py --source "path/to/video.mp4"

# OR run with test fixture sample:
python ai/video_processor.py --source sample
```
The backend initializes the AI vision pipeline, loads polygonal danger zones from `sample_danger_zones.json`, and starts broadcasting on `ws://127.0.0.1:8765`.

---

## 🧪 Automated Testing (105 Tests Passing)

All tests are verified in the active Windows environment.

```powershell
# 1. Run full Python test suite (68 tests):
python -m pytest -v

# 2. Run dedicated geometry and zone test suite (25 tests):
python -m pytest tests/test_geometry.py -v

# 3. Run JavaScript client geometry test suite (37 tests):
node tests/geometry.test.js

# 4. Validate frontend production build:
npm run build
```

Full execution logs and breakdown can be inspected in [docs/TESTING.md](docs/TESTING.md).

---

## 📖 Technical Documentation

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — System architecture, component responsibilities, and data schema.
- [docs/GEOMETRY_AND_ZONES.md](docs/GEOMETRY_AND_ZONES.md) — Computational geometry math, polygon geofences, coordinate systems, and state transitions.
- [docs/SAFETY_RULES.md](docs/SAFETY_RULES.md) — Authoritative risk scoring, PPE rules, REBA posture rules, and incident lifecycles.
- [docs/TESTING.md](docs/TESTING.md) — Comprehensive test commands, test coverage, and execution outputs.
- [docs/CHANGELOG.md](docs/CHANGELOG.md) — Detailed summary of all improvements and bug fixes.

---

## ⚠️ Known Limitations & Technical Honesty

1. **Python 3.14 MediaPipe Availability:** MediaPipe wheels are currently unavailable for Python 3.14 on Windows. In environments without MediaPipe wheels, `PoseDetector` gracefully handles missing pose estimation landmarks by returning `UNKNOWN`/`UNAVAILABLE` and confidence `0.0`. It never fabricates posture or defaults missing data to `SAFE`.
2. **Demonstration Ergonomic Thresholds:** Posture angle thresholds ($25^\circ$, $35^\circ$, $150^\circ$) are demonstration approximations inspired by Rapid Entire Body Assessment (REBA) and OSHA guidelines. They do not constitute certified clinical ergonomic evaluations.
3. **Simulation Explicit Labeling:** Demo test scenarios are explicitly tagged with `source: "SIMULATED"` across all telemetry payloads and dashboard badges, strictly separating simulated events from real computer vision inference.
