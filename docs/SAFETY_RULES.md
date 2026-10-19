# ErgoGuard AI Safety Rules & Authoritative Risk Engine

## 1. Overview & Authoritative Architecture

The Python Safety Engine (`safety_engine/risk_engine.py`) is the single authoritative source of truth for:
- Evaluating PPE compliance (`safety_engine/ppe_rules.py`)
- Analyzing ergonomic posture risk (`safety_engine/posture_rules.py`)
- Detecting emergency worker falls (`safety_engine/fall_rules.py`)
- Detecting restricted danger zone breaches (`safety_engine/zone_rules.py`)
- Scoring numerical risk and assigning severity tiers
- Managing continuous incident lifecycles (`safety_engine/alert_manager.py`)

The frontend dashboard displays risk levels and telemetry computed by this authoritative engine; it does not calculate duplicate or divergent risk scores.

---

## 2. Personal Protective Equipment (PPE) Rules

### 2.1 Three-State Representation: `PRESENT`, `MISSING`, `UNKNOWN`
To prevent false compliance or false accusations, ErgoGuard AI strictly distinguishes between:
- **`PRESENT`:** High-confidence affirmative visual evidence of required gear (e.g., Hardhat or Safety Vest).
- **`MISSING`:** Confirmed absence of equipment detected with high confidence (e.g., `NO-Hardhat` or `NO-Safety Vest` model class).
- **`UNKNOWN`:** Insufficient visual evidence (low camera resolution, severe occlusion, bad lighting, or model capability offline). **Missing data is NEVER classified as compliant (`PRESENT`)**.

### 2.2 Temporal Confirmation & Hysteresis
A single blurry or occluded frame where equipment cannot be identified does not immediately trigger a `MISSING` incident. The `PPEDetector` enforces temporal smoothing requiring consecutive confirmation frames before declaring a violation.

---

## 3. Ergonomic Posture Rules & REBA Demonstration Thresholds

### 3.1 Landmark Geometry & Joint Angles
ErgoGuard AI uses real joint landmark coordinates rather than naive bounding-box aspect ratios:
- **Trunk Inclination Angle:** Computed from the 3D anatomical vector connecting mid-hip to mid-shoulder relative to vertical.
- **Knee Flexion Angle:** Computed at the knee vertex using hip, knee, and ankle keypoints ($180^\circ = \text{straight leg}, < 140^\circ = \text{bent knee}$).
- **Neck Flexion Angle:** Computed from mid-shoulder to mid-ear.

### 3.2 Posture Categorization
- **`SAFE`:** Trunk inclination $< 25^\circ$, or squatting with deeply bent knees ($< 150^\circ$) to safely lift loads from the floor.
- **`WARNING`:** Moderate trunk flexion between $25^\circ$ and $35^\circ$ without deep knee bend.
- **`UNSAFE`:** Severe trunk bending $> 35^\circ$ with straight knees, producing dangerous lumbar shear stress.
- **`UNKNOWN` / `UNAVAILABLE`:** Returned when key landmarks are missing, occluded, or confidence $< 0.50$. **Never classified as SAFE when data is missing.**

> **Notice:** These thresholds are demonstration heuristics inspired by standard Rapid Entire Body Assessment (REBA) guidelines, not certified clinical medical diagnoses.

---

## 4. Fall Emergency Detection Rules

### 4.1 Kinematic Fall Vector Analysis
A dangerous fall is detected by evaluating:
1. **Vertical Centroid Velocity:** Rapid downward displacement of the worker's bounding box centroid exceeding velocity threshold ($> 35 \text{ px/sec}$).
2. **Aspect Ratio Inversion:** Rapid shift from upright aspect ratio ($\text{width} / \text{height} < 1.0$) to prostrate horizontal aspect ratio ($\text{width} / \text{height} > 1.25$).
3. **Temporal Persistence:** Sustained horizontal posture over consecutive confirmation frames to prevent false alarms from brief bending or sitting.

### 4.2 Critical Escalation Policy
A confirmed fall triggers an **immediate `CRITICAL` severity override**, regardless of baseline numerical risk score.

---

## 5. Danger Zone Geofencing Rules

### 5.1 Penetration Logic
- A worker is evaluated as inside a restricted zone when their ground contact foot-point (bottom-center of bounding box) lies inside the configured polygon (`point_in_polygon`).
- As a secondary safeguard, an Intersection over Area (IoA) $> 0.40$ also flags zone penetration if the worker's body overlaps the hazard volume.

---

## 6. Authoritative Numerical Risk Scoring & Severity Tiers

### 6.1 Penalty Weights
The bounded numerical risk score ranges from $0$ to $100$:

$$\text{Risk Score} = \min\left(100, \sum \text{Active Penalty Weights}\right)$$

| Violation Type | Weight Contribution |
|---|---|
| **`helmet_missing`** | +25 pts |
| **`vest_missing`** | +20 pts |
| **`unsafe_posture`** | +20 pts |
| **`danger_zone_entry`** | +35 pts |
| **`fall_detected`** | +50 pts (Triggers immediate `CRITICAL` severity override) |

### 6.2 Severity Categorization
- **`SAFE`:** Score $= 0$
- **`LOW`:** Score $1 - 30$
- **`MEDIUM`:** Score $31 - 60$
- **`HIGH`:** Score $61 - 100$
- **`CRITICAL`:** Confirmed worker fall (`CONFIRMED_FALL`)

---

## 7. Incident Lifecycle State Machine

To eliminate alarm fatigue and video-frame duplicate spam, `AlertManager` implements a formal state machine:

```
[ CLEAR ] ──(Violation Observed)──► [ DETECTED ]
                                          │
                               (Confirmation Frames Met)
                                          │
                                          ▼
                                    [ ACTIVE ] ◄──(Persists on same incident_id)
                                          │
                   ┌──────────────────────┴──────────────────────┐
            (Worker Absent)                               (Hazard Resolved)
                   │                                             │
                   ▼                                             ▼
            [ NOT_OBSERVED ]                              [ RESOLVED ]
                   │                                             │
       (Returns with Violation)                          (Violation Recurs)
                   │                                             │
                   ▼                                             ▼
        [ Reactivates ACTIVE ]                         [ New Incident Created ]
         (Same incident_id)                              (Fresh incident_id)
```

1. **Stable Incident ID:** Assigned once upon confirmation (`inc-{worker_id}-{violation}-{timestamp}-{uuid}`).
2. **Persistence Update:** While violation continues, the existing active incident record is updated (`last_seen_at`), producing no duplicate entries.
3. **Recurrence New ID:** If an incident has been resolved and the same violation occurs again later, a brand new unique incident ID is generated.
4. **Disappearance vs. Resolution:** A worker stepping out of the camera view or camera dropout transitions the incident to `NOT_OBSERVED`. Hazards are only marked `RESOLVED` when the worker is clearly observed in full compliance.
