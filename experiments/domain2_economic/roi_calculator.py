"""
ROI Calculator for SHAKTI-CHAIN Economic Performance (Domain 2).

Calculates Return on Investment for V2G marketplace participants,
accounting for:
- Trading profits/losses
- Battery degradation costs
- Transaction fees
- Time value of money
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum

import numpy as np


class AgentType(Enum):
    """Types of trading agents."""
    RATIONAL = "RAT"
    BOUNDED_RATIONAL = "BND"
    ZERO_INTELLIGENCE = "ZI"
    BEHAVIORAL = "BEH"
    ADVERSARIAL = "ADV"


@dataclass
class Trade:
    """Record of a single trade."""
    trade_id: str
    agent_id: str
    timestamp: float
    side: str  # "buy" or "sell"
    price: float
    quantity: float
    revenue: float  # Positive for sells, negative for buys
    fees: float = 0.0

    @property
    def net_revenue(self) -> float:
        """Net revenue after fees."""
        return self.revenue - self.fees


@dataclass
class Agent:
    """Representation of a trading agent for ROI calculation."""
    agent_id: str
    agent_type: AgentType
    battery_capacity_kwh: float
    initial_battery_value: float  # INR
    registration_cost: float  # INR
    trades: List[Trade] = field(default_factory=list)

    @property
    def initial_investment(self) -> float:
        """Total initial investment."""
        return self.initial_battery_value + self.registration_cost

    @property
    def is_small_participant(self) -> bool:
        """Check if small participant (< 10 kWh battery)."""
        return self.battery_capacity_kwh < 10.0

    @property
    def is_large_participant(self) -> bool:
        """Check if large participant (> 50 kWh battery)."""
        return self.battery_capacity_kwh > 50.0


@dataclass
class RoiResult:
    """
    ROI calculation result for a single agent.

    Attributes:
        agent_id: Unique agent identifier
        agent_type: Type of agent (RAT, BND, ZI, BEH)
        gross_roi: ROI before degradation and fees
        net_roi: ROI after all costs
        annualized_roi: ROI annualized to yearly rate
        total_revenue: Total trading revenue
        total_costs: Total costs including degradation
        total_fees: Total transaction fees
        degradation_cost: Cost from battery degradation
        num_trades: Number of trades executed
        num_cycles: Estimated charge/discharge cycles
        battery_size_category: "small", "medium", or "large"
    """
    agent_id: str
    agent_type: str
    gross_roi: float
    net_roi: float
    annualized_roi: float
    total_revenue: float
    total_costs: float
    total_fees: float
    degradation_cost: float
    num_trades: int
    num_cycles: float
    battery_size_category: str
    initial_investment: float

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "gross_roi": float(self.gross_roi),
            "net_roi": float(self.net_roi),
            "annualized_roi": float(self.annualized_roi),
            "total_revenue": float(self.total_revenue),
            "total_costs": float(self.total_costs),
            "total_fees": float(self.total_fees),
            "degradation_cost": float(self.degradation_cost),
            "num_trades": self.num_trades,
            "num_cycles": float(self.num_cycles),
            "battery_size_category": self.battery_size_category,
            "initial_investment": float(self.initial_investment),
        }


@dataclass
class RoiDistribution:
    """
    Distribution of ROI across all agents.

    Attributes:
        all_rois: All ROI values
        roi_by_type: ROI values grouped by agent type
        mean_roi: Overall mean ROI
        median_roi: Overall median ROI
        std_roi: Standard deviation of ROI
        min_roi: Minimum ROI
        max_roi: Maximum ROI
        positive_roi_rate: Proportion of agents with positive ROI
        results_by_agent: Individual RoiResult for each agent
    """
    all_rois: np.ndarray
    roi_by_type: Dict[str, np.ndarray]
    mean_roi: float
    median_roi: float
    std_roi: float
    min_roi: float
    max_roi: float
    positive_roi_rate: float
    results_by_agent: Dict[str, RoiResult]

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "mean_roi": float(self.mean_roi),
            "median_roi": float(self.median_roi),
            "std_roi": float(self.std_roi),
            "min_roi": float(self.min_roi),
            "max_roi": float(self.max_roi),
            "positive_roi_rate": float(self.positive_roi_rate),
            "num_agents": len(self.all_rois),
            "roi_by_type": {
                k: {
                    "mean": float(np.mean(v)),
                    "std": float(np.std(v)),
                    "n": len(v),
                }
                for k, v in self.roi_by_type.items()
            },
        }


def calculate_agent_roi(
    agent_id: str,
    agent_type: str,
    initial_investment: float,
    trades: List[Trade],
    transaction_fees: float,
    simulation_duration_days: float,
    battery_capacity_kwh: float,
    degradation_rate_per_cycle: float = 0.001,  # 0.1% per cycle
    annual_discount_rate: float = 0.08,  # 8% annual
) -> RoiResult:
    """
    Calculate ROI for a single agent.

    ROI = (Total Revenue - Total Cost - Fees - Degradation) / Initial Investment

    Annualize if simulation < 365 days.

    Args:
        agent_id: Unique identifier for the agent
        agent_type: Type of agent (RAT, BND, ZI, BEH)
        initial_investment: Battery value + registration cost (INR)
        trades: List of Trade objects for this agent
        transaction_fees: Total transaction fees paid
        simulation_duration_days: Duration of simulation in days
        battery_capacity_kwh: Battery capacity for degradation calculation
        degradation_rate_per_cycle: Battery degradation rate per cycle (default 0.1%)
        annual_discount_rate: Discount rate for time value of money

    Returns:
        RoiResult with all ROI metrics
    """
    if initial_investment <= 0:
        raise ValueError("Initial investment must be positive")

    # Calculate total trading revenue (profit from selling - cost of buying)
    total_revenue = 0.0
    total_energy_traded = 0.0

    for trade in trades:
        total_revenue += trade.net_revenue
        total_energy_traded += abs(trade.quantity)

    # Estimate number of charge/discharge cycles
    # Each full cycle = charge + discharge = 2 * battery_capacity
    if battery_capacity_kwh > 0:
        num_cycles = total_energy_traded / (2 * battery_capacity_kwh)
    else:
        num_cycles = 0.0

    # Calculate degradation cost
    # Degradation reduces battery value over time
    degradation_fraction = num_cycles * degradation_rate_per_cycle
    # Assume battery value is 80% of initial investment
    battery_value = initial_investment * 0.8
    degradation_cost = battery_value * degradation_fraction

    # Total costs
    total_costs = transaction_fees + degradation_cost

    # Gross ROI (before degradation)
    gross_profit = total_revenue - transaction_fees
    gross_roi = gross_profit / initial_investment

    # Net ROI (after all costs)
    net_profit = total_revenue - total_costs
    net_roi = net_profit / initial_investment

    # Annualize ROI if simulation < 365 days
    if simulation_duration_days > 0 and simulation_duration_days < 365:
        # Compound annual growth rate approach
        periods_per_year = 365 / simulation_duration_days
        if net_roi > -1:  # Avoid negative base for power
            annualized_roi = (1 + net_roi) ** periods_per_year - 1
        else:
            annualized_roi = -1.0  # Complete loss
    elif simulation_duration_days >= 365:
        # Already annual or longer
        years = simulation_duration_days / 365
        if net_roi > -1:
            annualized_roi = (1 + net_roi) ** (1 / years) - 1
        else:
            annualized_roi = -1.0
    else:
        annualized_roi = net_roi

    # Apply discount for time value of money (NPV adjustment)
    # For short simulations, this has minimal effect
    if simulation_duration_days > 0:
        daily_discount_rate = (1 + annual_discount_rate) ** (1/365) - 1
        discount_factor = 1 / (1 + daily_discount_rate) ** simulation_duration_days
        # Adjust expected future value to present value
        # This affects the interpretation but not the raw ROI

    # Determine battery size category
    if battery_capacity_kwh < 10:
        battery_size_category = "small"
    elif battery_capacity_kwh > 50:
        battery_size_category = "large"
    else:
        battery_size_category = "medium"

    return RoiResult(
        agent_id=agent_id,
        agent_type=agent_type,
        gross_roi=gross_roi,
        net_roi=net_roi,
        annualized_roi=annualized_roi,
        total_revenue=total_revenue,
        total_costs=total_costs,
        total_fees=transaction_fees,
        degradation_cost=degradation_cost,
        num_trades=len(trades),
        num_cycles=num_cycles,
        battery_size_category=battery_size_category,
        initial_investment=initial_investment,
    )


def calculate_roi_distribution(
    agents: List[Agent],
    simulation_duration_days: float,
    degradation_rate_per_cycle: float = 0.001,
    annual_discount_rate: float = 0.08,
) -> RoiDistribution:
    """
    Calculate ROI distribution for all agents, grouped by type.

    Args:
        agents: List of Agent objects with their trades
        simulation_duration_days: Duration of simulation
        degradation_rate_per_cycle: Battery degradation rate per cycle
        annual_discount_rate: Discount rate for time value of money

    Returns:
        RoiDistribution with aggregate statistics
    """
    results_by_agent: Dict[str, RoiResult] = {}
    roi_by_type: Dict[str, List[float]] = {}
    all_rois: List[float] = []

    for agent in agents:
        # Calculate total fees for this agent
        total_fees = sum(trade.fees for trade in agent.trades)

        # Calculate individual ROI
        result = calculate_agent_roi(
            agent_id=agent.agent_id,
            agent_type=agent.agent_type.value,
            initial_investment=agent.initial_investment,
            trades=agent.trades,
            transaction_fees=total_fees,
            simulation_duration_days=simulation_duration_days,
            battery_capacity_kwh=agent.battery_capacity_kwh,
            degradation_rate_per_cycle=degradation_rate_per_cycle,
            annual_discount_rate=annual_discount_rate,
        )

        results_by_agent[agent.agent_id] = result
        all_rois.append(result.annualized_roi)

        # Group by type
        type_key = agent.agent_type.value
        if type_key not in roi_by_type:
            roi_by_type[type_key] = []
        roi_by_type[type_key].append(result.annualized_roi)

    # Convert to numpy arrays
    all_rois_arr = np.array(all_rois)
    roi_by_type_arr = {k: np.array(v) for k, v in roi_by_type.items()}

    # Calculate statistics
    mean_roi = float(np.mean(all_rois_arr)) if len(all_rois_arr) > 0 else 0.0
    median_roi = float(np.median(all_rois_arr)) if len(all_rois_arr) > 0 else 0.0
    std_roi = float(np.std(all_rois_arr)) if len(all_rois_arr) > 0 else 0.0
    min_roi = float(np.min(all_rois_arr)) if len(all_rois_arr) > 0 else 0.0
    max_roi = float(np.max(all_rois_arr)) if len(all_rois_arr) > 0 else 0.0
    positive_roi_rate = float(np.mean(all_rois_arr > 0)) if len(all_rois_arr) > 0 else 0.0

    return RoiDistribution(
        all_rois=all_rois_arr,
        roi_by_type=roi_by_type_arr,
        mean_roi=mean_roi,
        median_roi=median_roi,
        std_roi=std_roi,
        min_roi=min_roi,
        max_roi=max_roi,
        positive_roi_rate=positive_roi_rate,
        results_by_agent=results_by_agent,
    )


def calculate_roi_by_battery_size(
    agents: List[Agent],
    simulation_duration_days: float,
    degradation_rate_per_cycle: float = 0.001,
) -> Dict[str, Dict[str, float]]:
    """
    Calculate ROI statistics grouped by battery size category.

    Categories:
    - Small: < 10 kWh
    - Medium: 10-50 kWh
    - Large: > 50 kWh

    Args:
        agents: List of Agent objects
        simulation_duration_days: Duration of simulation
        degradation_rate_per_cycle: Battery degradation rate

    Returns:
        Dictionary with statistics for each size category
    """
    roi_by_size: Dict[str, List[float]] = {
        "small": [],
        "medium": [],
        "large": [],
    }

    for agent in agents:
        total_fees = sum(trade.fees for trade in agent.trades)

        result = calculate_agent_roi(
            agent_id=agent.agent_id,
            agent_type=agent.agent_type.value,
            initial_investment=agent.initial_investment,
            trades=agent.trades,
            transaction_fees=total_fees,
            simulation_duration_days=simulation_duration_days,
            battery_capacity_kwh=agent.battery_capacity_kwh,
            degradation_rate_per_cycle=degradation_rate_per_cycle,
        )

        roi_by_size[result.battery_size_category].append(result.annualized_roi)

    # Calculate statistics for each category
    stats_by_size: Dict[str, Dict[str, float]] = {}

    for category, rois in roi_by_size.items():
        if len(rois) > 0:
            rois_arr = np.array(rois)
            stats_by_size[category] = {
                "mean": float(np.mean(rois_arr)),
                "median": float(np.median(rois_arr)),
                "std": float(np.std(rois_arr)),
                "min": float(np.min(rois_arr)),
                "max": float(np.max(rois_arr)),
                "n": len(rois),
                "positive_rate": float(np.mean(rois_arr > 0)),
            }
        else:
            stats_by_size[category] = {
                "mean": np.nan,
                "median": np.nan,
                "std": np.nan,
                "min": np.nan,
                "max": np.nan,
                "n": 0,
                "positive_rate": np.nan,
            }

    return stats_by_size


def calculate_present_value(
    future_cashflows: List[Tuple[float, float]],
    annual_discount_rate: float = 0.08,
) -> float:
    """
    Calculate present value of future cashflows.

    Args:
        future_cashflows: List of (days_from_now, amount) tuples
        annual_discount_rate: Annual discount rate

    Returns:
        Present value of all cashflows
    """
    pv = 0.0
    daily_rate = (1 + annual_discount_rate) ** (1/365) - 1

    for days, amount in future_cashflows:
        discount_factor = 1 / (1 + daily_rate) ** days
        pv += amount * discount_factor

    return pv


def calculate_irr(
    initial_investment: float,
    cashflows: List[Tuple[float, float]],
    max_iterations: int = 1000,
    tolerance: float = 1e-6,
) -> Optional[float]:
    """
    Calculate Internal Rate of Return using Newton-Raphson method.

    Args:
        initial_investment: Initial investment (positive number, will be negated)
        cashflows: List of (days_from_now, amount) tuples
        max_iterations: Maximum iterations for convergence
        tolerance: Convergence tolerance

    Returns:
        Annualized IRR or None if no convergence
    """
    if not cashflows:
        return None

    # Convert to daily periods
    all_flows = [(-initial_investment, 0)]  # Initial outflow at day 0
    all_flows.extend([(amount, days) for days, amount in cashflows])

    # Initial guess
    rate = 0.1 / 365  # Daily rate starting from 10% annual

    for _ in range(max_iterations):
        # Calculate NPV and its derivative
        npv = 0.0
        dnpv = 0.0

        for amount, days in all_flows:
            discount = (1 + rate) ** days
            npv += amount / discount
            if days > 0:
                dnpv -= days * amount / ((1 + rate) ** (days + 1))

        if abs(npv) < tolerance:
            # Annualize the daily rate
            annual_irr = (1 + rate) ** 365 - 1
            return annual_irr

        if abs(dnpv) < 1e-12:
            break

        rate = rate - npv / dnpv

        # Bounds check
        if rate <= -1:
            rate = -0.99
        elif rate > 10:
            rate = 10

    return None  # No convergence
