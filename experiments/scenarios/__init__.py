"""
SHAKTI-CHAIN Market Scenarios

This module provides various market scenarios for testing
the V2G energy trading platform under different conditions.
"""

from .normal_demand import NormalDemandScenario
from .peak_demand import PeakDemandScenario
from .supply_shock import SupplyShockScenario
from .high_volatility import HighVolatilityScenario
from .manipulation_attack import ManipulationAttackScenario

__all__ = [
    "NormalDemandScenario",
    "PeakDemandScenario",
    "SupplyShockScenario",
    "HighVolatilityScenario",
    "ManipulationAttackScenario",
]
