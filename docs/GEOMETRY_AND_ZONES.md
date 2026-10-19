# Geometry Utilities and Polygon Danger Zones

## 1. Overview & Architectural Motivation

In industrial manufacturing, logistics warehouses, and automated robotic workcells, virtual safety perimeters cannot be reliably approximated with simplistic axis-aligned bounding rectangles. Real facilities contain angled transport corridors, curved automated guided vehicle (AGV) paths, polygonal workcell safety envelopes, and non-rectangular storage bays.

To address this, ErgoGuard AI integrates a unified, high-performance computational geometry engine across both the Python AI vision backend (`ai/geometry.py`, `ai/zone_detection.py`) and the browser/client tier (`engine/geometry.js`, `frontend/src/utils/geometry.js`), selective adapted from GitHub reference repository `https://github.com/Sanket08-lab/ErgoGuard-AI/tree/feature/geometry`.

---

## 2. Geometry Utilities Specification

### 2.1 2D and 3D Joint Angle Calculation (`calculate_angle_3points` / `angleAt`)
Calculates the spatial interior angle at vertex $B$ between ray $B \to A$ and ray $B \to C$:

$$\cos(\theta) = \frac{\mathbf{v}_1 \cdot \mathbf{v}_2}{\|\mathbf{v}_1\| \|\mathbf{v}_2\|}$$

$$\theta = \arccos\left(\text{clamp}(\cos(\theta), -1.0, 1.0)\right) \times \frac{180^\circ}{\pi}$$

**Key Capabilities & Edge-Case Safeguards:**
- **Zero-Length Vector Resilience:** When vertex $B$ coincides with $A$ or $C$, or when duplicate keypoints occur, returns `0.0` safely rather than causing `ZeroDivisionError` or `NaN`.
- **Cos-Clamping:** Floating-point rounding errors can occasionally produce $\cos(\theta) = 1.0000000000000002$. Strict clamping to $[-1.0, 1.0]$ prevents domain errors in `math.acos()`.
- **3D Spatial Keypoint Support:** Computes true 3D joint angles when landmarks provide $(x, y, z)$ coordinates (such as depth channels in stereo or MediaPipe pose).
- **Invalid Point Sanitization:** Rejects `NaN`, `None`, and non-numeric coordinates gracefully by returning `0.0`.

### 2.2 Angle from Vertical (`calculate_angle_with_vertical` / `angleFromVertical`)
Calculates the angular inclination of a anatomical or physical vector (e.g., mid-hip to mid-shoulder) relative to the vertical line:

$$\theta_v = \arctan2\left(\sqrt{dx^2 + dz^2}, |dy|\right) \times \frac{180^\circ}{\pi}$$

- **0°:** Perfectly upright/vertical spine posture.
- **90°:** Completely horizontal prostrate or bent body.
- **Input Flexibility:** Accepts either two distinct points $(p_{\text{top}}, p_{\text{bottom}})$ or a direction vector $(dx, dy, dz)$.

### 2.3 Angle from Horizontal (`calculate_angle_with_horizontal`)
Measures the tilt angle of a body or segment relative to the floor plane:
- **0°:** Parallel to the floor (fallen/prone worker).
- **90°:** Completely vertical/standing.

### 2.4 Bounding Box Normalization & Overlap Metrics (`IoU` & `IoA`)
- **`to_box_coords`:** Standardizes diverse bounding box representations (OpenCV `[x, y, w, h]`, PyTorch `[x1, y1, x2, y2]`, and dictionary formats `{x, y, width, height}` or `{xmin, ymin, xmax, ymax}`) into a canonical $(x_1, y_1, x_2, y_2)$ tuple. Degenerate or inverted boxes ($x_2 < x_1$ or $y_2 < y_1$) return `None` safely.
- **Intersection over Union (IoU):**

$$\text{IoU}(A, B) = \frac{\text{Area}(A \cap B)}{\text{Area}(A) + \text{Area}(B) - \text{Area}(A \cap B)}$$

- **Intersection over Area (IoA):**

$$\text{IoA}(A, B) = \frac{\text{Area}(A \cap B)}{\text{Area}(A)}$$

$\text{IoA}(A, B) = 1.0$ indicates that box $A$ is 100% contained within zone box $B$, providing an effective secondary check for person intrusion when bounding boxes overlap hazard zones.

### 2.5 Person Foot-Point Calculation (`get_bottom_center_point`)
Workers move across 3D industrial floor planes. Testing whether a bounding box enters a zone can cause false positives if a tall worker's head passes near an overhead boundary. 

ErgoGuard AI projects the worker's position down to the ground plane by computing the **bottom-center** of the bounding box:

$$\text{Foot}_x = x + \frac{w}{2.0}, \quad \text{Foot}_y = y + h$$

