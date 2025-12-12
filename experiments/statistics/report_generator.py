"""
Statistical Report Generator Module.

Generates comprehensive statistical reports for SHAKTI-CHAIN experiments:
- Summary tables
- LaTeX tables for publication
- Markdown reports
- Statistical visualizations
- APA-style reporting
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import numpy as np

logger = logging.getLogger(__name__)

# Import local modules
try:
    from .hypothesis_tester import HypothesisTestResult, TestType
    from .effect_size_calculator import EffectSizeResult, EffectMagnitude
    from .power_analyzer import PowerAnalysisResult
    from .assumption_checker import AssumptionCheckResult, FullAssumptionReport, AssumptionStatus
    from .multiple_comparison import CorrectionResult
    from .bootstrap import BootstrapResult, BootstrapTestResult
    from .bayesian_tests import BayesianTestResult
except ImportError:
    # Allow standalone usage
    HypothesisTestResult = Any
    EffectSizeResult = Any
    PowerAnalysisResult = Any
    AssumptionCheckResult = Any
    FullAssumptionReport = Any
    CorrectionResult = Any
    BootstrapResult = Any
    BootstrapTestResult = Any
    BayesianTestResult = Any


@dataclass
class StatisticalReport:
    """
    Complete statistical report.

    Attributes:
        title: Report title
        hypothesis_id: Hypothesis identifier
        timestamp: Report generation time
        sections: Report sections
        summary: Executive summary
        conclusions: Key conclusions
    """
    title: str
    hypothesis_id: str
    timestamp: str
    sections: Dict[str, Any]
    summary: str
    conclusions: List[str]

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "title": self.title,
            "hypothesis_id": self.hypothesis_id,
            "timestamp": self.timestamp,
            "sections": self.sections,
            "summary": self.summary,
            "conclusions": self.conclusions,
        }


class StatisticalReportGenerator:
    """
    Generate comprehensive statistical reports.

    Supports multiple output formats and customizable templates.
    """

    def __init__(
        self,
        results: Optional[List[Any]] = None,
        alpha: float = 0.05,
    ):
        """
        Initialize report generator.

        Args:
            results: List of statistical test results
            alpha: Significance level used
        """
        self.results = results or []
        self.alpha = alpha
        self.hypothesis_results: List[HypothesisTestResult] = []
        self.effect_sizes: List[EffectSizeResult] = []
        self.power_analyses: List[PowerAnalysisResult] = []
        self.assumption_checks: List[AssumptionCheckResult] = []
        self.bootstrap_results: List[BootstrapResult] = []
        self.bayesian_results: List[BayesianTestResult] = []
        self.correction_results: List[CorrectionResult] = []

        # Categorize results
        for result in self.results:
            self._categorize_result(result)

    def _categorize_result(self, result: Any):
        """Categorize result by type."""
        type_name = type(result).__name__

        if 'HypothesisTest' in type_name:
            self.hypothesis_results.append(result)
        elif 'EffectSize' in type_name:
            self.effect_sizes.append(result)
        elif 'PowerAnalysis' in type_name:
            self.power_analyses.append(result)
        elif 'Assumption' in type_name:
            self.assumption_checks.append(result)
        elif 'Bootstrap' in type_name:
            self.bootstrap_results.append(result)
        elif 'Bayesian' in type_name:
            self.bayesian_results.append(result)
        elif 'Correction' in type_name:
            self.correction_results.append(result)

    def add_result(self, result: Any):
        """Add a result to the report."""
        self.results.append(result)
        self._categorize_result(result)

    def generate_summary_table(self) -> str:
        """
        Create summary table of all hypothesis tests.

        Returns:
            Formatted table string
        """
        if not self.hypothesis_results:
            return "No hypothesis test results to summarize."

        # Build table
        headers = ["Test", "Statistic", "p-value", "Effect Size", "Decision"]
        rows = []

        for result in self.hypothesis_results:
            if hasattr(result, 'test_name'):
                rows.append([
                    result.test_name[:30],
                    f"{result.statistic:.4f}" if hasattr(result, 'statistic') else "N/A",
                    f"{result.p_value:.4f}" if hasattr(result, 'p_value') else "N/A",
                    f"{result.effect_size:.3f}" if hasattr(result, 'effect_size') else "N/A",
                    "Sig*" if (hasattr(result, 'passed') and result.passed) or
                              (hasattr(result, 'p_value') and result.p_value < self.alpha)
                    else "NS",
                ])

        # Format table
        col_widths = [max(len(str(row[i])) for row in [headers] + rows) + 2
                      for i in range(len(headers))]

        table = ""
        # Header
        table += "|" + "|".join(h.center(w) for h, w in zip(headers, col_widths)) + "|\n"
        table += "|" + "|".join("-" * w for w in col_widths) + "|\n"
        # Rows
        for row in rows:
            table += "|" + "|".join(str(c).center(w) for c, w in zip(row, col_widths)) + "|\n"

        table += f"\n* Significant at α = {self.alpha}"

        return table

    def generate_latex_table(
        self,
        caption: str = "Summary of Statistical Tests",
        label: str = "tab:stats",
    ) -> str:
        """
        Generate LaTeX table for publication.

        Args:
            caption: Table caption
            label: LaTeX label

        Returns:
            LaTeX table code
        """
        if not self.hypothesis_results:
            return "% No results to display"

        latex = [
            r"\begin{table}[htbp]",
            r"\centering",
            f"\\caption{{{caption}}}",
            f"\\label{{{label}}}",
            r"\begin{tabular}{lcccc}",
            r"\toprule",
            r"Test & Statistic & $p$-value & Effect Size & Decision \\",
            r"\midrule",
        ]

        for result in self.hypothesis_results:
            if hasattr(result, 'test_name'):
                test_name = result.test_name.replace("_", " ").replace("&", r"\&")
                stat = f"{result.statistic:.3f}" if hasattr(result, 'statistic') else "--"
                p = f"{result.p_value:.4f}" if hasattr(result, 'p_value') else "--"
                es = f"{result.effect_size:.3f}" if hasattr(result, 'effect_size') else "--"

                sig = "*" if (hasattr(result, 'passed') and result.passed) or \
                            (hasattr(result, 'p_value') and result.p_value < self.alpha) else ""

                if hasattr(result, 'p_value'):
                    if result.p_value < 0.001:
                        p = r"$<$.001"
                    elif result.p_value < 0.01:
                        p = f"{result.p_value:.3f}"

                latex.append(f"{test_name} & {stat} & {p} & {es} & {sig} \\\\")

        latex.extend([
            r"\bottomrule",
            r"\end{tabular}",
            f"\\\\[2pt] \\small * $p < {self.alpha}$",
            r"\end{table}",
        ])

        return "\n".join(latex)

    def generate_markdown_report(
        self,
        title: str = "Statistical Analysis Report",
        hypothesis_id: str = "",
    ) -> str:
        """
        Generate detailed Markdown report.

        Args:
            title: Report title
            hypothesis_id: Hypothesis identifier

        Returns:
            Markdown report
        """
        md = []

        # Header
        md.append(f"# {title}")
        if hypothesis_id:
            md.append(f"\n**Hypothesis ID:** {hypothesis_id}")
        md.append(f"\n**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        md.append(f"\n**Significance Level:** α = {self.alpha}")
        md.append("\n---\n")

        # Executive Summary
        md.append("## Executive Summary\n")
        md.append(self._generate_executive_summary())
        md.append("\n")

        # Hypothesis Tests
        if self.hypothesis_results:
            md.append("## Hypothesis Tests\n")
            md.append(self.generate_summary_table())
            md.append("\n")

            md.append("### Detailed Results\n")
            for i, result in enumerate(self.hypothesis_results, 1):
                md.append(f"\n#### Test {i}: {getattr(result, 'test_name', 'Unknown')}\n")
                md.append(self._format_hypothesis_result(result))

        # Effect Sizes
        if self.effect_sizes:
            md.append("\n## Effect Sizes\n")
            for result in self.effect_sizes:
                md.append(self._format_effect_size(result))

        # Power Analysis
        if self.power_analyses:
            md.append("\n## Power Analysis\n")
            for result in self.power_analyses:
                md.append(self._format_power_analysis(result))

        # Assumption Checks
        if self.assumption_checks:
            md.append("\n## Assumption Checks\n")
            md.append(self._format_assumption_summary())

        # Bootstrap Results
        if self.bootstrap_results:
            md.append("\n## Bootstrap Analysis\n")
            for result in self.bootstrap_results:
                md.append(self._format_bootstrap_result(result))

        # Bayesian Results
        if self.bayesian_results:
            md.append("\n## Bayesian Analysis\n")
            for result in self.bayesian_results:
                md.append(self._format_bayesian_result(result))

        # Multiple Comparison Corrections
        if self.correction_results:
            md.append("\n## Multiple Comparison Corrections\n")
            for result in self.correction_results:
                md.append(self._format_correction_result(result))

        # Conclusions
        md.append("\n## Conclusions\n")
        md.append(self._generate_conclusions())

        # Footer
        md.append("\n---\n")
        md.append("*Report generated by SHAKTI-CHAIN Statistical Analysis Suite*")

        return "\n".join(md)

    def _generate_executive_summary(self) -> str:
        """Generate executive summary."""
        summary_parts = []

        # Count results
        n_tests = len(self.hypothesis_results)
        n_significant = sum(1 for r in self.hypothesis_results
                          if (hasattr(r, 'passed') and r.passed) or
                             (hasattr(r, 'p_value') and r.p_value < self.alpha))

        if n_tests > 0:
            summary_parts.append(
                f"- **{n_tests}** hypothesis tests were conducted, "
                f"of which **{n_significant}** ({n_significant/n_tests*100:.1f}%) "
                f"were statistically significant at α = {self.alpha}."
            )

        # Effect sizes
        if self.effect_sizes:
            magnitudes = []
            for es in self.effect_sizes:
                if hasattr(es, 'magnitude'):
                    magnitudes.append(es.magnitude.value if hasattr(es.magnitude, 'value') else str(es.magnitude))
            if magnitudes:
                summary_parts.append(
                    f"- Effect size magnitudes ranged from {min(magnitudes)} to {max(magnitudes)}."
                )

        # Assumptions
        if self.assumption_checks:
            n_satisfied = sum(1 for a in self.assumption_checks
                            if hasattr(a, 'status') and
                            (a.status == AssumptionStatus.SATISFIED if hasattr(AssumptionStatus, 'SATISFIED')
                             else str(a.status) == 'satisfied'))
            n_total = len(self.assumption_checks)
            if n_total > 0:
                summary_parts.append(
                    f"- **{n_satisfied}/{n_total}** statistical assumptions were satisfied."
                )

        # Bayesian
        if self.bayesian_results:
            summary_parts.append(
                f"- Bayesian analysis provided {len(self.bayesian_results)} "
                f"alternative interpretations with Bayes factors."
            )

        return "\n".join(summary_parts) if summary_parts else "No analyses to summarize."

    def _format_hypothesis_result(self, result: Any) -> str:
        """Format a single hypothesis test result."""
        lines = []

        if hasattr(result, 'null_hypothesis'):
            lines.append(f"- **H₀:** {result.null_hypothesis}")
        if hasattr(result, 'alt_hypothesis'):
            lines.append(f"- **H₁:** {result.alt_hypothesis}")

        if hasattr(result, 'statistic'):
            lines.append(f"- **Test Statistic:** {result.statistic:.4f}")
        if hasattr(result, 'p_value'):
            p_str = f"{result.p_value:.4f}" if result.p_value >= 0.0001 else "< 0.0001"
            lines.append(f"- **p-value:** {p_str}")
        if hasattr(result, 'degrees_freedom') and result.degrees_freedom:
            df = result.degrees_freedom
            if isinstance(df, tuple):
                lines.append(f"- **df:** ({df[0]}, {df[1]})")
            else:
                lines.append(f"- **df:** {df}")

        if hasattr(result, 'effect_size'):
            es_name = getattr(result, 'effect_size_name', 'Effect size') if hasattr(result, 'effect_size_name') else 'Effect size'
            lines.append(f"- **{es_name}:** {result.effect_size:.4f}")

        if hasattr(result, 'confidence_interval'):
            ci = result.confidence_interval
            if ci and ci[0] is not None and ci[1] is not None:
                lines.append(f"- **95% CI:** [{ci[0]:.4f}, {ci[1]:.4f}]")

        if hasattr(result, 'power') and result.power:
            lines.append(f"- **Power:** {result.power:.4f}")

        if hasattr(result, 'interpretation'):
            lines.append(f"\n**Interpretation:** {result.interpretation}")
        elif hasattr(result, 'passed'):
            decision = "Reject H₀" if result.passed else "Fail to reject H₀"
            lines.append(f"\n**Decision:** {decision}")

        return "\n".join(lines)

    def _format_effect_size(self, result: Any) -> str:
        """Format effect size result."""
        lines = []

        if hasattr(result, 'effect_type'):
            etype = result.effect_type.value if hasattr(result.effect_type, 'value') else str(result.effect_type)
            lines.append(f"### {etype}")

        if hasattr(result, 'value'):
            lines.append(f"- **Value:** {result.value:.4f}")
        if hasattr(result, 'magnitude'):
            mag = result.magnitude.value if hasattr(result.magnitude, 'value') else str(result.magnitude)
            lines.append(f"- **Magnitude:** {mag}")
        if hasattr(result, 'confidence_interval'):
            ci = result.confidence_interval
            lines.append(f"- **CI:** [{ci[0]:.4f}, {ci[1]:.4f}]")
        if hasattr(result, 'interpretation'):
            lines.append(f"\n{result.interpretation}")

        return "\n".join(lines) + "\n"

    def _format_power_analysis(self, result: Any) -> str:
        """Format power analysis result."""
        lines = []

        if hasattr(result, 'analysis_type'):
            atype = result.analysis_type.value if hasattr(result.analysis_type, 'value') else str(result.analysis_type)
            lines.append(f"### {atype}")

        if hasattr(result, 'sample_size'):
            lines.append(f"- **Sample Size:** {result.sample_size}")
        if hasattr(result, 'effect_size'):
            lines.append(f"- **Effect Size:** {result.effect_size:.3f}")
        if hasattr(result, 'power'):
            lines.append(f"- **Power:** {result.power:.4f}")
        if hasattr(result, 'alpha'):
            lines.append(f"- **Alpha:** {result.alpha}")
        if hasattr(result, 'interpretation'):
            lines.append(f"\n{result.interpretation}")

        return "\n".join(lines) + "\n"

    def _format_assumption_summary(self) -> str:
        """Format assumption check summary."""
        lines = []

        satisfied = []
        violated = []
        marginal = []

        for check in self.assumption_checks:
            status = getattr(check, 'status', None)
            assumption = getattr(check, 'assumption', 'Unknown')

            if status:
                status_str = status.value if hasattr(status, 'value') else str(status)
                if 'satisfied' in status_str.lower():
                    satisfied.append(assumption)
                elif 'violated' in status_str.lower():
                    violated.append(assumption)
                elif 'marginal' in status_str.lower():
                    marginal.append(assumption)

        if satisfied:
            lines.append(f"**Satisfied:** {', '.join(satisfied)}")
        if marginal:
            lines.append(f"**Marginal:** {', '.join(marginal)}")
        if violated:
            lines.append(f"**Violated:** {', '.join(violated)}")

        # Detailed table
        lines.append("\n| Assumption | Status | Test | p-value |")
        lines.append("|------------|--------|------|---------|")

        for check in self.assumption_checks:
            assumption = getattr(check, 'assumption', 'Unknown')[:20]
            status = getattr(check, 'status', '')
            status_str = status.value if hasattr(status, 'value') else str(status)
            test = getattr(check, 'test_name', 'N/A')[:15]
            p = getattr(check, 'p_value', -1)
            p_str = f"{p:.4f}" if p >= 0 else "N/A"

            lines.append(f"| {assumption} | {status_str} | {test} | {p_str} |")

        return "\n".join(lines)

    def _format_bootstrap_result(self, result: Any) -> str:
        """Format bootstrap result."""
        lines = []

        stat_name = getattr(result, 'statistic_name', 'Statistic')
        lines.append(f"### Bootstrap: {stat_name}")

        if hasattr(result, 'observed'):
            lines.append(f"- **Observed:** {result.observed:.4f}")
        if hasattr(result, 'ci_lower') and hasattr(result, 'ci_upper'):
            ci_method = getattr(result, 'ci_method', '')
            method_str = ci_method.value if hasattr(ci_method, 'value') else str(ci_method)
            lines.append(f"- **CI ({method_str}):** [{result.ci_lower:.4f}, {result.ci_upper:.4f}]")
        if hasattr(result, 'se'):
            lines.append(f"- **SE:** {result.se:.4f}")
        if hasattr(result, 'bias'):
            lines.append(f"- **Bias:** {result.bias:.4f}")
        if hasattr(result, 'n_bootstrap'):
            lines.append(f"- **Bootstrap samples:** {result.n_bootstrap}")

        return "\n".join(lines) + "\n"

    def _format_bayesian_result(self, result: Any) -> str:
        """Format Bayesian result."""
        lines = []

        test_name = getattr(result, 'test_name', 'Bayesian Test')
        lines.append(f"### {test_name}")

        if hasattr(result, 'bayes_factor'):
            bf = result.bayes_factor
            bf_str = f"{bf:.4f}" if bf < 1000 else f"{bf:.2e}"
            lines.append(f"- **Bayes Factor (BF₁₀):** {bf_str}")

        if hasattr(result, 'bf_interpretation'):
            interp = result.bf_interpretation.value if hasattr(result.bf_interpretation, 'value') else str(result.bf_interpretation)
            lines.append(f"- **Evidence:** {interp}")

        if hasattr(result, 'posterior_mean'):
            lines.append(f"- **Posterior Mean:** {result.posterior_mean:.4f}")
        if hasattr(result, 'posterior_std'):
            lines.append(f"- **Posterior SD:** {result.posterior_std:.4f}")
        if hasattr(result, 'credible_interval'):
            ci = result.credible_interval
            level = getattr(result, 'credible_level', 0.95) * 100
            lines.append(f"- **{level:.0f}% Credible Interval:** [{ci[0]:.4f}, {ci[1]:.4f}]")

        if hasattr(result, 'probability_in_rope') and result.probability_in_rope is not None:
            lines.append(f"- **P(in ROPE):** {result.probability_in_rope:.4f}")

        return "\n".join(lines) + "\n"

    def _format_correction_result(self, result: Any) -> str:
        """Format multiple comparison correction result."""
        lines = []

        method = getattr(result, 'method', '')
        method_str = method.value if hasattr(method, 'value') else str(method)
        lines.append(f"### {method_str}")

        if hasattr(result, 'n_tests'):
            lines.append(f"- **Number of tests:** {result.n_tests}")
        if hasattr(result, 'n_significant'):
            lines.append(f"- **Significant after correction:** {result.n_significant}")
        if hasattr(result, 'adjusted_alpha') and result.adjusted_alpha:
            lines.append(f"- **Adjusted α:** {result.adjusted_alpha:.6f}")
        if hasattr(result, 'fwer') and result.fwer:
            lines.append(f"- **FWER controlled:** {result.fwer}")
        if hasattr(result, 'fdr') and result.fdr:
            lines.append(f"- **FDR controlled:** {result.fdr}")

        return "\n".join(lines) + "\n"

    def _generate_conclusions(self) -> str:
        """Generate conclusions section."""
        conclusions = []

        # Based on hypothesis tests
        if self.hypothesis_results:
            n_sig = sum(1 for r in self.hypothesis_results
                       if (hasattr(r, 'passed') and r.passed) or
                          (hasattr(r, 'p_value') and r.p_value < self.alpha))
            n_total = len(self.hypothesis_results)

            if n_sig == n_total and n_total > 0:
                conclusions.append("All hypotheses were supported by the data.")
            elif n_sig > n_total / 2:
                conclusions.append(f"The majority ({n_sig}/{n_total}) of hypotheses were supported.")
            elif n_sig > 0:
                conclusions.append(f"Some hypotheses ({n_sig}/{n_total}) were supported.")
            else:
                conclusions.append("No hypotheses were statistically supported at the specified α level.")

        # Based on effect sizes
        large_effects = [es for es in self.effect_sizes
                        if hasattr(es, 'magnitude') and
                        ('large' in str(es.magnitude).lower() or 'very' in str(es.magnitude).lower())]
        if large_effects:
            conclusions.append(f"{len(large_effects)} large or very large effect(s) were observed.")

        # Based on Bayesian
        strong_bf = [r for r in self.bayesian_results
                    if hasattr(r, 'bayes_factor') and r.bayes_factor > 10]
        if strong_bf:
            conclusions.append(f"{len(strong_bf)} test(s) showed strong Bayesian evidence (BF > 10).")

        # Assumption violations
        violated = [a for a in self.assumption_checks
                   if hasattr(a, 'status') and 'violated' in str(a.status).lower()]
        if violated:
            conclusions.append(
                f"Note: {len(violated)} assumption violation(s) may affect result interpretation."
            )

        return "\n".join(f"- {c}" for c in conclusions) if conclusions else "- No conclusions to report."

    def generate_apa_report(self) -> str:
        """
        Generate APA-style statistical reporting.

        Returns:
            APA-formatted results string
        """
        reports = []

        for result in self.hypothesis_results:
            apa = self._format_apa_result(result)
            if apa:
                reports.append(apa)

        return "\n\n".join(reports) if reports else "No results to report in APA format."

    def _format_apa_result(self, result: Any) -> str:
        """Format single result in APA style."""
        test_name = getattr(result, 'test_name', '').lower()

        # Get common values
        stat = getattr(result, 'statistic', None)
        p = getattr(result, 'p_value', None)
        df = getattr(result, 'degrees_freedom', None)
        es = getattr(result, 'effect_size', None)
        es_name = getattr(result, 'effect_size_name', 'd')

        # Format p-value
        if p is not None:
            if p < 0.001:
                p_str = "p < .001"
            else:
                p_str = f"p = {p:.3f}".replace("0.", ".")
        else:
            p_str = ""

        # Format based on test type
        if 't-test' in test_name.lower() or 't test' in test_name.lower():
            if df is not None and stat is not None:
                base = f"t({df:.0f}) = {stat:.2f}, {p_str}"
                if es is not None:
                    base += f", {es_name} = {es:.2f}"
                return base

        elif 'anova' in test_name.lower():
            if df is not None and stat is not None:
                if isinstance(df, tuple):
                    base = f"F({df[0]:.0f}, {df[1]:.0f}) = {stat:.2f}, {p_str}"
                else:
                    base = f"F = {stat:.2f}, {p_str}"
                if es is not None:
                    base += f", η² = {es:.2f}"
                return base

        elif 'chi' in test_name.lower():
            if df is not None and stat is not None:
                n = result.additional_stats.get('n', result.sample_size) if hasattr(result, 'additional_stats') else getattr(result, 'sample_size', 'N')
                base = f"χ²({df:.0f}, N = {n}) = {stat:.2f}, {p_str}"
                return base

        elif 'correlation' in test_name.lower() or 'pearson' in test_name.lower():
            if stat is not None:
                r = es if es is not None else stat
                return f"r = {r:.2f}, {p_str}"

        # Generic format
        if stat is not None and p_str:
            return f"statistic = {stat:.3f}, {p_str}"

        return ""

    def save_report(
        self,
        filepath: Union[str, Path],
        format: str = "markdown",
        **kwargs
    ):
        """
        Save report to file.

        Args:
            filepath: Output file path
            format: 'markdown', 'latex', 'json', or 'txt'
            **kwargs: Additional arguments for generator
        """
        filepath = Path(filepath)

        if format == "markdown":
            content = self.generate_markdown_report(**kwargs)
        elif format == "latex":
            content = self.generate_latex_table(**kwargs)
        elif format == "json":
            content = json.dumps(self._to_json_serializable(), indent=2)
        elif format == "txt":
            content = self.generate_summary_table()
        else:
            raise ValueError(f"Unknown format: {format}")

        filepath.write_text(content, encoding='utf-8')
        logger.info(f"Report saved to {filepath}")

    def _to_json_serializable(self) -> Dict[str, Any]:
        """Convert all results to JSON-serializable format."""
        data = {
            "timestamp": datetime.now().isoformat(),
            "alpha": self.alpha,
            "hypothesis_tests": [],
            "effect_sizes": [],
            "power_analyses": [],
            "assumption_checks": [],
            "bootstrap_results": [],
            "bayesian_results": [],
            "correction_results": [],
        }

        for r in self.hypothesis_results:
            if hasattr(r, 'to_dict'):
                data["hypothesis_tests"].append(r.to_dict())

        for r in self.effect_sizes:
            if hasattr(r, 'to_dict'):
                data["effect_sizes"].append(r.to_dict())

        for r in self.power_analyses:
            if hasattr(r, 'to_dict'):
                data["power_analyses"].append(r.to_dict())

        for r in self.assumption_checks:
            if hasattr(r, 'to_dict'):
                data["assumption_checks"].append(r.to_dict())

        for r in self.bootstrap_results:
            if hasattr(r, 'to_dict'):
                data["bootstrap_results"].append(r.to_dict())

        for r in self.bayesian_results:
            if hasattr(r, 'to_dict'):
                data["bayesian_results"].append(r.to_dict())

        for r in self.correction_results:
            if hasattr(r, 'to_dict'):
                data["correction_results"].append(r.to_dict())

        return data

    def generate_visualization(
        self,
        output_dir: Union[str, Path],
        plot_types: Optional[List[str]] = None
    ):
        """
        Generate statistical visualizations.

        Args:
            output_dir: Directory for output files
            plot_types: Types of plots to generate
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        try:
            import matplotlib.pyplot as plt
            import matplotlib
            matplotlib.use('Agg')  # Non-interactive backend
        except ImportError:
            logger.warning("matplotlib not available for visualizations")
            return

        if plot_types is None:
            plot_types = ['p_values', 'effect_sizes', 'power']

        # P-value distribution
        if 'p_values' in plot_types and self.hypothesis_results:
            self._plot_p_values(output_dir / 'p_values.png')

        # Effect sizes
        if 'effect_sizes' in plot_types and self.effect_sizes:
            self._plot_effect_sizes(output_dir / 'effect_sizes.png')

        # Power curve
        if 'power' in plot_types and self.power_analyses:
            self._plot_power(output_dir / 'power.png')

        logger.info(f"Visualizations saved to {output_dir}")

    def _plot_p_values(self, filepath: Path):
        """Plot p-value distribution."""
        import matplotlib.pyplot as plt

        p_values = [r.p_value for r in self.hypothesis_results
                   if hasattr(r, 'p_value') and r.p_value is not None]

        if not p_values:
            return

        fig, ax = plt.subplots(figsize=(10, 6))

        ax.hist(p_values, bins=20, edgecolor='black', alpha=0.7)
        ax.axvline(x=self.alpha, color='red', linestyle='--',
                   label=f'α = {self.alpha}')
        ax.set_xlabel('P-value')
        ax.set_ylabel('Frequency')
        ax.set_title('Distribution of P-values')
        ax.legend()

        plt.tight_layout()
        plt.savefig(filepath, dpi=150)
        plt.close()

    def _plot_effect_sizes(self, filepath: Path):
        """Plot effect sizes."""
        import matplotlib.pyplot as plt

        es_values = [(getattr(r, 'effect_type', 'Unknown'),
                     getattr(r, 'value', 0))
                    for r in self.effect_sizes
                    if hasattr(r, 'value')]

        if not es_values:
            return

        fig, ax = plt.subplots(figsize=(10, 6))

        names = [str(e[0].value if hasattr(e[0], 'value') else e[0])[:15]
                for e in es_values]
        values = [e[1] for e in es_values]

        colors = ['green' if v >= 0.8 else 'orange' if v >= 0.5 else 'blue'
                 for v in np.abs(values)]

        ax.barh(range(len(values)), values, color=colors, alpha=0.7)
        ax.set_yticks(range(len(names)))
        ax.set_yticklabels(names)
        ax.set_xlabel('Effect Size')
        ax.set_title('Effect Sizes by Test')
        ax.axvline(x=0, color='black', linestyle='-', linewidth=0.5)

        # Reference lines
        ax.axvline(x=0.2, color='gray', linestyle=':', alpha=0.5, label='Small (0.2)')
        ax.axvline(x=0.5, color='gray', linestyle='--', alpha=0.5, label='Medium (0.5)')
        ax.axvline(x=0.8, color='gray', linestyle='-', alpha=0.5, label='Large (0.8)')
        ax.legend(loc='lower right')

        plt.tight_layout()
        plt.savefig(filepath, dpi=150)
        plt.close()

    def _plot_power(self, filepath: Path):
        """Plot power analysis results."""
        import matplotlib.pyplot as plt

        power_values = [(getattr(r, 'sample_size', 0),
                        getattr(r, 'power', 0))
                       for r in self.power_analyses
                       if hasattr(r, 'power')]

        if not power_values:
            return

        fig, ax = plt.subplots(figsize=(10, 6))

        sizes = [p[0] for p in power_values]
        powers = [p[1] for p in power_values]

        ax.bar(range(len(powers)), powers, alpha=0.7)
        ax.axhline(y=0.8, color='red', linestyle='--', label='80% Power')
        ax.set_xticks(range(len(sizes)))
        ax.set_xticklabels([f'n={s}' for s in sizes])
        ax.set_ylabel('Statistical Power')
        ax.set_title('Power Analysis Results')
        ax.set_ylim(0, 1)
        ax.legend()

        plt.tight_layout()
        plt.savefig(filepath, dpi=150)
        plt.close()


def generate_report(
    results: List[Any],
    title: str = "Statistical Analysis Report",
    output_path: Optional[Union[str, Path]] = None,
    format: str = "markdown",
) -> str:
    """
    Convenience function to generate a statistical report.

    Args:
        results: List of statistical test results
        title: Report title
        output_path: Optional output file path
        format: Output format

    Returns:
        Report content
    """
    generator = StatisticalReportGenerator(results)

    if format == "markdown":
        content = generator.generate_markdown_report(title=title)
    elif format == "latex":
        content = generator.generate_latex_table()
    elif format == "apa":
        content = generator.generate_apa_report()
    else:
        content = generator.generate_summary_table()

    if output_path:
        Path(output_path).write_text(content, encoding='utf-8')

    return content
