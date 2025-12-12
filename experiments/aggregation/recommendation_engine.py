"""
Recommendation Engine for SHAKTI-CHAIN Experiments.

Generates actionable recommendations based on experiment results and analysis.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple, Set
from enum import Enum
import json
from pathlib import Path
from collections import defaultdict
import numpy as np


class RecommendationType(Enum):
    """Types of recommendations."""
    EXPERIMENTAL = "experimental"
    IMPLEMENTATION = "implementation"
    THEORETICAL = "theoretical"
    DEPLOYMENT = "deployment"
    MONITORING = "monitoring"
    RISK_MITIGATION = "risk_mitigation"
    OPTIMIZATION = "optimization"
    FURTHER_RESEARCH = "further_research"


class RecommendationUrgency(Enum):
    """Urgency levels for recommendations."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"


class StakeholderType(Enum):
    """Types of stakeholders for targeted recommendations."""
    TECHNICAL_TEAM = "technical_team"
    RESEARCH_TEAM = "research_team"
    MANAGEMENT = "management"
    INVESTORS = "investors"
    OPERATIONS = "operations"
    SECURITY = "security"


@dataclass
class Recommendation:
    """A single actionable recommendation."""
    recommendation_id: str
    title: str
    description: str
    recommendation_type: RecommendationType
    urgency: RecommendationUrgency

    # Target
    target_hypotheses: List[str]
    target_domains: List[str]
    target_stakeholders: List[StakeholderType]

    # Action details
    action_items: List[str]
    prerequisites: List[str]
    expected_outcomes: List[str]

    # Impact
    impact_score: float  # 0-1
    confidence: float  # 0-1
    effort_estimate: str

    # Dependencies
    related_recommendations: List[str]
    blocking_issues: List[str]

    # Metadata
    rationale: str
    evidence: List[str]
    risks: List[str]
    metrics: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "recommendation_id": self.recommendation_id,
            "title": self.title,
            "description": self.description,
            "type": self.recommendation_type.value,
            "urgency": self.urgency.value,
            "target_hypotheses": self.target_hypotheses,
            "target_domains": self.target_domains,
            "target_stakeholders": [s.value for s in self.target_stakeholders],
            "action_items": self.action_items,
            "prerequisites": self.prerequisites,
            "expected_outcomes": self.expected_outcomes,
            "impact_score": self.impact_score,
            "confidence": self.confidence,
            "effort_estimate": self.effort_estimate,
            "related_recommendations": self.related_recommendations,
            "blocking_issues": self.blocking_issues,
            "rationale": self.rationale,
            "evidence": self.evidence,
            "risks": self.risks,
            "metrics": self.metrics,
        }


@dataclass
class RecommendationSet:
    """A set of related recommendations."""
    set_id: str
    title: str
    description: str
    recommendations: List[Recommendation]
    priority_order: List[str]
    total_impact: float
    implementation_sequence: List[List[str]]

    def to_dict(self) -> dict:
        return {
            "set_id": self.set_id,
            "title": self.title,
            "description": self.description,
            "recommendations": [r.to_dict() for r in self.recommendations],
            "priority_order": self.priority_order,
            "total_impact": self.total_impact,
            "implementation_sequence": self.implementation_sequence,
        }


@dataclass
class ActionPlan:
    """Comprehensive action plan with prioritized recommendations."""
    plan_id: str
    overall_verdict: str
    summary: str

    # Prioritized recommendations
    critical_actions: List[Recommendation]
    high_priority: List[Recommendation]
    medium_priority: List[Recommendation]
    low_priority: List[Recommendation]

    # Timelines
    immediate_phase: List[str]  # 0-2 weeks
    short_term_phase: List[str]  # 2-8 weeks
    long_term_phase: List[str]  # 8+ weeks

    # Resources
    resource_requirements: Dict[str, List[str]]
    stakeholder_assignments: Dict[str, List[str]]

    # Metrics
    success_metrics: List[str]
    risk_factors: List[str]
    contingencies: List[str]

    def to_dict(self) -> dict:
        return {
            "plan_id": self.plan_id,
            "overall_verdict": self.overall_verdict,
            "summary": self.summary,
            "critical_actions": [r.to_dict() for r in self.critical_actions],
            "high_priority": [r.to_dict() for r in self.high_priority],
            "medium_priority": [r.to_dict() for r in self.medium_priority],
            "low_priority": [r.to_dict() for r in self.low_priority],
            "immediate_phase": self.immediate_phase,
            "short_term_phase": self.short_term_phase,
            "long_term_phase": self.long_term_phase,
            "resource_requirements": self.resource_requirements,
            "stakeholder_assignments": self.stakeholder_assignments,
            "success_metrics": self.success_metrics,
            "risk_factors": self.risk_factors,
            "contingencies": self.contingencies,
        }


