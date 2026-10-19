# ErgoGuard AI — Demo Scenarios & Judge Evaluation Guide

This guide details the 5 mandatory hackathon evaluation scenarios and how to present them to judges.

---

## Scenario 1: Fully Compliant Worker (Baseline)
- **Objective:** Demonstrate regular compliant operations with zero false-alarm spam.
- **Trigger:** Click `Demo #1` in the dashboard or press `1` in the Python terminal.
- **Worker ID:** `W01`
- **Location:** `Assembly Line 1`
- **Conditions:**
  - Helmet: `PRESENT` (Confidence: 0.96)
  - Hi-Vis Vest: `PRESENT` (Confidence: 0.95)
  - Posture: `SAFE` (Spine angle: 12.0°)
  - Geofence: `Authorized Zone`
- **Expected Result:**
  - Risk Score: **0% • SAFE** (Green badge).
  - No active alarms or audio beeps.

---

## Scenario 2: Missing Hardhat Violation
- **Objective:** Show automated computer vision detection of missing mandatory head protection.
- **Trigger:** Click `Demo #2` or press `2` in Python terminal.
- **Worker ID:** `W02`
- **Location:** `Machine Zone A`
- **Conditions:**
  - Helmet: `MISSING` (Confidence: 0.92)
  - Hi-Vis Vest: `PRESENT` (Confidence: 0.95)
- **Expected Result:**
  - Risk score increases by +25 points to **25% • LOW RISK**.
  - Active Alert generated: `Missing protective hardhat detected`.
  - AlertCard appears with yellow `LOW RISK` badge.
  - Incident recorded in browser IndexedDB.

---

## Scenario 3: Restricted Danger-Zone Intrusion
- **Objective:** Demonstrate virtual geofencing preventing human-robot collisions in automated cells.
- **Trigger:** Click `Demo #3` or press `3` in Python.
- **Worker ID:** `W03`
- **Location:** `Robotic Cell 4 Perimeter`
- **Conditions:**
  - Full PPE equipped, but worker bounding box intersects normalized perimeter `[0.50, 0.25, 0.45, 0.65]`.
- **Expected Result:**
  - Risk score increases by +35 points to **35% • MEDIUM RISK**.
  - Red restricted perimeter boundary flashes in HUD.
  - Active Alert: `Unauthorized perimeter entry: Worker inside robotic hazard boundary`.

---

## Scenario 4: Worker Fall Emergency (Critical Override)
- **Objective:** Prove instant emergency escalation when a worker collapses or falls.
- **Trigger:** Click `Demo #4` or press `4` in Python.
- **Worker ID:** `W04`
- **Location:** `Loading Bay Ramp C`
- **Conditions:**
  - Fall status: `CONFIRMED_FALL` (Kinematic downward velocity + prostrate aspect ratio > 1.25).
- **Expected Result:**
  - Regardless of numerical score (50%), Risk Level immediately escalates to **`CRITICAL`**.
  - Audio emergency tone sounds to notify safety marshals.
  - Dashboard flashes red pulsing alert.
  - Incident logged with highest audit priority.

---

## Scenario 5: Multi-Hazard Interaction & Ergonomic Strain
- **Objective:** Demonstrate multi-factor composite risk engine.
- **Trigger:** Click `Demo #5` or press `5` in Python.
- **Worker ID:** `W05`
- **Location:** `Warehouse High-Rack 3`
- **Conditions:**
  - Missing hardhat (+25)
  - Missing vest (+20)
  - Unsafe ergonomic lumbar bend (+20)
- **Expected Result:**
  - Risk score aggregates to **65% • HIGH RISK**.
  - Demonstrates multi-violation aggregation without score overflow.

---

## Verifying Local Persistence (IndexedDB)
1. Open the **Incident Log** page (`/incidents`).
2. Verify all triggered scenarios appear in the table with exact timestamps, source tags (`SIM` or `LIVE`), and violation tags.
3. Refresh the browser page (`F5` or `Ctrl+R`).
4. Notice that all incidents remain persisted in IndexedDB!
5. Click **Export JSON** to download the complete audit trail.
