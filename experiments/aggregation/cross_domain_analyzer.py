"""
Cross-Domain Analyzer Module.

Finds patterns, correlations, and relationships across experiment domains.
Identifies tradeoffs, common failure patterns, and sensitivity factors.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
from scipy import stats
from collections import defaultdict

from .result_collector import DomainResults, HypothesisResult, CRITICAL_HYPOTHESES

logger = logging.getLogger(__name__)


@dataclass
class CorrelationResult:
    """Result of correlation analysis."""
    metric1: str
    metric2: str
    correlation: float
    p_value: float
    n_observations: int
    is_significant: bool
    interpretation: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metric1": self.metric1,
            "metric2": self.metric2,
            "correlation": self.correlation,
            "p_value": self.p_value,
            "n_observations": self.n_observations,
            "is_significant": self.is_significant,
            "interpretation": self.interpretation,
        }


@dataclass
class TradeoffAnalysis:
    """Result of tradeoff analysis."""
    factor1: str
    factor2: str
    relationship: str  # "tradeoff", "synergy", "independent"
    correlation: float
    evidence: List[str]
    recommendation: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "factor1": self.factor1,
            "factor2": self.factor2,
            "relationship": self.relationship,
            "correlation": self.correlation,
            "evidence": self.evidence,
            "recommendation": self.recommendation,
        }


@dataclass
class FailureCluster:
    """Cluster of related failures."""
    cluster_id: int
    hypotheses: List[str]
    common_factors: List[str]
    likely_cause: str
    severity: str  # "critical", "high", "medium", "low"
    suggested_fix: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cluster_id": self.cluster_id,
            "hypotheses": self.hypotheses,
            "common_factors": self.common_factors,
            "likely_cause": self.likely_cause,
            "severity": self.severity,
            "suggested_fix": self.suggested_fix,
        }


@dataclass
class SensitivityFactor:
    """Factor sensitivity analysis result."""
    parameter: str
    sensitivity_score: float
    affected_hypotheses: List[str]
    direction: str  # "positive", "negative", "nonlinear"
    recommendation: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "parameter": self.parameter,
            "sensitivity_score": self.sensitivity_score,
            "affected_hypotheses": self.affected_hypotheses,
            "direction": self.direction,
            "recommendation": self.recommendation,
        }


# Known metric relationships for SHAKTI-CHAIN
METRIC_CATEGORIES = {
    "efficiency": ["H1.1", "H2.3", "H3.1", "H3.2"],  # Efficiency-related
    "fairness": ["H1.2", "H1.3", "H5.2"],  # Fairness-related
    "economic": ["H1.4", "H2.1", "H2.2", "H4.1"],  # Economic viability
    "performance": ["H3.3", "H3.4", "H3.5", "H3.6"],  # System performance
    "incentives": ["H5.1", "H5.3", "H5.4"],  # Game theory
    "stability": ["H4.2", "H4.3", "H6.1"],  # System stability
}

# Known tradeoff relationships
KNOWN_TRADEOFFS = [
    ("throughput", "latency"),
    ("efficiency", "fairness"),
    ("decentralization", "performance"),
    ("security", "throughput"),
    ("stability", "responsiveness"),
]


class CrossDomainAnalyzer:
    """
    Analyzes patterns and relationships across experiment domains.

    Finds correlations, tradeoffs, failure patterns, and sensitivity factors.
    """

    def __init__(
        self,
        domain_results: Dict[str, DomainResults],
        alpha: float = 0.05
    ):
        """
        Initialize cross-domain analyzer.

        Args:
            domain_results: Dictionary of domain results from ResultCollector
            alpha: Significance level for correlation tests
        """
        self.results = domain_results
        self.alpha = alpha
        self._all_hypotheses = self._collect_all_hypotheses()

    def _collect_all_hypotheses(self) -> List[HypothesisResult]:
        """Collect all hypothesis results across domains."""
        hypotheses = []
        for domain in self.results.values():
            hypotheses.extend(domain.raw_results)
        return hypotheses

    def find_correlations(self) -> Dict[str, CorrelationResult]:
        """
        Find correlations between metrics across domains.

        Returns:
            Dictionary of correlation results
        """
        correlations = {}

        # Extract effect sizes and p-values for correlation analysis
        metrics = {}
        for hyp in self._all_hypotheses:
            if hyp.effect_size != 0:
                metrics[hyp.hypothesis_id] = {
                    "effect_size": hyp.effect_size,
                    "p_value": hyp.p_value,
                    "passed": 1 if hyp.passed else 0,
                }

        if len(metrics) < 3:
            return correlations

        # Correlate effect sizes across hypothesis categories
        for cat1, hyps1 in METRIC_CATEGORIES.items():
            for cat2, hyps2 in METRIC_CATEGORIES.items():
                if cat1 >= cat2:
                    continue

                # Get effect sizes for each category
                es1 = [metrics[h]["effect_size"] for h in hyps1 if h in metrics]
                es2 = [metrics[h]["effect_size"] for h in hyps2 if h in metrics]

                if len(es1) >= 2 and len(es2) >= 2:
                    # Use overlapping indices
                    min_len = min(len(es1), len(es2))
                    r, p = stats.pearsonr(es1[:min_len], es2[:min_len])

                    is_sig = p < self.alpha

                    if abs(r) > 0.3:  # Only report notable correlations
                        interpretation = self._interpret_correlation(r, cat1, cat2)

                        correlations[f"{cat1}_vs_{cat2}"] = CorrelationResult(
                            metric1=cat1,
                            metric2=cat2,
                            correlation=float(r),
                            p_value=float(p),
                            n_observations=min_len,
                            is_significant=is_sig,
                            interpretation=interpretation,
                        )

        # Correlate success rates across domains
        if len(self.results) >= 2:
            domain_success = [(d.success_rate, d.hypotheses_tested)
                            for d in self.results.values()
                            if d.hypotheses_tested > 0]

            if len(domain_success) >= 3:
                rates = [x[0] for x in domain_success]
                counts = [x[1] for x in domain_success]

                r, p = stats.pearsonr(rates, counts)
                correlations["success_vs_coverage"] = CorrelationResult(
                    metric1="success_rate",
                    metric2="test_coverage",
                    correlation=float(r),
                    p_value=float(p),
                    n_observations=len(rates),
                    is_significant=p < self.alpha,
                    interpretation=f"{'Positive' if r > 0 else 'Negative'} relationship "
                                  f"between success rate and test coverage",
                )

        return correlations

    def _interpret_correlation(self, r: float, cat1: str, cat2: str) -> str:
        """Interpret correlation between categories."""
        strength = "strong" if abs(r) > 0.7 else "moderate" if abs(r) > 0.5 else "weak"
        direction = "positive" if r > 0 else "negative"

        if r > 0.5:
            return f"Strong synergy between {cat1} and {cat2}: improvements in one tend to accompany improvements in the other"
        elif r < -0.5:
            return f"Tradeoff between {cat1} and {cat2}: improvements in one may come at the cost of the other"
        else:
            return f"{strength.title()} {direction} correlation between {cat1} and {cat2}"

    def identify_tradeoffs(self) -> List[TradeoffAnalysis]:
        """
        Identify tradeoff relationships between metrics.

        Returns:
            List of identified tradeoffs
        """
        tradeoffs = []

        # Analyze known tradeoff pairs
        for factor1, factor2 in KNOWN_TRADEOFFS:
            analysis = self._analyze_tradeoff(factor1, factor2)
            if analysis:
                tradeoffs.append(analysis)

        # Detect tradeoffs from correlation analysis
        correlations = self.find_correlations()
        for key, corr in correlations.items():
            if corr.correlation < -0.4 and corr.is_significant:
                tradeoffs.append(TradeoffAnalysis(
                    factor1=corr.metric1,
                    factor2=corr.metric2,
                    relationship="tradeoff",
                    correlation=corr.correlation,
                    evidence=[f"Correlation r={corr.correlation:.3f}, p={corr.p_value:.4f}"],
                    recommendation=f"Balance {corr.metric1} and {corr.metric2} based on priorities",
                ))

        return tradeoffs

    def _analyze_tradeoff(self, factor1: str, factor2: str) -> Optional[TradeoffAnalysis]:
        """Analyze a specific potential tradeoff."""
        # Find hypotheses related to each factor
        hyps1 = [h for h in self._all_hypotheses
                if factor1.lower() in h.hypothesis_name.lower()
                or factor1.lower() in h.hypothesis_id.lower()]

        hyps2 = [h for h in self._all_hypotheses
                if factor2.lower() in h.hypothesis_name.lower()
                or factor2.lower() in h.hypothesis_id.lower()]

        if not hyps1 or not hyps2:
            return None

        # Compare effect sizes
        es1 = [h.effect_size for h in hyps1]
        es2 = [h.effect_size for h in hyps2]

        mean1 = np.mean(es1)
        mean2 = np.mean(es2)

        # Determine relationship
        if mean1 * mean2 < 0:
            relationship = "tradeoff"
            recommendation = f"Consider prioritizing either {factor1} or {factor2}"
        elif mean1 > 0 and mean2 > 0:
            relationship = "synergy"
            recommendation = f"Both {factor1} and {factor2} can be optimized together"
        else:
            relationship = "independent"
            recommendation = f"{factor1} and {factor2} appear to be independent"

        return TradeoffAnalysis(
            factor1=factor1,
            factor2=factor2,
            relationship=relationship,
            correlation=float(np.corrcoef(es1[:min(len(es1), len(es2))],
                                         es2[:min(len(es1), len(es2))])[0, 1])
                        if len(es1) > 1 and len(es2) > 1 else 0.0,
            evidence=[
                f"Mean effect size for {factor1}: {mean1:.3f}",
                f"Mean effect size for {factor2}: {mean2:.3f}",
            ],
            recommendation=recommendation,
        )

    def cluster_failure_patterns(self) -> Dict[str, Any]:
        """
        Use clustering to find patterns in failures.

        Returns:
            Dictionary with failure clusters and analysis
        """
        # Collect failed hypotheses
        failures = [h for h in self._all_hypotheses if not h.passed]

        if not failures:
            return {
                "n_failures": 0,
                "clusters": [],
                "message": "No failures to cluster"
            }

        # Feature extraction for clustering
        features = []
        for h in failures:
            features.append({
                "id": h.hypothesis_id,
                "domain": h.domain_id,
                "p_value": h.p_value,
                "effect_size": h.effect_size,
                "sample_size": h.sample_size,
                "is_critical": h.is_critical,
            })

        # Simple clustering based on domain and p-value proximity
        clusters = self._cluster_failures(features)

        # Analyze each cluster
        analyzed_clusters = []
        for i, cluster in enumerate(clusters):
            hyp_ids = [f["id"] for f in cluster]
            domains = list(set(f["domain"] for f in cluster))

            # Determine common factors
            common_factors = []
            if len(domains) == 1:
                common_factors.append(f"All failures in {domains[0]}")
            if all(f["effect_size"] < 0.2 for f in cluster):
                common_factors.append("All have small effect sizes")
            if all(f["p_value"] > 0.1 for f in cluster):
                common_factors.append("All have high p-values")

            # Determine severity
            has_critical = any(f["is_critical"] for f in cluster)
            severity = "critical" if has_critical else "medium"

            # Suggest likely cause and fix
            likely_cause, suggested_fix = self._diagnose_cluster(cluster)

            analyzed_clusters.append(FailureCluster(
                cluster_id=i + 1,
                hypotheses=hyp_ids,
                common_factors=common_factors,
                likely_cause=likely_cause,
                severity=severity,
                suggested_fix=suggested_fix,
            ))

        return {
            "n_failures": len(failures),
            "n_clusters": len(analyzed_clusters),
            "clusters": [c.to_dict() for c in analyzed_clusters],
            "critical_clusters": sum(1 for c in analyzed_clusters if c.severity == "critical"),
        }

    def _cluster_failures(self, features: List[Dict]) -> List[List[Dict]]:
        """Simple clustering of failures by domain and similarity."""
        if not features:
            return []

        # Group by domain first
        by_domain = defaultdict(list)
        for f in features:
            by_domain[f["domain"]].append(f)

        clusters = []

        # Each domain forms initial clusters
        for domain, domain_failures in by_domain.items():
            if len(domain_failures) == 1:
                clusters.append(domain_failures)
            else:
                # Further cluster by p-value similarity
                sorted_failures = sorted(domain_failures, key=lambda x: x["p_value"])
                current_cluster = [sorted_failures[0]]

                for f in sorted_failures[1:]:
                    if f["p_value"] - current_cluster[-1]["p_value"] < 0.1:
                        current_cluster.append(f)
                    else:
                        clusters.append(current_cluster)
                        current_cluster = [f]

                clusters.append(current_cluster)

        return clusters

    def _diagnose_cluster(self, cluster: List[Dict]) -> Tuple[str, str]:
        """Diagnose likely cause and suggest fix for a cluster."""
        avg_effect = np.mean([f["effect_size"] for f in cluster])
        avg_p = np.mean([f["p_value"] for f in cluster])
        avg_n = np.mean([f["sample_size"] for f in cluster])

        # Diagnose based on statistics
        if avg_effect < 0.2 and avg_n > 100:
            return (
                "True null effect - hypothesis may not hold",
                "Revisit theoretical assumptions or mechanism design"
            )
        elif avg_n < 30:
            return (
                "Insufficient sample size for detection",
                "Increase simulation runs or data collection"
            )
        elif avg_p > 0.1 and avg_effect > 0.3:
            return (
                "High variance in measurements",
                "Improve measurement precision or reduce noise"
            )
        elif avg_effect < 0:
            return (
                "Effect in opposite direction of hypothesis",
                "Re-examine hypothesis formulation"
            )
        else:
            return (
                "Mixed factors affecting results",
                "Conduct more detailed analysis per hypothesis"
            )

    def sensitivity_analysis(self) -> Dict[str, Any]:
        """
        Determine which parameters most affect results.

        Returns:
            Dictionary with sensitivity analysis results
        """
        sensitivity_factors = []

        # Analyze sample size sensitivity
        sample_sizes = [h.sample_size for h in self._all_hypotheses if h.sample_size > 0]
        success_by_size = self._analyze_by_size(sample_sizes)

        if success_by_size:
            sensitivity_factors.append(SensitivityFactor(
                parameter="sample_size",
                sensitivity_score=success_by_size["sensitivity"],
                affected_hypotheses=success_by_size["affected"],
                direction="positive",
                recommendation="Larger sample sizes improve detection power",
            ))

        # Analyze effect size sensitivity
        effect_sizes = [h.effect_size for h in self._all_hypotheses]
        if effect_sizes:
            passed = [h.passed for h in self._all_hypotheses]
            if len(set(passed)) > 1:  # Both pass and fail exist
                try:
                    r, p = stats.pointbiserialr(passed, effect_sizes)
                    sensitivity_factors.append(SensitivityFactor(
                        parameter="effect_size",
                        sensitivity_score=abs(float(r)),
                        affected_hypotheses=[h.hypothesis_id for h in self._all_hypotheses
                                            if abs(h.effect_size) < 0.3],
                        direction="positive" if r > 0 else "negative",
                        recommendation="Effect sizes below 0.3 are at risk of non-significance",
                    ))
                except:
                    pass

        # Domain-specific sensitivity
        domain_sensitivity = self._analyze_domain_sensitivity()
        sensitivity_factors.extend(domain_sensitivity)

        return {
            "factors": [f.to_dict() for f in sensitivity_factors],
            "most_sensitive": sensitivity_factors[0].parameter if sensitivity_factors else None,
            "recommendations": [f.recommendation for f in sensitivity_factors],
        }

    def _analyze_by_size(self, sample_sizes: List[int]) -> Optional[Dict[str, Any]]:
        """Analyze relationship between sample size and success."""
        if not sample_sizes or len(sample_sizes) < 3:
            return None

        median_size = np.median(sample_sizes)

        small_samples = [h for h in self._all_hypotheses
                        if h.sample_size > 0 and h.sample_size < median_size]
        large_samples = [h for h in self._all_hypotheses
                        if h.sample_size >= median_size]

        if not small_samples or not large_samples:
            return None

        small_pass = sum(1 for h in small_samples if h.passed) / len(small_samples)
        large_pass = sum(1 for h in large_samples if h.passed) / len(large_samples)

        sensitivity = abs(large_pass - small_pass)

        return {
            "sensitivity": sensitivity,
            "affected": [h.hypothesis_id for h in small_samples if not h.passed],
            "small_sample_rate": small_pass,
            "large_sample_rate": large_pass,
        }

    def _analyze_domain_sensitivity(self) -> List[SensitivityFactor]:
        """Analyze sensitivity by domain."""
        factors = []

        # Check if success rate varies significantly by domain
        domain_rates = {d.domain_id: d.success_rate
                       for d in self.results.values()
                       if d.hypotheses_tested > 0}

        if len(domain_rates) >= 2:
            rates = list(domain_rates.values())
            variance = np.var(rates)

            if variance > 0.1:  # High variance across domains
                worst_domain = min(domain_rates, key=domain_rates.get)
                factors.append(SensitivityFactor(
                    parameter="domain",
                    sensitivity_score=float(variance),
                    affected_hypotheses=[h.hypothesis_id for h in self._all_hypotheses
                                        if h.domain_id == worst_domain and not h.passed],
                    direction="nonlinear",
                    recommendation=f"Focus attention on {worst_domain} which has lowest success rate",
                ))

        return factors

    def generate_cross_domain_report(self) -> Dict[str, Any]:
        """
        Generate comprehensive cross-domain analysis report.

        Returns:
            Complete analysis report
        """
        correlations = self.find_correlations()
        tradeoffs = self.identify_tradeoffs()
        failure_patterns = self.cluster_failure_patterns()
        sensitivity = self.sensitivity_analysis()

        # Summary statistics
        total_hyps = len(self._all_hypotheses)
        passed_hyps = sum(1 for h in self._all_hypotheses if h.passed)
        critical_failures = [h for h in self._all_hypotheses
                           if h.hypothesis_id in CRITICAL_HYPOTHESES and not h.passed]

        # Overall health assessment
        if critical_failures:
            health = "critical"
            health_message = f"{len(critical_failures)} critical hypothesis(es) failed - immediate attention required"
        elif passed_hyps / total_hyps < 0.7 if total_hyps > 0 else False:
            health = "warning"
            health_message = "Less than 70% of hypotheses supported - review recommended"
        elif passed_hyps / total_hyps < 0.9 if total_hyps > 0 else False:
            health = "acceptable"
            health_message = "Most hypotheses supported with some areas for improvement"
        else:
            health = "healthy"
            health_message = "Strong validation results across all domains"

        return {
            "summary": {
                "total_hypotheses": total_hyps,
                "passed": passed_hyps,
                "failed": total_hyps - passed_hyps,
                "success_rate": passed_hyps / total_hyps if total_hyps > 0 else 0,
                "health_status": health,
                "health_message": health_message,
            },
            "correlations": {k: v.to_dict() for k, v in correlations.items()},
            "tradeoffs": [t.to_dict() for t in tradeoffs],
            "failure_patterns": failure_patterns,
            "sensitivity": sensitivity,
            "critical_issues": [
                {
                    "hypothesis_id": h.hypothesis_id,
                    "domain": h.domain_id,
                    "description": CRITICAL_HYPOTHESES.get(h.hypothesis_id, "Unknown"),
                }
                for h in critical_failures
            ],
        }


def analyze_cross_domain(
    domain_results: Dict[str, DomainResults]
) -> Dict[str, Any]:
    """
    Convenience function for cross-domain analysis.

    Args:
        domain_results: Dictionary of domain results

    Returns:
        Complete analysis report
    """
    analyzer = CrossDomainAnalyzer(domain_results)
    return analyzer.generate_cross_domain_report()
