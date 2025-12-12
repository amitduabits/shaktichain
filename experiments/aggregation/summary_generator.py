"""
Summary Generator Module.

Generates executive summaries and reports from aggregated experiment results.
Provides multiple output formats for different audiences.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from .result_collector import DomainResults, HypothesisResult, ResultCollector, CRITICAL_HYPOTHESES
from .cross_domain_analyzer import CrossDomainAnalyzer

logger = logging.getLogger(__name__)


@dataclass
class ExecutiveSummary:
    """Executive summary for stakeholders."""
    title: str
    timestamp: str
    overall_verdict: str  # "pass", "conditional_pass", "fail"
    confidence_level: str  # "high", "medium", "low"
    key_findings: List[str]
    critical_issues: List[str]
    recommendations: List[str]
    metrics_summary: Dict[str, Any]
    next_steps: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "timestamp": self.timestamp,
            "overall_verdict": self.overall_verdict,
            "confidence_level": self.confidence_level,
            "key_findings": self.key_findings,
            "critical_issues": self.critical_issues,
            "recommendations": self.recommendations,
            "metrics_summary": self.metrics_summary,
            "next_steps": self.next_steps,
        }


class SummaryGenerator:
    """
    Generates executive summaries and reports.

    Provides output in multiple formats for different stakeholders.
    """

    def __init__(
        self,
        domain_results: Dict[str, DomainResults],
        title: str = "SHAKTI-CHAIN Validation Results"
    ):
        """
        Initialize summary generator.

        Args:
            domain_results: Dictionary of domain results
            title: Report title
        """
        self.results = domain_results
        self.title = title
        self.analyzer = CrossDomainAnalyzer(domain_results)

        # Compute core statistics
        self._compute_statistics()

    def _compute_statistics(self):
        """Compute core statistics for summaries."""
        self.total_hypotheses = 0
        self.passed = 0
        self.failed = 0
        self.critical_passed = 0
        self.critical_failed = 0
        self.all_results: List[HypothesisResult] = []

        for domain in self.results.values():
            self.total_hypotheses += domain.hypotheses_tested
            self.passed += domain.hypotheses_supported
            self.failed += domain.hypotheses_failed
            self.all_results.extend(domain.raw_results)

        for result in self.all_results:
            if result.hypothesis_id in CRITICAL_HYPOTHESES:
                if result.passed:
                    self.critical_passed += 1
                else:
                    self.critical_failed += 1

        self.success_rate = self.passed / self.total_hypotheses if self.total_hypotheses > 0 else 0
        self.critical_total = self.critical_passed + self.critical_failed

    def generate_executive_summary(self) -> ExecutiveSummary:
        """
        Generate executive summary for leadership.

        Returns:
            ExecutiveSummary object
        """
        # Determine overall verdict
        if self.critical_failed > 0:
            verdict = "fail"
            confidence = "high"
        elif self.success_rate >= 0.9:
            verdict = "pass"
            confidence = "high"
        elif self.success_rate >= 0.75:
            verdict = "conditional_pass"
            confidence = "medium"
        elif self.success_rate >= 0.6:
            verdict = "conditional_pass"
            confidence = "low"
        else:
            verdict = "fail"
            confidence = "medium"

        # Generate key findings
        key_findings = self._generate_key_findings()

        # Identify critical issues
        critical_issues = self._identify_critical_issues()

        # Generate recommendations
        recommendations = self._generate_recommendations()

        # Metrics summary
        metrics = {
            "total_hypotheses_tested": self.total_hypotheses,
            "hypotheses_supported": self.passed,
            "hypotheses_failed": self.failed,
            "success_rate": f"{self.success_rate * 100:.1f}%",
            "critical_hypotheses_tested": self.critical_total,
            "critical_passed": self.critical_passed,
            "critical_failed": self.critical_failed,
            "domains_evaluated": len(self.results),
            "domains_with_100_percent_pass": sum(1 for d in self.results.values() if d.is_clean),
        }

        # Next steps
        next_steps = self._determine_next_steps(verdict)

        return ExecutiveSummary(
            title=self.title,
            timestamp=datetime.now().isoformat(),
            overall_verdict=verdict,
            confidence_level=confidence,
            key_findings=key_findings,
            critical_issues=critical_issues,
            recommendations=recommendations,
            metrics_summary=metrics,
            next_steps=next_steps,
        )

    def _generate_key_findings(self) -> List[str]:
        """Generate key findings list."""
        findings = []

        # Overall success rate
        findings.append(
            f"Overall validation success rate: {self.success_rate * 100:.1f}% "
            f"({self.passed}/{self.total_hypotheses} hypotheses supported)"
        )

        # Critical hypotheses
        if self.critical_total > 0:
            if self.critical_failed == 0:
                findings.append(
                    f"All {self.critical_passed} critical hypotheses passed - "
                    f"system meets core viability requirements"
                )
            else:
                findings.append(
                    f"{self.critical_failed} of {self.critical_total} critical hypotheses failed - "
                    f"fundamental issues require resolution"
                )

        # Domain-level findings
        clean_domains = [d.domain_name for d in self.results.values() if d.is_clean]
        if clean_domains:
            findings.append(
                f"Complete validation in domains: {', '.join(clean_domains)}"
            )

        problematic_domains = [d.domain_name for d in self.results.values()
                              if d.success_rate < 0.7 and d.hypotheses_tested > 0]
        if problematic_domains:
            findings.append(
                f"Areas requiring attention: {', '.join(problematic_domains)}"
            )

        # Effect size summary
        large_effects = sum(1 for r in self.all_results if abs(r.effect_size) >= 0.8)
        if large_effects > 0:
            findings.append(
                f"{large_effects} hypotheses showed large effect sizes (d >= 0.8), "
                f"indicating strong practical significance"
            )

        # Strong statistical results
        strong_results = sum(1 for r in self.all_results if r.is_strong_result)
        if strong_results > 0:
            findings.append(
                f"{strong_results} hypotheses showed highly significant results (p < 0.001)"
            )

        return findings

    def _identify_critical_issues(self) -> List[str]:
        """Identify critical issues requiring immediate attention."""
        issues = []

        # Critical hypothesis failures
        for result in self.all_results:
            if result.hypothesis_id in CRITICAL_HYPOTHESES and not result.passed:
                issues.append(
                    f"[CRITICAL] {result.hypothesis_id}: {CRITICAL_HYPOTHESES[result.hypothesis_id]} - "
                    f"FAILED (p={result.p_value:.4f})"
                )

        # Near-miss results that need monitoring
        near_misses = [r for r in self.all_results if r.is_near_miss]
        if near_misses:
            issues.append(
                f"[WARNING] {len(near_misses)} hypothesis(es) barely passed (p close to α) - "
                f"results may not replicate"
            )

        # Low power tests
        low_power = [r for r in self.all_results
                    if r.power is not None and r.power < 0.8 and not r.passed]
        if low_power:
            issues.append(
                f"[NOTE] {len(low_power)} failed test(s) may have insufficient power - "
                f"consider increasing sample size"
            )

        # Domain-specific issues
        for domain in self.results.values():
            if domain.has_critical_failures:
                issues.append(
                    f"[DOMAIN] {domain.domain_name} has critical failures: "
                    f"{', '.join(domain.critical_failures)}"
                )

        return issues

    def _generate_recommendations(self) -> List[str]:
        """Generate actionable recommendations."""
        recommendations = []

        # Based on critical failures
        if self.critical_failed > 0:
            recommendations.append(
                "IMMEDIATE: Address critical hypothesis failures before proceeding with deployment"
            )
            recommendations.append(
                "INVESTIGATE: Root cause analysis required for critical failures"
            )

        # Based on success rate
        if self.success_rate < 0.8:
            recommendations.append(
                "IMPROVE: Review and enhance areas with low success rates"
            )

        # Based on near misses
        near_misses = [r for r in self.all_results if r.is_near_miss]
        if near_misses:
            recommendations.append(
                f"MONITOR: Track {len(near_misses)} near-miss result(s) in ongoing monitoring"
            )
            recommendations.append(
                "STRENGTHEN: Consider increasing sample sizes for borderline results"
            )

        # Based on effect sizes
        small_effects = [r for r in self.all_results
                        if r.passed and abs(r.effect_size) < 0.3]
        if small_effects:
            recommendations.append(
                f"EVALUATE: {len(small_effects)} passed hypothesis(es) have small effect sizes - "
                f"verify practical significance"
            )

        # General recommendations
        if self.success_rate >= 0.9 and self.critical_failed == 0:
            recommendations.append(
                "PROCEED: Validation results support moving to next development phase"
            )
            recommendations.append(
                "DOCUMENT: Publish validation methodology and results for transparency"
            )

        return recommendations

    def _determine_next_steps(self, verdict: str) -> List[str]:
        """Determine next steps based on verdict."""
        steps = []

        if verdict == "fail":
            steps = [
                "1. Halt deployment planning until critical issues resolved",
                "2. Form task force to address critical hypothesis failures",
                "3. Root cause analysis for each critical failure",
                "4. Design and implement fixes for identified issues",
                "5. Re-run validation tests after fixes",
                "6. Seek external review of problematic areas",
            ]
        elif verdict == "conditional_pass":
            steps = [
                "1. Address any critical issues identified above",
                "2. Develop mitigation plans for near-miss results",
                "3. Implement additional monitoring for weak areas",
                "4. Proceed with limited deployment/beta testing",
                "5. Collect production data to validate results",
                "6. Schedule follow-up validation round",
            ]
        else:  # pass
            steps = [
                "1. Proceed with deployment planning",
                "2. Document validation results for stakeholders",
                "3. Set up production monitoring for validated metrics",
                "4. Plan periodic re-validation schedule",
                "5. Archive test data and methodology",
                "6. Communicate results to community",
            ]

        return steps

    def generate_technical_summary(self) -> str:
        """
        Generate technical summary for developers.

        Returns:
            Markdown-formatted technical summary
        """
        lines = [
            f"# {self.title} - Technical Summary",
            f"\n*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n",
            "---\n",
            "## Overview\n",
            f"- **Total Hypotheses Tested:** {self.total_hypotheses}",
            f"- **Passed:** {self.passed} ({self.success_rate * 100:.1f}%)",
            f"- **Failed:** {self.failed}",
            f"- **Alpha Level:** 0.05",
            "",
            "## Critical Hypotheses\n",
        ]

        # Critical hypothesis details
        for result in self.all_results:
            if result.hypothesis_id in CRITICAL_HYPOTHESES:
                status = "PASSED" if result.passed else "**FAILED**"
                lines.append(
                    f"- {result.hypothesis_id}: {status} "
                    f"(p={result.p_value:.4f}, d={result.effect_size:.3f})"
                )

        lines.append("\n## Domain Results\n")
        lines.append("| Domain | Tested | Passed | Failed | Rate |")
        lines.append("|--------|--------|--------|--------|------|")

        for domain in sorted(self.results.values(), key=lambda d: d.domain_id):
            rate = f"{domain.success_rate * 100:.1f}%"
            lines.append(
                f"| {domain.domain_name} | {domain.hypotheses_tested} | "
                f"{domain.hypotheses_supported} | {domain.hypotheses_failed} | {rate} |"
            )

        # Effect size distribution
        lines.append("\n## Effect Size Distribution\n")
        effect_counts = {"negligible": 0, "small": 0, "medium": 0, "large": 0}
        for r in self.all_results:
            es = abs(r.effect_size)
            if es < 0.2:
                effect_counts["negligible"] += 1
            elif es < 0.5:
                effect_counts["small"] += 1
            elif es < 0.8:
                effect_counts["medium"] += 1
            else:
                effect_counts["large"] += 1

        for mag, count in effect_counts.items():
            pct = count / len(self.all_results) * 100 if self.all_results else 0
            lines.append(f"- {mag.title()}: {count} ({pct:.1f}%)")

        # Failed hypotheses detail
        if self.failed > 0:
            lines.append("\n## Failed Hypotheses Detail\n")
            for r in self.all_results:
                if not r.passed:
                    lines.append(
                        f"- **{r.hypothesis_id}** ({r.domain_id}): "
                        f"p={r.p_value:.4f}, d={r.effect_size:.3f}, n={r.sample_size}"
                    )
                    if r.is_critical:
                        lines.append(f"  - *CRITICAL: {CRITICAL_HYPOTHESES.get(r.hypothesis_id, '')}*")

        return "\n".join(lines)

    def generate_stakeholder_report(self) -> str:
        """
        Generate non-technical report for stakeholders.

        Returns:
            Plain-text summary
        """
        summary = self.generate_executive_summary()

        lines = [
            f"{'=' * 60}",
            f"  {summary.title}",
            f"  Report Date: {datetime.now().strftime('%B %d, %Y')}",
            f"{'=' * 60}",
            "",
            f"OVERALL VERDICT: {summary.overall_verdict.upper().replace('_', ' ')}",
            f"Confidence: {summary.confidence_level.title()}",
            "",
            "-" * 60,
            "KEY METRICS",
            "-" * 60,
            f"  Tests Conducted:     {summary.metrics_summary['total_hypotheses_tested']}",
            f"  Tests Passed:        {summary.metrics_summary['hypotheses_supported']}",
            f"  Tests Failed:        {summary.metrics_summary['hypotheses_failed']}",
            f"  Success Rate:        {summary.metrics_summary['success_rate']}",
            f"  Critical Tests:      {summary.metrics_summary['critical_hypotheses_tested']}",
            f"  Critical Passed:     {summary.metrics_summary['critical_passed']}",
            f"  Critical Failed:     {summary.metrics_summary['critical_failed']}",
            "",
            "-" * 60,
            "KEY FINDINGS",
            "-" * 60,
        ]

        for i, finding in enumerate(summary.key_findings, 1):
            lines.append(f"  {i}. {finding}")

        if summary.critical_issues:
            lines.extend([
                "",
                "-" * 60,
                "ISSUES REQUIRING ATTENTION",
                "-" * 60,
            ])
            for issue in summary.critical_issues:
                lines.append(f"  * {issue}")

        lines.extend([
            "",
            "-" * 60,
            "RECOMMENDATIONS",
            "-" * 60,
        ])
        for i, rec in enumerate(summary.recommendations, 1):
            lines.append(f"  {i}. {rec}")

        lines.extend([
            "",
            "-" * 60,
            "NEXT STEPS",
            "-" * 60,
        ])
        for step in summary.next_steps:
            lines.append(f"  {step}")

        lines.extend([
            "",
            "=" * 60,
            "  End of Report",
            "=" * 60,
        ])

        return "\n".join(lines)

    def generate_json_report(self) -> Dict[str, Any]:
        """
        Generate machine-readable JSON report.

        Returns:
            Complete report as dictionary
        """
        summary = self.generate_executive_summary()
        cross_domain = self.analyzer.generate_cross_domain_report()

        return {
            "report_metadata": {
                "title": self.title,
                "generated_at": datetime.now().isoformat(),
                "version": "1.0",
            },
            "executive_summary": summary.to_dict(),
            "statistics": {
                "total_hypotheses": self.total_hypotheses,
                "passed": self.passed,
                "failed": self.failed,
                "success_rate": self.success_rate,
                "critical_total": self.critical_total,
                "critical_passed": self.critical_passed,
                "critical_failed": self.critical_failed,
            },
            "domain_results": {k: v.to_dict() for k, v in self.results.items()},
            "cross_domain_analysis": cross_domain,
            "all_results": [r.to_dict() for r in self.all_results],
        }

    def save_reports(
        self,
        output_dir: Union[str, Path],
        formats: Optional[List[str]] = None
    ):
        """
        Save reports in multiple formats.

        Args:
            output_dir: Output directory
            formats: List of formats ('json', 'markdown', 'text')
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        if formats is None:
            formats = ["json", "markdown", "text"]

        if "json" in formats:
            json_path = output_dir / "validation_report.json"
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(self.generate_json_report(), f, indent=2)
            logger.info(f"JSON report saved to {json_path}")

        if "markdown" in formats:
            md_path = output_dir / "validation_report.md"
            with open(md_path, 'w', encoding='utf-8') as f:
                f.write(self.generate_technical_summary())
            logger.info(f"Markdown report saved to {md_path}")

        if "text" in formats:
            txt_path = output_dir / "validation_report.txt"
            with open(txt_path, 'w', encoding='utf-8') as f:
                f.write(self.generate_stakeholder_report())
            logger.info(f"Text report saved to {txt_path}")


def generate_summary(
    results_dir: Union[str, Path],
    output_dir: Optional[Union[str, Path]] = None,
    formats: Optional[List[str]] = None
) -> ExecutiveSummary:
    """
    Convenience function to generate summary from results directory.

    Args:
        results_dir: Directory containing domain results
        output_dir: Optional output directory for reports
        formats: Optional list of output formats

    Returns:
        ExecutiveSummary object
    """
    collector = ResultCollector(results_dir)
    domain_results = collector.collect_all_results()

    generator = SummaryGenerator(domain_results)
    summary = generator.generate_executive_summary()

    if output_dir:
        generator.save_reports(output_dir, formats)

    return summary
