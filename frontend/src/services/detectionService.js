/**
 * Detection Service & Demo Scenario Registry
 * Manages demo scenario templates and explicit mode switches.
 * Every demo scenario is labeled source: "SIMULATED".
 */

export const DEMO_SCENARIOS = [
  {
    id: 'SCENARIO_1',
    name: '1. Compliant Baseline',
    description: 'Worker fully compliant with helmet, vest, and upright spine',
    badge: 'SAFE',
    event: {
      schema_version: '1.0',
      event_id: 'sim-w01-compliant',
      source: 'SIMULATED',
      lifecycle_state: 'CLEAR',
      worker_id: 'W01',
      location: 'Assembly Line 1',
      ppe: {
        helmet: { status: 'PRESENT', confidence: 0.96 },
        vest: { status: 'PRESENT', confidence: 0.95 }
      },
      posture: 'SAFE',
      fall_status: 'NONE',
      danger_zone: { entered: false, zone_id: 'ZONE_1', zone_name: 'Assembly Perimeter' },
      violations: [],
      risk_score: 0,
      risk_level: 'SAFE',
      confidence: 0.96,
      details: 'Full PPE compliance verified. Normal ergonomic posture.'
    }
  },
  {
    id: 'SCENARIO_2',
    name: '2. Missing Hardhat Violation',
    description: 'Worker detected in machine zone without mandatory hardhat',
    badge: 'LOW RISK',
    event: {
      schema_version: '1.0',
      event_id: 'sim-w02-missing-helmet',
      source: 'SIMULATED',
      lifecycle_state: 'ACTIVE',
      worker_id: 'W02',
      location: 'Machine Zone A',
      ppe: {
        helmet: { status: 'MISSING', confidence: 0.92 },
        vest: { status: 'PRESENT', confidence: 0.95 }
      },
      posture: 'SAFE',
      fall_status: 'NONE',
      danger_zone: { entered: false, zone_id: 'ZONE_A', zone_name: 'Machine Zone A' },
      violations: ['helmet_missing'],
      risk_score: 25,
      risk_level: 'LOW',
      confidence: 0.93,
      details: 'Missing protective hardhat detected in mandatory head-protection zone.'
    }
  },
  {
    id: 'SCENARIO_3',
    name: '3. Danger-Zone Intrusion',
    description: 'Worker breaches automated robotic cell perimeter',
    badge: 'MEDIUM RISK',
    event: {
      schema_version: '1.0',
      event_id: 'sim-w03-danger-zone',
      source: 'SIMULATED',
      lifecycle_state: 'ACTIVE',
      worker_id: 'W03',
      location: 'Robotic Cell 4 Perimeter',
      ppe: {
        helmet: { status: 'PRESENT', confidence: 0.94 },
        vest: { status: 'PRESENT', confidence: 0.92 }
      },
      posture: 'SAFE',
      fall_status: 'NONE',
      danger_zone: { entered: true, zone_id: 'ZONE_ROBOT_CELL_4', zone_name: 'Robotic Cell 4 Perimeter' },
      violations: ['danger_zone_entry'],
      risk_score: 35,
      risk_level: 'MEDIUM',
      confidence: 0.94,
      details: 'Unauthorized perimeter entry: Worker penetrated robotic hazard boundary.'
    }
  },
  {
    id: 'SCENARIO_4',
    name: '4. Fall Emergency Alert',
    description: 'Prostrate worker on floor triggers immediate critical alert',
    badge: 'CRITICAL',
    event: {
      schema_version: '1.0',
      event_id: 'sim-w04-fall-critical',
      source: 'SIMULATED',
      lifecycle_state: 'ACTIVE',
      worker_id: 'W04',
      location: 'Loading Bay Ramp C',
      bbox: [0.16, 0.65, 0.60, 0.22],
      spine_angle: 84.0,
      ppe: {
        helmet: { status: 'PRESENT', confidence: 0.91 },
        vest: { status: 'PRESENT', confidence: 0.90 }
      },
      posture: 'HIGH_RISK',
      fall_status: 'CONFIRMED_FALL',
      danger_zone: { entered: false, zone_id: 'RAMP_C', zone_name: 'Loading Bay' },
      violations: ['fall_detected'],
      risk_score: 50,
      risk_level: 'CRITICAL',
      confidence: 0.98,
      details: 'CRITICAL EMERGENCY: Confirmed worker fall detected! Worker prostrate at 84° spine angle.'
    }
  },
  {
    id: 'SCENARIO_5',
    name: '5. Ergonomic Strain & Missing Vest',
    description: 'Acute spine bend (>40°) combined with missing hi-vis vest',
    badge: 'HIGH RISK',
    event: {
      schema_version: '1.0',
      event_id: 'sim-w05-multi-hazard',
      source: 'SIMULATED',
      lifecycle_state: 'ACTIVE',
      worker_id: 'W05',
      location: 'Warehouse High-Rack 3',
      ppe: {
        helmet: { status: 'MISSING', confidence: 0.88 },
        vest: { status: 'MISSING', confidence: 0.89 }
      },
      posture: 'UNSAFE',
      fall_status: 'NONE',
      danger_zone: { entered: false, zone_id: 'RACK_3', zone_name: 'Warehouse High-Rack' },
      violations: ['helmet_missing', 'vest_missing', 'unsafe_posture'],
      risk_score: 65,
      risk_level: 'HIGH',
      confidence: 0.91,
      details: 'Multiple violations: Missing hardhat, missing vest, and acute spine bend (>40°).'
    }
  }
];

export function createSimulatedEvent(scenarioId) {
  const match = DEMO_SCENARIOS.find(s => s.id === scenarioId);
  if (!match) return null;
  return {
    ...match.event,
    timestamp: new Date().toISOString(),
    event_id: `sim-${scenarioId.toLowerCase()}-${Date.now()}`
  };
}
