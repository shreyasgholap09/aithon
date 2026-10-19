/**
 * Geometry Utilities for ErgoGuard AI Frontend
 * Provides 2D/3D joint angles, bounding box IoU/IoA metrics,
 * ray-casting polygon containment, and foot-point ground anchors.
 */

// Converts array or object coordinates to a unified point object with x, y, and optional z.
export function toPoint(p) {
  if (Array.isArray(p)) {
    return { x: Number(p[0]) || 0, y: Number(p[1]) || 0, z: p[2] !== undefined ? Number(p[2]) : undefined };
  }
  if (p && typeof p === 'object') {
    return {
      x: Number(p.x) || 0,
      y: Number(p.y) || 0,
      z: p.z !== undefined ? Number(p.z) : undefined
    };
  }
  return { x: 0, y: 0 };
}

// Computes joint angle in degrees at vertex b formed by rays ba and bc for ergonomic posture tracking.
export function angleAt(a, b, c) {
  const pa = toPoint(a);
  const pb = toPoint(b);
  const pc = toPoint(c);

  const v1x = pa.x - pb.x;
  const v1y = pa.y - pb.y;
  const v2x = pc.x - pb.x;
  const v2y = pc.y - pb.y;

  const hasZ = pa.z !== undefined && pb.z !== undefined && pc.z !== undefined;
  const v1z = hasZ ? pa.z - pb.z : 0;
  const v2z = hasZ ? pc.z - pb.z : 0;

  const dot = v1x * v2x + v1y * v2y + v1z * v2z;
  const mag1 = Math.hypot(v1x, v1y, v1z);
  const mag2 = Math.hypot(v2x, v2y, v2z);

  if (mag1 === 0 || mag2 === 0) return 0;

  const cosTheta = Math.max(-1, Math.min(1, dot / (mag1 * mag2)));
  return (Math.acos(cosTheta) * 180) / Math.PI;
}

// Computes inclination angle in degrees of a segment or vector relative to the vertical axis.
export function angleFromVertical(a, b) {
  const pa = toPoint(a);
  let dx = 0;
  let dy = 0;
  let dz = 0;

  if (b !== undefined) {
    const pb = toPoint(b);
    dx = pb.x - pa.x;
    dy = pb.y - pa.y;
    if (pa.z !== undefined && pb.z !== undefined) {
      dz = pb.z - pa.z;
    }
  } else {
    dx = pa.x;
    dy = pa.y;
    if (pa.z !== undefined) {
      dz = pa.z;
    }
  }

  const horizontalDist = Math.hypot(dx, dz);
  const verticalDist = Math.abs(dy);

  if (horizontalDist === 0 && verticalDist === 0) return 0;

  return (Math.atan2(horizontalDist, verticalDist) * 180) / Math.PI;
}

// Normalizes various bounding box representations into [xmin, ymin, xmax, ymax] order.
export function toBoxCoords(box) {
  if (Array.isArray(box)) {
    return [box[0], box[1], box[2], box[3]];
  }
  if (!box || typeof box !== 'object') {
    return [0, 0, 0, 0];
  }
  if (box.xmin !== undefined && box.xmax !== undefined) {
    return [box.xmin, box.ymin, box.xmax, box.ymax];
  }
  if (box.minX !== undefined && box.maxX !== undefined) {
    return [box.minX, box.minY, box.maxX, box.maxY];
  }
  if (box.left !== undefined && box.right !== undefined) {
    return [box.left, box.top, box.right, box.bottom];
  }

  const x = box.x ?? box.left ?? 0;
  const y = box.y ?? box.top ?? 0;
  const w = box.width ?? box.w ?? 0;
  const h = box.height ?? box.h ?? 0;
  return [x, y, x + w, y + h];
}

// Computes intersection area and individual box areas for bounding box metric calculations.
export function boxIntersectionAndAreas(a, b) {
  const [aX1, aY1, aX2, aY2] = toBoxCoords(a);
  const [bX1, bY1, bX2, bY2] = toBoxCoords(b);

  const interX1 = Math.max(Math.min(aX1, aX2), Math.min(bX1, bX2));
  const interY1 = Math.max(Math.min(aY1, aY2), Math.min(bY1, bY2));
  const interX2 = Math.min(Math.max(aX1, aX2), Math.max(bX1, bX2));
  const interY2 = Math.min(Math.max(aY1, aY2), Math.max(bY1, bY2));

  const interW = Math.max(0, interX2 - interX1);
  const interH = Math.max(0, interY2 - interY1);
  const interArea = interW * interH;

  const areaA = Math.max(0, Math.abs(aX2 - aX1)) * Math.max(0, Math.abs(aY2 - aY1));
  const areaB = Math.max(0, Math.abs(bX2 - bX1)) * Math.max(0, Math.abs(bY2 - bY1));

  return { interArea, areaA, areaB };
}

// Calculates Intersection over Union between two bounding boxes for overlap evaluation and NMS.
export function iou(a, b) {
  const { interArea, areaA, areaB } = boxIntersectionAndAreas(a, b);
  const unionArea = areaA + areaB - interArea;
  if (unionArea <= 0) return 0;
  return interArea / unionArea;
}

// Calculates Intersection over Area of box a covered by box b for containment and occlusion analysis.
export function ioa(a, b) {
  const { interArea, areaA } = boxIntersectionAndAreas(a, b);
  if (areaA <= 0) return 0;
  return interArea / areaA;
}

// Ray-casting algorithm to test if a point is inside a 2D polygon.
export function pointInPolygon(point, polygon) {
  const pt = toPoint(point);
  if (!Array.isArray(polygon) || polygon.length < 3) return false;

  const pts = polygon.map(p => toPoint(p));
  const n = pts.length;
  let inside = false;

  let p1 = pts[0];
  for (let i = 1; i <= n; i++) {
    const p2 = pts[i % n];
    if (pt.y > Math.min(p1.y, p2.y) && pt.y <= Math.max(p1.y, p2.y) && pt.x <= Math.max(p1.x, p2.x)) {
      const xinters = p1.y !== p2.y ? (pt.y - p1.y) * (p2.x - p1.x) / (p2.y - p1.y) + p1.x : p1.x;
      if (p1.x === p2.x || pt.x <= xinters) {
        inside = not inside;
      }
    }
    p1 = p2;
  }
  return inside;
}

// Extracts worker bottom-center foot position from bounding box.
export function getBottomCenterPoint(box) {
  const [x1, y1, x2, y2] = toBoxCoords(box);
  return {
    x: (x1 + x2) / 2,
    y: Math.max(y1, y2)
  };
}
