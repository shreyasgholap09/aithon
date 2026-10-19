"""
Unit Tests for Safety Engine & Risk Assessment Policy
Covers:
- Zero violation baseline
- Missing helmet (+25)
- Missing vest (+20)
- Multi-hazard aggregation (+65)
- Danger zone penetration (+35)
- Fall detection (+50 with CRITICAL override)
- Score capping at 100
- Severity thresholds
- UNKNOWN PPE state handling
- Incident lifecycle state transitions
"""

import unittest
import os
import sys

# Add project root to sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from safety_engine.risk_engine import RiskEngine
from safety_engine.alert_manager import AlertManager
from safety_engine.ppe_rules import evaluate_ppe
from safety_engine.posture_rules import evaluate_posture
from safety_engine.fall_rules import evaluate_fall
from safety_engine.zone_rules import evaluate_zone

class TestRiskEngine(unittest.TestCase):
    def setUp(self):
        self.alert_manager = AlertManager(confirmation_frames=1, resolution_timeout=1.0)
        self.engine = RiskEngine(alert_manager=self.alert_manager)

    def test_zero_violations_baseline(self):
        event, new_inc, res_inc = self.engine.assess_worker(
            worker_id="W01",
            location="Assembly Line 1",
            ppe={"helmet": True, "vest": True},
            posture="SAFE",
            fall_input="NONE",
            danger_zone_input=False
        )
        self.assertEqual(event["risk_score"], 0)
        self.assertEqual(event["risk_level"], "SAFE")
        self.assertEqual(event["violations"], [])
        self.assertEqual(len(new_inc), 0)

    def test_missing_helmet_only(self):
        event, new_inc, _ = self.engine.assess_worker(
            worker_id="W02",
            location="Machine Zone A",
            ppe={"helmet": False, "vest": True}
        )
        self.assertEqual(event["risk_score"], 25)
        self.assertEqual(event["risk_level"], "LOW")
        self.assertIn("helmet_missing", event["violations"])
        self.assertEqual(len(new_inc), 1)
        self.assertEqual(new_inc[0]["violation"], "helmet_missing")

    def test_missing_vest_only(self):
        event, _, _ = self.engine.assess_worker(
            worker_id="W03",
            location="Loading Bay",
            ppe={"helmet": True, "vest": False}
        )
        self.assertEqual(event["risk_score"], 20)
        self.assertEqual(event["risk_level"], "LOW")
        self.assertIn("vest_missing", event["violations"])

    def test_danger_zone_entry(self):
        event, _, _ = self.engine.assess_worker(
            worker_id="W04",
            location="Robotic Cell",
            ppe={"helmet": True, "vest": True},
            danger_zone_input=True
        )
        self.assertEqual(event["risk_score"], 35)
        self.assertEqual(event["risk_level"], "MEDIUM")
        self.assertIn("danger_zone_entry", event["violations"])

    def test_unsafe_posture(self):
        event, _, _ = self.engine.assess_worker(
            worker_id="W05",
            location="Warehouse",
            ppe={"helmet": True, "vest": True},
            posture="UNSAFE",
            spine_angle=42.0
        )
        self.assertEqual(event["risk_score"], 20)
        self.assertIn("unsafe_posture", event["violations"])

    def test_fall_detection_critical_override(self):
        event, _, _ = self.engine.assess_worker(
            worker_id="W06",
            location="Ramp C",
            ppe={"helmet": True, "vest": True},
            fall_input="CONFIRMED_FALL"
        )
        self.assertEqual(event["risk_score"], 50)
        # Confirmed fall must ALWAYS trigger CRITICAL override regardless of numerical score!
        self.assertEqual(event["risk_level"], "CRITICAL")
        self.assertIn("fall_detected", event["violations"])

    def test_multi_hazard_aggregation_and_capping(self):
        # Missing helmet (+25), vest (+20), posture (+20), danger zone (+35), fall (+50) = 150 pts -> Capped at 100
        event, _, _ = self.engine.assess_worker(
            worker_id="W07",
            location="All Hazards Zone",
            ppe={"helmet": False, "vest": False},
            posture="UNSAFE",
            fall_input="CONFIRMED_FALL",
            danger_zone_input=True
        )
        self.assertEqual(event["risk_score"], 100)
        self.assertEqual(event["risk_level"], "CRITICAL")
        self.assertEqual(len(event["violations"]), 5)

    def test_unknown_ppe_state(self):
        # UNKNOWN should not count as compliant, nor should it falsely add penalties
        event, _, _ = self.engine.assess_worker(
            worker_id="W08",
            location="Dimly Lit Zone",
            ppe={"helmet": {"status": "UNKNOWN", "confidence": 0.2}, "vest": True}
        )
        self.assertEqual(event["risk_score"], 0)
        self.assertEqual(event["risk_level"], "SAFE")
        self.assertNotIn("helmet_missing", event["violations"])
        self.assertEqual(event["ppe"]["helmet"]["status"], "UNKNOWN")

    def test_incident_lifecycle_and_resolution(self):
        # Step 1: Detect violation
        _, new_inc_1, _ = self.engine.assess_worker("W09", "Zone B", {"helmet": False, "vest": True})
        self.assertEqual(len(new_inc_1), 1)

        # Step 2: Continuous next frame with same violation -> should NOT create duplicate incident
        _, new_inc_2, _ = self.engine.assess_worker("W09", "Zone B", {"helmet": False, "vest": True})
        self.assertEqual(len(new_inc_2), 0)

        # Step 3: Violation clears
        import time
        time.sleep(1.1)  # wait for resolution timeout
        _, _, res_inc = self.engine.assess_worker("W09", "Zone B", {"helmet": True, "vest": True})
        self.assertEqual(len(res_inc), 1)
        self.assertEqual(res_inc[0]["lifecycle_state"], "RESOLVED")

    def test_simultaneous_violations_distinct_stable_incident_ids(self):
        """One worker with multiple simultaneous violations gets distinct stable incident IDs."""
        event, new_inc, _ = self.engine.assess_worker(
            worker_id="W10",
            location="Zone C",
            ppe={"helmet": False, "vest": False},
            posture="UNSAFE"
        )
        self.assertEqual(len(new_inc), 3)
        ids = [inc["incident_id"] for inc in new_inc]
        # All IDs must be distinct
        self.assertEqual(len(set(ids)), 3)
        for inc_id in ids:
            self.assertTrue(inc_id.startswith("inc-W10-"))

        # Subsequent frame with same violations must preserve identical incident IDs
        event2, new_inc2, _ = self.engine.assess_worker(
            worker_id="W10",
            location="Zone C",
            ppe={"helmet": False, "vest": False},
            posture="UNSAFE"
        )
        self.assertEqual(len(new_inc2), 0, "No duplicate incidents on continuous frames")
        active_ids = [inc["incident_id"] for inc in event2["active_incidents"]]
        self.assertEqual(sorted(ids), sorted(active_ids))

    def test_clearing_one_violation_preserves_other_active_violation(self):
        """Clearing one violation resolves it while leaving other simultaneous violations active."""
        # Frame 1: Helmet missing + Vest missing
        self.engine.assess_worker("W11", "Zone D", {"helmet": False, "vest": False})
        
        # Frame 2: Helmet put on (PRESENT), vest still MISSING
        import time
        time.sleep(1.1)
        event, _, res_inc = self.engine.assess_worker("W11", "Zone D", {"helmet": True, "vest": False})
        
        # Helmet is resolved
        self.assertEqual(len(res_inc), 1)
        self.assertEqual(res_inc[0]["violation"], "helmet_missing")
        self.assertEqual(res_inc[0]["lifecycle_state"], "RESOLVED")

        # Vest remains active
        self.assertIn("vest_missing", event["violations"])
        self.assertEqual(len(event["active_incidents"]), 1)
        self.assertEqual(event["active_incidents"][0]["violation"], "vest_missing")
        self.assertEqual(event["active_incidents"][0]["lifecycle_state"], "ACTIVE")

    def test_recurring_violation_gets_new_incident_id(self):
        """A violation that resolves and recurs later receives a new incident ID."""
        import time
        # 1. First occurrence
        _, new_inc1, _ = self.engine.assess_worker("W12", "Zone E", {"helmet": False, "vest": True})
        self.assertEqual(len(new_inc1), 1)
        id_1 = new_inc1[0]["incident_id"]

        # 2. Cleared & Resolved
        time.sleep(1.1)
        self.engine.assess_worker("W12", "Zone E", {"helmet": True, "vest": True})

        # 3. Recurrence later
        time.sleep(0.1)
        _, new_inc2, _ = self.engine.assess_worker("W12", "Zone E", {"helmet": False, "vest": True})
        self.assertEqual(len(new_inc2), 1)
        id_2 = new_inc2[0]["incident_id"]

        self.assertNotEqual(id_1, id_2, "Recurring violation must receive a new distinct incident ID")

    def test_worker_disappearance_transitions_to_not_observed(self):
        """Disappearing worker transitions active incident to NOT_OBSERVED, never falsely RESOLVED."""
        import time
        # Worker detected with missing helmet
        _, new_inc, _ = self.engine.assess_worker("W13", "Zone F", {"helmet": False, "vest": True})
        self.assertEqual(len(new_inc), 1)
        orig_id = new_inc[0]["incident_id"]

        # Worker disappears for longer than disappearance_timeout (3.0s)
        stale_incidents = self.alert_manager.handle_disappeared_workers(
            active_worker_ids=set(),
            current_time=time.time() + 4.0
        )
        self.assertEqual(len(stale_incidents), 1)
        self.assertEqual(stale_incidents[0]["incident_id"], orig_id)
        self.assertEqual(stale_incidents[0]["lifecycle_state"], "NOT_OBSERVED")
        self.assertNotEqual(stale_incidents[0]["lifecycle_state"], "RESOLVED")

    def test_stale_incident_reactivates_when_worker_returns(self):
        """When a disappeared worker returns with the same violation, incident reactivates without duplicate ID."""
        import time
        _, new_inc, _ = self.engine.assess_worker("W14", "Zone G", {"helmet": False, "vest": True})
        orig_id = new_inc[0]["incident_id"]

        # Disappear -> NOT_OBSERVED
        self.alert_manager.handle_disappeared_workers(set(), current_time=time.time() + 4.0)

        # Worker returns
        event, new_inc_after, _ = self.engine.assess_worker("W14", "Zone G", {"helmet": False, "vest": True})
        # Should NOT emit a new incident creation
        self.assertEqual(len(new_inc_after), 0)
        # Active incident must have same original ID and be ACTIVE
        self.assertEqual(len(event["active_incidents"]), 1)
        self.assertEqual(event["active_incidents"][0]["incident_id"], orig_id)
        self.assertEqual(event["active_incidents"][0]["lifecycle_state"], "ACTIVE")

    def test_one_worker_disappears_while_another_remains(self):
        """Worker disappearance is isolated per-worker."""
        import time
        self.engine.assess_worker("W15_A", "Zone H", {"helmet": False, "vest": True})
        self.engine.assess_worker("W15_B", "Zone H", {"helmet": True, "vest": False})

        # W15_A disappears, W15_B remains active
        stale = self.alert_manager.handle_disappeared_workers(
            active_worker_ids={"W15_B"},
            current_time=time.time() + 4.0
        )
        self.assertEqual(len(stale), 1)
        self.assertEqual(stale[0]["worker_id"], "W15_A")
        self.assertEqual(stale[0]["lifecycle_state"], "NOT_OBSERVED")

        # W15_B's incident is still ACTIVE
        self.assertEqual(self.alert_manager.active_incidents[("W15_B", "vest_missing")].lifecycle_state, "ACTIVE")

if __name__ == "__main__":
    unittest.main()
