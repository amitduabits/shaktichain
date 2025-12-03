"""Statistical tests and confidence intervals for backtesting.

Provides:
- Bootstrap confidence intervals
- T-tests vs baselines
- Monte Carlo simulation
- Statistical significance testing
"""

import numpy as np
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from scipy import stats
import logging

from .backtester import BacktestRun

logger = logging.getLogger(__name__)


@dataclass
class BootstrapResult:
    """Results from bootstrap analysis."""
    metric_name: str
    point_estimate: float
    ci_lower: float
    ci_upper: float
    ci_level: float
    std_error: float
    bootstrap_distribution: List[float]


@dataclass
class HypothesisTestResult:
    """Results from hypothesis test."""
    test_name: str
    statistic: float
    p_value: float
    is_significant: bool
    confidence_level: float
    effect_size: float
    interpretation: str


@dataclass
class MonteCarloResult:
    """Results from Monte Carlo simulation."""
    n_simulations: int
    metric_name: str
    mean: float
    std: float
    percentile_5: float
    percentile_25: float
    median: float
    percentile_75: float
    percentile_95: float
    distribution: List[float]
    probability_positive: float
    probability_above_target: float
    target: float


class BootstrapCI:
    """Bootstrap confidence interval calculator."""

    def __init__(
        self,
        n_bootstrap: int = 10000,
        random_state: Optional[int] = None,
    ):
        """Initialize bootstrap calculator.

        Args:
            n_bootstrap: Number of bootstrap samples
            random_state: Random seed
        """
        self.n_bootstrap = n_bootstrap
        self.rng = np.random.default_rng(random_state)

    def calculate(
        self,
        data: np.ndarray,
        statistic_func: callable = np.mean,
        confidence_level: float = 0.95,
    ) -> BootstrapResult:
        """Calculate bootstrap confidence interval.

        Args:
            data: Sample data
            statistic_func: Function to calculate statistic
            confidence_level: Confidence level (0-1)

        Returns:
            BootstrapResult with CI bounds
        """
        n = len(data)
        bootstrap_stats = []

        for _ in range(self.n_bootstrap):
            sample = self.rng.choice(data, size=n, replace=True)
            stat = statistic_func(sample)
            bootstrap_stats.append(stat)

        bootstrap_stats = np.array(bootstrap_stats)
        point_estimate = statistic_func(data)

        alpha = 1 - confidence_level
        ci_lower = np.percentile(bootstrap_stats, alpha / 2 * 100)
        ci_upper = np.percentile(bootstrap_stats, (1 - alpha / 2) * 100)
        std_error = np.std(bootstrap_stats)

        return BootstrapResult(
            metric_name=statistic_func.__name__,
            point_estimate=point_estimate,
            ci_lower=ci_lower,
            ci_upper=ci_upper,
            ci_level=confidence_level,
            std_error=std_error,
            bootstrap_distribution=bootstrap_stats.tolist(),
        )

    def calculate_multiple(
        self,
        data: np.ndarray,
        statistics: Dict[str, callable],
        confidence_level: float = 0.95,
    ) -> Dict[str, BootstrapResult]:
        """Calculate CIs for multiple statistics.

        Args:
            data: Sample data
            statistics: Dictionary of {name: function}
            confidence_level: Confidence level

        Returns:
            Dictionary of BootstrapResults
        """
        results = {}
        for name, func in statistics.items():
            result = self.calculate(data, func, confidence_level)
            result.metric_name = name
            results[name] = result
        return results


