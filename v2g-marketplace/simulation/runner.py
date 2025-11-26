"""
Simulation Runner for V2G Marketplace

A multi-agent simulation framework for testing vehicle-to-grid energy trading.
"""

import json
import os
import random
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from enum import Enum


class AgentType(Enum):
    RESIDENTIAL = "residential"
    COMMERCIAL = "commercial"
    FLEET = "fleet"


@dataclass
class Bid:
    """Represents a bid in the energy auction."""
    agent_id: int
    quantity: float  # kWh (positive = buy, negative = sell)
    price: float     # INR per kWh
    is_buy: bool


@dataclass
class Agent:
    """Base agent for V2G marketplace simulation."""
    id: int
    agent_type: AgentType
    battery_capacity: float  # kWh
    soc: float               # State of charge (0.0 to 1.0)
    min_soc: float = 0.2     # Minimum SOC to maintain
    max_soc: float = 0.9     # Maximum SOC target

    # Agent-specific parameters
    charge_rate: float = 7.0      # kW
    discharge_rate: float = 5.0   # kW
    base_price_buy: float = 6.0   # Base willingness to pay (INR/kWh)
    base_price_sell: float = 4.0  # Base willingness to accept (INR/kWh)

    def get_current_energy(self) -> float:
        """Get current energy stored in battery (kWh)."""
        return self.soc * self.battery_capacity

    def generate_bid(self, hour: int) -> Optional[Bid]:
        """Generate a bid based on current SOC and time of day."""
        # Time-of-day pricing factor (peak hours 18-22 have higher prices)
        tod_factor = 1.0
        if 18 <= hour % 24 <= 22:
            tod_factor = 1.5  # Peak hours
        elif 0 <= hour % 24 <= 6:
            tod_factor = 0.7  # Off-peak hours

        # Determine if buying or selling based on SOC and randomness
        urgency = random.uniform(0.8, 1.2)

        if self.soc < self.min_soc + 0.1:
            # Low SOC - need to buy
            quantity = min(self.charge_rate, (self.max_soc - self.soc) * self.battery_capacity)
            price = self.base_price_buy * tod_factor * urgency
            return Bid(self.id, quantity, price, is_buy=True)

        elif self.soc > self.max_soc - 0.1:
            # High SOC - willing to sell
            quantity = min(self.discharge_rate, (self.soc - self.min_soc) * self.battery_capacity)
            price = self.base_price_sell * tod_factor * urgency
            return Bid(self.id, -quantity, price, is_buy=False)

        else:
            # Medium SOC - probabilistic decision
            if random.random() < 0.5:
                # Decide to buy
                quantity = min(self.charge_rate * 0.5, (self.max_soc - self.soc) * self.battery_capacity)
                price = self.base_price_buy * tod_factor * urgency * 0.9
                return Bid(self.id, quantity, price, is_buy=True)
            elif random.random() < 0.3:
                # Decide to sell
                quantity = min(self.discharge_rate * 0.5, (self.soc - self.min_soc) * self.battery_capacity)
                price = self.base_price_sell * tod_factor * urgency * 1.1
                return Bid(self.id, -quantity, price, is_buy=False)

        return None  # No bid this period

    def update_soc(self, energy_change: float):
        """Update SOC based on energy bought (positive) or sold (negative)."""
        new_energy = self.get_current_energy() + energy_change
        self.soc = max(0.0, min(1.0, new_energy / self.battery_capacity))


def create_residential_agent(agent_id: int) -> Agent:
    """Create a residential agent with typical EV parameters."""
    return Agent(
        id=agent_id,
        agent_type=AgentType.RESIDENTIAL,
        battery_capacity=random.uniform(40, 75),  # Typical EV battery
        soc=random.uniform(0.3, 0.8),
        charge_rate=random.uniform(3.3, 7.4),     # Home charger
        discharge_rate=random.uniform(3.0, 5.0),
        base_price_buy=random.uniform(5.0, 7.0),
        base_price_sell=random.uniform(3.5, 5.0)
    )


def create_commercial_agent(agent_id: int) -> Agent:
    """Create a commercial agent with larger capacity."""
    return Agent(
        id=agent_id,
        agent_type=AgentType.COMMERCIAL,
        battery_capacity=random.uniform(100, 200),  # Larger commercial EVs
        soc=random.uniform(0.4, 0.7),
        charge_rate=random.uniform(22, 50),         # DC fast charging
        discharge_rate=random.uniform(15, 30),
        base_price_buy=random.uniform(4.5, 6.0),    # More price sensitive
        base_price_sell=random.uniform(4.0, 5.5)
    )


