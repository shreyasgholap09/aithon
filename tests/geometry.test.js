import assert from 'node:assert/strict';
import { angleAt, angleFromVertical, iou, ioa, pointInPolygon, getBottomCenterPoint } from '../engine/geometry.js';

// Helper for floating point comparisons within tolerance
function assertApprox(actual, expected, tolerance = 1e-5, message = '') {
  assert.ok(
    Math.abs(actual - expected) <= tolerance,
    `${message} Expected ${expected} (+/- ${tolerance}), got ${actual}`
  );
}

// Track test count
let testsRun = 0;
function test(name, fn) {
  testsRun += 1;
  try {
    fn();
    console.log(`  ✓ ${name}`);
  } catch (err) {
    console.error(`  ✗ ${name}`);
    throw err;
  }
}

console.log('Running geometry.js test suite...\n');

// -------------------------------------------------------------
// angleAt tests
// -------------------------------------------------------------
console.log('Testing angleAt:');

test('angleAt: 90-degree right angle (points along axes)', () => {
  const a = { x: 1, y: 0 };
  const b = { x: 0, y: 0 };
  const c = { x: 0, y: 1 };
  assertApprox(angleAt(a, b, c), 90, 1e-5, 'Right angle should be 90 degrees');
});

test('angleAt: 180-degree straight line (opposite rays)', () => {
  const a = { x: -5, y: 0 };
  const b = { x: 0, y: 0 };
  const c = { x: 5, y: 0 };
  assertApprox(angleAt(a, b, c), 180, 1e-5, 'Straight angle should be 180 degrees');
});

test('angleAt: 0-degree angle (co-directional rays)', () => {
  const a = { x: 2, y: 0 };
  const b = { x: 0, y: 0 };
  const c = { x: 4, y: 0 };
  assertApprox(angleAt(a, b, c), 0, 1e-5, 'Collinear same-direction rays should be 0 degrees');
});

test('angleAt: 45-degree angle', () => {
  const a = { x: 1, y: 1 };
  const b = { x: 0, y: 0 };
  const c = { x: 1, y: 0 };
  assertApprox(angleAt(a, b, c), 45, 1e-5, 'Diagonal to axis should be 45 degrees');
});

test('angleAt: 60-degree angle (equilateral triangle geometry)', () => {
  const a = { x: 1, y: 0 };
  const b = { x: 0, y: 0 };
  const c = { x: 0.5, y: Math.sqrt(3) / 2 };
  assertApprox(angleAt(a, b, c), 60, 1e-5, 'Should match equilateral triangle 60 degrees');
});

test('angleAt: 120-degree obtuse angle', () => {
  const a = { x: 1, y: 0 };
  const b = { x: 0, y: 0 };
  const c = { x: -0.5, y: Math.sqrt(3) / 2 };
  assertApprox(angleAt(a, b, c), 120, 1e-5, 'Should match obtuse 120 degrees');
});

test('angleAt: non-origin vertex', () => {
  const a = { x: 5, y: 10 };
  const b = { x: 5, y: 5 };
  const c = { x: 10, y: 5 };
  assertApprox(angleAt(a, b, c), 90, 1e-5, 'Translated vertex right angle should be 90 degrees');
});

test('angleAt: 3D coordinates right angle', () => {
  const a = { x: 0, y: 0, z: 1 };
  const b = { x: 0, y: 0, z: 0 };
  const c = { x: 1, y: 0, z: 0 };
  assertApprox(angleAt(a, b, c), 90, 1e-5, '3D perpendicular vectors should be 90 degrees');
});

test('angleAt: coordinates passed as arrays', () => {
  assertApprox(angleAt([1, 0], [0, 0], [0, 1]), 90, 1e-5, 'Array coords right angle should be 90 degrees');
});

test('angleAt: degenerate coincident points return 0', () => {
  assert.strictEqual(angleAt({ x: 0, y: 0 }, { x: 0, y: 0 }, { x: 1, y: 0 }), 0);
});

// -------------------------------------------------------------
// angleFromVertical tests
// -------------------------------------------------------------
console.log('\nTesting angleFromVertical:');

test('angleFromVertical: perfectly vertical upright segment (0 degrees)', () => {
  const a = { x: 0, y: 0 };
  const b = { x: 0, y: 10 };
  assertApprox(angleFromVertical(a, b), 0, 1e-5, 'Vertical line should be 0 degrees');
});