This foot coordinate serves as the authoritative ground anchor point for danger-zone polygon containment.

### 2.6 Point-in-Polygon Detection (`point_in_polygon` / `pointInPolygon`)
Uses the Ray-Casting algorithm to determine whether point $(p_x, p_y)$ lies inside an arbitrary convex or concave polygon.
- **Boundary Edge & Vertex Inclusivity:** A common failure mode in ray-casting is points lying directly on polygon boundary segments or vertices. ErgoGuard AI implements collinear cross-product and segment bounding box checks (`on_edge_inside=True`) to guarantee that workers on boundary lines are correctly classified as inside.

---

## 3. Danger Zone Configuration & Coordinate Systems

### 3.1 Normalized Polygon Specification
Zones are declared in `sample_danger_zones.json` using normalized coordinates in the range $[0.0, 1.0]$:
- $X \in [0.0, 1.0]$ maps from the left edge ($0.0$) to the right edge ($1.0$) of the video frame.
- $Y \in [0.0, 1.0]$ maps from the top edge ($0.0$) to the bottom edge ($1.0$) of the video frame.

This ensures danger zone boundaries remain invariant regardless of camera stream resolution ($1280 \times 720$, $1920 \times 1080$, or $640 \times 360$).

```json
{
  "version": "1.0",
  "coordinate_mode": "normalized",
  "zones": [
    {
      "zone_id": "ZONE_ROBOT_CELL_4",
      "zone_name": "Robotic Cell 4 Perimeter",
      "severity": "CRITICAL",
      "description": "Exclusion perimeter around automated industrial robotic assembly arm.",
      "coordinate_mode": "normalized",
      "polygon": [
        [0.50, 0.25],
        [0.95, 0.25],
        [0.95, 0.90],
        [0.50, 0.90]
      ],
      "required_ppe": ["helmet", "vest"],
      "max_dwell_seconds": 0.0,
      "color_bgr": [0, 0, 240]
    },
    {
      "zone_id": "DZ-02",
      "zone_name": "Forklift Transit Corridor",
      "severity": "HIGH",
      "description": "High-speed automated guided vehicle and forklift corridor.",
      "coordinate_mode": "normalized",
      "polygon": [
        [0.05, 0.55],
        [0.45, 0.55],
        [0.45, 0.95],
        [0.05, 0.95]
      ],
      "required_ppe": ["vest", "helmet"],
      "max_dwell_seconds": 3.0,
      "color_bgr": [0, 165, 255]
    },
    {
      "zone_id": "DZ-03",
      "zone_name": "Chemical Storage / Solvent Area",
      "severity": "HIGH",
      "description": "Storage area for volatile chemical solvents. Full PPE required.",
      "coordinate_mode": "normalized",
      "polygon": [
        [0.60, 0.02],
        [0.95, 0.02],
        [0.95, 0.22],
        [0.60, 0.22]
      ],
      "required_ppe": ["helmet", "goggles", "vest"],
      "max_dwell_seconds": 0.0,
      "color_bgr": [0, 215, 255]
    }
  ]
}
```

### 3.2 Dynamic Frame Scaling
At runtime, `scale_polygon_coordinates` scales normalized vertices to pixel coordinates using the active frame dimensions:

$$x_{\text{pixel}} = x_{\text{norm}} \times \text{frame\_width}, \quad y_{\text{pixel}} = y_{\text{norm}} \times \text{frame\_height}$$

---

## 4. State Transitions & Dwell Time Tracking

### 4.1 Transition State Machine
The `ZoneDetector` (`ai/zone_detection.py`) maintains per-worker spatial state to prevent duplicate alarm generation on every video frame:

| State Transition | Condition | Action Taken |
|---|---|---|
| **`ENTRY` (`ENTERED`)** | Worker moves from outside any zone into Zone $Z_i$ | Record `entry_time`, emit zone breach alert, initialize `dwell_seconds = 0.0`. |
| **`INSIDE` (`DWELLING`)** | Worker remains inside Zone $Z_i$ across consecutive frames | Increment `dwell_seconds = now - entry_time`. Suppress duplicate entry alerts. |
| **`TRANSFER` (`TRANSFERRED`)** | Worker moves directly from Zone $Z_i$ to Zone $Z_j$ | Record `last_zone = Z_i`, update `current_zone = Z_j`, reset `entry_time`. |
| **`EXIT` (`EXITED`)** | Worker steps out of Zone $Z_i$ into an unmonitored safe area | Record `last_zone = Z_i`, set `current_zone = None`, transition lifecycle. |

### 4.2 Multi-Zone Disappearance Safety Rule
When a worker inside a danger zone disappears from the camera view (due to occlusion or camera dropout), the system **never marks the worker safe**. Instead, the incident state is set to `NOT_OBSERVED` until confirmed safe resolution is observed.