# Domain-specific recommendation templates
DOMAIN_RECOMMENDATIONS = {
    "token_economics": {
        "success": [
            ("Proceed with token deployment", RecommendationType.DEPLOYMENT, RecommendationUrgency.MEDIUM),
            ("Establish monitoring for token metrics", RecommendationType.MONITORING, RecommendationUrgency.HIGH),
        ],
        "partial": [
            ("Review token distribution model", RecommendationType.THEORETICAL, RecommendationUrgency.HIGH),
            ("Conduct additional stress tests", RecommendationType.EXPERIMENTAL, RecommendationUrgency.MEDIUM),
        ],
        "failure": [
            ("Revise token economics model", RecommendationType.THEORETICAL, RecommendationUrgency.CRITICAL),
            ("Delay deployment until issues resolved", RecommendationType.DEPLOYMENT, RecommendationUrgency.CRITICAL),
        ],
    },
    "data_integrity": {
        "success": [
            ("Implement data validation in production", RecommendationType.IMPLEMENTATION, RecommendationUrgency.HIGH),
            ("Set up integrity monitoring", RecommendationType.MONITORING, RecommendationUrgency.HIGH),
        ],
        "partial": [
            ("Strengthen validation mechanisms", RecommendationType.IMPLEMENTATION, RecommendationUrgency.HIGH),
            ("Investigate edge cases", RecommendationType.EXPERIMENTAL, RecommendationUrgency.MEDIUM),
        ],
        "failure": [
            ("Redesign data integrity approach", RecommendationType.IMPLEMENTATION, RecommendationUrgency.CRITICAL),
            ("Halt deployment pending fixes", RecommendationType.DEPLOYMENT, RecommendationUrgency.CRITICAL),
        ],
    },
    "system_dynamics": {
        "success": [
            ("Document stable operating parameters", RecommendationType.IMPLEMENTATION, RecommendationUrgency.MEDIUM),
            ("Implement system monitoring", RecommendationType.MONITORING, RecommendationUrgency.HIGH),
        ],
        "partial": [
            ("Identify stability boundaries", RecommendationType.EXPERIMENTAL, RecommendationUrgency.HIGH),
            ("Add circuit breakers", RecommendationType.IMPLEMENTATION, RecommendationUrgency.HIGH),
        ],
        "failure": [
            ("Analyze instability sources", RecommendationType.THEORETICAL, RecommendationUrgency.CRITICAL),
            ("Implement stability controls", RecommendationType.IMPLEMENTATION, RecommendationUrgency.CRITICAL),
        ],
    },
    "agent_behavior": {
        "success": [
            ("Deploy agent coordination framework", RecommendationType.DEPLOYMENT, RecommendationUrgency.MEDIUM),
            ("Monitor agent interactions", RecommendationType.MONITORING, RecommendationUrgency.MEDIUM),
        ],
        "partial": [
            ("Refine agent behavior models", RecommendationType.THEORETICAL, RecommendationUrgency.HIGH),
            ("Test additional scenarios", RecommendationType.EXPERIMENTAL, RecommendationUrgency.MEDIUM),
        ],
        "failure": [
            ("Redesign agent coordination", RecommendationType.IMPLEMENTATION, RecommendationUrgency.CRITICAL),
            ("Research alternative approaches", RecommendationType.FURTHER_RESEARCH, RecommendationUrgency.HIGH),
        ],
    },
    "stress_testing": {
        "success": [
            ("Document system limits", RecommendationType.IMPLEMENTATION, RecommendationUrgency.MEDIUM),
            ("Implement load monitoring", RecommendationType.MONITORING, RecommendationUrgency.HIGH),
        ],
        "partial": [
            ("Optimize performance bottlenecks", RecommendationType.OPTIMIZATION, RecommendationUrgency.HIGH),
            ("Conduct targeted stress tests", RecommendationType.EXPERIMENTAL, RecommendationUrgency.MEDIUM),
        ],
        "failure": [
            ("Critical performance improvements needed", RecommendationType.IMPLEMENTATION, RecommendationUrgency.CRITICAL),
            ("Delay launch until performance acceptable", RecommendationType.DEPLOYMENT, RecommendationUrgency.CRITICAL),
        ],
    },
    "forecasting": {
        "success": [
            ("Deploy forecasting models", RecommendationType.DEPLOYMENT, RecommendationUrgency.MEDIUM),
            ("Monitor prediction accuracy", RecommendationType.MONITORING, RecommendationUrgency.MEDIUM),
        ],
        "partial": [
            ("Improve model calibration", RecommendationType.IMPLEMENTATION, RecommendationUrgency.MEDIUM),
            ("Collect additional training data", RecommendationType.EXPERIMENTAL, RecommendationUrgency.LOW),
        ],
        "failure": [
            ("Revise forecasting approach", RecommendationType.THEORETICAL, RecommendationUrgency.HIGH),
            ("Consider alternative models", RecommendationType.FURTHER_RESEARCH, RecommendationUrgency.HIGH),
        ],
    },
}