test('angleFromVertical: vertical segment inverted order (0 degrees)', () => {
  const a = { x: 0, y: 10 };
  const b = { x: 0, y: 0 };
  assertApprox(angleFromVertical(a, b), 0, 1e-5, 'Inverted vertical segment should be 0 degrees');
});

test('angleFromVertical: perfectly horizontal segment (90 degrees)', () => {
  const a = { x: 0, y: 0 };
  const b = { x: 10, y: 0 };
  assertApprox(angleFromVertical(a, b), 90, 1e-5, 'Horizontal segment should be 90 degrees');
});

test('angleFromVertical: 45-degree inclination', () => {
  const a = { x: 0, y: 0 };
  const b = { x: 10, y: 10 };
  assertApprox(angleFromVertical(a, b), 45, 1e-5, 'Equal dx and dy should be 45 degrees');
});

test('angleFromVertical: 30-degree tilt from vertical', () => {
  const a = { x: 0, y: 0 };
  const b = { x: 1, y: Math.sqrt(3) };
  assertApprox(angleFromVertical(a, b), 30, 1e-5, 'dx=1, dy=sqrt(3) should be 30 degrees');
});

test('angleFromVertical: 60-degree tilt from vertical', () => {
  const a = { x: 0, y: 0 };
  const b = { x: Math.sqrt(3), y: 1 };
  assertApprox(angleFromVertical(a, b), 60, 1e-5, 'dx=sqrt(3), dy=1 should be 60 degrees');
});

test('angleFromVertical: symmetric tilt in negative x direction', () => {
  const a = { x: 0, y: 0 };
  const b = { x: -1, y: Math.sqrt(3) };
  assertApprox(angleFromVertical(a, b), 30, 1e-5, 'Negative dx should give same inclination');
});

test('angleFromVertical: single vector object input', () => {
  assertApprox(angleFromVertical({ x: 0, y: 15 }), 0, 1e-5, 'Vector along vertical should be 0');
  assertApprox(angleFromVertical({ x: 10, y: 10 }), 45, 1e-5, 'Diagonal vector should be 45');
});

test('angleFromVertical: array inputs', () => {
  assertApprox(angleFromVertical([0, 0], [0, 5]), 0, 1e-5, 'Vertical array segment should be 0');
  assertApprox(angleFromVertical([5, 5]), 45, 1e-5, 'Single vector array should be 45');
});

test('angleFromVertical: zero-length segment returns 0', () => {
  assert.strictEqual(angleFromVertical({ x: 5, y: 5 }, { x: 5, y: 5 }), 0);
});

// -------------------------------------------------------------
// iou tests
// -------------------------------------------------------------
console.log('\nTesting iou:');

test('iou: identical bounding boxes (1.0)', () => {
  const a = { x: 0, y: 0, width: 10, height: 10 };
  const b = { x: 0, y: 0, width: 10, height: 10 };
  assertApprox(iou(a, b), 1.0, 1e-5, 'Identical boxes should have IoU = 1');
});

test('iou: completely disjoint boxes (0.0)', () => {
  const a = { x: 0, y: 0, width: 10, height: 10 };
  const b = { x: 20, y: 20, width: 10, height: 10 };
  assert.strictEqual(iou(a, b), 0, 'Disjoint boxes should have IoU = 0');
});

test('iou: touching boundary with 0 area intersection (0.0)', () => {
  const a = { x: 0, y: 0, width: 10, height: 10 };
  const b = { x: 10, y: 0, width: 10, height: 10 };
  assert.strictEqual(iou(a, b), 0, 'Touching edge boxes should have IoU = 0');
});

test('iou: 50% horizontal shift (known answer 1/3)', () => {
  const a = { x: 0, y: 0, width: 10, height: 10 };
  const b = { x: 5, y: 0, width: 10, height: 10 };
  assertApprox(iou(a, b), 1 / 3, 1e-5, 'Half-shifted squares should have IoU = 1/3');
});

test('iou: 50% overlap in both X and Y (known answer 1/7)', () => {
  const a = { x: 0, y: 0, width: 10, height: 10 };
  const b = { x: 5, y: 5, width: 10, height: 10 };
  assertApprox(iou(a, b), 1 / 7, 1e-5, 'Corner overlap should have IoU = 1/7');
});

test('iou: small box fully contained in larger box', () => {
  const a = { x: 2, y: 2, width: 4, height: 4 };
  const b = { x: 0, y: 0, width: 10, height: 10 };
  assertApprox(iou(a, b), 0.16, 1e-5, 'Contained box should have IoU = 0.16');
});

