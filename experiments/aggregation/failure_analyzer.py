"""
Failure Analyzer for SHAKTI-CHAIN Experiments.

Analyzes failed hypotheses to identify root causes, patterns, and remediation strategies.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple, Set
from enum import Enum
import json
from pathlib import Path
from collections import defaultdict
import numpy as np

try:
    from scipy import stats
    from scipy.cluster.hierarchy import linkage, fcluster
    from scipy.spatial.distance import pdist
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False


class FailureCategory(Enum):
    """Categories of hypothesis failures."""
    STATISTICAL_POWER = "statistical_power"
    EFFECT_SIZE = "effect_size"
    ASSUMPTION_VIOLATION = "assumption_violation"
    DATA_QUALITY = "data_quality"
    METHODOLOGY = "methodology"
    IMPLEMENTATION = "implementation"
    EXTERNAL_FACTORS = "external_factors"
    THRESHOLD_BOUNDARY = "threshold_boundary"
    UNKNOWN = "unknown"


class FailureSeverity(Enum):
    """Severity levels for failures."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RemediationPriority(Enum):
    """Priority for remediation actions."""
    IMMEDIATE = "immediate"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    OPTIONAL = "optional"


@dataclass
class FailureAnalysis:
    """Detailed analysis of a single hypothesis failure."""
    hypothesis_id: str
    domain: str
    category: FailureCategory
    severity: FailureSeverity

    # Statistical details
    p_value: float
    effect_size: float
    required_effect_size: float
    sample_size: int
    statistical_power: float

    # Analysis
    root_cause: str
    contributing_factors: List[str]
    evidence: List[str]

    # Remediation
    remediation_options: List[str]
    remediation_priority: RemediationPriority
    estimated_effort: str

    # Impact
    is_critical: bool
    dependent_hypotheses: List[str]
    cascade_risk: float

    # Metadata
    confidence: float  # Confidence in the analysis
    additional_data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "hypothesis_id": self.hypothesis_id,
            "domain": self.domain,
            "category": self.category.value,
            "severity": self.severity.value,
            "p_value": self.p_value,
            "effect_size": self.effect_size,
            "required_effect_size": self.required_effect_size,
            "sample_size": self.sample_size,
            "statistical_power": self.statistical_power,
            "root_cause": self.root_cause,
            "contributing_factors": self.contributing_factors,
            "evidence": self.evidence,
            "remediation_options": self.remediation_options,
            "remediation_priority": self.remediation_priority.value,
            "estimated_effort": self.estimated_effort,
            "is_critical": self.is_critical,
            "dependent_hypotheses": self.dependent_hypotheses,
            "cascade_risk": self.cascade_risk,
            "confidence": self.confidence,
            "additional_data": self.additional_data,
        }


@dataclass
class FailurePattern:
    """A pattern of failures across hypotheses."""
    pattern_id: str
    description: str
    affected_hypotheses: List[str]
    affected_domains: List[str]
    common_characteristics: Dict[str, Any]
    potential_root_cause: str
    confidence: float

    def to_dict(self) -> dict:
        return {
            "pattern_id": self.pattern_id,
            "description": self.description,
            "affected_hypotheses": self.affected_hypotheses,
            "affected_domains": list(set(self.affected_domains)),
            "common_characteristics": self.common_characteristics,
            "potential_root_cause": self.potential_root_cause,
            "confidence": self.confidence,
        }


@dataclass
class RemediationPlan:
    """A comprehensive plan to address failures."""
    plan_id: str
    target_hypotheses: List[str]

    # Actions
    immediate_actions: List[str]
    short_term_actions: List[str]
    long_term_actions: List[str]

    # Resources
    estimated_time: str
    required_resources: List[str]
    dependencies: List[str]

    # Expected outcomes
    expected_improvement: Dict[str, float]
    success_probability: float
    risk_factors: List[str]

    def to_dict(self) -> dict:
        return {
            "plan_id": self.plan_id,
            "target_hypotheses": self.target_hypotheses,
            "immediate_actions": self.immediate_actions,
            "short_term_actions": self.short_term_actions,
            "long_term_actions": self.long_term_actions,
            "estimated_time": self.estimated_time,
            "required_resources": self.required_resources,
            "dependencies": self.dependencies,
            "expected_improvement": self.expected_improvement,
            "success_probability": self.success_probability,
            "risk_factors": self.risk_factors,
        }


# Critical hypotheses and their dependencies
CRITICAL_HYPOTHESES = {
    "H1.2", "H1.3", "H1.4",  # Core token economics
    "H3.6",  # System stability
    "H5.1",  # Agent coordination
    "H2.1",  # Data integrity
}