# Critical hypothesis handling
CRITICAL_HYPOTHESIS_RECOMMENDATIONS = {
    "H1.2": {
        "failure": [
            "Token price stability mechanism must be redesigned",
            "Consider alternative market-making approaches",
            "Delay mainnet launch until resolved",
        ]
    },
    "H1.3": {
        "failure": [
            "Incentive alignment fundamentally flawed",
            "Review game-theoretic model assumptions",
            "Engage external economists for review",
        ]
    },
    "H1.4": {
        "failure": [
            "Supply-demand equilibrium not achieved",
            "Revise tokenomics parameters",
            "Consider dynamic adjustment mechanisms",
        ]
    },
    "H2.1": {
        "failure": [
            "Data integrity guarantees not met",
            "Implement additional validation layers",
            "Cannot proceed without data integrity",
        ]
    },
    "H3.6": {
        "failure": [
            "System stability under load inadequate",
            "Add rate limiting and circuit breakers",
            "Performance optimization critical path",
        ]
    },
    "H5.1": {
        "failure": [
            "Agent coordination mechanism flawed",
            "Redesign multi-agent interaction protocol",
            "Test with simplified agent models first",
        ]
    },
}


class RecommendationEngine:
    """
    Generates actionable recommendations based on experiment results.

    This engine analyzes results and produces:
    - Prioritized recommendations
    - Stakeholder-specific guidance
    - Implementation roadmaps
    - Risk mitigation strategies
    """

    def __init__(
        self,
        domain_results: Optional[Dict[str, Any]] = None,
        failure_analysis: Optional[Dict[str, Any]] = None,
        cross_domain_analysis: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize recommendation engine.

        Args:
            domain_results: Results from each domain
            failure_analysis: Failure analysis results
            cross_domain_analysis: Cross-domain analysis results
        """
        self.domain_results = domain_results or {}
        self.failure_analysis = failure_analysis or {}
        self.cross_domain_analysis = cross_domain_analysis or {}

        self.recommendations: List[Recommendation] = []
        self._recommendation_counter = 0

    def _generate_id(self) -> str:
        """Generate unique recommendation ID."""
        self._recommendation_counter += 1
        return f"REC-{self._recommendation_counter:03d}"

    def analyze_and_recommend(self) -> List[Recommendation]:
        """
        Analyze all inputs and generate comprehensive recommendations.

        Returns:
            List of recommendations
        """
        self.recommendations = []

        # Generate domain-specific recommendations
        self._generate_domain_recommendations()

        # Generate failure-based recommendations
        self._generate_failure_recommendations()

        # Generate cross-domain recommendations
        self._generate_cross_domain_recommendations()

        # Generate risk mitigation recommendations
        self._generate_risk_recommendations()

        # Generate deployment recommendations
        self._generate_deployment_recommendations()

        # Sort by urgency and impact
        self.recommendations.sort(
            key=lambda r: (
                -list(RecommendationUrgency).index(r.urgency),
                -r.impact_score,
            )
        )

        return self.recommendations

    def _determine_domain_status(self, domain: str) -> str:
        """Determine domain status (success/partial/failure)."""
        if domain not in self.domain_results:
            return "partial"

        results = self.domain_results[domain]
        if isinstance(results, dict):
            success_rate = results.get("success_rate", 0.5)
            critical_failures = results.get("critical_failures", [])
        else:
            # Assume it's a domain results object
            success_rate = getattr(results, "success_rate", 0.5)
            critical_failures = getattr(results, "critical_failures", [])

        if critical_failures:
            return "failure"
        if success_rate >= 0.8:
            return "success"
        if success_rate >= 0.5:
            return "partial"
        return "failure"

    def _generate_domain_recommendations(self) -> None:
        """Generate recommendations for each domain."""
        for domain, templates in DOMAIN_RECOMMENDATIONS.items():
            status = self._determine_domain_status(domain)
            domain_templates = templates.get(status, [])

            for title, rec_type, urgency in domain_templates:
                rec = Recommendation(
                    recommendation_id=self._generate_id(),
                    title=title,
                    description=f"Based on {domain} experiment results ({status})",
                    recommendation_type=rec_type,
                    urgency=urgency,
                    target_hypotheses=[],
                    target_domains=[domain],
                    target_stakeholders=self._get_stakeholders_for_type(rec_type),
                    action_items=self._get_action_items(title, rec_type, domain),
                    prerequisites=[],
                    expected_outcomes=[f"Improved {domain} performance"],
                    impact_score=self._calculate_impact(urgency, domain),
                    confidence=0.7,
                    effort_estimate=self._estimate_effort(rec_type),
                    related_recommendations=[],
                    blocking_issues=[],
                    rationale=f"Domain {domain} shows {status} status",
                    evidence=[f"{domain} experiments analyzed"],
                    risks=self._identify_risks(rec_type, urgency),
                )
                self.recommendations.append(rec)

    def _generate_failure_recommendations(self) -> None:
        """Generate recommendations based on failure analysis."""
        failures = self.failure_analysis.get("failures", [])

        for failure in failures:
            h_id = failure.get("hypothesis_id", "UNKNOWN")
            is_critical = failure.get("is_critical", False)
            category = failure.get("category", "unknown")
            domain = failure.get("domain", "unknown")

            # Check for critical hypothesis specific recommendations
            if h_id in CRITICAL_HYPOTHESIS_RECOMMENDATIONS:
                for action in CRITICAL_HYPOTHESIS_RECOMMENDATIONS[h_id]["failure"]:
                    rec = Recommendation(
                        recommendation_id=self._generate_id(),
                        title=f"Address {h_id} failure",
                        description=action,
                        recommendation_type=RecommendationType.IMPLEMENTATION,
                        urgency=RecommendationUrgency.CRITICAL,
                        target_hypotheses=[h_id],
                        target_domains=[domain],
                        target_stakeholders=[
                            StakeholderType.TECHNICAL_TEAM,
                            StakeholderType.RESEARCH_TEAM,
                            StakeholderType.MANAGEMENT,
                        ],
                        action_items=[action],
                        prerequisites=[],
                        expected_outcomes=[f"Resolution of {h_id} failure"],
                        impact_score=0.95,
                        confidence=0.8,
                        effort_estimate="High",
                        related_recommendations=[],
                        blocking_issues=[],
                        rationale=f"Critical hypothesis {h_id} failed validation",
                        evidence=[f"P-value: {failure.get('p_value', 'N/A')}"],
                        risks=["System may not function as designed without fix"],
                    )
                    self.recommendations.append(rec)
            elif is_critical:
                # Generic critical failure recommendation
                rec = Recommendation(
                    recommendation_id=self._generate_id(),
                    title=f"Investigate critical failure: {h_id}",
                    description=failure.get("root_cause", "Unknown root cause"),
                    recommendation_type=self._category_to_type(category),
                    urgency=RecommendationUrgency.CRITICAL,
                    target_hypotheses=[h_id],
                    target_domains=[domain],
                    target_stakeholders=[
                        StakeholderType.TECHNICAL_TEAM,
                        StakeholderType.RESEARCH_TEAM,
                    ],
                    action_items=failure.get("remediation_options", []),
                    prerequisites=[],
                    expected_outcomes=["Resolution of critical failure"],
                    impact_score=0.9,
                    confidence=failure.get("confidence", 0.7),
                    effort_estimate=failure.get("estimated_effort", "Unknown"),
                    related_recommendations=[],
                    blocking_issues=[],
                    rationale=f"Critical hypothesis failure requires immediate attention",
                    evidence=failure.get("evidence", []),
                    risks=["Cascade effects possible"],
                )
                self.recommendations.append(rec)

        # Pattern-based recommendations
        patterns = self.failure_analysis.get("patterns", [])
        for pattern in patterns:
            rec = Recommendation(
                recommendation_id=self._generate_id(),
                title=f"Address pattern: {pattern.get('description', 'Unknown')}",
                description=pattern.get("potential_root_cause", ""),
                recommendation_type=RecommendationType.IMPLEMENTATION,
                urgency=RecommendationUrgency.HIGH,
                target_hypotheses=pattern.get("affected_hypotheses", []),
                target_domains=pattern.get("affected_domains", []),
                target_stakeholders=[
                    StakeholderType.TECHNICAL_TEAM,
                    StakeholderType.RESEARCH_TEAM,
                ],
                action_items=["Investigate systematic pattern", "Apply unified fix"],
                prerequisites=[],
                expected_outcomes=["Resolution of multiple related failures"],
                impact_score=0.8,
                confidence=pattern.get("confidence", 0.6),
                effort_estimate="Medium-High",
                related_recommendations=[],
                blocking_issues=[],
                rationale="Systematic pattern affects multiple hypotheses",
                evidence=[f"Affects {len(pattern.get('affected_hypotheses', []))} hypotheses"],
                risks=["Pattern may indicate fundamental issue"],
            )
            self.recommendations.append(rec)

    def _generate_cross_domain_recommendations(self) -> None:
        """Generate recommendations from cross-domain analysis."""
        tradeoffs = self.cross_domain_analysis.get("tradeoffs", [])
        correlations = self.cross_domain_analysis.get("correlations", {})

        for tradeoff in tradeoffs:
            rec = Recommendation(
                recommendation_id=self._generate_id(),
                title=f"Optimize tradeoff: {tradeoff.get('domain1', 'X')} vs {tradeoff.get('domain2', 'Y')}",
                description=tradeoff.get("recommendation", "Balance competing concerns"),
                recommendation_type=RecommendationType.OPTIMIZATION,
                urgency=RecommendationUrgency.MEDIUM,
                target_hypotheses=[],
                target_domains=[tradeoff.get("domain1"), tradeoff.get("domain2")],
                target_stakeholders=[
                    StakeholderType.TECHNICAL_TEAM,
                    StakeholderType.MANAGEMENT,
                ],
                action_items=[
                    "Analyze tradeoff boundaries",
                    "Define acceptable operating range",
                    "Implement monitoring for balance",
                ],
                prerequisites=[],
                expected_outcomes=["Optimized balance between domains"],
                impact_score=0.6,
                confidence=0.65,
                effort_estimate="Medium",
                related_recommendations=[],
                blocking_issues=[],
                rationale="Cross-domain tradeoff identified",
                evidence=[f"Correlation: {tradeoff.get('correlation', 'N/A')}"],
                risks=["Over-optimization in one domain may harm another"],
            )
            self.recommendations.append(rec)

        # Strong correlations suggest shared factors
        for key, corr_data in correlations.items():
            if isinstance(corr_data, dict):
                corr_value = corr_data.get("correlation", 0)
            else:
                corr_value = float(corr_data) if corr_data else 0

            if abs(corr_value) > 0.7:
                domains = key.split("_vs_") if "_vs_" in key else [key]
                rec = Recommendation(
                    recommendation_id=self._generate_id(),
                    title=f"Leverage correlation: {key}",
                    description=f"Strong correlation ({corr_value:.2f}) suggests shared factors",
                    recommendation_type=RecommendationType.OPTIMIZATION,
                    urgency=RecommendationUrgency.LOW,
                    target_hypotheses=[],
                    target_domains=domains,
                    target_stakeholders=[StakeholderType.RESEARCH_TEAM],
                    action_items=[
                        "Investigate shared factors",
                        "Consider unified optimization",
                    ],
                    prerequisites=[],
                    expected_outcomes=["Efficient multi-domain improvement"],
                    impact_score=0.5,
                    confidence=0.6,
                    effort_estimate="Low",
                    related_recommendations=[],
                    blocking_issues=[],
                    rationale="Strong correlation indicates optimization opportunity",
                    evidence=[f"r = {corr_value:.2f}"],
                    risks=[],
                )
                self.recommendations.append(rec)

    def _generate_risk_recommendations(self) -> None:
        """Generate risk mitigation recommendations."""
        # Check for cascade risks
        failures = self.failure_analysis.get("failures", [])
        high_cascade = [
            f for f in failures
            if f.get("cascade_risk", 0) > 0.5
        ]

        if high_cascade:
            affected = [f["hypothesis_id"] for f in high_cascade]
            rec = Recommendation(
                recommendation_id=self._generate_id(),
                title="Mitigate cascade failure risk",
                description="Multiple failures have high cascade risk",
                recommendation_type=RecommendationType.RISK_MITIGATION,
                urgency=RecommendationUrgency.HIGH,
                target_hypotheses=affected,
                target_domains=[],
                target_stakeholders=[
                    StakeholderType.TECHNICAL_TEAM,
                    StakeholderType.MANAGEMENT,
                ],
                action_items=[
                    "Prioritize resolution of high-cascade failures",
                    "Implement isolation mechanisms",
                    "Create contingency plans",
                ],
                prerequisites=[],
                expected_outcomes=["Reduced risk of cascading failures"],
                impact_score=0.85,
                confidence=0.75,
                effort_estimate="High",
                related_recommendations=[],
                blocking_issues=[],
                rationale=f"{len(high_cascade)} failures have cascade risk > 50%",
                evidence=[f["hypothesis_id"] for f in high_cascade[:3]],
                risks=["Unaddressed cascade risks may cause systemic failure"],
            )
            self.recommendations.append(rec)

        # Check overall failure rate
        summary = self.failure_analysis.get("summary", {})
        total_failures = summary.get("total_failures", 0)
        critical_failures = summary.get("critical_failures", 0)

        if critical_failures > 0:
            rec = Recommendation(
                recommendation_id=self._generate_id(),
                title="Address critical hypothesis failures",
                description=f"{critical_failures} critical hypotheses have failed",
                recommendation_type=RecommendationType.RISK_MITIGATION,
                urgency=RecommendationUrgency.CRITICAL,
                target_hypotheses=[],
                target_domains=[],
                target_stakeholders=[
                    StakeholderType.MANAGEMENT,
                    StakeholderType.INVESTORS,
                ],
                action_items=[
                    "Review and address each critical failure",
                    "Assess impact on project timeline",
                    "Communicate risks to stakeholders",
                ],
                prerequisites=[],
                expected_outcomes=["All critical hypotheses pass validation"],
                impact_score=0.95,
                confidence=0.9,
                effort_estimate="Variable",
                related_recommendations=[],
                blocking_issues=[],
                rationale="Critical hypotheses are blockers for deployment",
                evidence=[f"{critical_failures} critical failures identified"],
                risks=["Project cannot proceed without resolution"],
            )
            self.recommendations.append(rec)

    def _generate_deployment_recommendations(self) -> None:
        """Generate deployment-related recommendations."""
        # Assess overall readiness
        failures = self.failure_analysis.get("failures", [])
        critical_failures = [f for f in failures if f.get("is_critical", False)]

        if not critical_failures:
            # No critical failures - can consider deployment
            rec = Recommendation(
                recommendation_id=self._generate_id(),
                title="Proceed with staged deployment",
                description="No critical failures; system may be ready for limited deployment",
                recommendation_type=RecommendationType.DEPLOYMENT,
                urgency=RecommendationUrgency.MEDIUM,
                target_hypotheses=[],
                target_domains=[],
                target_stakeholders=[
                    StakeholderType.MANAGEMENT,
                    StakeholderType.OPERATIONS,
                ],
                action_items=[
                    "Prepare deployment checklist",
                    "Set up monitoring infrastructure",
                    "Plan rollback procedures",
                    "Start with limited testnet deployment",
                ],
                prerequisites=["Address all high-priority recommendations"],
                expected_outcomes=["Successful limited deployment"],
                impact_score=0.7,
                confidence=0.6,
                effort_estimate="High",
                related_recommendations=[],
                blocking_issues=[],
                rationale="No critical blockers identified",
                evidence=["All critical hypotheses validated"],
                risks=["Non-critical issues may surface in deployment"],
            )
            self.recommendations.append(rec)
        else:
            # Critical failures exist - deployment not recommended
            rec = Recommendation(
                recommendation_id=self._generate_id(),
                title="Delay deployment pending fixes",
                description="Critical failures must be resolved before deployment",
                recommendation_type=RecommendationType.DEPLOYMENT,
                urgency=RecommendationUrgency.CRITICAL,
                target_hypotheses=[f["hypothesis_id"] for f in critical_failures],
                target_domains=[],
                target_stakeholders=[
                    StakeholderType.MANAGEMENT,
                    StakeholderType.INVESTORS,
                ],
                action_items=[
                    "Do not proceed with deployment",
                    "Resolve all critical failures first",
                    "Re-run validation after fixes",
                ],
                prerequisites=[],
                expected_outcomes=["Safe deployment after issues resolved"],
                impact_score=1.0,
                confidence=0.95,
                effort_estimate="N/A",
                related_recommendations=[],
                blocking_issues=[f["hypothesis_id"] for f in critical_failures],
                rationale=f"{len(critical_failures)} critical failures block deployment",
                evidence=[f["hypothesis_id"] for f in critical_failures],
                risks=["Deployment without fixes risks system failure"],
            )
            self.recommendations.append(rec)

    def _get_stakeholders_for_type(
        self,
        rec_type: RecommendationType,
    ) -> List[StakeholderType]:
        """Get relevant stakeholders for recommendation type."""
        mapping = {
            RecommendationType.EXPERIMENTAL: [
                StakeholderType.RESEARCH_TEAM,
                StakeholderType.TECHNICAL_TEAM,
            ],
            RecommendationType.IMPLEMENTATION: [
                StakeholderType.TECHNICAL_TEAM,
            ],
            RecommendationType.THEORETICAL: [
                StakeholderType.RESEARCH_TEAM,
            ],
            RecommendationType.DEPLOYMENT: [
                StakeholderType.MANAGEMENT,
                StakeholderType.OPERATIONS,
            ],
            RecommendationType.MONITORING: [
                StakeholderType.OPERATIONS,
                StakeholderType.TECHNICAL_TEAM,
            ],
            RecommendationType.RISK_MITIGATION: [
                StakeholderType.MANAGEMENT,
                StakeholderType.SECURITY,
            ],
            RecommendationType.OPTIMIZATION: [
                StakeholderType.TECHNICAL_TEAM,
                StakeholderType.RESEARCH_TEAM,
            ],
            RecommendationType.FURTHER_RESEARCH: [
                StakeholderType.RESEARCH_TEAM,
            ],
        }
        return mapping.get(rec_type, [StakeholderType.TECHNICAL_TEAM])

    def _get_action_items(
        self,
        title: str,
        rec_type: RecommendationType,
        domain: str,
    ) -> List[str]:
        """Generate action items for a recommendation."""
        base_items = {
            RecommendationType.EXPERIMENTAL: [
                f"Design additional {domain} experiments",
                "Determine required sample sizes",
                "Execute experiments and collect data",
                "Analyze results and update findings",
            ],
            RecommendationType.IMPLEMENTATION: [
                "Review current implementation",
                "Design improvements",
                "Implement changes",
                "Test and validate",
            ],
            RecommendationType.THEORETICAL: [
                "Review theoretical assumptions",
                "Consult relevant literature",
                "Update models if needed",
                "Document changes",
            ],
            RecommendationType.DEPLOYMENT: [
                "Prepare deployment plan",
                "Set up infrastructure",
                "Execute staged rollout",
                "Monitor and adjust",
            ],
            RecommendationType.MONITORING: [
                "Define key metrics",
                "Set up monitoring dashboards",
                "Configure alerts",
                "Establish response procedures",
            ],
            RecommendationType.RISK_MITIGATION: [
                "Identify specific risks",
                "Develop mitigation strategies",
                "Implement safeguards",
                "Test contingency plans",
            ],
            RecommendationType.OPTIMIZATION: [
                "Profile current performance",
                "Identify bottlenecks",
                "Implement optimizations",
                "Measure improvements",
            ],
            RecommendationType.FURTHER_RESEARCH: [
                "Define research questions",
                "Literature review",
                "Design studies",
                "Execute and publish findings",
            ],
        }
        return base_items.get(rec_type, ["Review", "Plan", "Execute", "Validate"])

    def _calculate_impact(
        self,
        urgency: RecommendationUrgency,
        domain: str,
    ) -> float:
        """Calculate impact score."""
        urgency_scores = {
            RecommendationUrgency.CRITICAL: 0.95,
            RecommendationUrgency.HIGH: 0.8,
            RecommendationUrgency.MEDIUM: 0.6,
            RecommendationUrgency.LOW: 0.4,
            RecommendationUrgency.INFORMATIONAL: 0.2,
        }

        domain_weights = {
            "token_economics": 1.0,
            "data_integrity": 0.95,
            "system_dynamics": 0.85,
            "agent_behavior": 0.8,
            "stress_testing": 0.75,
            "forecasting": 0.7,
        }

        base = urgency_scores.get(urgency, 0.5)
        weight = domain_weights.get(domain, 0.8)

        return base * weight

    def _estimate_effort(self, rec_type: RecommendationType) -> str:
        """Estimate effort for recommendation type."""
        efforts = {
            RecommendationType.EXPERIMENTAL: "Medium-High (2-4 weeks)",
            RecommendationType.IMPLEMENTATION: "Medium (1-2 weeks)",
            RecommendationType.THEORETICAL: "Low-Medium (1-2 weeks)",
            RecommendationType.DEPLOYMENT: "High (4-8 weeks)",
            RecommendationType.MONITORING: "Low (< 1 week)",
            RecommendationType.RISK_MITIGATION: "Medium (1-3 weeks)",
            RecommendationType.OPTIMIZATION: "Medium (1-2 weeks)",
            RecommendationType.FURTHER_RESEARCH: "High (4+ weeks)",
        }
        return efforts.get(rec_type, "Unknown")

    def _identify_risks(
        self,
        rec_type: RecommendationType,
        urgency: RecommendationUrgency,
    ) -> List[str]:
        """Identify risks associated with recommendation."""
        risks = []

        if urgency in [RecommendationUrgency.CRITICAL, RecommendationUrgency.HIGH]:
            risks.append("Delay in addressing may have significant consequences")

        if rec_type == RecommendationType.DEPLOYMENT:
            risks.append("Deployment risks include potential service disruption")
        elif rec_type == RecommendationType.IMPLEMENTATION:
            risks.append("Implementation changes may introduce new issues")
        elif rec_type == RecommendationType.EXPERIMENTAL:
            risks.append("Experiments may not yield conclusive results")

        return risks

    def _category_to_type(self, category: str) -> RecommendationType:
        """Map failure category to recommendation type."""
        mapping = {
            "statistical_power": RecommendationType.EXPERIMENTAL,
            "effect_size": RecommendationType.THEORETICAL,
            "assumption_violation": RecommendationType.EXPERIMENTAL,
            "data_quality": RecommendationType.IMPLEMENTATION,
            "methodology": RecommendationType.EXPERIMENTAL,
            "implementation": RecommendationType.IMPLEMENTATION,
            "external_factors": RecommendationType.RISK_MITIGATION,
            "threshold_boundary": RecommendationType.EXPERIMENTAL,
            "unknown": RecommendationType.FURTHER_RESEARCH,
        }
        return mapping.get(category, RecommendationType.IMPLEMENTATION)

    def generate_action_plan(self) -> ActionPlan:
        """
        Generate comprehensive action plan from recommendations.

        Returns:
            Structured action plan
        """
        if not self.recommendations:
            self.analyze_and_recommend()

        # Categorize by urgency
        critical = [r for r in self.recommendations if r.urgency == RecommendationUrgency.CRITICAL]
        high = [r for r in self.recommendations if r.urgency == RecommendationUrgency.HIGH]
        medium = [r for r in self.recommendations if r.urgency == RecommendationUrgency.MEDIUM]
        low = [r for r in self.recommendations if r.urgency in [RecommendationUrgency.LOW, RecommendationUrgency.INFORMATIONAL]]

        # Determine overall verdict
        if critical:
            verdict = "NOT_READY"
            summary = f"System not ready for deployment. {len(critical)} critical issues require resolution."
        elif high:
            verdict = "CONDITIONAL"
            summary = f"System conditionally ready. {len(high)} high-priority issues should be addressed."
        else:
            verdict = "READY"
            summary = "System ready for staged deployment. Continue monitoring recommendations."

        # Create phased timeline
        immediate = [r.title for r in critical[:5]]
        short_term = [r.title for r in high[:10]]
        long_term = [r.title for r in medium[:10] + low[:5]]

        # Aggregate resources
        resources: Dict[str, List[str]] = defaultdict(list)
        stakeholder_assignments: Dict[str, List[str]] = defaultdict(list)

        for rec in self.recommendations:
            for stakeholder in rec.target_stakeholders:
                stakeholder_assignments[stakeholder.value].append(rec.recommendation_id)

            if rec.recommendation_type == RecommendationType.EXPERIMENTAL:
                resources["research"].append(rec.recommendation_id)
            elif rec.recommendation_type == RecommendationType.IMPLEMENTATION:
                resources["engineering"].append(rec.recommendation_id)
            elif rec.recommendation_type == RecommendationType.DEPLOYMENT:
                resources["operations"].append(rec.recommendation_id)

        # Success metrics
        success_metrics = [
            "All critical recommendations addressed",
            "80% of high-priority recommendations completed",
            "All critical hypotheses pass validation",
            "No new critical issues identified",
        ]

        # Risk factors
        risk_factors = []
        if critical:
            risk_factors.append(f"{len(critical)} critical issues outstanding")
        if len(self.failure_analysis.get("patterns", [])) > 0:
            risk_factors.append("Systematic failure patterns detected")

        # Contingencies
        contingencies = [
            "If timeline slips: Prioritize critical issues only",
            "If new issues emerge: Re-run full analysis",
            "If resources constrained: Focus on blocking issues",
        ]

        return ActionPlan(
            plan_id="PLAN-001",
            overall_verdict=verdict,
            summary=summary,
            critical_actions=critical,
            high_priority=high,
            medium_priority=medium,
            low_priority=low,
            immediate_phase=immediate,
            short_term_phase=short_term,
            long_term_phase=long_term,
            resource_requirements=dict(resources),
            stakeholder_assignments=dict(stakeholder_assignments),
            success_metrics=success_metrics,
            risk_factors=risk_factors,
            contingencies=contingencies,
        )

    def get_recommendations_for_stakeholder(
        self,
        stakeholder: StakeholderType,
    ) -> List[Recommendation]:
        """Get recommendations relevant to a specific stakeholder."""
        if not self.recommendations:
            self.analyze_and_recommend()

        return [
            r for r in self.recommendations
            if stakeholder in r.target_stakeholders
        ]

    def get_recommendations_by_type(
        self,
        rec_type: RecommendationType,
    ) -> List[Recommendation]:
        """Get recommendations of a specific type."""
        if not self.recommendations:
            self.analyze_and_recommend()

        return [
            r for r in self.recommendations
            if r.recommendation_type == rec_type
        ]

    def generate_markdown_report(self) -> str:
        """Generate markdown-formatted recommendations report."""
        if not self.recommendations:
            self.analyze_and_recommend()

        plan = self.generate_action_plan()

        lines = [
            "# SHAKTI-CHAIN Recommendations Report",
            "",
            "## Executive Summary",
            "",
            f"**Overall Verdict**: {plan.overall_verdict}",
            "",
            plan.summary,
            "",
            "## Statistics",
            "",
            f"- Total Recommendations: {len(self.recommendations)}",
            f"- Critical: {len(plan.critical_actions)}",
            f"- High Priority: {len(plan.high_priority)}",
            f"- Medium Priority: {len(plan.medium_priority)}",
            f"- Low Priority: {len(plan.low_priority)}",
            "",
        ]

        if plan.critical_actions:
            lines.extend([
                "## Critical Actions (Immediate)",
                "",
            ])
            for rec in plan.critical_actions:
                lines.extend([
                    f"### {rec.recommendation_id}: {rec.title}",
                    "",
                    rec.description,
                    "",
                    "**Action Items:**",
                ])
                for item in rec.action_items:
                    lines.append(f"- {item}")
                lines.extend([
                    "",
                    f"**Impact**: {rec.impact_score:.0%} | **Confidence**: {rec.confidence:.0%}",
                    "",
                ])

        if plan.high_priority:
            lines.extend([
                "## High Priority Actions",
                "",
            ])
            for rec in plan.high_priority[:10]:
                lines.extend([
                    f"### {rec.recommendation_id}: {rec.title}",
                    "",
                    rec.description,
                    "",
                    f"**Effort**: {rec.effort_estimate}",
                    "",
                ])

        lines.extend([
            "## Implementation Timeline",
            "",
            "### Immediate (0-2 weeks)",
            "",
        ])
        for action in plan.immediate_phase:
            lines.append(f"- {action}")

        lines.extend([
            "",
            "### Short-term (2-8 weeks)",
            "",
        ])
        for action in plan.short_term_phase[:10]:
            lines.append(f"- {action}")

        lines.extend([
            "",
            "### Long-term (8+ weeks)",
            "",
        ])
        for action in plan.long_term_phase[:10]:
            lines.append(f"- {action}")

        if plan.risk_factors:
            lines.extend([
                "",
                "## Risk Factors",
                "",
            ])
            for risk in plan.risk_factors:
                lines.append(f"- {risk}")

        lines.extend([
            "",
            "## Success Metrics",
            "",
        ])
        for metric in plan.success_metrics:
            lines.append(f"- {metric}")

        return "\n".join(lines)

    def save_report(
        self,
        output_path: Path,
        format: str = "json",
    ) -> None:
        """
        Save recommendations report.

        Args:
            output_path: Output file path
            format: 'json' or 'markdown'
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if format == "json":
            plan = self.generate_action_plan()
            with open(output_path, "w") as f:
                json.dump({
                    "action_plan": plan.to_dict(),
                    "all_recommendations": [r.to_dict() for r in self.recommendations],
                }, f, indent=2)
        elif format == "markdown":
            with open(output_path, "w") as f:
                f.write(self.generate_markdown_report())
        else:
            raise ValueError(f"Unknown format: {format}")


def generate_recommendations(
    domain_results: Dict[str, Any],
    failure_analysis: Optional[Dict[str, Any]] = None,
    cross_domain_analysis: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Convenience function to generate recommendations.

    Args:
        domain_results: Results from each domain
        failure_analysis: Optional failure analysis
        cross_domain_analysis: Optional cross-domain analysis

    Returns:
        Action plan and recommendations
    """
    engine = RecommendationEngine(
        domain_results=domain_results,
        failure_analysis=failure_analysis or {},
        cross_domain_analysis=cross_domain_analysis or {},
    )

    plan = engine.generate_action_plan()

    return {
        "action_plan": plan.to_dict(),
        "recommendations": [r.to_dict() for r in engine.recommendations],
        "markdown_report": engine.generate_markdown_report(),
    }
