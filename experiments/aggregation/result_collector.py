"""
Result Collector Module.

Gathers and aggregates hypothesis test results from all experiment domains.
Provides unified access to results for cross-domain analysis.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)


@dataclass
class HypothesisResult:
    """
    Individual hypothesis test result.

    Attributes:
        hypothesis_id: Unique identifier (e.g., "H1.1")
        hypothesis_name: Descriptive name
        domain_id: Domain this hypothesis belongs to
        null_hypothesis: H0 statement
        alternative_hypothesis: H1 statement
        test_name: Statistical test used
        test_statistic: Value of test statistic
        p_value: P-value from test
        effect_size: Computed effect size
        effect_size_name: Name of effect size measure
        confidence_interval: CI for effect
        sample_size: Number of samples
        power: Statistical power
        decision: "reject_null" or "fail_to_reject_null"
        alpha: Significance level used
        is_critical: Whether this is a critical hypothesis
        timestamp: When test was run
        metadata: Additional test metadata
    """
    hypothesis_id: str
    hypothesis_name: str
    domain_id: str
    null_hypothesis: str
    alternative_hypothesis: str
    test_name: str
    test_statistic: float
    p_value: float
    effect_size: float
    effect_size_name: str
    confidence_interval: Tuple[Optional[float], Optional[float]]
    sample_size: int
    power: Optional[float]
    decision: str
    alpha: float = 0.05
    is_critical: bool = False
    timestamp: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        """Whether hypothesis was supported (null rejected)."""
        return self.decision == "reject_null"

    @property
    def is_near_miss(self) -> bool:
        """Whether result barely passed (p close to alpha)."""
        return self.passed and self.p_value > (self.alpha * 0.2)

    @property
    def is_strong_result(self) -> bool:
        """Whether result is strongly significant."""
        return self.passed and self.p_value < 0.001

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "hypothesis_id": self.hypothesis_id,
            "hypothesis_name": self.hypothesis_name,
            "domain_id": self.domain_id,
            "null_hypothesis": self.null_hypothesis,
            "alternative_hypothesis": self.alternative_hypothesis,
            "test_name": self.test_name,
            "test_statistic": self.test_statistic,
            "p_value": self.p_value,
            "effect_size": self.effect_size,
            "effect_size_name": self.effect_size_name,
            "confidence_interval": list(self.confidence_interval),
            "sample_size": self.sample_size,
            "power": self.power,
            "decision": self.decision,
            "alpha": self.alpha,
            "is_critical": self.is_critical,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HypothesisResult":
        """Create from dictionary."""
        ci = data.get("confidence_interval", [None, None])
        if isinstance(ci, list):
            ci = tuple(ci)
        return cls(
            hypothesis_id=data.get("hypothesis_id", ""),
            hypothesis_name=data.get("hypothesis_name", ""),
            domain_id=data.get("domain_id", ""),
            null_hypothesis=data.get("null_hypothesis", ""),
            alternative_hypothesis=data.get("alternative_hypothesis", data.get("alt_hypothesis", "")),
            test_name=data.get("test_name", ""),
            test_statistic=float(data.get("test_statistic", data.get("statistic", 0))),
            p_value=float(data.get("p_value", 1.0)),
            effect_size=float(data.get("effect_size", 0)),
            effect_size_name=data.get("effect_size_name", ""),
            confidence_interval=ci,
            sample_size=int(data.get("sample_size", 0)),
            power=data.get("power"),
            decision=data.get("decision", "fail_to_reject_null"),
            alpha=float(data.get("alpha", 0.05)),
            is_critical=data.get("is_critical", False),
            timestamp=data.get("timestamp", ""),
            metadata=data.get("metadata", {}),
        )


@dataclass
class DomainResults:
    """
    Aggregated results for a single experiment domain.

    Attributes:
        domain_id: Unique domain identifier
        domain_name: Human-readable domain name
        description: Domain description
        hypotheses_tested: Number of hypotheses tested
        hypotheses_supported: Number that rejected null
        hypotheses_failed: Number that failed to reject null
        critical_failures: List of critical hypothesis IDs that failed
        key_findings: Major findings from this domain
        effect_sizes: Map of hypothesis ID to effect size
        confidence_intervals: Map of hypothesis ID to CI
        raw_results: List of individual hypothesis results
        metadata: Additional domain metadata
    """
    domain_id: str
    domain_name: str
    description: str = ""
    hypotheses_tested: int = 0
    hypotheses_supported: int = 0
    hypotheses_failed: int = 0
    critical_failures: List[str] = field(default_factory=list)
    key_findings: List[str] = field(default_factory=list)
    effect_sizes: Dict[str, float] = field(default_factory=dict)
    confidence_intervals: Dict[str, Tuple[float, float]] = field(default_factory=dict)
    raw_results: List[HypothesisResult] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def success_rate(self) -> float:
        """Proportion of hypotheses supported."""
        if self.hypotheses_tested == 0:
            return 0.0
        return self.hypotheses_supported / self.hypotheses_tested

    @property
    def has_critical_failures(self) -> bool:
        """Whether any critical hypotheses failed."""
        return len(self.critical_failures) > 0

    @property
    def is_clean(self) -> bool:
        """Whether all hypotheses passed."""
        return self.hypotheses_failed == 0

    def add_result(self, result: HypothesisResult):
        """Add a hypothesis result to this domain."""
        self.raw_results.append(result)
        self.hypotheses_tested += 1

        if result.passed:
            self.hypotheses_supported += 1
        else:
            self.hypotheses_failed += 1
            if result.is_critical:
                self.critical_failures.append(result.hypothesis_id)

        self.effect_sizes[result.hypothesis_id] = result.effect_size
        if result.confidence_interval[0] is not None:
            self.confidence_intervals[result.hypothesis_id] = result.confidence_interval

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "domain_id": self.domain_id,
            "domain_name": self.domain_name,
            "description": self.description,
            "hypotheses_tested": self.hypotheses_tested,
            "hypotheses_supported": self.hypotheses_supported,
            "hypotheses_failed": self.hypotheses_failed,
            "success_rate": self.success_rate,
            "critical_failures": self.critical_failures,
            "key_findings": self.key_findings,
            "effect_sizes": self.effect_sizes,
            "confidence_intervals": {k: list(v) for k, v in self.confidence_intervals.items()},
            "raw_results": [r.to_dict() for r in self.raw_results],
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DomainResults":
        """Create from dictionary."""
        domain = cls(
            domain_id=data.get("domain_id", ""),
            domain_name=data.get("domain_name", ""),
            description=data.get("description", ""),
            hypotheses_tested=data.get("hypotheses_tested", 0),
            hypotheses_supported=data.get("hypotheses_supported", 0),
            hypotheses_failed=data.get("hypotheses_failed", 0),
            critical_failures=data.get("critical_failures", []),
            key_findings=data.get("key_findings", []),
            effect_sizes=data.get("effect_sizes", {}),
            confidence_intervals={
                k: tuple(v) for k, v in data.get("confidence_intervals", {}).items()
            },
            metadata=data.get("metadata", {}),
        )

        # Parse raw results
        for result_data in data.get("raw_results", []):
            domain.raw_results.append(HypothesisResult.from_dict(result_data))

        return domain


# Domain ID to name mapping
DOMAIN_MAPPING = {
    "domain1": ("domain1_mechanism", "Mechanism Validation"),
    "domain2": ("domain2_economic", "Economic Validation"),
    "domain3": ("domain3_system", "System Validation"),
    "domain4": ("domain4_token", "Token Economics"),
    "domain5": ("domain5_agents", "Multi-Agent Simulation"),
    "domain6": ("domain6_stress", "Stress Testing"),
    "domain7": ("domain7_forecasting", "Forecasting & Prediction"),
    "domain8": ("domain8_benchmarks", "Benchmarks & Comparison"),
}

# Critical hypotheses that must pass for system viability
CRITICAL_HYPOTHESES = {
    "H1.2": "Individual Rationality (Compute) - Miners must be profitable",
    "H1.3": "Individual Rationality (Network) - Users must get fair value",
    "H1.4": "Budget Balance - System must be economically sustainable",
    "H3.6": "Availability SLA - Must meet production availability requirements",
    "H5.1": "Incentive Compatibility - Honest behavior must be optimal strategy",
    "H2.1": "ROI Viability - Must provide competitive returns",
}


class ResultCollector:
    """
    Collects and aggregates results from all experiment domains.

    Expected directory structure:
    results/
    ├── domain1_mechanism/
    │   └── hypothesis_results.json
    ├── domain2_economic/
    │   └── hypothesis_results.json
    ├── domain3_system/
    │   └── hypothesis_results.json
    ...
    """

    def __init__(
        self,
        results_dir: Union[str, Path],
        alpha: float = 0.05
    ):
        """
        Initialize result collector.

        Args:
            results_dir: Directory containing domain result folders
            alpha: Significance level used for tests
        """
        self.results_dir = Path(results_dir)
        self.alpha = alpha
        self.domain_results: Dict[str, DomainResults] = {}
        self._collected = False

    def collect_all_results(self) -> Dict[str, DomainResults]:
        """
        Scan results directory and collect all hypothesis test results.

        Returns:
            Dictionary mapping domain_id to DomainResults
        """
        if not self.results_dir.exists():
            logger.warning(f"Results directory does not exist: {self.results_dir}")
            return {}

        self.domain_results = {}

        # Scan for domain directories
        for domain_dir in self.results_dir.iterdir():
            if not domain_dir.is_dir():
                continue

            domain_id = domain_dir.name
            domain_name = self._get_domain_name(domain_id)

            logger.info(f"Collecting results from {domain_id}")

            # Look for result files
            results_file = domain_dir / "hypothesis_results.json"
            if not results_file.exists():
                # Try alternative names
                for alt_name in ["results.json", "test_results.json", "hypotheses.json"]:
                    alt_file = domain_dir / alt_name
                    if alt_file.exists():
                        results_file = alt_file
                        break

            if results_file.exists():
                domain_results = self._load_domain_results(domain_id, domain_name, results_file)
                if domain_results:
                    self.domain_results[domain_id] = domain_results
            else:
                # Create empty domain results if directory exists but no results
                self.domain_results[domain_id] = DomainResults(
                    domain_id=domain_id,
                    domain_name=domain_name,
                )

        self._collected = True
        logger.info(f"Collected results from {len(self.domain_results)} domains")

        return self.domain_results

    def _get_domain_name(self, domain_id: str) -> str:
        """Get human-readable domain name."""
        for key, (folder, name) in DOMAIN_MAPPING.items():
            if domain_id == folder or domain_id == key:
                return name
        return domain_id.replace("_", " ").title()

    def _load_domain_results(
        self,
        domain_id: str,
        domain_name: str,
        results_file: Path
    ) -> Optional[DomainResults]:
        """Load results from a domain results file."""
        try:
            with open(results_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Handle different file formats
            if isinstance(data, list):
                # List of hypothesis results
                domain = DomainResults(
                    domain_id=domain_id,
                    domain_name=domain_name,
                )
                for item in data:
                    result = self._parse_hypothesis_result(item, domain_id)
                    if result:
                        domain.add_result(result)

            elif isinstance(data, dict):
                if "raw_results" in data or "hypotheses_tested" in data:
                    # Already in DomainResults format
                    domain = DomainResults.from_dict(data)
                    domain.domain_id = domain_id
                    domain.domain_name = domain_name
                elif "results" in data:
                    # Results nested under 'results' key
                    domain = DomainResults(
                        domain_id=domain_id,
                        domain_name=domain_name,
                        description=data.get("description", ""),
                        metadata=data.get("metadata", {}),
                    )
                    for item in data["results"]:
                        result = self._parse_hypothesis_result(item, domain_id)
                        if result:
                            domain.add_result(result)
                else:
                    # Single result or unknown format
                    domain = DomainResults(
                        domain_id=domain_id,
                        domain_name=domain_name,
                    )
                    result = self._parse_hypothesis_result(data, domain_id)
                    if result:
                        domain.add_result(result)

            return domain

        except Exception as e:
            logger.error(f"Error loading results from {results_file}: {e}")
            return None

    def _parse_hypothesis_result(
        self,
        data: Dict[str, Any],
        domain_id: str
    ) -> Optional[HypothesisResult]:
        """Parse a hypothesis result from dictionary."""
        try:
            # Determine hypothesis ID
            hyp_id = data.get("hypothesis_id", data.get("id", ""))

            # Check if critical
            is_critical = hyp_id in CRITICAL_HYPOTHESES

            # Parse confidence interval
            ci = data.get("confidence_interval", [None, None])
            if isinstance(ci, list):
                ci = (ci[0], ci[1]) if len(ci) >= 2 else (None, None)
            elif ci is None:
                ci = (None, None)

            # Determine decision
            decision = data.get("decision", "")
            if not decision:
                p_value = float(data.get("p_value", 1.0))
                passed = data.get("passed", p_value < self.alpha)
                decision = "reject_null" if passed else "fail_to_reject_null"

            return HypothesisResult(
                hypothesis_id=hyp_id,
                hypothesis_name=data.get("hypothesis_name", data.get("name", "")),
                domain_id=domain_id,
                null_hypothesis=data.get("null_hypothesis", data.get("h0", "")),
                alternative_hypothesis=data.get("alternative_hypothesis",
                                                data.get("alt_hypothesis", data.get("h1", ""))),
                test_name=data.get("test_name", ""),
                test_statistic=float(data.get("test_statistic", data.get("statistic", 0))),
                p_value=float(data.get("p_value", 1.0)),
                effect_size=float(data.get("effect_size", 0)),
                effect_size_name=data.get("effect_size_name", ""),
                confidence_interval=ci,
                sample_size=int(data.get("sample_size", 0)),
                power=data.get("power"),
                decision=decision,
                alpha=float(data.get("alpha", self.alpha)),
                is_critical=is_critical,
                timestamp=data.get("timestamp", ""),
                metadata=data.get("metadata", data.get("additional_stats", {})),
            )

        except Exception as e:
            logger.warning(f"Error parsing hypothesis result: {e}")
            return None

    def get_overall_summary(self) -> Dict[str, Any]:
        """
        Aggregate summary across all domains.

        Returns:
            Dictionary with aggregated statistics
        """
        if not self._collected:
            self.collect_all_results()

        total_hypotheses = 0
        total_supported = 0
        total_failed = 0
        critical_failures = []
        domains_clean = []
        near_misses = []
        strong_results = []

        for domain_id, domain in self.domain_results.items():
            total_hypotheses += domain.hypotheses_tested
            total_supported += domain.hypotheses_supported
            total_failed += domain.hypotheses_failed

            if domain.has_critical_failures:
                for failure_id in domain.critical_failures:
                    critical_failures.append({
                        "hypothesis_id": failure_id,
                        "domain": domain.domain_name,
                        "implication": CRITICAL_HYPOTHESES.get(failure_id, "Unknown"),
                    })

            if domain.is_clean:
                domains_clean.append(domain_id)

            # Find near misses and strong results
            for result in domain.raw_results:
                if result.is_near_miss:
                    near_misses.append(result.hypothesis_id)
                if result.is_strong_result:
                    strong_results.append(result.hypothesis_id)

        success_rate = total_supported / total_hypotheses if total_hypotheses > 0 else 0

        return {
            "total_hypotheses": total_hypotheses,
            "total_supported": total_supported,
            "total_failed": total_failed,
            "success_rate": success_rate,
            "success_rate_percent": f"{success_rate * 100:.1f}%",
            "critical_failures": critical_failures,
            "n_critical_failures": len(critical_failures),
            "domains_clean": domains_clean,
            "n_domains_clean": len(domains_clean),
            "total_domains": len(self.domain_results),
            "near_misses": near_misses,
            "n_near_misses": len(near_misses),
            "strong_results": strong_results,
            "n_strong_results": len(strong_results),
            "alpha": self.alpha,
            "timestamp": datetime.now().isoformat(),
        }

    def identify_critical_failures(self) -> List[Dict[str, Any]]:
        """
        Identify hypotheses that MUST pass for system viability.

        Returns:
            List of critical failure details
        """
        if not self._collected:
            self.collect_all_results()

        failures = []

        for domain in self.domain_results.values():
            for result in domain.raw_results:
                if result.hypothesis_id in CRITICAL_HYPOTHESES and not result.passed:
                    failures.append({
                        "id": result.hypothesis_id,
                        "name": result.hypothesis_name,
                        "domain": domain.domain_name,
                        "domain_id": domain.domain_id,
                        "p_value": result.p_value,
                        "effect_size": result.effect_size,
                        "confidence_interval": result.confidence_interval,
                        "implication": CRITICAL_HYPOTHESES[result.hypothesis_id],
                        "severity": "critical",
                        "test_name": result.test_name,
                    })

        return failures

    def get_domain_summary(self, domain_id: str) -> Optional[Dict[str, Any]]:
        """Get summary for a specific domain."""
        if not self._collected:
            self.collect_all_results()

        domain = self.domain_results.get(domain_id)
        if not domain:
            return None

        return {
            "domain_id": domain.domain_id,
            "domain_name": domain.domain_name,
            "hypotheses_tested": domain.hypotheses_tested,
            "hypotheses_supported": domain.hypotheses_supported,
            "hypotheses_failed": domain.hypotheses_failed,
            "success_rate": domain.success_rate,
            "is_clean": domain.is_clean,
            "critical_failures": domain.critical_failures,
            "key_findings": domain.key_findings,
            "effect_sizes": domain.effect_sizes,
        }

    def get_all_hypothesis_ids(self) -> List[str]:
        """Get list of all hypothesis IDs."""
        if not self._collected:
            self.collect_all_results()

        ids = []
        for domain in self.domain_results.values():
            for result in domain.raw_results:
                ids.append(result.hypothesis_id)

        return sorted(set(ids))

    def get_hypothesis_result(self, hypothesis_id: str) -> Optional[HypothesisResult]:
        """Get result for a specific hypothesis."""
        if not self._collected:
            self.collect_all_results()

        for domain in self.domain_results.values():
            for result in domain.raw_results:
                if result.hypothesis_id == hypothesis_id:
                    return result

        return None

    def get_results_by_status(self, passed: bool = True) -> List[HypothesisResult]:
        """Get all results filtered by pass/fail status."""
        if not self._collected:
            self.collect_all_results()

        results = []
        for domain in self.domain_results.values():
            for result in domain.raw_results:
                if result.passed == passed:
                    results.append(result)

        return results

    def get_effect_size_summary(self) -> Dict[str, Any]:
        """Get summary of effect sizes across all tests."""
        if not self._collected:
            self.collect_all_results()

        effect_sizes = []
        by_magnitude = {"negligible": 0, "small": 0, "medium": 0, "large": 0}

        for domain in self.domain_results.values():
            for result in domain.raw_results:
                es = abs(result.effect_size)
                effect_sizes.append(es)

                # Classify (assuming Cohen's d scale)
                if es < 0.2:
                    by_magnitude["negligible"] += 1
                elif es < 0.5:
                    by_magnitude["small"] += 1
                elif es < 0.8:
                    by_magnitude["medium"] += 1
                else:
                    by_magnitude["large"] += 1

        if effect_sizes:
            import numpy as np
            return {
                "mean": float(np.mean(effect_sizes)),
                "median": float(np.median(effect_sizes)),
                "std": float(np.std(effect_sizes)),
                "min": float(min(effect_sizes)),
                "max": float(max(effect_sizes)),
                "by_magnitude": by_magnitude,
            }

        return {"mean": 0, "median": 0, "std": 0, "min": 0, "max": 0, "by_magnitude": by_magnitude}

    def export_results(
        self,
        output_path: Union[str, Path],
        format: str = "json"
    ):
        """
        Export all collected results.

        Args:
            output_path: Output file path
            format: 'json' or 'csv'
        """
        if not self._collected:
            self.collect_all_results()

        output_path = Path(output_path)

        if format == "json":
            data = {
                "summary": self.get_overall_summary(),
                "domains": {k: v.to_dict() for k, v in self.domain_results.items()},
            }
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)

        elif format == "csv":
            import csv
            rows = []
            for domain in self.domain_results.values():
                for result in domain.raw_results:
                    rows.append({
                        "domain": domain.domain_name,
                        "hypothesis_id": result.hypothesis_id,
                        "hypothesis_name": result.hypothesis_name,
                        "test_name": result.test_name,
                        "statistic": result.test_statistic,
                        "p_value": result.p_value,
                        "effect_size": result.effect_size,
                        "passed": result.passed,
                        "is_critical": result.is_critical,
                    })

            with open(output_path, 'w', newline='', encoding='utf-8') as f:
                if rows:
                    writer = csv.DictWriter(f, fieldnames=rows[0].keys())
                    writer.writeheader()
                    writer.writerows(rows)

        logger.info(f"Results exported to {output_path}")


def collect_results(results_dir: Union[str, Path]) -> Dict[str, DomainResults]:
    """
    Convenience function to collect all results.

    Args:
        results_dir: Directory containing domain results

    Returns:
        Dictionary of domain results
    """
    collector = ResultCollector(results_dir)
    return collector.collect_all_results()
