"""
src/controller/decision_engine.py
Adaptive concurrency control decision engine.

This is the core of the proposed research framework. It takes predictions
from the ML models and decides whether to switch the active concurrency
control protocol.

Three strategies are implemented for comparison:
  1. StaticController      — never switches (baseline).
  2. ReactiveController    — switches based on current measurements.
  3. PredictiveController  — switches based on ML predictions + cost awareness.

All controllers share a common interface and log every decision for analysis.
"""

import numpy as np
import pandas as pd
from datetime import datetime
from typing import Optional
import yaml
from pathlib import Path

from src.controller.switching_cost import SwitchingCostEstimator


class ControllerDecision:
    """Represents a single controller decision."""

    def __init__(
        self,
        timestamp: datetime,
        current_protocol: str,
        recommended_protocol: str,
        action: str,  # 'maintain' or 'switch'
        reason: str,
        confidence: float,
        predicted_contention: Optional[float] = None,
        predicted_network_rtt: Optional[float] = None,
        switching_cost_ms: float = 0.0,
        controller_type: str = "unknown",
    ):
        self.timestamp = timestamp
        self.current_protocol = current_protocol
        self.recommended_protocol = recommended_protocol
        self.action = action
        self.reason = reason
        self.confidence = confidence
        self.predicted_contention = predicted_contention
        self.predicted_network_rtt = predicted_network_rtt
        self.switching_cost_ms = switching_cost_ms
        self.controller_type = controller_type

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp.isoformat() if isinstance(
                self.timestamp, datetime) else str(self.timestamp),
            "current_protocol": self.current_protocol,
            "recommended_protocol": self.recommended_protocol,
            "action": self.action,
            "reason": self.reason,
            "confidence": self.confidence,
            "predicted_contention": self.predicted_contention,
            "predicted_network_rtt": self.predicted_network_rtt,
            "switching_cost_ms": self.switching_cost_ms,
            "controller_type": self.controller_type,
        }


class BaseController:
    """Base class for all controllers."""

    SUPPORTED_PROTOCOLS = ["OCC", "2PL", "MVCC"]

    def __init__(self, config_path: Optional[str] = "config.yaml"):
        self.config = {}
        if config_path and Path(config_path).exists():
            with open(config_path, "r") as f:
                self.config = yaml.safe_load(f)

        self.ctrl_cfg = self.config.get("controller", {})
        self.cost_estimator = SwitchingCostEstimator(config_path)
        self.decision_log: list[ControllerDecision] = []
        self.last_switch_time: Optional[datetime] = None
        self.min_switch_interval = self.ctrl_cfg.get(
            "min_switch_interval_sec", 30)

    def _can_switch(self, current_time: datetime) -> bool:
        """Check if enough time has passed since the last switch (hysteresis)."""
        if self.last_switch_time is None:
            return True
        elapsed = (current_time - self.last_switch_time).total_seconds()
        return elapsed >= self.min_switch_interval

    def _log_decision(self, decision: ControllerDecision):
        """Record a decision."""
        self.decision_log.append(decision)
        if decision.action == "switch":
            self.last_switch_time = decision.timestamp

    def get_decision_log_df(self) -> pd.DataFrame:
        """Return the decision log as a DataFrame."""
        if not self.decision_log:
            return pd.DataFrame()
        return pd.DataFrame([d.to_dict() for d in self.decision_log])

    def decide(self, **kwargs) -> ControllerDecision:
        raise NotImplementedError


class StaticController(BaseController):
    """Baseline: always keeps the initial protocol.

    This represents the traditional approach where a DBA selects a
    concurrency control protocol at deployment and never changes it.
    """

    def __init__(self, fixed_protocol: str = "MVCC",
                 config_path: Optional[str] = "config.yaml"):
        super().__init__(config_path)
        self.fixed_protocol = fixed_protocol

    def decide(
        self,
        current_protocol: str,
        current_time: Optional[datetime] = None,
        **kwargs,
    ) -> ControllerDecision:
        """Always maintain the fixed protocol."""
        if current_time is None:
            current_time = datetime.now()

        decision = ControllerDecision(
            timestamp=current_time,
            current_protocol=current_protocol,
            recommended_protocol=self.fixed_protocol,
            action="maintain",
            reason=f"Static controller: always use {self.fixed_protocol}.",
            confidence=1.0,
            controller_type="static",
        )
        self._log_decision(decision)
        return decision