HYPOTHESIS_DEPENDENCIES = {
    "H1.2": ["H1.1"],
    "H1.3": ["H1.1", "H1.2"],
    "H1.4": ["H1.2", "H1.3"],
    "H2.1": [],
    "H2.2": ["H2.1"],
    "H3.1": ["H1.2"],
    "H3.6": ["H3.1", "H3.2", "H3.3"],
    "H4.1": ["H3.1"],
    "H5.1": ["H1.3", "H3.6"],
    "H5.2": ["H5.1"],
}

# Effect size thresholds by domain
DOMAIN_EFFECT_THRESHOLDS = {
    "token_economics": {"minimum": 0.3, "target": 0.5},
    "data_integrity": {"minimum": 0.4, "target": 0.6},
    "system_dynamics": {"minimum": 0.25, "target": 0.4},
    "forecasting": {"minimum": 0.2, "target": 0.35},
    "agent_behavior": {"minimum": 0.35, "target": 0.5},
    "stress_testing": {"minimum": 0.3, "target": 0.45},
}


class FailureAnalyzer:
    """
    Analyzes failed hypotheses and provides remediation recommendations.

    This class performs:
    - Root cause analysis for failures
    - Pattern detection across failures
    - Severity and impact assessment
    - Remediation planning
    """

    def __init__(
        self,
        results_dir: Optional[Path] = None,
        alpha: float = 0.05,
        power_threshold: float = 0.8,
    ):
        """
        Initialize failure analyzer.

        Args:
            results_dir: Directory containing experiment results
            alpha: Significance level
            power_threshold: Minimum acceptable statistical power
        """
        self.results_dir = Path(results_dir) if results_dir else None
        self.alpha = alpha
        self.power_threshold = power_threshold

        self.failures: Dict[str, FailureAnalysis] = {}
        self.patterns: List[FailurePattern] = []
        self.remediation_plans: List[RemediationPlan] = []

    def analyze_failure(
        self,
        hypothesis_id: str,
        domain: str,
        p_value: float,
        effect_size: float,
        sample_size: int,
        power: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> FailureAnalysis:
        """
        Analyze a single hypothesis failure.

        Args:
            hypothesis_id: Hypothesis identifier
            domain: Domain the hypothesis belongs to
            p_value: Observed p-value
            effect_size: Observed effect size
            sample_size: Sample size used
            power: Statistical power (calculated if not provided)
            metadata: Additional metadata about the experiment

        Returns:
            Detailed failure analysis
        """
        metadata = metadata or {}

        # Get domain thresholds
        thresholds = DOMAIN_EFFECT_THRESHOLDS.get(
            domain, {"minimum": 0.3, "target": 0.5}
        )
        required_effect = thresholds["minimum"]

        # Calculate power if not provided
        if power is None:
            power = self._estimate_power(effect_size, sample_size)

        # Determine category and root cause
        category, root_cause, evidence = self._determine_failure_category(
            p_value=p_value,
            effect_size=effect_size,
            required_effect=required_effect,
            power=power,
            sample_size=sample_size,
            metadata=metadata,
        )

        # Identify contributing factors
        contributing_factors = self._identify_contributing_factors(
            category=category,
            p_value=p_value,
            effect_size=effect_size,
            power=power,
            metadata=metadata,
        )

        # Determine severity
        is_critical = hypothesis_id in CRITICAL_HYPOTHESES
        severity = self._determine_severity(
            category=category,
            is_critical=is_critical,
            effect_size=effect_size,
            required_effect=required_effect,
            p_value=p_value,
        )

        # Calculate cascade risk
        dependent_hypotheses = self._find_dependent_hypotheses(hypothesis_id)
        cascade_risk = self._calculate_cascade_risk(
            hypothesis_id, dependent_hypotheses, is_critical
        )

        # Generate remediation options
        remediation_options, priority, effort = self._generate_remediation(
            category=category,
            severity=severity,
            is_critical=is_critical,
            power=power,
            effect_size=effect_size,
            sample_size=sample_size,
        )

        # Confidence in analysis
        confidence = self._calculate_analysis_confidence(
            category=category,
            evidence=evidence,
            metadata=metadata,
        )

        analysis = FailureAnalysis(
            hypothesis_id=hypothesis_id,
            domain=domain,
            category=category,
            severity=severity,
            p_value=p_value,
            effect_size=effect_size,
            required_effect_size=required_effect,
            sample_size=sample_size,
            statistical_power=power,
            root_cause=root_cause,
            contributing_factors=contributing_factors,
            evidence=evidence,
            remediation_options=remediation_options,
            remediation_priority=priority,
            estimated_effort=effort,
            is_critical=is_critical,
            dependent_hypotheses=dependent_hypotheses,
            cascade_risk=cascade_risk,
            confidence=confidence,
            additional_data=metadata,
        )

        self.failures[hypothesis_id] = analysis
        return analysis

    def _estimate_power(self, effect_size: float, sample_size: int) -> float:
        """Estimate statistical power."""
        if not SCIPY_AVAILABLE:
            # Rough approximation
            return min(0.99, 0.5 + 0.1 * abs(effect_size) * np.sqrt(sample_size))

        # Use non-central t distribution for power calculation
        df = sample_size - 1
        ncp = abs(effect_size) * np.sqrt(sample_size)  # Non-centrality parameter
        critical_t = stats.t.ppf(1 - self.alpha / 2, df)

        # Power = P(|T| > critical | H1)
        power = 1 - stats.nct.cdf(critical_t, df, ncp) + stats.nct.cdf(-critical_t, df, ncp)
        return float(power)

    def _determine_failure_category(
        self,
        p_value: float,
        effect_size: float,
        required_effect: float,
        power: float,
        sample_size: int,
        metadata: Dict[str, Any],
    ) -> Tuple[FailureCategory, str, List[str]]:
        """Determine the category and root cause of failure."""
        evidence = []

        # Check for threshold boundary (near-miss)
        if 0.05 <= p_value <= 0.10:
            evidence.append(f"P-value ({p_value:.4f}) is borderline significant")
            if power < self.power_threshold:
                return (
                    FailureCategory.THRESHOLD_BOUNDARY,
                    "Near-miss due to insufficient statistical power",
                    evidence + [f"Power ({power:.2f}) below threshold ({self.power_threshold})"],
                )
            return (
                FailureCategory.THRESHOLD_BOUNDARY,
                "Near-miss with adequate power suggests true effect may be smaller than expected",
                evidence,
            )

        # Check for low power
        if power < 0.5:
            evidence.append(f"Very low statistical power ({power:.2f})")
            return (
                FailureCategory.STATISTICAL_POWER,
                "Insufficient statistical power to detect effect",
                evidence + [f"Sample size ({sample_size}) may be too small"],
            )

        if power < self.power_threshold:
            evidence.append(f"Power ({power:.2f}) below recommended threshold")
            return (
                FailureCategory.STATISTICAL_POWER,
                "Underpowered study; effect may exist but undetectable",
                evidence,
            )

        # Check for small effect size
        if abs(effect_size) < required_effect * 0.5:
            evidence.append(f"Effect size ({effect_size:.3f}) much smaller than required ({required_effect})")
            return (
                FailureCategory.EFFECT_SIZE,
                "True effect appears negligible or non-existent",
                evidence,
            )

        if abs(effect_size) < required_effect:
            evidence.append(f"Effect size ({effect_size:.3f}) below threshold ({required_effect})")
            return (
                FailureCategory.EFFECT_SIZE,
                "Effect exists but below practical significance threshold",
                evidence,
            )

        # Check metadata for assumption violations
        if metadata.get("normality_violated"):
            evidence.append("Normality assumption violated")
            return (
                FailureCategory.ASSUMPTION_VIOLATION,
                "Statistical test assumptions not met",
                evidence,
            )

        if metadata.get("homoscedasticity_violated"):
            evidence.append("Homoscedasticity assumption violated")
            return (
                FailureCategory.ASSUMPTION_VIOLATION,
                "Variance heterogeneity may have affected results",
                evidence,
            )

        # Check for data quality issues
        if metadata.get("outlier_percentage", 0) > 10:
            evidence.append(f"High outlier rate ({metadata['outlier_percentage']}%)")
            return (
                FailureCategory.DATA_QUALITY,
                "Data quality issues may have obscured true effect",
                evidence,
            )

        if metadata.get("missing_data_percentage", 0) > 15:
            evidence.append(f"High missing data ({metadata['missing_data_percentage']}%)")
            return (
                FailureCategory.DATA_QUALITY,
                "Excessive missing data reduced effective sample size",
                evidence,
            )

        # Check for implementation issues
        if metadata.get("implementation_issues"):
            evidence.extend(metadata["implementation_issues"])
            return (
                FailureCategory.IMPLEMENTATION,
                "Implementation issues may have affected experimental validity",
                evidence,
            )

        # Check for external factors
        if metadata.get("external_factors"):
            evidence.extend(metadata["external_factors"])
            return (
                FailureCategory.EXTERNAL_FACTORS,
                "External factors may have confounded results",
                evidence,
            )

        # Default: unknown
        evidence.append("No clear pattern identified in failure")
        return (
            FailureCategory.UNKNOWN,
            "Root cause unclear; further investigation needed",
            evidence,
        )

    def _identify_contributing_factors(
        self,
        category: FailureCategory,
        p_value: float,
        effect_size: float,
        power: float,
        metadata: Dict[str, Any],
    ) -> List[str]:
        """Identify factors contributing to the failure."""
        factors = []

        if category == FailureCategory.STATISTICAL_POWER:
            if power < 0.5:
                factors.append("Severely underpowered study design")
            else:
                factors.append("Marginally underpowered study")
            factors.append("Consider larger sample size or stronger manipulation")

        elif category == FailureCategory.EFFECT_SIZE:
            if abs(effect_size) < 0.1:
                factors.append("Effect appears to be near zero")
                factors.append("Theory or implementation may need revision")
            else:
                factors.append("Effect exists but below practical threshold")
                factors.append("Consider revising success criteria")

        elif category == FailureCategory.ASSUMPTION_VIOLATION:
            if metadata.get("normality_violated"):
                factors.append("Non-normal distribution detected")
                factors.append("Consider non-parametric alternatives")
            if metadata.get("homoscedasticity_violated"):
                factors.append("Unequal variances across groups")
                factors.append("Consider robust statistical methods")

        elif category == FailureCategory.DATA_QUALITY:
            if metadata.get("outlier_percentage", 0) > 5:
                factors.append(f"Outlier contamination: {metadata.get('outlier_percentage', 'unknown')}%")
            if metadata.get("missing_data_percentage", 0) > 5:
                factors.append(f"Missing data: {metadata.get('missing_data_percentage', 'unknown')}%")

        elif category == FailureCategory.THRESHOLD_BOUNDARY:
            factors.append("Result is borderline; small changes could alter conclusion")
            if power < self.power_threshold:
                factors.append("Low power increases uncertainty")

        # Add general factors
        if p_value > 0.1 and abs(effect_size) > 0.2:
            factors.append("Moderate effect size but high p-value suggests variability issue")

        if metadata.get("replications", 1) < 3:
            factors.append("Limited replications reduce confidence in results")

        return factors

    def _determine_severity(
        self,
        category: FailureCategory,
        is_critical: bool,
        effect_size: float,
        required_effect: float,
        p_value: float,
    ) -> FailureSeverity:
        """Determine failure severity."""
        if is_critical:
            # Critical hypotheses start at HIGH minimum
            if category in [FailureCategory.EFFECT_SIZE, FailureCategory.METHODOLOGY]:
                return FailureSeverity.CRITICAL
            if p_value > 0.2:
                return FailureSeverity.CRITICAL
            return FailureSeverity.HIGH

        # Non-critical hypotheses
        if category == FailureCategory.THRESHOLD_BOUNDARY:
            return FailureSeverity.LOW

        if category == FailureCategory.STATISTICAL_POWER:
            return FailureSeverity.MEDIUM

        if abs(effect_size) < required_effect * 0.25:
            return FailureSeverity.HIGH

        if p_value > 0.2:
            return FailureSeverity.MEDIUM

        return FailureSeverity.LOW

    def _find_dependent_hypotheses(self, hypothesis_id: str) -> List[str]:
        """Find hypotheses that depend on the given hypothesis."""
        dependents = []
        for h_id, deps in HYPOTHESIS_DEPENDENCIES.items():
            if hypothesis_id in deps:
                dependents.append(h_id)
        return dependents

    def _calculate_cascade_risk(
        self,
        hypothesis_id: str,
        dependents: List[str],
        is_critical: bool,
    ) -> float:
        """Calculate risk of failure cascading to other hypotheses."""
        if not dependents:
            return 0.0

        base_risk = len(dependents) * 0.15

        # Check if any dependents are critical
        critical_dependents = sum(1 for d in dependents if d in CRITICAL_HYPOTHESES)
        base_risk += critical_dependents * 0.25

        if is_critical:
            base_risk *= 1.5

        return min(1.0, base_risk)

    def _generate_remediation(
        self,
        category: FailureCategory,
        severity: FailureSeverity,
        is_critical: bool,
        power: float,
        effect_size: float,
        sample_size: int,
    ) -> Tuple[List[str], RemediationPriority, str]:
        """Generate remediation options."""
        options = []

        if category == FailureCategory.STATISTICAL_POWER:
            # Calculate required sample size
            if SCIPY_AVAILABLE and abs(effect_size) > 0:
                required_n = self._required_sample_size(abs(effect_size))
                options.append(f"Increase sample size to {required_n} (currently {sample_size})")
            else:
                options.append("Increase sample size by 50-100%")
            options.append("Use more sensitive measurement instruments")
            options.append("Reduce experimental noise through better controls")

            priority = RemediationPriority.HIGH if is_critical else RemediationPriority.MEDIUM
            effort = "Medium (1-2 additional experiment cycles)"

        elif category == FailureCategory.EFFECT_SIZE:
            options.append("Review theoretical assumptions about effect magnitude")
            options.append("Consider if practical significance threshold is appropriate")
            options.append("Investigate potential moderating variables")
            if abs(effect_size) > 0:
                options.append("Effect exists; consider revising success criteria")

            priority = RemediationPriority.HIGH
            effort = "High (requires theoretical review)"

        elif category == FailureCategory.ASSUMPTION_VIOLATION:
            options.append("Use non-parametric alternatives (permutation tests, bootstrap)")
            options.append("Apply data transformations (log, Box-Cox)")
            options.append("Use robust statistical methods")
            options.append("Collect additional data to improve normality")

            priority = RemediationPriority.MEDIUM
            effort = "Low (reanalysis with different methods)"

        elif category == FailureCategory.DATA_QUALITY:
            options.append("Implement stricter data quality controls")
            options.append("Use robust estimation methods")
            options.append("Apply outlier detection and handling procedures")
            options.append("Investigate sources of missing data")

            priority = RemediationPriority.MEDIUM
            effort = "Medium (data collection improvements)"

        elif category == FailureCategory.THRESHOLD_BOUNDARY:
            options.append("Replicate experiment to reduce uncertainty")
            options.append("Use Bayesian methods for more nuanced inference")
            options.append("Consider sequential testing approaches")
            if power < self.power_threshold:
                options.append("Increase sample size for definitive result")

            priority = RemediationPriority.MEDIUM if is_critical else RemediationPriority.LOW
            effort = "Low-Medium (replication study)"

        elif category == FailureCategory.IMPLEMENTATION:
            options.append("Review and fix implementation issues")
            options.append("Add validation checks and logging")
            options.append("Conduct pilot study before full experiment")

            priority = RemediationPriority.IMMEDIATE if is_critical else RemediationPriority.HIGH
            effort = "Variable (depends on issues identified)"

        elif category == FailureCategory.EXTERNAL_FACTORS:
            options.append("Identify and control for external confounds")
            options.append("Add covariates to analysis")
            options.append("Conduct experiment under more controlled conditions")

            priority = RemediationPriority.MEDIUM
            effort = "High (experimental redesign may be needed)"

        else:
            options.append("Conduct detailed investigation of failure")
            options.append("Review methodology and experimental design")
            options.append("Consult domain experts")

            priority = RemediationPriority.MEDIUM
            effort = "Unknown (requires investigation)"

        return options, priority, effort

    def _required_sample_size(self, effect_size: float, power: float = 0.8) -> int:
        """Calculate required sample size for given effect size and power."""
        if not SCIPY_AVAILABLE:
            return int(64 / (effect_size ** 2))  # Rough approximation

        from scipy.optimize import brentq

        def power_func(n):
            n = int(n)
            df = n - 1
            ncp = effect_size * np.sqrt(n)
            critical_t = stats.t.ppf(1 - self.alpha / 2, df)
            calc_power = 1 - stats.nct.cdf(critical_t, df, ncp) + stats.nct.cdf(-critical_t, df, ncp)
            return calc_power - power

        try:
            required_n = brentq(power_func, 4, 10000)
            return int(np.ceil(required_n))
        except ValueError:
            return int(64 / (effect_size ** 2))

    def _calculate_analysis_confidence(
        self,
        category: FailureCategory,
        evidence: List[str],
        metadata: Dict[str, Any],
    ) -> float:
        """Calculate confidence in the analysis."""
        base_confidence = 0.7

        # More evidence increases confidence
        base_confidence += min(0.15, len(evidence) * 0.05)

        # Known categories have higher confidence
        if category != FailureCategory.UNKNOWN:
            base_confidence += 0.1

        # Rich metadata increases confidence
        if len(metadata) > 3:
            base_confidence += 0.05

        return min(0.95, base_confidence)

    def detect_failure_patterns(
        self,
        min_pattern_size: int = 2,
    ) -> List[FailurePattern]:
        """
        Detect patterns across multiple failures.

        Args:
            min_pattern_size: Minimum number of failures for a pattern

        Returns:
            List of detected failure patterns
        """
        if len(self.failures) < min_pattern_size:
            return []

        patterns = []

        # Group by category
        category_groups: Dict[FailureCategory, List[str]] = defaultdict(list)
        for h_id, analysis in self.failures.items():
            category_groups[analysis.category].append(h_id)

        for category, hypotheses in category_groups.items():
            if len(hypotheses) >= min_pattern_size:
                affected_domains = [self.failures[h].domain for h in hypotheses]
                avg_effect = np.mean([self.failures[h].effect_size for h in hypotheses])
                avg_power = np.mean([self.failures[h].statistical_power for h in hypotheses])

                pattern = FailurePattern(
                    pattern_id=f"PATTERN_{category.value.upper()}",
                    description=f"Multiple failures due to {category.value.replace('_', ' ')}",
                    affected_hypotheses=hypotheses,
                    affected_domains=affected_domains,
                    common_characteristics={
                        "category": category.value,
                        "avg_effect_size": float(avg_effect),
                        "avg_power": float(avg_power),
                    },
                    potential_root_cause=self._pattern_root_cause(category),
                    confidence=0.8 if len(hypotheses) >= 3 else 0.6,
                )
                patterns.append(pattern)

        # Group by domain
        domain_groups: Dict[str, List[str]] = defaultdict(list)
        for h_id, analysis in self.failures.items():
            domain_groups[analysis.domain].append(h_id)

        for domain, hypotheses in domain_groups.items():
            if len(hypotheses) >= min_pattern_size:
                categories = [self.failures[h].category for h in hypotheses]
                most_common = max(set(categories), key=categories.count)

                pattern = FailurePattern(
                    pattern_id=f"PATTERN_DOMAIN_{domain.upper()}",
                    description=f"Concentrated failures in {domain} domain",
                    affected_hypotheses=hypotheses,
                    affected_domains=[domain],
                    common_characteristics={
                        "domain": domain,
                        "failure_count": len(hypotheses),
                        "primary_category": most_common.value,
                    },
                    potential_root_cause=f"Domain-specific issues in {domain}",
                    confidence=0.7,
                )
                patterns.append(pattern)

        # Check for power-related pattern across domains
        low_power_failures = [
            h_id for h_id, a in self.failures.items()
            if a.statistical_power < self.power_threshold
        ]
        if len(low_power_failures) >= min_pattern_size:
            pattern = FailurePattern(
                pattern_id="PATTERN_SYSTEMATIC_UNDERPOWER",
                description="Systematic underpowering across experiments",
                affected_hypotheses=low_power_failures,
                affected_domains=[self.failures[h].domain for h in low_power_failures],
                common_characteristics={
                    "avg_power": float(np.mean([
                        self.failures[h].statistical_power for h in low_power_failures
                    ])),
                    "count": len(low_power_failures),
                },
                potential_root_cause="Sample sizes systematically too small",
                confidence=0.85,
            )
            patterns.append(pattern)

        self.patterns = patterns
        return patterns

    def _pattern_root_cause(self, category: FailureCategory) -> str:
        """Get root cause description for a pattern category."""
        causes = {
            FailureCategory.STATISTICAL_POWER: "Systematic underpowering of studies",
            FailureCategory.EFFECT_SIZE: "Effects smaller than theoretical predictions",
            FailureCategory.ASSUMPTION_VIOLATION: "Data characteristics inconsistent with parametric assumptions",
            FailureCategory.DATA_QUALITY: "Systematic data quality issues",
            FailureCategory.METHODOLOGY: "Methodological design issues",
            FailureCategory.IMPLEMENTATION: "Implementation problems",
            FailureCategory.EXTERNAL_FACTORS: "External factors affecting multiple experiments",
            FailureCategory.THRESHOLD_BOUNDARY: "Multiple borderline results",
            FailureCategory.UNKNOWN: "Unknown systematic factor",
        }
        return causes.get(category, "Unknown")

    def generate_remediation_plan(
        self,
        target_hypotheses: Optional[List[str]] = None,
    ) -> RemediationPlan:
        """
        Generate a comprehensive remediation plan.

        Args:
            target_hypotheses: Specific hypotheses to target (default: all failed)

        Returns:
            Remediation plan
        """
        if target_hypotheses is None:
            target_hypotheses = list(self.failures.keys())

        if not target_hypotheses:
            return RemediationPlan(
                plan_id="EMPTY_PLAN",
                target_hypotheses=[],
                immediate_actions=["No failures to remediate"],
                short_term_actions=[],
                long_term_actions=[],
                estimated_time="N/A",
                required_resources=[],
                dependencies=[],
                expected_improvement={},
                success_probability=1.0,
                risk_factors=[],
            )

        immediate = []
        short_term = []
        long_term = []
        resources = set()
        dependencies = set()

        # Categorize actions by priority
        critical_failures = [
            h for h in target_hypotheses
            if h in self.failures and self.failures[h].is_critical
        ]

        for h_id in target_hypotheses:
            if h_id not in self.failures:
                continue

            analysis = self.failures[h_id]

            if analysis.remediation_priority == RemediationPriority.IMMEDIATE:
                immediate.extend(
                    f"[{h_id}] {opt}" for opt in analysis.remediation_options[:2]
                )
            elif analysis.remediation_priority == RemediationPriority.HIGH:
                short_term.extend(
                    f"[{h_id}] {opt}" for opt in analysis.remediation_options[:2]
                )
            else:
                long_term.extend(
                    f"[{h_id}] {opt}" for opt in analysis.remediation_options[:1]
                )

            # Collect dependencies
            for dep in analysis.dependent_hypotheses:
                if dep in target_hypotheses:
                    dependencies.add(f"{h_id} -> {dep}")

            # Collect resources based on category
            if analysis.category == FailureCategory.STATISTICAL_POWER:
                resources.add("Additional data collection capacity")
            elif analysis.category == FailureCategory.DATA_QUALITY:
                resources.add("Data quality improvement tools")
            elif analysis.category == FailureCategory.ASSUMPTION_VIOLATION:
                resources.add("Statistical consulting")

        # Calculate expected improvements
        expected_improvement = {}
        for h_id in target_hypotheses:
            if h_id in self.failures:
                analysis = self.failures[h_id]
                # Estimate improvement potential
                if analysis.category == FailureCategory.STATISTICAL_POWER:
                    expected_improvement[h_id] = 0.7  # High chance of success with more data
                elif analysis.category == FailureCategory.THRESHOLD_BOUNDARY:
                    expected_improvement[h_id] = 0.6  # Good chance with replication
                elif analysis.category == FailureCategory.EFFECT_SIZE:
                    expected_improvement[h_id] = 0.3  # Lower chance if effect truly small
                else:
                    expected_improvement[h_id] = 0.5

        # Estimate overall success probability
        success_prob = np.mean(list(expected_improvement.values())) if expected_improvement else 0.5

        # Identify risk factors
        risks = []
        if len(critical_failures) > 0:
            risks.append(f"{len(critical_failures)} critical hypotheses require attention")
        if any(self.failures[h].cascade_risk > 0.5 for h in target_hypotheses if h in self.failures):
            risks.append("High cascade risk - failures may affect dependent hypotheses")
        if self.patterns:
            risks.append(f"{len(self.patterns)} systematic patterns detected")

        # Estimate time
        total_hypotheses = len(target_hypotheses)
        if any(self.failures[h].estimated_effort.startswith("High") for h in target_hypotheses if h in self.failures):
            time_estimate = f"{total_hypotheses * 2}-{total_hypotheses * 4} weeks"
        else:
            time_estimate = f"{total_hypotheses}-{total_hypotheses * 2} weeks"

        plan = RemediationPlan(
            plan_id=f"PLAN_{len(self.remediation_plans) + 1}",
            target_hypotheses=target_hypotheses,
            immediate_actions=list(set(immediate))[:5],
            short_term_actions=list(set(short_term))[:10],
            long_term_actions=list(set(long_term))[:5],
            estimated_time=time_estimate,
            required_resources=list(resources),
            dependencies=list(dependencies),
            expected_improvement=expected_improvement,
            success_probability=float(success_prob),
            risk_factors=risks,
        )

        self.remediation_plans.append(plan)
        return plan

    def generate_failure_report(self) -> Dict[str, Any]:
        """Generate comprehensive failure analysis report."""
        if not self.failures:
            return {
                "summary": "No failures analyzed",
                "failures": [],
                "patterns": [],
                "remediation_plan": None,
            }

        # Summary statistics
        total_failures = len(self.failures)
        critical_count = sum(1 for a in self.failures.values() if a.is_critical)

        category_counts = defaultdict(int)
        severity_counts = defaultdict(int)
        domain_counts = defaultdict(int)

        for analysis in self.failures.values():
            category_counts[analysis.category.value] += 1
            severity_counts[analysis.severity.value] += 1
            domain_counts[analysis.domain] += 1

        avg_effect = np.mean([a.effect_size for a in self.failures.values()])
        avg_power = np.mean([a.statistical_power for a in self.failures.values()])

        # Generate patterns if not done
        if not self.patterns:
            self.detect_failure_patterns()

        # Generate remediation plan if not done
        if not self.remediation_plans:
            self.generate_remediation_plan()

        return {
            "summary": {
                "total_failures": total_failures,
                "critical_failures": critical_count,
                "average_effect_size": float(avg_effect),
                "average_power": float(avg_power),
                "categories": dict(category_counts),
                "severities": dict(severity_counts),
                "by_domain": dict(domain_counts),
            },
            "failures": [a.to_dict() for a in self.failures.values()],
            "patterns": [p.to_dict() for p in self.patterns],
            "remediation_plan": self.remediation_plans[-1].to_dict() if self.remediation_plans else None,
        }

    def generate_markdown_report(self) -> str:
        """Generate a markdown-formatted failure report."""
        report_data = self.generate_failure_report()

        lines = [
            "# Failure Analysis Report",
            "",
            "## Executive Summary",
            "",
            f"- **Total Failures Analyzed**: {report_data['summary']['total_failures']}",
            f"- **Critical Failures**: {report_data['summary']['critical_failures']}",
            f"- **Average Effect Size**: {report_data['summary']['average_effect_size']:.3f}",
            f"- **Average Statistical Power**: {report_data['summary']['average_power']:.2f}",
            "",
            "### Failures by Category",
            "",
        ]

        for cat, count in report_data['summary']['categories'].items():
            lines.append(f"- {cat.replace('_', ' ').title()}: {count}")

        lines.extend([
            "",
            "### Failures by Severity",
            "",
        ])

        for sev, count in report_data['summary']['severities'].items():
            lines.append(f"- {sev.title()}: {count}")

        lines.extend([
            "",
            "## Detailed Failure Analysis",
            "",
        ])

        for failure in report_data['failures']:
            critical_marker = " [CRITICAL]" if failure['is_critical'] else ""
            lines.extend([
                f"### {failure['hypothesis_id']}{critical_marker}",
                "",
                f"- **Domain**: {failure['domain']}",
                f"- **Category**: {failure['category'].replace('_', ' ').title()}",
                f"- **Severity**: {failure['severity'].title()}",
                f"- **P-value**: {failure['p_value']:.4f}",
                f"- **Effect Size**: {failure['effect_size']:.3f} (required: {failure['required_effect_size']:.3f})",
                f"- **Power**: {failure['statistical_power']:.2f}",
                "",
                f"**Root Cause**: {failure['root_cause']}",
                "",
                "**Contributing Factors**:",
            ])
            for factor in failure['contributing_factors']:
                lines.append(f"- {factor}")

            lines.extend([
                "",
                "**Remediation Options**:",
            ])
            for opt in failure['remediation_options']:
                lines.append(f"1. {opt}")

            lines.extend([
                "",
                f"Priority: {failure['remediation_priority'].title()} | Effort: {failure['estimated_effort']}",
                "",
            ])

        if report_data['patterns']:
            lines.extend([
                "## Detected Patterns",
                "",
            ])
            for pattern in report_data['patterns']:
                lines.extend([
                    f"### {pattern['pattern_id']}",
                    "",
                    f"{pattern['description']}",
                    "",
                    f"- **Affected Hypotheses**: {', '.join(pattern['affected_hypotheses'])}",
                    f"- **Affected Domains**: {', '.join(pattern['affected_domains'])}",
                    f"- **Potential Root Cause**: {pattern['potential_root_cause']}",
                    f"- **Confidence**: {pattern['confidence']:.0%}",
                    "",
                ])

        if report_data['remediation_plan']:
            plan = report_data['remediation_plan']
            lines.extend([
                "## Remediation Plan",
                "",
                f"**Plan ID**: {plan['plan_id']}",
                f"**Target Hypotheses**: {', '.join(plan['target_hypotheses'])}",
                f"**Estimated Time**: {plan['estimated_time']}",
                f"**Success Probability**: {plan['success_probability']:.0%}",
                "",
                "### Immediate Actions",
                "",
            ])
            for action in plan['immediate_actions']:
                lines.append(f"1. {action}")

            lines.extend([
                "",
                "### Short-term Actions",
                "",
            ])
            for action in plan['short_term_actions']:
                lines.append(f"1. {action}")

            if plan['risk_factors']:
                lines.extend([
                    "",
                    "### Risk Factors",
                    "",
                ])
                for risk in plan['risk_factors']:
                    lines.append(f"- {risk}")

        return "\n".join(lines)

    def save_report(
        self,
        output_path: Path,
        format: str = "json",
    ) -> None:
        """
        Save failure report to file.

        Args:
            output_path: Output file path
            format: Output format ('json' or 'markdown')
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if format == "json":
            with open(output_path, "w") as f:
                json.dump(self.generate_failure_report(), f, indent=2)
        elif format == "markdown":
            with open(output_path, "w") as f:
                f.write(self.generate_markdown_report())
        else:
            raise ValueError(f"Unknown format: {format}")


def analyze_failures(
    failed_results: List[Dict[str, Any]],
    alpha: float = 0.05,
) -> Dict[str, Any]:
    """
    Convenience function to analyze a list of failed results.

    Args:
        failed_results: List of failed hypothesis results
        alpha: Significance level

    Returns:
        Complete failure analysis report
    """
    analyzer = FailureAnalyzer(alpha=alpha)

    for result in failed_results:
        analyzer.analyze_failure(
            hypothesis_id=result.get("hypothesis_id", "UNKNOWN"),
            domain=result.get("domain", "unknown"),
            p_value=result.get("p_value", 1.0),
            effect_size=result.get("effect_size", 0.0),
            sample_size=result.get("sample_size", 30),
            power=result.get("power"),
            metadata=result.get("metadata", {}),
        )

    return analyzer.generate_failure_report()
