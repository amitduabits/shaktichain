"""
Hypothesis Tests for SHAKTI-CHAIN Agent Behavior Domain (Domain 5).

Implements statistical tests for all agent behavior hypotheses:
- H5.1: Incentive Compatibility (Exact binomial test)
- H5.2: Convergence Under Rational Agents (ADF test)
- H5.3: Robustness to Bounded Rationality (Two-sample t-test)
- H5.4: Manipulation Resistance (One-sample t-test)
- H5.5: Sybil Attack Resistance (Regression slope test)
- H5.6: Collusion Resistance (Two-sample t-test)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np
from scipy import stats as scipy_stats

from .incentive_compatibility import IncentiveCompatibilityTester, ICTestResult
from .convergence_analyzer import ConvergenceAnalyzer, ConvergenceTestResult, RobustnessTestResult
from .manipulation_simulator import ManipulationSimulator, ManipulationTestResult
from .sybil_tester import SybilTester, ComprehensiveSybilResult
from .collusion_detector import CollusionSimulator, CollusionTestResult

logger = logging.getLogger(__name__)


@dataclass
class AgentHypothesisResult:
    """
    Result of a single hypothesis test.

    Attributes:
        hypothesis_id: Hypothesis identifier (e.g., "H5.1")
        description: Human-readable description
        test_type: Statistical test used
        passed: Whether hypothesis passed
        observed_value: Observed test statistic or metric
        threshold: Threshold for passing
        test_statistic: Statistical test statistic
        p_value: P-value
        confidence_interval: Optional CI
        effect_size: Optional effect size
        decision: Statistical decision description
        additional_info: Extra information
    """
    hypothesis_id: str
    description: str
    test_type: str
    passed: bool
    observed_value: float
    threshold: float
    test_statistic: float
    p_value: float
    confidence_interval: Optional[tuple] = None
    effect_size: Optional[float] = None
    decision: str = ""
    additional_info: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "hypothesis_id": self.hypothesis_id,
            "description": self.description,
            "test_type": self.test_type,
            "passed": self.passed,
            "observed_value": float(self.observed_value),
            "threshold": float(self.threshold),
            "test_statistic": float(self.test_statistic),
            "p_value": float(self.p_value),
            "confidence_interval": self.confidence_interval,
            "effect_size": float(self.effect_size) if self.effect_size else None,
            "decision": self.decision,
        }


class AgentHypothesisTester:
    """
    Run all hypothesis tests for Domain 5: Agent Behavior.

    Hypotheses:
    - H5.1: Incentive Compatibility - Truthful bidding is optimal
    - H5.2: Convergence - Prices converge within 50 rounds
    - H5.3: Robustness - Efficiency >= 85% with mixed agents
    - H5.4: Manipulation Resistance - Manipulation gain < 5%
    - H5.5: Sybil Resistance - No profit from splitting identities
    - H5.6: Collusion Resistance - Collusion gain < 10%
    """

    def __init__(
        self,
        alpha: float = 0.05,
        num_agents: int = 30,
        seed: Optional[int] = None,
    ):
        """
        Initialize hypothesis tester.

        Args:
            alpha: Significance level
            num_agents: Number of agents for simulations
            seed: Random seed
        """
        self.alpha = alpha
        self.num_agents = num_agents
        self.seed = seed

    def test_h5_1_incentive_compatibility(
        self,
        ic_result: Optional[ICTestResult] = None,
        n_rounds: int = 30,
    ) -> AgentHypothesisResult:
        """
        Test H5.1: Truthful bidding yields utility >= any deviation.

        Uses exact binomial test on deviation success rate.
        H0: Deviation success rate >= 0.5 (profitable to deviate)
        H1: Deviation success rate < 0.5 (truthful is better)

        Args:
            ic_result: Pre-computed IC test result
            n_rounds: Rounds to run if computing

        Returns:
            AgentHypothesisResult
        """
        if ic_result is None:
            tester = IncentiveCompatibilityTester(
                num_buyers=self.num_agents // 2,
                num_sellers=self.num_agents // 2,
                seed=self.seed,
            )
            ic_result = tester.run_comprehensive_test(
                n_agents=self.num_agents,
                n_rounds=n_rounds,
            )

        # Binomial test
        success_rate = ic_result.deviation_success_rate
        p_value = ic_result.binomial_p_value

        # IC holds if success rate is low
        threshold = 0.10  # Less than 10% of deviations profitable
        passed = success_rate < threshold and p_value < self.alpha

        return AgentHypothesisResult(
            hypothesis_id="H5.1",
            description="Incentive Compatibility",
            test_type="Exact Binomial Test",
            passed=passed,
            observed_value=success_rate,
            threshold=threshold,
            test_statistic=ic_result.deviation_success_count,
            p_value=p_value,
            effect_size=ic_result.mean_deviation_gain,
            decision="reject_null" if passed else "fail_to_reject",
            additional_info={
                "total_tests": ic_result.total_tests,
                "max_deviation_gain": ic_result.max_deviation_gain,
            },
        )

    def test_h5_2_convergence(
        self,
        convergence_result: Optional[ConvergenceTestResult] = None,
        num_rounds: int = 50,
    ) -> AgentHypothesisResult:
        """
        Test H5.2: Prices converge within 50 rounds.

        Uses Augmented Dickey-Fuller test for stationarity.
        H0: Unit root exists (no convergence)
        H1: Stationary (converged)

        Args:
            convergence_result: Pre-computed convergence result
            num_rounds: Rounds to simulate if computing

        Returns:
            AgentHypothesisResult
        """
        if convergence_result is None:
            from .convergence_analyzer import simulate_convergence_test
            convergence_result = simulate_convergence_test(
                num_agents=self.num_agents,
                num_rounds=num_rounds,
                seed=self.seed,
            )

        threshold = 50  # Must converge within 50 rounds
        passed = convergence_result.converged and (
            convergence_result.convergence_round is None or
            convergence_result.convergence_round <= threshold
        )

        return AgentHypothesisResult(
            hypothesis_id="H5.2",
            description="Convergence Under Rational Agents",
            test_type="Augmented Dickey-Fuller Test",
            passed=passed,
            observed_value=convergence_result.convergence_round or num_rounds,
            threshold=threshold,
            test_statistic=convergence_result.adf_statistic,
            p_value=convergence_result.adf_p_value,
            effect_size=convergence_result.price_deviation,
            decision="reject_null" if passed else "fail_to_reject",
            additional_info={
                "final_price": convergence_result.final_price,
                "equilibrium_price": convergence_result.equilibrium_price,
                "critical_values": convergence_result.critical_values,
            },
        )

    def test_h5_3_robustness(
        self,
        robustness_result: Optional[RobustnessTestResult] = None,
        bounded_rational_fraction: float = 0.50,
        efficiency_threshold: float = 0.85,
    ) -> AgentHypothesisResult:
        """
        Test H5.3: Efficiency >= 85% with 50% bounded rational agents.

        Uses two-sample t-test comparing efficiency distributions.
        H0: Efficiency < 85%
        H1: Efficiency >= 85%

        Args:
            robustness_result: Pre-computed robustness result
            bounded_rational_fraction: Fraction of BR agents
            efficiency_threshold: Required efficiency

        Returns:
            AgentHypothesisResult
        """
        if robustness_result is None:
            from .convergence_analyzer import simulate_robustness_test
            robustness_result = simulate_robustness_test(
                bounded_rational_fraction=bounded_rational_fraction,
                efficiency_threshold=efficiency_threshold,
                seed=self.seed,
            )

        passed = robustness_result.is_robust

        return AgentHypothesisResult(
            hypothesis_id="H5.3",
            description="Robustness to Bounded Rationality",
            test_type="Two-Sample t-Test",
            passed=passed,
            observed_value=robustness_result.efficiency_with_mixed,
            threshold=efficiency_threshold,
            test_statistic=robustness_result.t_statistic,
            p_value=robustness_result.p_value,
            effect_size=robustness_result.effect_size,
            decision="reject_null" if passed else "fail_to_reject",
            additional_info={
                "efficiency_rational": robustness_result.efficiency_with_rational,
                "bounded_rational_fraction": bounded_rational_fraction,
            },
        )

    def test_h5_4_manipulation_resistance(
        self,
        manipulation_result: Optional[ManipulationTestResult] = None,
        gain_threshold: float = 0.05,
    ) -> AgentHypothesisResult:
        """
        Test H5.4: Manipulation gain < 5%.

        Uses one-sample t-test on manipulation gains.
        H0: Mean gain >= 5%
        H1: Mean gain < 5%

        Args:
            manipulation_result: Pre-computed manipulation result
            gain_threshold: Maximum acceptable gain

        Returns:
            AgentHypothesisResult
        """
        if manipulation_result is None:
            from .manipulation_simulator import simulate_manipulation_test
            manipulation_result = simulate_manipulation_test(
                num_agents=self.num_agents,
                seed=self.seed,
            )

        passed = manipulation_result.is_resistant

        return AgentHypothesisResult(
            hypothesis_id="H5.4",
            description="Manipulation Resistance",
            test_type="One-Sample t-Test",
            passed=passed,
            observed_value=manipulation_result.max_manipulation_gain,
            threshold=gain_threshold,
            test_statistic=manipulation_result.t_statistic,
            p_value=manipulation_result.p_value,
            effect_size=manipulation_result.mean_manipulation_gain,
            decision="reject_null" if passed else "fail_to_reject",
            additional_info={
                "strategies_tested": list(manipulation_result.results_by_strategy.keys()),
            },
        )

    def test_h5_5_sybil_resistance(
        self,
        sybil_result: Optional[ComprehensiveSybilResult] = None,
    ) -> AgentHypothesisResult:
        """
        Test H5.5: Utility with n identities <= utility with 1.

        Uses regression slope test.
        H0: Slope > 0 (Sybil profitable)
        H1: Slope <= 0 (Sybil not profitable)

        Args:
            sybil_result: Pre-computed Sybil result

        Returns:
            AgentHypothesisResult
        """
        if sybil_result is None:
            from .sybil_tester import simulate_comprehensive_sybil_test
            sybil_result = simulate_comprehensive_sybil_test(
                n_tests=10,
                seed=self.seed,
            )

        passed = sybil_result.is_resistant

        return AgentHypothesisResult(
            hypothesis_id="H5.5",
            description="Sybil Attack Resistance",
            test_type="Regression Slope Test",
            passed=passed,
            observed_value=sybil_result.mean_slope,
            threshold=0.0,  # Slope should be <= 0
            test_statistic=sybil_result.t_statistic,
            p_value=sybil_result.p_value,
            effect_size=sybil_result.positive_slope_fraction,
            decision="reject_null" if passed else "fail_to_reject",
            additional_info={
                "slope_std": sybil_result.slope_std,
                "positive_slope_fraction": sybil_result.positive_slope_fraction,
            },
        )

    def test_h5_6_collusion_resistance(
        self,
        collusion_result: Optional[CollusionTestResult] = None,
        gain_threshold: float = 0.10,
    ) -> AgentHypothesisResult:
        """
        Test H5.6: Collusion gain < 10%.

        Uses two-sample t-test comparing colluding vs honest profits.
        H0: Collusion gain >= 10%
        H1: Collusion gain < 10%

        Args:
            collusion_result: Pre-computed collusion result
            gain_threshold: Maximum acceptable gain

        Returns:
            AgentHypothesisResult
        """
        if collusion_result is None:
            from .collusion_detector import simulate_collusion_test
            collusion_result = simulate_collusion_test(
                num_agents=self.num_agents,
                seed=self.seed,
            )

        passed = collusion_result.is_resistant

        return AgentHypothesisResult(
            hypothesis_id="H5.6",
            description="Collusion Resistance",
            test_type="Two-Sample t-Test",
            passed=passed,
            observed_value=collusion_result.max_collusion_gain,
            threshold=gain_threshold,
            test_statistic=collusion_result.t_statistic,
            p_value=collusion_result.p_value,
            effect_size=collusion_result.mean_collusion_gain,
            decision="reject_null" if passed else "fail_to_reject",
            additional_info={
                "strategies_tested": list(collusion_result.results_by_strategy.keys()),
                "coalition_size_effect": collusion_result.coalition_size_effect,
            },
        )

    def run_all_tests(
        self,
        ic_result: Optional[ICTestResult] = None,
        convergence_result: Optional[ConvergenceTestResult] = None,
        robustness_result: Optional[RobustnessTestResult] = None,
        manipulation_result: Optional[ManipulationTestResult] = None,
        sybil_result: Optional[ComprehensiveSybilResult] = None,
        collusion_result: Optional[CollusionTestResult] = None,
    ) -> Dict[str, AgentHypothesisResult]:
        """
        Run all hypothesis tests.

        Args:
            ic_result: Pre-computed IC result
            convergence_result: Pre-computed convergence result
            robustness_result: Pre-computed robustness result
            manipulation_result: Pre-computed manipulation result
            sybil_result: Pre-computed Sybil result
            collusion_result: Pre-computed collusion result

        Returns:
            Dictionary mapping hypothesis ID to result
        """
        results = {}

        logger.info("Testing H5.1: Incentive Compatibility...")
        results["H5.1"] = self.test_h5_1_incentive_compatibility(ic_result)

        logger.info("Testing H5.2: Convergence...")
        results["H5.2"] = self.test_h5_2_convergence(convergence_result)

        logger.info("Testing H5.3: Robustness to Bounded Rationality...")
        results["H5.3"] = self.test_h5_3_robustness(robustness_result)

        logger.info("Testing H5.4: Manipulation Resistance...")
        results["H5.4"] = self.test_h5_4_manipulation_resistance(manipulation_result)

        logger.info("Testing H5.5: Sybil Resistance...")
        results["H5.5"] = self.test_h5_5_sybil_resistance(sybil_result)

        logger.info("Testing H5.6: Collusion Resistance...")
        results["H5.6"] = self.test_h5_6_collusion_resistance(collusion_result)

        return results

    def generate_summary(
        self,
        results: Dict[str, AgentHypothesisResult],
    ) -> str:
        """
        Generate summary of hypothesis test results.

        Args:
            results: Dictionary of hypothesis results

        Returns:
            Summary string
        """
        passed = sum(1 for r in results.values() if r.passed)
        total = len(results)

        lines = [
            "Domain 5: Agent Behavior Hypothesis Test Summary",
            "=" * 50,
            f"Passed: {passed}/{total}",
            "",
            "Individual Results:",
        ]

        for h_id in sorted(results.keys()):
            result = results[h_id]
            status = "PASS" if result.passed else "FAIL"
            lines.append(f"  {h_id} ({result.description}): {status}")
            lines.append(f"      Observed: {result.observed_value:.4f}, Threshold: {result.threshold:.4f}")
            lines.append(f"      p-value: {result.p_value:.6f}")

        return "\n".join(lines)
