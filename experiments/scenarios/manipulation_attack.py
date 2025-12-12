"""
Manipulation Attack Scenario - Coordinated market manipulation attack.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import numpy as np

from .base_scenario import BaseScenario, ScenarioConfig, ScenarioState


class AttackPhase(Enum):
    """Phases of a manipulation attack."""
    RECONNAISSANCE = "reconnaissance"
    ACCUMULATION = "accumulation"
    MANIPULATION = "manipulation"
    EXIT = "exit"
    COMPLETE = "complete"


@dataclass
class AttackConfig:
    """Configuration for the attack."""
    num_attackers: int = 10
    capital_tokens: float = 10000.0
    coordination: str = "centralized"
    target_price_change: float = 0.3
    strategies: list = field(default_factory=lambda: ["spoofing", "wash_trading"])


class ManipulationAttackScenario(BaseScenario):
    """
    Scenario with coordinated market manipulation attack.

    Features:
    - Multi-phase attack pattern
    - Multiple attack strategies
    - Coordinated attacker behavior
    - Market resilience testing
    """

    def __init__(
        self,
        base_demand_kwh: float = 1000.0,
        attack_config: Optional[AttackConfig] = None,
        recon_hours: float = 2.0,
        accumulation_hours: float = 3.0,
        manipulation_hours: float = 2.0,
        exit_hours: float = 1.0,
        duration_hours: int = 12,
    ):
        """
        Initialize manipulation attack scenario.

        Args:
            base_demand_kwh: Base demand level
            attack_config: Attack configuration
            recon_hours: Duration of reconnaissance phase
            accumulation_hours: Duration of accumulation phase
            manipulation_hours: Duration of manipulation phase
            exit_hours: Duration of exit phase
            duration_hours: Total scenario duration
        """
        config = ScenarioConfig(
            name="manipulation_attack",
            description="Coordinated market manipulation attack for resilience testing",
            duration_hours=duration_hours,
            base_demand_kwh=base_demand_kwh,
            volatility=0.1,
            warmup_periods=10,
        )
        super().__init__(config)

        self.attack_config = attack_config or AttackConfig()
        self.recon_hours = recon_hours
        self.accumulation_hours = accumulation_hours
        self.manipulation_hours = manipulation_hours
        self.exit_hours = exit_hours

        # Phase boundaries (in periods, assuming 60 periods/hour)
        self._periods_per_hour = 60
        self._phase_starts = self._calculate_phase_starts()

        # Attack state
        self._current_phase = AttackPhase.RECONNAISSANCE
        self._attack_position = 0.0
        self._artificial_price_impact = 0.0
        self._fake_volume = 0.0

    def _calculate_phase_starts(self) -> dict:
        """Calculate when each phase starts."""
        recon_end = self.recon_hours * self._periods_per_hour
        accum_end = recon_end + self.accumulation_hours * self._periods_per_hour
        manip_end = accum_end + self.manipulation_hours * self._periods_per_hour
        exit_end = manip_end + self.exit_hours * self._periods_per_hour

        return {
            AttackPhase.RECONNAISSANCE: (0, recon_end),
            AttackPhase.ACCUMULATION: (recon_end, accum_end),
            AttackPhase.MANIPULATION: (accum_end, manip_end),
            AttackPhase.EXIT: (manip_end, exit_end),
            AttackPhase.COMPLETE: (exit_end, float("inf")),
        }

    def _update_phase(self, period: int) -> None:
        """Update the current attack phase."""
        for phase, (start, end) in self._phase_starts.items():
            if start <= period < end:
                self._current_phase = phase
                break

    def get_demand(self, period: int) -> float:
        """
        Get demand during attack.

        During manipulation phase, attackers may inflate apparent demand.
        """
        self._update_phase(period)
        hour = period % 24

        # Base diurnal pattern
        phase = 2 * np.pi * (hour - 15) / 24
        base_pattern = 0.6 + 0.8 * (0.5 * (1 - np.cos(phase)))

        # Attack effects
        if self._current_phase == AttackPhase.MANIPULATION:
            # Attackers create artificial demand signals
            fake_demand = 0.2 * np.sin(period * 0.1)  # Oscillating fake demand
            pattern_factor = base_pattern + fake_demand
        else:
            pattern_factor = base_pattern

        # Normal noise
        noise = 1 + self._random_state.normal(0, self.config.volatility)

        demand = self.config.base_demand_kwh * pattern_factor * max(0.5, noise)

        self.state.demand_level = pattern_factor
        return demand

    def get_supply(self, period: int) -> float:
        """Get supply during attack scenario."""
        # Supply is mostly normal
        base_supply = self.config.base_demand_kwh

        hour = period % 24
        # Slight variation
        if 6 <= hour <= 18:
            solar_bonus = 0.15 * np.sin(np.pi * (hour - 6) / 12)
            supply_factor = 1.0 + solar_bonus
        else:
            supply_factor = 0.95

        noise = 1 + self._random_state.normal(0, 0.05)

        self.state.supply_level = supply_factor
        return base_supply * supply_factor * noise

    def get_attack_instructions(self, period: int) -> dict:
        """
        Get instructions for adversarial agents.

        Returns strategy and intensity for the current phase.
        """
        self._update_phase(period)

        if self._current_phase == AttackPhase.RECONNAISSANCE:
            return {
                "activity": "passive_observation",
                "intensity": 0.0,
                "strategies": [],
                "target_position": 0.0,
            }

        elif self._current_phase == AttackPhase.ACCUMULATION:
            # Gradually build position
            progress = self._get_phase_progress(period, AttackPhase.ACCUMULATION)
            target = self.attack_config.capital_tokens * 0.3 * progress

            return {
                "activity": "gradual_position_building",
                "intensity": 0.3,
                "strategies": [],
                "target_position": target,
                "bid_aggressiveness": 0.95,  # Slightly below market
            }

        elif self._current_phase == AttackPhase.MANIPULATION:
            return {
                "activity": "price_manipulation",
                "intensity": 1.0,
                "strategies": self.attack_config.strategies,
                "target_price_change": self.attack_config.target_price_change,
                "spoofing_intensity": 0.8,
                "wash_trading_volume": self.attack_config.capital_tokens * 0.1,
            }

        elif self._current_phase == AttackPhase.EXIT:
            progress = self._get_phase_progress(period, AttackPhase.EXIT)
            return {
                "activity": "position_liquidation",
                "intensity": 0.7,
                "strategies": [],
                "sell_urgency": 0.5 + 0.5 * progress,
            }

        return {"activity": "none", "intensity": 0.0}

    def _get_phase_progress(self, period: int, phase: AttackPhase) -> float:
        """Get progress through a phase (0 to 1)."""
        start, end = self._phase_starts[phase]
        if period < start:
            return 0.0
        if period >= end:
            return 1.0
        return (period - start) / (end - start)

    def get_price_factors(self, period: int) -> dict:
        """Get price factors during attack."""
        if self._current_phase == AttackPhase.MANIPULATION:
            # Artificial price pressure from attack
            attack_progress = self._get_phase_progress(period, AttackPhase.MANIPULATION)
            artificial_pressure = (
                self.attack_config.target_price_change *
                attack_progress *
                0.5  # Not fully effective
            )

            return {
                "base_multiplier": 1.0,
                "demand_pressure": artificial_pressure,
                "supply_pressure": 0.0,
                "volatility_premium": 0.15,
                "attack_impact": artificial_pressure,
            }

        elif self._current_phase == AttackPhase.EXIT:
            # Downward pressure as attackers exit
            exit_progress = self._get_phase_progress(period, AttackPhase.EXIT)
            exit_pressure = -0.1 * exit_progress

            return {
                "base_multiplier": 1.0,
                "demand_pressure": exit_pressure,
                "supply_pressure": 0.0,
                "volatility_premium": 0.1,
            }

        return {
            "base_multiplier": 1.0,
            "demand_pressure": 0.0,
            "supply_pressure": 0.0,
            "volatility_premium": 0.0,
        }

    def get_detection_signals(self, period: int) -> dict:
        """
        Get signals that detection systems might use.

        These are the observable patterns of the attack.
        """
        if self._current_phase == AttackPhase.MANIPULATION:
            return {
                "volume_anomaly": True,
                "price_momentum": self.attack_config.target_price_change > 0,
                "order_cancellation_rate": 0.8,  # High for spoofing
                "self_trade_ratio": 0.15,  # Elevated for wash trading
                "order_book_imbalance": 0.6,
                "suspicious_patterns": self.attack_config.strategies,
            }

        elif self._current_phase == AttackPhase.ACCUMULATION:
            return {
                "volume_anomaly": False,
                "unusual_buyer_activity": True,
                "order_book_imbalance": 0.2,
            }

        return {
            "volume_anomaly": False,
            "suspicious_patterns": [],
        }

    def get_agent_adjustments(self, agent_type: str) -> dict:
        """Adjust legitimate agent behavior during attack."""
        if agent_type == "adversarial":
            return self.get_attack_instructions(self.state.period)

        if self._current_phase == AttackPhase.MANIPULATION:
            if agent_type == "rational":
                return {
                    "caution_level": 1.3,
                    "volume_limit": 0.7,
                }
            elif agent_type == "behavioral":
                return {
                    "herding_modifier": 1.5,  # More likely to follow
                    "fear_modifier": 1.2,
                }

        return {}

    def step(self) -> ScenarioState:
        """Advance to next period."""
        super().step()

        self._update_phase(self.state.period)

        self.state.is_attack_active = self._current_phase in [
            AttackPhase.MANIPULATION,
            AttackPhase.EXIT,
        ]

        self.state.custom_data["attack_phase"] = self._current_phase.value
        self.state.custom_data["attack_instructions"] = self.get_attack_instructions(
            self.state.period
        )
        self.state.custom_data["detection_signals"] = self.get_detection_signals(
            self.state.period
        )

        return self.state

    def get_attack_summary(self) -> dict:
        """Get summary of the attack."""
        return {
            "attack_config": {
                "num_attackers": self.attack_config.num_attackers,
                "capital": self.attack_config.capital_tokens,
                "strategies": self.attack_config.strategies,
                "target_price_change": self.attack_config.target_price_change,
            },
            "phase_durations": {
                "reconnaissance": self.recon_hours,
                "accumulation": self.accumulation_hours,
                "manipulation": self.manipulation_hours,
                "exit": self.exit_hours,
            },
            "current_phase": self._current_phase.value,
        }