class ReactiveController(BaseController):
    """Reactive controller: switches based on CURRENT measurements.

    Uses simple threshold rules:
    - High contention + normal network → prefer 2PL or MVCC.
    - Low contention + normal network → prefer OCC.
    - Any contention + degraded network → prefer MVCC (less sensitive to RTT).
    """

    def decide(
        self,
        current_protocol: str,
        current_contention: float,
        current_network_rtt: float,
        current_time: Optional[datetime] = None,
        **kwargs,
    ) -> ControllerDecision:
        if current_time is None:
            current_time = datetime.now()

        thresholds = self.ctrl_cfg.get("thresholds", {})
        high_contention_thresh = thresholds.get("high_contention", 0.20)
        low_contention_thresh = thresholds.get("low_contention", 0.05)
        high_rtt_thresh = thresholds.get("high_network_rtt", 50.0)

        # Determine recommended protocol
        is_high_contention = current_contention > high_contention_thresh
        is_high_rtt = current_network_rtt > high_rtt_thresh

        if is_high_rtt:
            recommended = "MVCC"
            reason = (f"High network RTT ({current_network_rtt:.1f} ms "
                      f"> {high_rtt_thresh} ms) → MVCC preferred.")
        elif is_high_contention:
            recommended = "2PL"
            reason = (f"High contention ({current_contention:.3f} "
                      f"> {high_contention_thresh}) → 2PL preferred.")
        else:
            recommended = "OCC"
            reason = (f"Low contention ({current_contention:.3f}), "
                      f"normal network ({current_network_rtt:.1f} ms) → OCC.")

        # Check if switch is allowed (hysteresis)
        if recommended != current_protocol and self._can_switch(current_time):
            cost = self.cost_estimator.get_cost(current_protocol, recommended)
            action = "switch"
            reason += f" Switching cost: {cost:.0f} ms."
        elif recommended != current_protocol:
            action = "maintain"
            reason += " Switch blocked by hysteresis interval."
            cost = 0.0
        else:
            action = "maintain"
            cost = 0.0

        decision = ControllerDecision(
            timestamp=current_time,
            current_protocol=current_protocol,
            recommended_protocol=recommended,
            action=action,
            reason=reason,
            confidence=0.7,  # reactive decisions have moderate confidence
            predicted_contention=current_contention,
            predicted_network_rtt=current_network_rtt,
            switching_cost_ms=cost if action == "switch" else 0.0,
            controller_type="reactive",
        )
        self._log_decision(decision)
        return decision


