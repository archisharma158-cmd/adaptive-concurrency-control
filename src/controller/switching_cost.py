"""
src/controller/switching_cost.py
Switching cost estimation for concurrency control protocol transitions.

In real distributed databases, switching between concurrency control
protocols is NOT trivial. This module models the costs and safety
constraints of protocol transitions.

IMPORTANT SAFETY NOTE:
Protocol switching in a live database requires:
  1. Draining in-flight transactions under the old protocol.
  2. Ensuring no locks/validations are left in an inconsistent state.
  3. Waiting for a quiescent point or using a phased transition.
  4. Starting new transactions under the new protocol.
  5. Verifying correctness after the switch.

This module provides cost ESTIMATES. Production-safe switching has NOT
been demonstrated and would require formal verification or extensive
testing with a specific database's internals.
"""

from typing import Optional
import yaml
from pathlib import Path


# Default switching costs in milliseconds of throughput disruption.
# These are research estimates — actual costs depend on the database,
# workload, and number of in-flight transactions.
DEFAULT_SWITCHING_COSTS = {
    ("OCC", "2PL"): 500,
    ("OCC", "MVCC"): 300,
    ("2PL", "OCC"): 500,
    ("2PL", "MVCC"): 400,
    ("MVCC", "OCC"): 300,
    ("MVCC", "2PL"): 400,
    # Same protocol → 0 cost
    ("OCC", "OCC"): 0,
    ("2PL", "2PL"): 0,
    ("MVCC", "MVCC"): 0,
}


class SwitchingCostEstimator:
    """Estimates the cost of switching between CC protocols.

    Parameters
    ----------
    config_path : str, optional
        Path to config.yaml for custom cost values.
    """

    def __init__(self, config_path: Optional[str] = None):
        self.costs = dict(DEFAULT_SWITCHING_COSTS)

        if config_path and Path(config_path).exists():
            with open(config_path, "r") as f:
                config = yaml.safe_load(f)
            ctrl_cfg = config.get("controller", {})
            custom_costs = ctrl_cfg.get("switching_costs", {})
            for key, value in custom_costs.items():
                parts = key.split("_to_")
                if len(parts) == 2:
                    self.costs[(parts[0], parts[1])] = value

    def get_cost(self, from_protocol: str, to_protocol: str) -> float:
        """Get the estimated switching cost in milliseconds.

        Parameters
        ----------
        from_protocol : str
            Current protocol (e.g. 'OCC').
        to_protocol : str
            Target protocol (e.g. '2PL').

        Returns
        -------
        float
            Estimated cost in ms.
        """
        if from_protocol == to_protocol:
            return 0.0
        return float(self.costs.get(
            (from_protocol, to_protocol),
            500.0  # conservative default for unknown transitions
        ))

    def is_switch_worthwhile(
        self,
        from_protocol: str,
        to_protocol: str,
        predicted_improvement_ms: float,
        measurement_window_sec: float = 60.0,
    ) -> bool:
        """Determine if a switch is worth the cost.

        A switch is worthwhile if the predicted latency improvement
        over the measurement window exceeds the one-time switching cost.

        Parameters
        ----------
        from_protocol : str
        to_protocol : str
        predicted_improvement_ms : float
            Expected per-transaction latency improvement in ms.
        measurement_window_sec : float
            Time window to amortize the switching cost over.

        Returns
        -------
        bool
        """
        if from_protocol == to_protocol:
            return False

        cost = self.get_cost(from_protocol, to_protocol)
        # Switching cost is amortized over the measurement window
        # The improvement should exceed the amortized cost
        return predicted_improvement_ms > (cost / measurement_window_sec)

    def get_transition_requirements(
        self, from_protocol: str, to_protocol: str
    ) -> dict:
        """Document what a protocol transition requires.

        This is informational — it describes what WOULD need to happen
        in a real database. It does not implement the transition.

        Returns
        -------
        dict with transition steps and safety notes.
        """
        transitions = {
            ("OCC", "2PL"): {
                "steps": [
                    "1. Wait for all in-flight OCC transactions to commit or abort.",
                    "2. OCC validation checks must complete.",
                    "3. Acquire locks for the 2PL protocol.",
                    "4. Start new transactions under 2PL.",
                ],
                "safety": (
                    "OCC transactions in the validation phase may conflict with "
                    "new 2PL lock acquisitions. A quiescent point is recommended."
                ),
                "estimated_duration_ms": 500,
            },
            ("OCC", "MVCC"): {
                "steps": [
                    "1. Wait for in-flight OCC validations to complete.",
                    "2. Initialize MVCC version chains.",
                    "3. Start new transactions under MVCC.",
                ],
                "safety": (
                    "MVCC is generally compatible with OCC during transition "
                    "since both are optimistic. Transition is smoother."
                ),
                "estimated_duration_ms": 300,
            },
            ("2PL", "OCC"): {
                "steps": [
                    "1. Wait for all 2PL transactions to release locks.",
                    "2. Clear the lock table.",
                    "3. Initialize OCC validation structures.",
                    "4. Start new transactions under OCC.",
                ],
                "safety": (
                    "Long-held 2PL locks can delay the transition. Deadlock "
                    "detection should be active during drain."
                ),
                "estimated_duration_ms": 500,
            },
            ("2PL", "MVCC"): {
                "steps": [
                    "1. Drain 2PL lock queue.",
                    "2. Release all locks.",
                    "3. Initialize MVCC version chains.",
                    "4. Start new transactions under MVCC.",
                ],
                "safety": (
                    "Lock-to-MVCC transition requires careful handling of "
                    "transactions that held exclusive locks."
                ),
                "estimated_duration_ms": 400,
            },
            ("MVCC", "OCC"): {
                "steps": [
                    "1. Wait for active MVCC reads to complete.",
                    "2. Garbage-collect old versions.",
                    "3. Initialize OCC write sets.",
                    "4. Start new transactions under OCC.",
                ],
                "safety": (
                    "MVCC snapshot isolation must be maintained for in-flight "
                    "reads during the transition."
                ),
                "estimated_duration_ms": 300,
            },
            ("MVCC", "2PL"): {
                "steps": [
                    "1. Wait for active MVCC transactions to complete.",
                    "2. Initialize 2PL lock table.",
                    "3. Start new transactions under 2PL.",
                ],
                "safety": (
                    "MVCC to 2PL is the most disruptive transition. Version "
                    "chains and lock tables are fundamentally different."
                ),
                "estimated_duration_ms": 400,
            },
        }

        if from_protocol == to_protocol:
            return {
                "steps": ["No transition needed."],
                "safety": "Same protocol.",
                "estimated_duration_ms": 0,
            }

        return transitions.get(
            (from_protocol, to_protocol),
            {
                "steps": ["Unknown transition — needs investigation."],
                "safety": "Unknown risks.",
                "estimated_duration_ms": 500,
            },
        )