class StatisticalTests:
    """Statistical hypothesis testing for strategy comparison."""

    def __init__(self, alpha: float = 0.05):
        """Initialize test suite.

        Args:
            alpha: Significance level
        """
        self.alpha = alpha

    def t_test_vs_baseline(
        self,
        strategy_returns: np.ndarray,
        baseline_returns: np.ndarray,
        alternative: str = 'greater',
    ) -> HypothesisTestResult:
        """Perform paired t-test against baseline.

        Args:
            strategy_returns: Strategy daily returns
            baseline_returns: Baseline daily returns
            alternative: 'two-sided', 'greater', or 'less'

        Returns:
            HypothesisTestResult
        """
        # Ensure same length
        n = min(len(strategy_returns), len(baseline_returns))
        strategy_returns = strategy_returns[:n]
        baseline_returns = baseline_returns[:n]

        # Paired t-test
        t_stat, p_value = stats.ttest_rel(
            strategy_returns,
            baseline_returns,
            alternative=alternative,
        )

        # Effect size (Cohen's d)
        diff = strategy_returns - baseline_returns
        effect_size = np.mean(diff) / (np.std(diff) + 1e-8)

        is_significant = p_value < self.alpha

        interpretation = self._interpret_t_test(
            is_significant, t_stat, effect_size, alternative
        )

        return HypothesisTestResult(
            test_name="Paired t-test",
            statistic=t_stat,
            p_value=p_value,
            is_significant=is_significant,
            confidence_level=1 - self.alpha,
            effect_size=effect_size,
            interpretation=interpretation,
        )

    def welch_t_test(
        self,
        strategy_returns: np.ndarray,
        baseline_returns: np.ndarray,
        alternative: str = 'greater',
    ) -> HypothesisTestResult:
        """Perform Welch's t-test (unequal variances).

        Args:
            strategy_returns: Strategy returns
            baseline_returns: Baseline returns
            alternative: 'two-sided', 'greater', or 'less'

        Returns:
            HypothesisTestResult
        """
        t_stat, p_value = stats.ttest_ind(
            strategy_returns,
            baseline_returns,
            equal_var=False,
            alternative=alternative,
        )

        # Effect size
        pooled_std = np.sqrt(
            (np.std(strategy_returns)**2 + np.std(baseline_returns)**2) / 2
        )
        effect_size = (np.mean(strategy_returns) - np.mean(baseline_returns)) / (pooled_std + 1e-8)

        is_significant = p_value < self.alpha

        interpretation = self._interpret_t_test(
            is_significant, t_stat, effect_size, alternative
        )

        return HypothesisTestResult(
            test_name="Welch's t-test",
            statistic=t_stat,
            p_value=p_value,
            is_significant=is_significant,
            confidence_level=1 - self.alpha,
            effect_size=effect_size,
            interpretation=interpretation,
        )

    def mann_whitney_test(
        self,
        strategy_returns: np.ndarray,
        baseline_returns: np.ndarray,
        alternative: str = 'greater',
    ) -> HypothesisTestResult:
        """Mann-Whitney U test (non-parametric).

        Args:
            strategy_returns: Strategy returns
            baseline_returns: Baseline returns
            alternative: 'two-sided', 'greater', or 'less'

        Returns:
            HypothesisTestResult
        """
        u_stat, p_value = stats.mannwhitneyu(
            strategy_returns,
            baseline_returns,
            alternative=alternative,
        )

        # Effect size (rank-biserial correlation)
        n1, n2 = len(strategy_returns), len(baseline_returns)
        effect_size = 1 - (2 * u_stat) / (n1 * n2)

        is_significant = p_value < self.alpha

        interpretation = f"{'Significant' if is_significant else 'Not significant'} difference (p={p_value:.4f})"

        return HypothesisTestResult(
            test_name="Mann-Whitney U",
            statistic=u_stat,
            p_value=p_value,
            is_significant=is_significant,
            confidence_level=1 - self.alpha,
            effect_size=effect_size,
            interpretation=interpretation,
        )

    def sharpe_ratio_test(
        self,
        strategy_returns: np.ndarray,
        baseline_returns: np.ndarray,
        risk_free_rate: float = 0.04 / 365,
    ) -> HypothesisTestResult:
        """Test difference in Sharpe ratios.

        Uses Jobson-Korkie test with Memmel correction.

        Args:
            strategy_returns: Strategy returns
            baseline_returns: Baseline returns
            risk_free_rate: Daily risk-free rate

        Returns:
            HypothesisTestResult
        """
        # Calculate Sharpe ratios
        sr1 = (np.mean(strategy_returns) - risk_free_rate) / (np.std(strategy_returns) + 1e-8)
        sr2 = (np.mean(baseline_returns) - risk_free_rate) / (np.std(baseline_returns) + 1e-8)

        n = len(strategy_returns)

        # Variance of difference (simplified)
        var1, var2 = np.var(strategy_returns), np.var(baseline_returns)
        cov12 = np.cov(strategy_returns, baseline_returns)[0, 1]

        # Asymptotic variance of SR difference
        var_diff = (1/n) * (2 - 2 * cov12 / np.sqrt(var1 * var2 + 1e-8))
        se_diff = np.sqrt(var_diff + 1e-8)

        # Test statistic
        z_stat = (sr1 - sr2) / se_diff
        p_value = 1 - stats.norm.cdf(z_stat)

        is_significant = p_value < self.alpha

        interpretation = (
            f"Strategy SR: {sr1:.3f}, Baseline SR: {sr2:.3f}. "
            f"{'Significant' if is_significant else 'Not significant'} improvement (p={p_value:.4f})"
        )

        return HypothesisTestResult(
            test_name="Sharpe Ratio Difference",
            statistic=z_stat,
            p_value=p_value,
            is_significant=is_significant,
            confidence_level=1 - self.alpha,
            effect_size=sr1 - sr2,
            interpretation=interpretation,
        )

    def _interpret_t_test(
        self,
        is_significant: bool,
        t_stat: float,
        effect_size: float,
        alternative: str,
    ) -> str:
        """Generate interpretation string for t-test."""
        sig_str = "statistically significant" if is_significant else "not statistically significant"

        if abs(effect_size) < 0.2:
            effect_str = "negligible"
        elif abs(effect_size) < 0.5:
            effect_str = "small"
        elif abs(effect_size) < 0.8:
            effect_str = "medium"
        else:
            effect_str = "large"

        direction = "higher" if t_stat > 0 else "lower"

        return f"The difference is {sig_str} with {effect_str} effect size. Strategy returns are {direction} than baseline."

    def run_all_tests(
        self,
        strategy_returns: np.ndarray,
        baseline_returns: np.ndarray,
    ) -> Dict[str, HypothesisTestResult]:
        """Run all statistical tests.

        Args:
            strategy_returns: Strategy returns
            baseline_returns: Baseline returns

        Returns:
            Dictionary of test results
        """
        return {
            'paired_t_test': self.t_test_vs_baseline(strategy_returns, baseline_returns),
            'welch_t_test': self.welch_t_test(strategy_returns, baseline_returns),
            'mann_whitney': self.mann_whitney_test(strategy_returns, baseline_returns),
            'sharpe_ratio': self.sharpe_ratio_test(strategy_returns, baseline_returns),
        }