class PredictiveController(BaseController):
    """Proposed predictive controller with switching-cost optimization.

    Uses ML predictions of FUTURE contention and network conditions to
    make proactive protocol selection decisions.

    Key features:
    - Uses predicted (future) values, not current measurements.
    - Accounts for switching cost before recommending a change.
    - Requires a minimum predicted improvement to justify switching.
    - Hysteresis prevents rapid oscillation.
    - Handles missing/unreliable predictions gracefully.
    """

    def __init__(self, config_path: Optional[str] = "config.yaml"):
        super().__init__(config_path)
        self.improvement_threshold = self.ctrl_cfg.get(
            "improvement_threshold", 0.10)

        # Protocol suitability scores from config
        self.suitability = self.ctrl_cfg.get("protocol_suitability", {})

    def _get_suitability_score(
        self, protocol: str, contention_level: str, network_level: str
    ) -> float:
        """Look up the suitability score for a protocol under given conditions."""
        key = f"{contention_level}_contention_{network_level}_network"
        proto_scores = self.suitability.get(protocol, {})
        return proto_scores.get(key, 0.5)

    def _select_best_protocol(
        self,
        predicted_contention: float,
        predicted_network_rtt: float,
        current_protocol: str,
    ) -> tuple[str, float, str]:
        """Select the best protocol based on predictions and costs.

        Returns
        -------
        (recommended_protocol, confidence, reason)
        """
        thresholds = self.ctrl_cfg.get("thresholds", {})
        high_contention_thresh = thresholds.get("high_contention", 0.20)
        high_rtt_thresh = thresholds.get("high_network_rtt", 50.0)

        # Categorize predicted conditions
        contention_level = ("high" if predicted_contention > high_contention_thresh
                           else "low")
        network_level = ("degraded" if predicted_network_rtt > high_rtt_thresh
                        else "normal")

        # Score each protocol
        scores = {}
        for protocol in self.SUPPORTED_PROTOCOLS:
            base_score = self._get_suitability_score(
                protocol, contention_level, network_level)

            # Penalty for switching cost
            if protocol != current_protocol:
                cost = self.cost_estimator.get_cost(current_protocol, protocol)
                # Normalize cost penalty (higher cost = lower score)
                cost_penalty = min(cost / 1000.0, 0.3)  # cap at 0.3
                scores[protocol] = base_score - cost_penalty
            else:
                # Bonus for staying (no switching cost)
                scores[protocol] = base_score + 0.05

            scores[protocol] = max(0.0, min(1.0, scores[protocol]))

        # Select best
        best = max(scores, key=scores.get)
        confidence = scores[best]

        reason_parts = [
            f"Predicted contention={predicted_contention:.3f} "
            f"({contention_level}), "
            f"network RTT={predicted_network_rtt:.1f} ms ({network_level}).",
        ]
        reason_parts.append(
            f"Scores: {', '.join(f'{p}={s:.3f}' for p, s in scores.items())}."
        )

        # Check improvement threshold
        if best != current_protocol:
            improvement = scores[best] - scores[current_protocol]
            if improvement < self.improvement_threshold:
                best = current_protocol
                reason_parts.append(
                    f"Improvement ({improvement:.3f}) below threshold "
                    f"({self.improvement_threshold}). Maintaining {current_protocol}."
                )

        return best, confidence, " ".join(reason_parts)

    def decide(
        self,
        current_protocol: str,
        predicted_contention: Optional[float] = None,
        predicted_network_rtt: Optional[float] = None,
        current_contention: Optional[float] = None,
        current_network_rtt: Optional[float] = None,
        current_time: Optional[datetime] = None,
        **kwargs,
    ) -> ControllerDecision:
        """Make a predictive protocol selection decision.

        Parameters
        ----------
        current_protocol : str
        predicted_contention : float, optional
            ML-predicted future contention. Falls back to current if None.
        predicted_network_rtt : float, optional
            ML-predicted future RTT. Falls back to current if None.
        current_contention : float, optional
            Current measured contention (fallback).
        current_network_rtt : float, optional
            Current measured RTT (fallback).
        current_time : datetime, optional

        Returns
        -------
        ControllerDecision
        """
        if current_time is None:
            current_time = datetime.now()

        # Handle missing predictions gracefully
        use_contention = predicted_contention
        use_network = predicted_network_rtt
        fallback_used = False

        if use_contention is None:
            use_contention = current_contention if current_contention is not None else 0.1
            fallback_used = True
        if use_network is None:
            use_network = current_network_rtt if current_network_rtt is not None else 5.0
            fallback_used = True

        # Validate prediction values (sanity check)
        if use_contention < 0 or use_contention > 1:
            use_contention = np.clip(use_contention, 0, 1)
        if use_network < 0:
            use_network = max(use_network, 0.1)

        recommended, confidence, reason = self._select_best_protocol(
            use_contention, use_network, current_protocol
        )

        if fallback_used:
            reason = "[FALLBACK: using current values] " + reason
            confidence *= 0.7  # reduce confidence when using fallback

        # Hysteresis check
        if recommended != current_protocol:
            if not self._can_switch(current_time):
                action = "maintain"
                cost = 0.0
                reason += " Switch blocked by hysteresis."
            else:
                action = "switch"
                cost = self.cost_estimator.get_cost(
                    current_protocol, recommended)
                reason += f" Switching cost: {cost:.0f} ms."
        else:
            action = "maintain"
            cost = 0.0

        decision = ControllerDecision(
            timestamp=current_time,
            current_protocol=current_protocol,
            recommended_protocol=recommended,
            action=action,
            reason=reason,
            confidence=confidence,
            predicted_contention=use_contention,
            predicted_network_rtt=use_network,
            switching_cost_ms=cost if action == "switch" else 0.0,
            controller_type="predictive",
        )
        self._log_decision(decision)
        return decision

