# ErgoGuard AI — Setup & Run Guide (Windows & VS Code)

## Prerequisites

1. **Node.js**: v18+ or v20+ (Verified on Node v25)
2. **Python**: 3.10 through 3.14 (Verified on Python 3.14)
3. **Web Browser**: Chrome, Edge, or Firefox

---

## Step 1: Frontend Setup & Launch

Open a PowerShell terminal in the repository root:

```powershell
# Navigate into frontend or run directly from root:
cd frontend
npm install

# Start the Vite development server
npm run dev
```

Open your browser at:
👉 **[http://localhost:5173](http://localhost:5173)**

The dashboard opens immediately in **Autonomous Simulation & IndexedDB mode** even before Python is started.

---

## Step 2: Python AI Pipeline Setup

Open a **second PowerShell terminal** in the repository root:

```powershell
# Optional: Create and activate virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install Python dependencies
pip install -r ai/requirements.txt

# Download / verify YOLOv8 Person and PPE ONNX models:
python ai/download_models.py
```

Launch the video processing pipeline and WebSocket transport:

```powershell
# Option A: With default webcam (index 0)
python ai/video_processor.py

# Option B: With sample image / test video feed
python ai/video_processor.py --source ai/test_sample.jpg

# Option C: In headless mode (no OpenCV desktop popup window)
python ai/video_processor.py --source ai/test_sample.jpg --nowin
```

The terminal will display:
```text
======================================================================
 ErgoGuard AI — Video Pipeline & Safety Telemetry Engine
 Transport: ws://127.0.0.1:8765
 Active Mode: LIVE_AI (Real frame analysis)
 Terminal Commands: [L] Live Mode, [1-5] Demo Scenarios, [R] Reset, [Q] Quit
======================================================================
```

---

## Step 3: Run Automated Tests

To run the complete 22-test suite verifying real YOLOv8 inference, centroid tracking, PPE inspection, posture smoothing, fall kinematics, geofencing, risk scoring, and schema compliance:

```powershell
python -m unittest discover tests
```

Expected result:
```text
Ran 22 tests in 3.394s
OK
```

To verify the production frontend build:
```powershell
npm --prefix frontend run build
```

---

## 5-Minute Prototype Demonstration Checklist

1. **Live Camera / Video Inference**:
   - Start Python: `python ai/video_processor.py --source ai/test_sample.jpg`
   - Refresh `http://localhost:5173/`.
   - Verify connection badge shows `SYSTEM ONLINE` (green).
   - In the video monitor, observe the live annotated video feed streamed from Python with real YOLOv8 bounding boxes, tracker IDs (`W01`, `W02`), PPE tags, and the red `RESTRICTED ROBOTIC GEOFENCE`.

2. **Truthful Zero-Worker Reporting**:
   - When no workers are in view (e.g. blank input), active workers count drops to `0`, compliance displays `—`, and risk score defaults to safe without fabricating fake detections.

3. **Deterministic Safety Rules & Risk Scoring**:
   - Unsafe Posture: +20
   - Missing Helmet: +25
   - Missing Vest: +20
   - Danger-Zone Intrusion: +35
   - Confirmed Fall: +50 (with automatic CRITICAL severity level override)

4. **Strict Isolation of Demo Scenarios**:
   - Click `Demo 2: Missing Hardhat` in the top navbar.
   - The badge updates to `MODE: SIMULATED` (amber) with `SIMULATED SCENARIO` tag.
   - Click `Live AI Mode` to return to genuine camera inference.

5. **IndexedDB Incident Deduplication & Persistence**:
   - Navigate to `/incidents`.
   - Confirm incidents are stored with timestamps, worker IDs, and violation tags.
   - Press `F5` to refresh the browser — incidents persist intact from IndexedDB.