def create_fleet_agent(agent_id: int) -> Agent:
    """Create a fleet agent representing aggregated EVs."""
    return Agent(
        id=agent_id,
        agent_type=AgentType.FLEET,
        battery_capacity=random.uniform(500, 1000),  # Aggregated fleet
        soc=random.uniform(0.35, 0.65),
        charge_rate=random.uniform(100, 200),        # High-power charging
        discharge_rate=random.uniform(80, 150),
        base_price_buy=random.uniform(4.0, 5.5),     # Most price sensitive
        base_price_sell=random.uniform(4.5, 6.0)
    )


class Auction:
    """Simple uniform-price double auction for energy trading."""

    @staticmethod
    def clear(bids: List[Bid]) -> tuple[float, float, float]:
        """
        Clear the auction and return (clearing_price, volume, welfare).

        Uses uniform-price auction where all trades settle at clearing price.
        """
        if not bids:
            return 0.0, 0.0, 0.0

        buy_bids = sorted([b for b in bids if b.is_buy], key=lambda x: -x.price)
        sell_bids = sorted([b for b in bids if not b.is_buy], key=lambda x: x.price)

        if not buy_bids or not sell_bids:
            return 0.0, 0.0, 0.0

        # Find clearing price and volume
        total_volume = 0.0
        clearing_price = 0.0
        welfare = 0.0

        buy_idx = 0
        sell_idx = 0
        buy_remaining = buy_bids[0].quantity if buy_bids else 0
        sell_remaining = abs(sell_bids[0].quantity) if sell_bids else 0

        while buy_idx < len(buy_bids) and sell_idx < len(sell_bids):
            buy_bid = buy_bids[buy_idx]
            sell_bid = sell_bids[sell_idx]

            # Check if trade is possible
            if buy_bid.price < sell_bid.price:
                break

            # Determine trade quantity
            trade_qty = min(buy_remaining, sell_remaining)

            # Update clearing price (midpoint of marginal bids)
            clearing_price = (buy_bid.price + sell_bid.price) / 2

            # Calculate welfare (consumer + producer surplus)
            welfare += (buy_bid.price - sell_bid.price) * trade_qty

            total_volume += trade_qty

            # Update remaining quantities
            buy_remaining -= trade_qty
            sell_remaining -= trade_qty

            if buy_remaining <= 0.001:
                buy_idx += 1
                if buy_idx < len(buy_bids):
                    buy_remaining = buy_bids[buy_idx].quantity

            if sell_remaining <= 0.001:
                sell_idx += 1
                if sell_idx < len(sell_bids):
                    sell_remaining = abs(sell_bids[sell_idx].quantity)

        return clearing_price, total_volume, welfare


