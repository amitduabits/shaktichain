"""
Prosumer Agent Module

Represents EV owners participating in the V2G marketplace.
Prosumers can act as both buyers (charging) and sellers (discharging to grid).
"""

from dataclasses import dataclass, field
from typing import Literal, Tuple
import random


AgentType = Literal["residential", "commercial", "fleet"]
Role = Literal["buyer", "seller"]


@dataclass
class Bid:
    """Represents a bid in the V2G marketplace auction."""
    agent_id: str
    role: Role
    price: float  # INR/kWh
    quantity: float  # kWh
    timestamp: float = 0.0


@dataclass
class Prosumer:
    """
    Represents an EV owner participating in the V2G marketplace.

    Prosumers can switch between buyer (charging) and seller (V2G discharge)
    roles based on their battery state and market conditions.
    """
    agent_id: str
    agent_type: AgentType
    battery_capacity: float = 50.0  # kWh
    current_soc: float = 0.5  # 0-1, state of charge
    location: Tuple[float, float] = (0.0, 0.0)  # (lat, lng)
    true_valuation: float = 6.0  # INR/kWh - willingness to pay/accept

    # SOC thresholds for role decision
    min_soc_threshold: float = field(default=0.2, repr=False)
    max_soc_threshold: float = field(default=0.8, repr=False)

    # Peak hours when selling is more attractive (evening peak in India)
    peak_hours: Tuple[int, ...] = field(default=(17, 18, 19, 20, 21), repr=False)

    def __post_init__(self):
        """Validate inputs after initialization."""
        if not 0 <= self.current_soc <= 1:
            raise ValueError(f"current_soc must be between 0 and 1, got {self.current_soc}")
        if self.battery_capacity <= 0:
            raise ValueError(f"battery_capacity must be positive, got {self.battery_capacity}")
        if self.true_valuation < 0:
            raise ValueError(f"true_valuation must be non-negative, got {self.true_valuation}")

    @property
    def available_energy(self) -> float:
        """Energy available for selling (kWh), respecting minimum SOC."""
        sellable_soc = max(0, self.current_soc - self.min_soc_threshold)
        return sellable_soc * self.battery_capacity

    @property
    def energy_needed(self) -> float:
        """Energy needed to reach full charge (kWh)."""
        return (1 - self.current_soc) * self.battery_capacity

    def decide_role(self, hour: int) -> Role:
        """
        Decide whether to act as buyer or seller based on SOC and time.

        Decision logic:
        - Low SOC (< min_threshold): Always buyer (need to charge)
        - High SOC (> max_threshold): Always seller (can discharge)
        - Middle SOC: Seller during peak hours, buyer otherwise

        Args:
            hour: Hour of day (0-23)

        Returns:
            "buyer" or "seller"
        """
        if not 0 <= hour <= 23:
            raise ValueError(f"hour must be between 0 and 23, got {hour}")

        # Low battery - must charge
        if self.current_soc < self.min_soc_threshold:
            return "buyer"

        # High battery - prefer to sell
        if self.current_soc > self.max_soc_threshold:
            return "seller"

        # Medium SOC - depends on time of day
        # Peak hours = high demand = good time to sell
        if hour in self.peak_hours:
            return "seller"

        return "buyer"

    def generate_bid(self, current_price: float, hour: int = 12) -> Bid:
        """
        Generate a bid based on true valuation with small noise.

        Buyers bid slightly below their true valuation.
        Sellers ask slightly above their true valuation.

        Args:
            current_price: Current market price (INR/kWh)
            hour: Current hour for role decision

        Returns:
            Bid object with price and quantity
        """
        role = self.decide_role(hour)

        # Add noise to true valuation (±5%)
        noise = random.uniform(-0.05, 0.05)
        base_price = self.true_valuation * (1 + noise)

        if role == "buyer":
            # Buyers: bid at or slightly below true valuation
            # Also influenced by current market price
            bid_price = min(base_price, current_price * 1.1)
            quantity = min(self.energy_needed, self.battery_capacity * 0.3)  # Max 30% at once
        else:
            # Sellers: ask at or slightly above true valuation
            bid_price = max(base_price, current_price * 0.9)
            quantity = min(self.available_energy, self.battery_capacity * 0.3)

        # Ensure minimum quantity
        quantity = max(quantity, 1.0) if quantity > 0.5 else 0.0

        return Bid(
            agent_id=self.agent_id,
            role=role,
            price=round(bid_price, 2),
            quantity=round(quantity, 2)
        )

    def update_soc(self, quantity: float, is_buying: bool) -> None:
        """
        Update battery state of charge after a trade.

        Args:
            quantity: Energy traded (kWh)
            is_buying: True if buying (charging), False if selling (discharging)
        """
        if quantity < 0:
            raise ValueError(f"quantity must be non-negative, got {quantity}")

        soc_change = quantity / self.battery_capacity

        if is_buying:
            self.current_soc = min(1.0, self.current_soc + soc_change)
        else:
            self.current_soc = max(0.0, self.current_soc - soc_change)

    def compute_utility(self, price: float, quantity: float) -> float:
        """
        Calculate utility (profit/surplus) from a trade.

        For buyers: utility = (true_valuation - price) * quantity
            Positive when buying below valuation
        For sellers: utility = (price - true_valuation) * quantity
            Positive when selling above valuation

        Args:
            price: Trade price (INR/kWh)
            quantity: Energy traded (kWh)

        Returns:
            Utility value in INR (positive = profit, negative = loss)
        """
        # Determine role based on whether we'd be gaining or losing energy
        # This is a simplified utility - actual role doesn't matter for calculation
        # Buyers gain utility when price < valuation
        # Sellers gain utility when price > valuation

        # Return the surplus regardless of role
        # Caller knows the role context
        return (price - self.true_valuation) * quantity

    def compute_buyer_utility(self, price: float, quantity: float) -> float:
        """Compute utility when acting as a buyer."""
        return (self.true_valuation - price) * quantity

    def compute_seller_utility(self, price: float, quantity: float) -> float:
        """Compute utility when acting as a seller."""
        return (price - self.true_valuation) * quantity