class MonteCarloSimulation:
    """Monte Carlo simulation for robustness testing."""

    def __init__(
        self,
        n_simulations: int = 1000,
        random_state: Optional[int] = None,
    ):
        """Initialize Monte Carlo simulator.

        Args:
            n_simulations: Number of simulations
            random_state: Random seed
        """
        self.n_simulations = n_simulations
        self.rng = np.random.default_rng(random_state)

    def simulate_returns(
        self,
        historical_returns: np.ndarray,
        n_days: int = 365,
        method: str = 'bootstrap',
        target_return: float = 0.15,
    ) -> MonteCarloResult:
        """Simulate future returns based on historical data.

        Args:
            historical_returns: Historical daily returns
            n_days: Number of days to simulate
            method: 'bootstrap' or 'parametric'
            target_return: Target annual return for probability calculation

        Returns:
            MonteCarloResult with distribution
        """
        simulated_total_returns = []

        for _ in range(self.n_simulations):
            if method == 'bootstrap':
                # Bootstrap from historical returns
                sim_returns = self.rng.choice(historical_returns, size=n_days, replace=True)
            else:
                # Parametric (assume normal)
                mean = np.mean(historical_returns)
                std = np.std(historical_returns)
                sim_returns = self.rng.normal(mean, std, size=n_days)

            # Calculate total return
            total_return = np.prod(1 + sim_returns) - 1
            simulated_total_returns.append(total_return)

        simulated_total_returns = np.array(simulated_total_returns)

        # Convert target to same period
        daily_target = (1 + target_return) ** (1/365) - 1
        period_target = (1 + daily_target) ** n_days - 1

        return MonteCarloResult(
            n_simulations=self.n_simulations,
            metric_name='total_return',
            mean=np.mean(simulated_total_returns),
            std=np.std(simulated_total_returns),
            percentile_5=np.percentile(simulated_total_returns, 5),
            percentile_25=np.percentile(simulated_total_returns, 25),
            median=np.median(simulated_total_returns),
            percentile_75=np.percentile(simulated_total_returns, 75),
            percentile_95=np.percentile(simulated_total_returns, 95),
            distribution=simulated_total_returns.tolist(),
            probability_positive=np.mean(simulated_total_returns > 0),
            probability_above_target=np.mean(simulated_total_returns > period_target),
            target=target_return,
        )

    def simulate_drawdown(
        self,
        historical_returns: np.ndarray,
        n_days: int = 365,
    ) -> MonteCarloResult:
        """Simulate maximum drawdown distribution.

        Args:
            historical_returns: Historical returns
            n_days: Simulation period

        Returns:
            MonteCarloResult with drawdown distribution
        """
        simulated_drawdowns = []

        for _ in range(self.n_simulations):
            sim_returns = self.rng.choice(historical_returns, size=n_days, replace=True)

            # Calculate equity curve
            equity = np.cumprod(1 + sim_returns)
            running_max = np.maximum.accumulate(equity)
            drawdown = (equity - running_max) / running_max

            max_dd = np.min(drawdown)
            simulated_drawdowns.append(max_dd)

        simulated_drawdowns = np.array(simulated_drawdowns)

        return MonteCarloResult(
            n_simulations=self.n_simulations,
            metric_name='max_drawdown',
            mean=np.mean(simulated_drawdowns),
            std=np.std(simulated_drawdowns),
            percentile_5=np.percentile(simulated_drawdowns, 5),
            percentile_25=np.percentile(simulated_drawdowns, 25),
            median=np.median(simulated_drawdowns),
            percentile_75=np.percentile(simulated_drawdowns, 75),
            percentile_95=np.percentile(simulated_drawdowns, 95),
            distribution=simulated_drawdowns.tolist(),
            probability_positive=0,  # Drawdowns are always negative
            probability_above_target=np.mean(simulated_drawdowns > -0.1),  # Above -10%
            target=-0.1,
        )

    def stress_test(
        self,
        historical_returns: np.ndarray,
        stress_scenarios: Dict[str, float],
    ) -> Dict[str, float]:
        """Run stress test scenarios.

        Args:
            historical_returns: Historical returns
            stress_scenarios: Dictionary of {scenario_name: return_multiplier}

        Returns:
            Dictionary of scenario results
        """
        base_return = np.prod(1 + historical_returns) - 1
        results = {'base': base_return}

        for scenario, multiplier in stress_scenarios.items():
            stressed_returns = historical_returns * multiplier
            stressed_return = np.prod(1 + stressed_returns) - 1
            results[scenario] = stressed_return

        return results
