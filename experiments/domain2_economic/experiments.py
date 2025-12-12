"""
Economic Performance Experiment Runner (Domain 2).

Main orchestration module for running economic performance experiments
and generating comprehensive validation results for SHAKTI-CHAIN.

Validates hypotheses:
- H2.1: Participant ROI > 15%
- H2.2: ROI varies by agent type (ANOVA)
- H2.3: Welfare Gini < 0.4
- H2.4: Price CV < 0.15
- H2.5: Bid-Ask Spread < 10%
- H2.6: Fill Rate > 80%
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from .roi_calculator import (
    Agent,
    AgentType,
    Trade,
    RoiDistribution,
    RoiResult,
    calculate_agent_roi,
    calculate_roi_distribution,
    calculate_roi_by_battery_size,
)
from .fairness_metrics import (
    calculate_gini_coefficient,
    bootstrap_gini_ci,
    calculate_lorenz_curve,
    calculate_all_fairness_metrics,
)
from .liquidity_metrics import (
    Order,
    OrderBookSnapshot,
    SpreadMetrics,
    DepthMetrics,
    VolatilityMetrics,
    calculate_bid_ask_spread,
    calculate_fill_rate,
    calculate_price_volatility,
    calculate_all_liquidity_metrics,
)
from .hypothesis_tests import (
    EconomicHypothesisTester,
    EconomicHypothesisResult,
)
from .visualization import EconomicVisualizer

logger = logging.getLogger(__name__)


@dataclass
class EconomicExperimentConfig:
    """Configuration for economic performance experiments."""

    # Agent configuration
    num_agents_per_type: int = 25  # 25 agents per type = 100 total for 4 types
    agent_types: List[str] = field(
        default_factory=lambda: ["RAT", "BND", "ZI", "BEH"]
    )

    # Battery configuration (INR values based on Indian market)
    min_battery_capacity_kwh: float = 5.0
    max_battery_capacity_kwh: float = 100.0
    battery_cost_per_kwh: float = 10000.0  # INR per kWh
    registration_cost: float = 500.0  # INR

    # Trading configuration
    min_trades_per_agent: int = 5
    max_trades_per_agent: int = 50
    min_price: float = 5.0  # INR per kWh
    max_price: float = 15.0  # INR per kWh
    fee_rate: float = 0.01  # 1% transaction fee

    # Market configuration
    order_book_snapshots_per_run: int = 100
    simulation_duration_days: float = 30.0

    # ROI parameters (from requirements)
    degradation_rate_per_cycle: float = 0.001  # 0.1% per cycle
    annual_discount_rate: float = 0.08  # 8% annual

    # Experiment parameters
    num_runs: int = 100
    seed: Optional[int] = None

    # Statistical parameters
    alpha: float = 0.05
    bootstrap_iterations: int = 10000
    correction_method: str = "holm"

    # Output configuration
    output_dir: str = "results/domain2"
    save_raw_data: bool = True
    generate_plots: bool = True

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "num_agents_per_type": self.num_agents_per_type,
            "agent_types": self.agent_types,
            "min_battery_capacity_kwh": self.min_battery_capacity_kwh,
            "max_battery_capacity_kwh": self.max_battery_capacity_kwh,
            "battery_cost_per_kwh": self.battery_cost_per_kwh,
            "registration_cost": self.registration_cost,
            "min_trades_per_agent": self.min_trades_per_agent,
            "max_trades_per_agent": self.max_trades_per_agent,
            "min_price": self.min_price,
            "max_price": self.max_price,
            "fee_rate": self.fee_rate,
            "order_book_snapshots_per_run": self.order_book_snapshots_per_run,
            "simulation_duration_days": self.simulation_duration_days,
            "degradation_rate_per_cycle": self.degradation_rate_per_cycle,
            "annual_discount_rate": self.annual_discount_rate,
            "num_runs": self.num_runs,
            "seed": self.seed,
            "alpha": self.alpha,
            "bootstrap_iterations": self.bootstrap_iterations,
            "correction_method": self.correction_method,
            "output_dir": self.output_dir,
            "save_raw_data": self.save_raw_data,
            "generate_plots": self.generate_plots,
        }


@dataclass
class SingleRunResults:
    """Results from a single simulation run."""

    roi_distribution: RoiDistribution
    welfare_distribution: np.ndarray
    prices: List[float]
    order_book_snapshots: List[OrderBookSnapshot]
    submitted_orders: List[Order]
    spread_metrics: SpreadMetrics
    volatility_metrics: VolatilityMetrics
    fill_rate: float
    agents: List[Agent]

    def to_dict(self) -> dict:
        """Convert to serializable dictionary."""
        return {
            "roi_distribution": self.roi_distribution.to_dict(),
            "welfare_stats": {
                "mean": float(np.mean(self.welfare_distribution)),
                "std": float(np.std(self.welfare_distribution)),
                "min": float(np.min(self.welfare_distribution)),
                "max": float(np.max(self.welfare_distribution)),
                "gini": float(calculate_gini_coefficient(self.welfare_distribution)),
            },
            "spread_metrics": self.spread_metrics.to_dict(),
            "volatility_metrics": self.volatility_metrics.to_dict(),
            "fill_rate": self.fill_rate,
            "num_agents": len(self.agents),
            "num_prices": len(self.prices),
        }


@dataclass
class EconomicExperimentResults:
    """
    Complete results from economic performance experiment.

    Contains all run results, hypothesis tests, and aggregate statistics.
    """

    config: EconomicExperimentConfig
    run_results: List[SingleRunResults]
    hypothesis_results: Dict[str, EconomicHypothesisResult]
    aggregate_stats: Dict[str, Any]
    roi_by_battery_size: Dict[str, Dict[str, float]]
    execution_time_seconds: float
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        """Convert to serializable dictionary."""
        return {
            "config": self.config.to_dict(),
            "hypothesis_results": {
                h_id: result.to_dict()
                for h_id, result in self.hypothesis_results.items()
            },
            "aggregate_stats": self.aggregate_stats,
            "roi_by_battery_size": self.roi_by_battery_size,
            "execution_time_seconds": self.execution_time_seconds,
            "timestamp": self.timestamp,
            "num_runs": len(self.run_results),
        }

    def summary(self) -> str:
        """Generate summary string."""
        passed = sum(1 for r in self.hypothesis_results.values() if r.passed)
        total = len(self.hypothesis_results)

        lines = [
            "Economic Performance Experiment Results",
            "=" * 45,
            f"Runs: {len(self.run_results)}",
            f"Hypotheses Passed: {passed}/{total}",
            f"Execution Time: {self.execution_time_seconds:.2f}s",
            "",
            "Aggregate Statistics:",
        ]

        for key, value in self.aggregate_stats.items():
            if isinstance(value, float):
                lines.append(f"  {key}: {value:.4f}")
            else:
                lines.append(f"  {key}: {value}")

        lines.extend([
            "",
            "Hypothesis Results:",
        ])

        for h_id in sorted(self.hypothesis_results.keys()):
            result = self.hypothesis_results[h_id]
            status = "PASS" if result.passed else "FAIL"
            lines.append(f"  {h_id}: {status} (p={result.p_value:.4f})")

        return "\n".join(lines)


class EconomicPerformanceExperiment:
    """
    Main experiment runner for Domain 2 - Economic Performance.

    Orchestrates:
    1. Agent generation with configurable types and battery sizes
    2. Trade simulation
    3. Order book and liquidity metrics
    4. ROI calculation per agent
    5. Welfare distribution and fairness metrics
    6. Hypothesis testing
    7. Result aggregation and reporting
    """

    def __init__(self, config: Optional[EconomicExperimentConfig] = None):
        """
        Initialize experiment runner.

        Args:
            config: Experiment configuration (uses defaults if None)
        """
        self.config = config or EconomicExperimentConfig()
        self.hypothesis_tester = EconomicHypothesisTester(
            alpha=self.config.alpha,
            min_samples=30,
            bootstrap_iterations=self.config.bootstrap_iterations,
            correction_method=self.config.correction_method,
        )

        if self.config.seed is not None:
            np.random.seed(self.config.seed)

    def run(self, progress_callback=None) -> EconomicExperimentResults:
        """
        Execute the full experiment.

        Args:
            progress_callback: Optional callback(run_number, total_runs)

        Returns:
            EconomicExperimentResults with all metrics and hypothesis tests
        """
        start_time = time.time()
        logger.info(f"Starting economic performance experiment with {self.config.num_runs} runs")

        run_results: List[SingleRunResults] = []

        for run_idx in range(self.config.num_runs):
            if progress_callback:
                progress_callback(run_idx + 1, self.config.num_runs)

            # Generate agents
            agents = self._generate_agents()

            # Simulate trading
            agents, trades_by_agent = self._simulate_trading(agents)

            # Generate order book snapshots
            order_book_snapshots = self._generate_order_book_snapshots()

            # Generate price series
            prices = self._generate_price_series()

            # Generate orders
            submitted_orders = self._generate_orders(agents)

            # Calculate ROI distribution
            roi_distribution = calculate_roi_distribution(
                agents,
                self.config.simulation_duration_days,
                self.config.degradation_rate_per_cycle,
                self.config.annual_discount_rate,
            )

            # Calculate welfare distribution (profits from trading)
            welfare_distribution = self._calculate_welfare(agents)

            # Calculate liquidity metrics
            spread_metrics = calculate_bid_ask_spread(order_book_snapshots)
            volatility_metrics = calculate_price_volatility(prices)
            fill_rate = calculate_fill_rate(submitted_orders)

            run_result = SingleRunResults(
                roi_distribution=roi_distribution,
                welfare_distribution=welfare_distribution,
                prices=prices,
                order_book_snapshots=order_book_snapshots,
                submitted_orders=submitted_orders,
                spread_metrics=spread_metrics,
                volatility_metrics=volatility_metrics,
                fill_rate=fill_rate,
                agents=agents,
            )
            run_results.append(run_result)

            if (run_idx + 1) % 10 == 0:
                logger.debug(f"Completed run {run_idx + 1}/{self.config.num_runs}")

        # Run hypothesis tests
        logger.info("Running hypothesis tests...")
        hypothesis_results = self._run_hypothesis_tests(run_results)

        # Compute aggregate statistics
        aggregate_stats = self._compute_aggregate_stats(run_results)

        # Calculate ROI by battery size (using all agents from all runs)
        all_agents = []
        for run_result in run_results:
            all_agents.extend(run_result.agents)
        roi_by_battery_size = calculate_roi_by_battery_size(
            all_agents,
            self.config.simulation_duration_days,
            self.config.degradation_rate_per_cycle,
        )

        execution_time = time.time() - start_time
        logger.info(f"Experiment completed in {execution_time:.2f}s")

        results = EconomicExperimentResults(
            config=self.config,
            run_results=run_results,
            hypothesis_results=hypothesis_results,
            aggregate_stats=aggregate_stats,
            roi_by_battery_size=roi_by_battery_size,
            execution_time_seconds=execution_time,
        )

        return results

    def _generate_agents(self) -> List[Agent]:
        """
        Generate agents of different types with varied battery capacities.

        Returns:
            List of Agent objects
        """
        agents = []
        agent_id_counter = 0

        for agent_type_str in self.config.agent_types:
            agent_type = AgentType(agent_type_str)

            for _ in range(self.config.num_agents_per_type):
                # Generate battery capacity (biased towards typical EV battery sizes)
                # Small: 5-20 kWh, Medium: 20-50 kWh, Large: 50-100 kWh
                size_category = np.random.choice(["small", "medium", "large"], p=[0.3, 0.5, 0.2])

                if size_category == "small":
                    battery_capacity = np.random.uniform(
                        self.config.min_battery_capacity_kwh,
                        min(20.0, self.config.max_battery_capacity_kwh),
                    )
                elif size_category == "medium":
                    battery_capacity = np.random.uniform(20.0, 50.0)
                else:
                    battery_capacity = np.random.uniform(
                        50.0,
                        self.config.max_battery_capacity_kwh,
                    )

                # Calculate battery value
                battery_value = battery_capacity * self.config.battery_cost_per_kwh

                agent = Agent(
                    agent_id=f"agent_{agent_id_counter}",
                    agent_type=agent_type,
                    battery_capacity_kwh=battery_capacity,
                    initial_battery_value=battery_value,
                    registration_cost=self.config.registration_cost,
                    trades=[],
                )
                agents.append(agent)
                agent_id_counter += 1

        return agents

    def _simulate_trading(
        self,
        agents: List[Agent],
    ) -> Tuple[List[Agent], Dict[str, List[Trade]]]:
        """
        Simulate trading activity for all agents.

        Different agent types have different trading strategies:
        - RAT (Rational): Optimal timing, higher profits
        - BND (Bounded Rational): Suboptimal timing, moderate profits
        - ZI (Zero Intelligence): Random trading
        - BEH (Behavioral): Biased trading patterns

        Returns:
            Updated agents with trades, and trades by agent dict
        """
        trades_by_agent: Dict[str, List[Trade]] = {}
        trade_id_counter = 0

        for agent in agents:
            num_trades = np.random.randint(
                self.config.min_trades_per_agent,
                self.config.max_trades_per_agent + 1,
            )

            agent_trades = []

            # Set profitability based on agent type
            if agent.agent_type == AgentType.RATIONAL:
                # Rational agents make better trades
                profit_bias = 0.15  # 15% profit margin on average
                profit_std = 0.08
            elif agent.agent_type == AgentType.BOUNDED_RATIONAL:
                # Bounded rational - moderate performance
                profit_bias = 0.10
                profit_std = 0.10
            elif agent.agent_type == AgentType.ZERO_INTELLIGENCE:
                # Zero intelligence - random, lower average
                profit_bias = 0.05
                profit_std = 0.15
            else:  # BEHAVIORAL
                # Behavioral biases - slightly below optimal
                profit_bias = 0.08
                profit_std = 0.12

            for i in range(num_trades):
                # Generate trade timestamp
                timestamp = np.random.uniform(0, self.config.simulation_duration_days * 24)

                # Randomly buy or sell
                side = np.random.choice(["buy", "sell"])

                # Trade quantity (fraction of battery capacity)
                quantity = np.random.uniform(0.1, 0.5) * agent.battery_capacity_kwh

                # Base price
                base_price = np.random.uniform(self.config.min_price, self.config.max_price)

                # Adjust price based on agent type profit bias
                if side == "sell":
                    # Selling - higher is better
                    price_adjustment = np.random.normal(profit_bias, profit_std)
                    price = base_price * (1 + price_adjustment)
                    revenue = price * quantity
                else:
                    # Buying - lower is better
                    price_adjustment = np.random.normal(-profit_bias, profit_std)
                    price = base_price * (1 + price_adjustment)
                    revenue = -price * quantity

                # Calculate fees
                fees = abs(revenue) * self.config.fee_rate

                trade = Trade(
                    trade_id=f"trade_{trade_id_counter}",
                    agent_id=agent.agent_id,
                    timestamp=timestamp,
                    side=side,
                    price=price,
                    quantity=quantity,
                    revenue=revenue,
                    fees=fees,
                )
                agent_trades.append(trade)
                trade_id_counter += 1

            # Add trades to agent
            agent.trades = agent_trades
            trades_by_agent[agent.agent_id] = agent_trades

        return agents, trades_by_agent

    def _generate_order_book_snapshots(self) -> List[OrderBookSnapshot]:
        """
        Generate synthetic order book snapshots.

        Returns:
            List of OrderBookSnapshot objects
        """
        snapshots = []
        base_price = (self.config.min_price + self.config.max_price) / 2

        for i in range(self.config.order_book_snapshots_per_run):
            timestamp = float(i)

            # Random walk for base price
            base_price += np.random.normal(0, 0.1)
            base_price = np.clip(base_price, self.config.min_price, self.config.max_price)

            # Generate spread (aim for < 10% most of the time)
            spread_pct = np.random.exponential(0.03)  # Mean 3% spread
            spread_pct = min(spread_pct, 0.20)  # Cap at 20%

            half_spread = base_price * spread_pct / 2
            best_bid = base_price - half_spread
            best_ask = base_price + half_spread

            # Generate order book levels
            bids = []
            asks = []

            for level in range(5):
                bid_price = best_bid - level * 0.1
                bid_quantity = np.random.exponential(50)
                bids.append((bid_price, bid_quantity))

                ask_price = best_ask + level * 0.1
                ask_quantity = np.random.exponential(50)
                asks.append((ask_price, ask_quantity))

            snapshot = OrderBookSnapshot(
                timestamp=timestamp,
                bids=bids,
                asks=asks,
            )
            snapshots.append(snapshot)

        return snapshots

    def _generate_price_series(self) -> List[float]:
        """
        Generate synthetic price time series.

        Uses geometric Brownian motion for realistic price dynamics.

        Returns:
            List of prices
        """
        n_prices = self.config.order_book_snapshots_per_run
        mean_price = (self.config.min_price + self.config.max_price) / 2

        # GBM parameters
        mu = 0.0001  # Slight upward drift
        sigma = 0.03  # Volatility (targeting CV < 0.15)

        # Generate returns
        returns = np.random.normal(mu, sigma, n_prices - 1)

        # Generate prices
        prices = [mean_price]
        for ret in returns:
            new_price = prices[-1] * (1 + ret)
            new_price = np.clip(new_price, self.config.min_price, self.config.max_price)
            prices.append(new_price)

        return prices

    def _generate_orders(self, agents: List[Agent]) -> List[Order]:
        """
        Generate submitted orders from agent trades.

        Returns:
            List of Order objects
        """
        orders = []
        order_id_counter = 0

        for agent in agents:
            for trade in agent.trades:
                # Most orders get filled (targeting > 80% fill rate)
                fill_probability = 0.85

                if np.random.random() < fill_probability:
                    status = "filled"
                    filled_quantity = trade.quantity
                else:
                    # Partial or no fill
                    if np.random.random() < 0.5:
                        status = "partial"
                        filled_quantity = trade.quantity * np.random.uniform(0.3, 0.9)
                    else:
                        status = "cancelled"
                        filled_quantity = 0.0

                order = Order(
                    order_id=f"order_{order_id_counter}",
                    agent_id=agent.agent_id,
                    side=trade.side,
                    price=trade.price,
                    quantity=trade.quantity,
                    timestamp=trade.timestamp,
                    status=status,
                    filled_quantity=filled_quantity,
                )
                orders.append(order)
                order_id_counter += 1

        return orders

    def _calculate_welfare(self, agents: List[Agent]) -> np.ndarray:
        """
        Calculate welfare distribution across agents.

        Welfare = Total profit from trading.

        Returns:
            Array of welfare values for each agent
        """
        welfare = []

        for agent in agents:
            total_profit = sum(trade.net_revenue for trade in agent.trades)
            welfare.append(total_profit)

        return np.array(welfare)

    def _run_hypothesis_tests(
        self,
        run_results: List[SingleRunResults],
    ) -> Dict[str, EconomicHypothesisResult]:
        """
        Run all economic hypothesis tests.

        Args:
            run_results: List of single run results

        Returns:
            Dictionary of hypothesis results
        """
        # Extract data from all runs
        roi_distributions = [r.roi_distribution for r in run_results]
        welfare_distributions = [r.welfare_distribution for r in run_results]
        spread_metrics_list = [r.spread_metrics for r in run_results]
        volatility_metrics_list = [r.volatility_metrics for r in run_results]
        fill_rates = [r.fill_rate for r in run_results]

        return self.hypothesis_tester.run_all_tests(
            roi_distributions=roi_distributions,
            welfare_distributions=welfare_distributions,
            spread_metrics_list=spread_metrics_list,
            volatility_metrics_list=volatility_metrics_list,
            fill_rates=fill_rates,
        )

    def _compute_aggregate_stats(
        self,
        run_results: List[SingleRunResults],
    ) -> Dict[str, Any]:
        """
        Compute aggregate statistics across all runs.

        Args:
            run_results: List of single run results

        Returns:
            Dictionary of aggregate statistics
        """
        # ROI statistics
        all_rois = np.concatenate([r.roi_distribution.all_rois for r in run_results])
        mean_rois_per_run = [r.roi_distribution.mean_roi for r in run_results]

        # Welfare statistics
        all_welfare = np.concatenate([r.welfare_distribution for r in run_results])
        gini_per_run = [calculate_gini_coefficient(r.welfare_distribution) for r in run_results]

        # Spread statistics
        spreads_per_run = [r.spread_metrics.mean_spread_pct for r in run_results]

        # Volatility statistics
        cv_per_run = [r.volatility_metrics.cv for r in run_results]

        # Fill rate statistics
        fill_rates = [r.fill_rate for r in run_results]

        return {
            # ROI
            "roi_mean": float(np.mean(all_rois)),
            "roi_std": float(np.std(all_rois)),
            "roi_median": float(np.median(all_rois)),
            "roi_positive_rate": float(np.mean(all_rois > 0)),
            "roi_above_15pct_rate": float(np.mean(all_rois > 0.15)),
            "mean_roi_per_run_avg": float(np.mean(mean_rois_per_run)),

            # Welfare
            "welfare_mean": float(np.mean(all_welfare)),
            "welfare_std": float(np.std(all_welfare)),
            "gini_mean": float(np.mean(gini_per_run)),
            "gini_std": float(np.std(gini_per_run)),
            "gini_below_0.4_rate": float(np.mean(np.array(gini_per_run) < 0.4)),

            # Spread
            "spread_mean": float(np.mean(spreads_per_run)),
            "spread_std": float(np.std(spreads_per_run)),
            "spread_below_10pct_rate": float(np.mean(np.array(spreads_per_run) < 0.10)),

            # Volatility
            "cv_mean": float(np.mean(cv_per_run)),
            "cv_std": float(np.std(cv_per_run)),
            "cv_below_15pct_rate": float(np.mean(np.array(cv_per_run) < 0.15)),

            # Fill rate
            "fill_rate_mean": float(np.mean(fill_rates)),
            "fill_rate_std": float(np.std(fill_rates)),
            "fill_rate_above_80pct_rate": float(np.mean(np.array(fill_rates) > 0.80)),

            # Run counts
            "total_runs": len(run_results),
            "total_agents": sum(len(r.agents) for r in run_results),
        }

    def save_results(
        self,
        results: EconomicExperimentResults,
        output_dir: Optional[str] = None,
    ) -> Path:
        """
        Save experiment results to disk.

        Args:
            results: Experiment results to save
            output_dir: Output directory (uses config default if None)

        Returns:
            Path to saved results directory
        """
        output_path = Path(output_dir or self.config.output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_dir = output_path / f"run_{timestamp}"
        run_dir.mkdir(exist_ok=True)

        # Save summary JSON
        summary_file = run_dir / "results_summary.json"
        with open(summary_file, "w") as f:
            json.dump(results.to_dict(), f, indent=2)

        # Save hypothesis test report
        report_file = run_dir / "hypothesis_report.txt"
        report = self.hypothesis_tester.generate_summary_report(results.hypothesis_results)
        with open(report_file, "w") as f:
            f.write(report)

        # Save raw data if configured
        if self.config.save_raw_data:
            raw_data_file = run_dir / "raw_run_data.json"
            raw_data = [r.to_dict() for r in results.run_results]
            with open(raw_data_file, "w") as f:
                json.dump(raw_data, f, indent=2)

            # Save key arrays for analysis
            np.savez(
                run_dir / "economic_arrays.npz",
                all_rois=np.concatenate([r.roi_distribution.all_rois for r in results.run_results]),
                all_welfare=np.concatenate([r.welfare_distribution for r in results.run_results]),
                mean_rois=np.array([r.roi_distribution.mean_roi for r in results.run_results]),
                spreads=np.array([r.spread_metrics.mean_spread_pct for r in results.run_results]),
                cvs=np.array([r.volatility_metrics.cv for r in results.run_results]),
                fill_rates=np.array([r.fill_rate for r in results.run_results]),
            )

        # Generate plots if configured
        if self.config.generate_plots:
            self._generate_and_save_plots(results, run_dir)

        logger.info(f"Results saved to {run_dir}")
        return run_dir

    def _generate_and_save_plots(
        self,
        results: EconomicExperimentResults,
        output_dir: Path,
    ) -> None:
        """Generate and save visualization plots."""
        try:
            visualizer = EconomicVisualizer(str(output_dir / "plots"))

            # Use first run's detailed data for some plots
            first_run = results.run_results[0]

            # Aggregate ROI distribution for violin plot
            # Merge all ROI by type across runs
            merged_roi_by_type = {}
            for run_result in results.run_results:
                for agent_type, rois in run_result.roi_distribution.roi_by_type.items():
                    if agent_type not in merged_roi_by_type:
                        merged_roi_by_type[agent_type] = []
                    merged_roi_by_type[agent_type].extend(rois.tolist())

            all_rois = np.concatenate([r.roi_distribution.all_rois for r in results.run_results])

            merged_distribution = RoiDistribution(
                all_rois=all_rois,
                roi_by_type={k: np.array(v) for k, v in merged_roi_by_type.items()},
                mean_roi=float(np.mean(all_rois)),
                median_roi=float(np.median(all_rois)),
                std_roi=float(np.std(all_rois)),
                min_roi=float(np.min(all_rois)),
                max_roi=float(np.max(all_rois)),
                positive_roi_rate=float(np.mean(all_rois > 0)),
                results_by_agent={},
            )

            # Aggregate welfare distribution
            merged_welfare = np.concatenate([r.welfare_distribution for r in results.run_results])

            # Generate plots
            visualizer.generate_all_plots(
                roi_distribution=merged_distribution,
                welfare_distribution=merged_welfare,
                prices=first_run.prices,
                order_book_snapshots=first_run.order_book_snapshots,
                hypothesis_results=results.hypothesis_results,
                roi_by_size=results.roi_by_battery_size,
                show=False,
            )

            visualizer.close_all()

        except ImportError:
            logger.warning("matplotlib not available, skipping plot generation")
        except Exception as e:
            logger.error(f"Error generating plots: {e}")

    @staticmethod
    def load_results(results_dir: str) -> Dict[str, Any]:
        """
        Load saved experiment results.

        Args:
            results_dir: Path to results directory

        Returns:
            Dictionary with loaded results
        """
        results_path = Path(results_dir)

        loaded = {}

        summary_file = results_path / "results_summary.json"
        if summary_file.exists():
            with open(summary_file) as f:
                loaded["summary"] = json.load(f)

        raw_file = results_path / "raw_run_data.json"
        if raw_file.exists():
            with open(raw_file) as f:
                loaded["raw_data"] = json.load(f)

        arrays_file = results_path / "economic_arrays.npz"
        if arrays_file.exists():
            loaded["arrays"] = dict(np.load(arrays_file))

        return loaded


def run_quick_economic_test() -> EconomicExperimentResults:
    """
    Run a quick test with minimal configuration.

    Useful for verifying the implementation works.
    """
    config = EconomicExperimentConfig(
        num_agents_per_type=10,
        num_runs=5,
        seed=42,
        bootstrap_iterations=1000,
        order_book_snapshots_per_run=50,
        generate_plots=False,
    )

    experiment = EconomicPerformanceExperiment(config)
    results = experiment.run()

    print(results.summary())
    print("\n")
    print(experiment.hypothesis_tester.generate_summary_report(results.hypothesis_results))

    return results


def run_full_economic_experiment(
    num_runs: int = 100,
    seed: Optional[int] = None,
    output_dir: str = "results/domain2",
) -> EconomicExperimentResults:
    """
    Run full experiment with default configuration.

    Args:
        num_runs: Number of experiment runs
        seed: Random seed for reproducibility
        output_dir: Directory for saving results

    Returns:
        Complete experiment results
    """
    config = EconomicExperimentConfig(
        num_runs=num_runs,
        seed=seed,
        output_dir=output_dir,
    )

    experiment = EconomicPerformanceExperiment(config)

    def progress(current, total):
        if current % 10 == 0 or current == total:
            print(f"Progress: {current}/{total} runs completed")

    results = experiment.run(progress_callback=progress)
    experiment.save_results(results)

    return results


if __name__ == "__main__":
    # Run quick test when executed directly
    logging.basicConfig(level=logging.INFO)
    run_quick_economic_test()