class SimulationRunner:
    """
    Run multi-agent V2G marketplace simulations.

    Simulates energy trading between various agent types
    (residential, commercial, fleet) over multiple periods.
    """

    def __init__(self, n_agents: int = 100, n_days: int = 7):
        """
        Initialize the simulation runner.

        Args:
            n_agents: Total number of agents in the simulation
            n_days: Number of days to simulate
        """
        self.n_agents = n_agents
        self.n_days = n_days
        self.n_periods = n_days * 24  # Hourly periods
        self.agents: List[Agent] = []
        self.results: Dict = {
            'periods': [],
            'prices': [],
            'volumes': [],
            'welfare': []
        }
        self._simulation_complete = False

    def create_agents(self):
        """
        Create a mix of agents: 60% residential, 30% commercial, 10% fleet.
        """
        self.agents = []

        n_residential = int(self.n_agents * 0.6)
        n_commercial = int(self.n_agents * 0.3)
        n_fleet = self.n_agents - n_residential - n_commercial

        agent_id = 0

        # Create residential agents (60%)
        for _ in range(n_residential):
            self.agents.append(create_residential_agent(agent_id))
            agent_id += 1

        # Create commercial agents (30%)
        for _ in range(n_commercial):
            self.agents.append(create_commercial_agent(agent_id))
            agent_id += 1

        # Create fleet agents (10%)
        for _ in range(n_fleet):
            self.agents.append(create_fleet_agent(agent_id))
            agent_id += 1

    def run_single_period(self, hour: int) -> tuple[float, float, float]:
        """
        Run a single trading period.

        Args:
            hour: The hour number (0 to n_periods-1)

        Returns:
            Tuple of (clearing_price, volume, welfare)
        """
        # Collect bids from all agents
        bids = []
        for agent in self.agents:
            bid = agent.generate_bid(hour)
            if bid is not None:
                bids.append(bid)

        # Run auction
        clearing_price, volume, welfare = Auction.clear(bids)

        # Update SOCs based on auction results
        if volume > 0 and clearing_price > 0:
            # Determine which bids were matched
            buy_bids = sorted([b for b in bids if b.is_buy], key=lambda x: -x.price)
            sell_bids = sorted([b for b in bids if not b.is_buy], key=lambda x: x.price)

            remaining_volume = volume

            # Process matched buy bids
            for bid in buy_bids:
                if remaining_volume <= 0:
                    break
                if bid.price >= clearing_price:
                    matched_qty = min(bid.quantity, remaining_volume)
                    agent = next((a for a in self.agents if a.id == bid.agent_id), None)
                    if agent:
                        agent.update_soc(matched_qty)
                    remaining_volume -= matched_qty

            remaining_volume = volume

            # Process matched sell bids
            for bid in sell_bids:
                if remaining_volume <= 0:
                    break
                if bid.price <= clearing_price:
                    matched_qty = min(abs(bid.quantity), remaining_volume)
                    agent = next((a for a in self.agents if a.id == bid.agent_id), None)
                    if agent:
                        agent.update_soc(-matched_qty)
                    remaining_volume -= matched_qty

        return clearing_price, volume, welfare

    def run_simulation(self):
        """
        Run the complete simulation over all periods.
        """
        # Reset results
        self.results = {
            'periods': [],
            'prices': [],
            'volumes': [],
            'welfare': []
        }

        # Create agents if not already created
        if not self.agents:
            self.create_agents()

        # Run each period
        for hour in range(self.n_periods):
            price, volume, welfare = self.run_single_period(hour)

            self.results['periods'].append(hour)
            self.results['prices'].append(price)
            self.results['volumes'].append(volume)
            self.results['welfare'].append(welfare)

        self._simulation_complete = True

    def get_results(self) -> Dict:
        """
        Get the simulation results.

        Returns:
            Dict with periods, prices, volumes, and welfare per period.
        """
        return self.results.copy()

    def get_daily_summary(self) -> List[Dict]:
        """
        Get a daily summary of the simulation results.

        Returns:
            List of dicts with daily avg_price and total_volume.
        """
        if not self._simulation_complete:
            return []

        daily_summary = []
        for day in range(self.n_days):
            start_hour = day * 24
            end_hour = start_hour + 24

            day_prices = self.results['prices'][start_hour:end_hour]
            day_volumes = self.results['volumes'][start_hour:end_hour]

            # Calculate average price (excluding zero-volume periods)
            valid_prices = [p for p, v in zip(day_prices, day_volumes) if v > 0]
            avg_price = sum(valid_prices) / len(valid_prices) if valid_prices else 0.0

            total_volume = sum(day_volumes)

            daily_summary.append({
                'day': day + 1,
                'avg_price': round(avg_price, 2),
                'total_volume': round(total_volume, 2)
            })

        return daily_summary


if __name__ == "__main__":
    # Set random seed for reproducibility
    random.seed(42)

    # Run a 7-day simulation with 100 agents
    print("Starting V2G Marketplace Simulation")
    print("=" * 50)
    print(f"Agents: 100 (60 residential, 30 commercial, 10 fleet)")
    print(f"Duration: 7 days (168 hourly periods)")
    print("=" * 50)

    runner = SimulationRunner(n_agents=100, n_days=7)
    runner.create_agents()
    runner.run_simulation()

    # Print daily summary
    print("\nDaily Summary:")
    print("-" * 40)
    print(f"{'Day':<6}{'Avg Price (INR/kWh)':<22}{'Total Volume (kWh)'}")
    print("-" * 40)

    daily_summary = runner.get_daily_summary()
    for day_data in daily_summary:
        print(f"{day_data['day']:<6}{day_data['avg_price']:<22}{day_data['total_volume']}")

    print("-" * 40)

    # Calculate overall statistics
    results = runner.get_results()
    total_volume = sum(results['volumes'])
    valid_prices = [p for p, v in zip(results['prices'], results['volumes']) if v > 0]
    avg_price = sum(valid_prices) / len(valid_prices) if valid_prices else 0
    total_welfare = sum(results['welfare'])

    print(f"\nOverall Statistics:")
    print(f"  Total Volume Traded: {total_volume:.2f} kWh")
    print(f"  Average Price: {avg_price:.2f} INR/kWh")
    print(f"  Total Social Welfare: {total_welfare:.2f} INR")

    # Save results to JSON
    output_dir = os.path.join(os.path.dirname(__file__), 'results')
    os.makedirs(output_dir, exist_ok=True)

    output_path = os.path.join(output_dir, 'sim_output.json')

    output_data = {
        'config': {
            'n_agents': 100,
            'n_days': 7,
            'agent_mix': {
                'residential': 60,
                'commercial': 30,
                'fleet': 10
            }
        },
        'results': results,
        'daily_summary': daily_summary,
        'overall': {
            'total_volume': round(total_volume, 2),
            'avg_price': round(avg_price, 2),
            'total_welfare': round(total_welfare, 2)
        }
    }

    with open(output_path, 'w') as f:
        json.dump(output_data, f, indent=2)

    print(f"\nResults saved to: {output_path}")
