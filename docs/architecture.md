# ErgoGuard AI System Architecture

## 1. System Architecture Overview

ErgoGuard AI is a multi-tier, real-time computer vision safety platform designed to monitor personal safety compliance, posture ergonomics, and hazard zone boundaries in industrial environments.

```
┌────────────────────────────────────────────────────────────────────────┐
│                          CAMERA / VIDEO FEED                           │
│     (USB Webcam / DirectShow / RTSP Stream / Test Fixture Samples)    │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ BGR Video Frames (OpenCV)
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        AI VISION SUBSYSTEM                             │
│  - Person Detection & Centroid Tracking (ai/person_tracking.py)       │
│  - Fine-Tuned YOLOv8 PPE Inspection     (ai/ppe_detection.py)         │
│  - Landmark Ergonomic Pose Detection    (ai/pose_detection.py)        │
│  - Kinematic Fall Vector Analysis       (ai/fall_detection.py)        │
│  - Polygon Geofence Danger Zones        (ai/zone_detection.py)        │
│  - Unified Computational Geometry Core  (ai/geometry.py)              │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ Raw Detections & Tracking Records
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                     SAFETY & RISK ASSESSMENT ENGINE                    │
│                     (safety_engine/risk_engine.py)                     │
│  - Authoritative Heuristic Rules       (ppe, posture, fall, zone)      │
│  - Continuous Incident Lifecycle Engine (safety_engine/alert_manager.py)│
│  - Bounded Risk Scoring (0–100%) & Critical Override                   │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ Canonical Telemetry Event (JSON)
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                     WEBSOCKET TELEMETRY BRIDGE                         │
│                    (ai/event_sender.py • Port 8765)                    │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ WebSocket Stream (ws://127.0.0.1:8765)
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                    REACT FRONTEND DASHBOARD & UI                       │
│  - Real-Time Camera HUD & Overlays     (frontend/src/pages/Dashboard)  │
│  - Incident Lifecycle Audit Log        (frontend/src/pages/Incidents)  │
│  - Safety Trends & Analytics           (frontend/src/pages/Analytics)  │
│  - Local Browser IndexedDB Store       (frontend/src/services/db.js)   │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Component Responsibilities

### 2.1 Computer Vision & Tracking Tier (`ai/`)
- **`ai/geometry.py`:** Core 2D/3D computational geometry utilities: Euclidean distance, 3-point spatial joint angles with cosine clamping, vertical/horizontal orientation angles, bounding box IoU/IoA metrics, bottom-center foot coordinates, and ray-casting polygon containment.
- **`ai/person_tracking.py`:** YOLOv8-based person detector with Euclidean distance centroid tracking. Assigns stable IDs (`W01`, `W02`) across temporal frames.
- **`ai/ppe_detection.py`:** YOLOv8 PPE ONNX model + secondary HSV color validation. Strictly returns `PRESENT`, `MISSING`, or `UNKNOWN`.
- **`ai/pose_detection.py`:** Computes 3D joint angles, spinal trunk inclination, and knee flexion. Differentiates safe squatting from hazardous forward bending. Rejects missing/low-confidence landmarks as `UNKNOWN`/`UNAVAILABLE` (never assumes safety).
- **`ai/fall_detection.py`:** Tracks vertical centroid velocity, aspect ratio inversion, and multi-frame persistence to confirm worker falls.
- **`ai/zone_detection.py`:** Loads polygon zones from JSON, scales normalized coordinates $[0.0, 1.0]$ to frame dimensions, and tracks state transitions (`ENTRY`, `INSIDE`, `TRANSFER`, `EXIT`).
- **`ai/detector.py`:** Master orchestrator integrating all specialized vision sub-detectors into a unified pipeline.
- **`ai/video_processor.py`:** Captures video via OpenCV DirectShow, renders live polygon HUD overlays, and broadcasts telemetry and MJPEG stream.

### 2.2 Safety Engine Tier (`safety_engine/`)
- **`safety_engine/risk_engine.py`:** Authoritative module that calculates risk scores ($0 - 100$), determines categorical risk levels (`SAFE`, `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`), and issues telemetry events conforming to `shared/detection_schema.json`.
- **`safety_engine/alert_manager.py`:** State machine governing incident lifecycles (`CLEAR` $\to$ `DETECTED` $\to$ `ACTIVE` $\to$ `RESOLVED` / `NOT_OBSERVED`). Prevents duplicate frame alerts and maintains stable incident IDs.

### 2.3 Frontend Tier (`frontend/`)
- **React 18 + Vite:** Modern reactive UI with responsive TailwindCSS layout.
- **`frontend/src/utils/geometry.js`:** Pure JavaScript geometry mirror of `ai/geometry.py` ensuring mathematical parity on the client tier.
- **`frontend/src/pages/Dashboard.jsx`:** Live video stream, visual HUD geofences, real-time safety scores, active worker list, and judge demonstration scenario triggers.
- **`frontend/src/pages/Incidents.jsx`:** Complete incident table with severity badges, lifecycle filters, and CSV/JSON export.
- **`frontend/src/pages/Analytics.jsx`:** Longitudinal compliance charts, risk breakdowns, and trend analysis.
- **`frontend/src/services/indexedDB.js`:** Local browser IndexedDB persistence ensuring records survive page refreshes.

---

## 3. Data Flow & Contract

All communication across the WebSocket bridge adheres to `shared/detection_schema.json`:

```json
{
  "schema_version": "1.0",
  "event_id": "evt-W01-1774011244000-a1b2c3",
  "incident_id": "inc-W01-helmet_missing-1774011240000-d4e5f6",
  "primary_incident_id": "inc-W01-helmet_missing-1774011240000-d4e5f6",
  "active_incidents": [
    {
      "incident_id": "inc-W01-helmet_missing-1774011240000-d4e5f6",
      "worker_id": "W01",
      "violation": "helmet_missing",
      "location": "Robotic Cell 4 Perimeter",
      "severity": "LOW",
      "lifecycle_state": "ACTIVE",
      "first_detected_at": 1774011240.0,
      "last_seen_at": 1774011244.0,
      "resolved_at": null
    }
  ],
  "timestamp": "2026-10-19T13:00:44.000Z",
  "source": "LIVE_AI",
  "lifecycle_state": "ACTIVE",
  "worker_id": "W01",
  "track_state": "OBSERVED",
  "location": "Robotic Cell 4 Perimeter",
  "ppe": {
    "helmet": { "status": "MISSING", "confidence": 0.88, "method": "model" },
    "vest": { "status": "PRESENT", "confidence": 0.94, "method": "model" }
  },
  "posture": "SAFE",
  "fall_status": "NONE",
  "danger_zone": {
    "entered": true,
    "zone_id": "ZONE_ROBOT_CELL_4",
    "zone_name": "Robotic Cell 4 Perimeter"
  },
  "violations": ["helmet_missing", "danger_zone_entry"],
  "risk_score": 60,
  "risk_level": "MEDIUM",
  "confidence": 0.91,
  "details": "Restricted zone breach (Robotic Cell 4 Perimeter); Missing safety helmet"
}
```