test('iou: xmin/ymin/xmax/ymax format', () => {
  const a = { xmin: 0, ymin: 0, xmax: 10, ymax: 10 };
  const b = { xmin: 5, ymin: 0, xmax: 15, ymax: 10 };
  assertApprox(iou(a, b), 1 / 3, 1e-5, 'xmin/xmax format should compute IoU = 1/3');
});

test('iou: array [xmin, ymin, xmax, ymax] format', () => {
  const a = [0, 0, 10, 10];
  const b = [0, 0, 10, 10];
  assertApprox(iou(a, b), 1.0, 1e-5, 'Array format should compute IoU = 1.0');
});

test('iou: zero-area box returns 0', () => {
  const a = { x: 0, y: 0, width: 0, height: 0 };
  const b = { x: 0, y: 0, width: 10, height: 10 };
  assert.strictEqual(iou(a, b), 0, 'Zero-area box should return 0');
});

// -------------------------------------------------------------
// ioa tests
// -------------------------------------------------------------
console.log('\nTesting ioa:');

test('ioa: identical boxes (1.0)', () => {
  const a = { x: 0, y: 0, width: 10, height: 10 };
  const b = { x: 0, y: 0, width: 10, height: 10 };
  assertApprox(ioa(a, b), 1.0, 1e-5, 'Identical boxes should have IoA = 1.0');
});

test('ioa: small box fully contained inside large box', () => {
  const a = { x: 2, y: 2, width: 4, height: 4 };
  const b = { x: 0, y: 0, width: 10, height: 10 };
  assertApprox(ioa(a, b), 1.0, 1e-5, 'Small box inside large box should have ioa(a, b) = 1.0');
  assertApprox(ioa(b, a), 0.16, 1e-5, 'Large box with small inside should have ioa(b, a) = 0.16');
});

test('ioa: completely disjoint boxes (0.0)', () => {
  const a = { x: 0, y: 0, width: 10, height: 10 };
  const b = { x: 20, y: 20, width: 10, height: 10 };
  assert.strictEqual(ioa(a, b), 0, 'Disjoint boxes should have IoA = 0');
});

test('ioa: 50% overlap of reference box (0.5)', () => {
  const a = { x: 0, y: 0, width: 10, height: 10 };
  const b = { x: 5, y: 0, width: 10, height: 10 };
  assertApprox(ioa(a, b), 0.5, 1e-5, 'Half-covered box should have IoA = 0.5');
});

test('ioa: zero-area reference box returns 0', () => {
  const a = { x: 0, y: 0, width: 0, height: 0 };
  const b = { x: 0, y: 0, width: 10, height: 10 };
  assert.strictEqual(ioa(a, b), 0, 'Zero-area reference box should return 0');
});

// -------------------------------------------------------------
// pointInPolygon tests
// -------------------------------------------------------------
console.log('\nTesting pointInPolygon:');

test('pointInPolygon: points inside, outside, and on boundary of square', () => {
  const square = [
    [0, 0],
    [10, 0],
    [10, 10],
    [0, 10]
  ];
  assert.strictEqual(pointInPolygon([5, 5], square), true, 'Center point should be inside');
  assert.strictEqual(pointInPolygon([15, 5], square), false, 'Point outside should be false');
  assert.strictEqual(pointInPolygon([-1, 5], square), false, 'Point to the left should be false');
  assert.strictEqual(pointInPolygon([5, 15], square), false, 'Point below should be false');
});

test('pointInPolygon: concave L-shaped polygon', () => {
  const lShape = [
    [0, 0],
    [10, 0],
    [10, 5],
    [5, 5],
    [5, 10],
    [0, 10]
  ];
  assert.strictEqual(pointInPolygon([2, 2], lShape), true, 'Inside base');
  assert.strictEqual(pointInPolygon([2, 8], lShape), true, 'Inside stem');
  assert.strictEqual(pointInPolygon([8, 8], lShape), false, 'Inside the cutout area should be false');
});

// -------------------------------------------------------------
// getBottomCenterPoint tests
// -------------------------------------------------------------
console.log('\nTesting getBottomCenterPoint:');

test('getBottomCenterPoint: extracts feet anchor', () => {
  const box = { x: 100, y: 50, width: 100, height: 200 };
  const pt = getBottomCenterPoint(box);
  assertApprox(pt.x, 150, 1e-5, 'Center X should be 150');
  assertApprox(pt.y, 250, 1e-5, 'Bottom Y should be 250');
});

console.log(`\nAll ${testsRun} geometry tests passed successfully!`);
