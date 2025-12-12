"""
Publication Table Formatter for SHAKTI-CHAIN.

Formats statistical results into publication-quality tables
in LaTeX, Markdown, and HTML formats.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Union
import logging

logger = logging.getLogger(__name__)

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False


class TableFormat:
    """Supported table formats."""
    LATEX = "latex"
    MARKDOWN = "markdown"
    HTML = "html"
    CSV = "csv"


@dataclass
class TableStyle:
    """Table styling options."""
    caption_above: bool = True
    bold_headers: bool = True
    bold_best: bool = True
    highlight_significant: bool = True
    significance_threshold: float = 0.05
    decimal_places: int = 3
    use_booktabs: bool = True
    small_font: bool = True


class PublicationTableFormatter:
    """
    Format data as publication-quality tables.

    Supports hypothesis results, system comparisons,
    summary statistics, and effect size tables.
    """

    def __init__(self, style: Optional[TableStyle] = None):
        """
        Initialize formatter.

        Args:
            style: Table styling options
        """
        self.style = style or TableStyle()

    def format_hypothesis_table(
        self,
        results: List[Dict[str, Any]],
        format: str = TableFormat.LATEX,
        caption: str = "Hypothesis test results",
        label: str = "tab:hypothesis",
    ) -> str:
        """
        Format hypothesis results as publication table.

        Args:
            results: List of hypothesis test results
            format: Output format (latex, markdown, html)
            caption: Table caption
            label: Table label (for LaTeX)

        Returns:
            Formatted table string
        """
        if format == TableFormat.LATEX:
            return self._hypothesis_table_latex(results, caption, label)
        elif format == TableFormat.MARKDOWN:
            return self._hypothesis_table_markdown(results, caption)
        elif format == TableFormat.HTML:
            return self._hypothesis_table_html(results, caption)
        else:
            return self._hypothesis_table_csv(results)

    def _hypothesis_table_latex(
        self,
        results: List[Dict[str, Any]],
        caption: str,
        label: str,
    ) -> str:
        """Generate LaTeX hypothesis table."""
        lines = []

        # Table environment
        lines.append("\\begin{table}[htbp]")
        lines.append("\\centering")

        if self.style.caption_above:
            lines.append(f"\\caption{{{caption}}}")
            lines.append(f"\\label{{{label}}}")

        if self.style.small_font:
            lines.append("\\small")

        # Column specification
        if self.style.use_booktabs:
            lines.append("\\begin{tabular}{@{}lp{2.5cm}lrrr@{}}")
            lines.append("\\toprule")
        else:
            lines.append("\\begin{tabular}{|l|p{2.5cm}|l|r|r|r|}")
            lines.append("\\hline")

        # Header
        header = "\\textbf{ID} & \\textbf{Hypothesis} & \\textbf{Test} & "
        header += "\\textbf{Statistic} & \\textbf{p-value} & \\textbf{Decision}"
        lines.append(header + " \\\\")

        if self.style.use_booktabs:
            lines.append("\\midrule")
        else:
            lines.append("\\hline")

        # Data rows
        for result in results:
            h_id = result.get("hypothesis_id", "N/A")
            hypothesis = self._escape_latex(
                result.get("hypothesis_name", result.get("null_hypothesis", ""))[:35]
            )
            test = result.get("test_name", "N/A")
            statistic = result.get("test_statistic", 0)
            p_value = result.get("p_value", 1.0)
            decision = result.get("decision", "")

            # Format decision
            decision_text = "Supported" if "reject" in decision.lower() else "Not Supp."

            # Highlight significant p-values
            if self.style.highlight_significant and p_value < self.style.significance_threshold:
                p_str = f"\\textbf{{{p_value:.{self.style.decimal_places}f}}}"
            else:
                p_str = f"{p_value:.{self.style.decimal_places}f}"

            row = f"{h_id} & {hypothesis}... & {test} & "
            row += f"{statistic:.2f} & {p_str} & {decision_text} \\\\"
            lines.append(row)

        # Footer
        if self.style.use_booktabs:
            lines.append("\\bottomrule")
        else:
            lines.append("\\hline")

        lines.append("\\end{tabular}")

        if not self.style.caption_above:
            lines.append(f"\\caption{{{caption}}}")
            lines.append(f"\\label{{{label}}}")

        lines.append("\\end{table}")

        return "\n".join(lines)

    def _hypothesis_table_markdown(
        self,
        results: List[Dict[str, Any]],
        caption: str,
    ) -> str:
        """Generate Markdown hypothesis table."""
        lines = []

        if caption:
            lines.append(f"**{caption}**")
            lines.append("")

        # Header
        lines.append("| ID | Hypothesis | Test | Statistic | p-value | Decision |")
        lines.append("|:---|:-----------|:-----|----------:|--------:|:---------|")

        # Data rows
        for result in results:
            h_id = result.get("hypothesis_id", "N/A")
            hypothesis = result.get("hypothesis_name", result.get("null_hypothesis", ""))[:35]
            test = result.get("test_name", "N/A")
            statistic = result.get("test_statistic", 0)
            p_value = result.get("p_value", 1.0)
            decision = result.get("decision", "")

            decision_text = "Supported" if "reject" in decision.lower() else "Not Supp."

            # Bold significant p-values
            if self.style.highlight_significant and p_value < self.style.significance_threshold:
                p_str = f"**{p_value:.{self.style.decimal_places}f}**"
            else:
                p_str = f"{p_value:.{self.style.decimal_places}f}"

            lines.append(
                f"| {h_id} | {hypothesis}... | {test} | "
                f"{statistic:.2f} | {p_str} | {decision_text} |"
            )

        return "\n".join(lines)

    def _hypothesis_table_html(
        self,
        results: List[Dict[str, Any]],
        caption: str,
    ) -> str:
        """Generate HTML hypothesis table."""
        lines = [
            '<table class="hypothesis-results">',
            f'  <caption>{caption}</caption>',
            '  <thead>',
            '    <tr>',
            '      <th>ID</th>',
            '      <th>Hypothesis</th>',
            '      <th>Test</th>',
            '      <th>Statistic</th>',
            '      <th>p-value</th>',
            '      <th>Decision</th>',
            '    </tr>',
            '  </thead>',
            '  <tbody>',
        ]

        for result in results:
            h_id = result.get("hypothesis_id", "N/A")
            hypothesis = result.get("hypothesis_name", result.get("null_hypothesis", ""))[:35]
            test = result.get("test_name", "N/A")
            statistic = result.get("test_statistic", 0)
            p_value = result.get("p_value", 1.0)
            decision = result.get("decision", "")

            decision_text = "Supported" if "reject" in decision.lower() else "Not Supp."

            # Style significant p-values
            if self.style.highlight_significant and p_value < self.style.significance_threshold:
                p_cell = f'<td class="significant"><strong>{p_value:.{self.style.decimal_places}f}</strong></td>'
            else:
                p_cell = f'<td>{p_value:.{self.style.decimal_places}f}</td>'

            lines.extend([
                '    <tr>',
                f'      <td>{h_id}</td>',
                f'      <td>{hypothesis}...</td>',
                f'      <td>{test}</td>',
                f'      <td>{statistic:.2f}</td>',
                f'      {p_cell}',
                f'      <td>{decision_text}</td>',
                '    </tr>',
            ])

        lines.extend([
            '  </tbody>',
            '</table>',
        ])

        return "\n".join(lines)

    def _hypothesis_table_csv(
        self,
        results: List[Dict[str, Any]],
    ) -> str:
        """Generate CSV hypothesis table."""
        lines = ["ID,Hypothesis,Test,Statistic,p-value,Decision"]

        for result in results:
            h_id = result.get("hypothesis_id", "N/A")
            hypothesis = result.get("hypothesis_name", result.get("null_hypothesis", ""))[:35]
            test = result.get("test_name", "N/A")
            statistic = result.get("test_statistic", 0)
            p_value = result.get("p_value", 1.0)
            decision = result.get("decision", "")

            decision_text = "Supported" if "reject" in decision.lower() else "Not Supported"

            # Escape commas in hypothesis text
            hypothesis = f'"{hypothesis}"' if "," in hypothesis else hypothesis

            lines.append(
                f'{h_id},{hypothesis},{test},{statistic:.4f},{p_value:.6f},{decision_text}'
            )

        return "\n".join(lines)

    def format_comparison_table(
        self,
        systems: List[str],
        metrics: Dict[str, List[float]],
        format: str = TableFormat.LATEX,
        caption: str = "System comparison",
        label: str = "tab:comparison",
        higher_better: Optional[Dict[str, bool]] = None,
    ) -> str:
        """
        Format system comparison table.

        Args:
            systems: List of system names (columns)
            metrics: Dictionary mapping metric names to values for each system
            format: Output format
            caption: Table caption
            label: Table label
            higher_better: Dict indicating if higher values are better per metric

        Returns:
            Formatted table string
        """
        higher_better = higher_better or {}

        if format == TableFormat.LATEX:
            return self._comparison_table_latex(
                systems, metrics, caption, label, higher_better
            )
        elif format == TableFormat.MARKDOWN:
            return self._comparison_table_markdown(
                systems, metrics, caption, higher_better
            )
        else:
            return self._comparison_table_latex(
                systems, metrics, caption, label, higher_better
            )

    def _comparison_table_latex(
        self,
        systems: List[str],
        metrics: Dict[str, List[float]],
        caption: str,
        label: str,
        higher_better: Dict[str, bool],
    ) -> str:
        """Generate LaTeX comparison table."""
        n_systems = len(systems)
        col_spec = "l" + "c" * n_systems

        lines = [
            "\\begin{table}[htbp]",
            "\\centering",
            f"\\caption{{{caption}. Bold indicates best performance.}}",
            f"\\label{{{label}}}",
        ]

        if self.style.small_font:
            lines.append("\\small")

        lines.append(f"\\begin{{tabular}}{{@{{}}{col_spec}@{{}}}}")
        lines.append("\\toprule")

        # Header
        header = "\\textbf{Metric}"
        for system in systems:
            header += f" & \\textbf{{{system}}}"
        lines.append(header + " \\\\")
        lines.append("\\midrule")

        # Data rows
        for metric_name, values in metrics.items():
            if len(values) != n_systems:
                continue

            # Find best value
            is_higher_better = higher_better.get(metric_name, True)
            if is_higher_better:
                best_idx = values.index(max(values))
            else:
                best_idx = values.index(min(values))

            row = metric_name
            for i, val in enumerate(values):
                if self.style.bold_best and i == best_idx:
                    row += f" & \\textbf{{{val:.{self.style.decimal_places}f}}}"
                else:
                    row += f" & {val:.{self.style.decimal_places}f}"
            lines.append(row + " \\\\")

        lines.extend([
            "\\bottomrule",
            "\\end{tabular}",
            "\\end{table}",
        ])

        return "\n".join(lines)

    def _comparison_table_markdown(
        self,
        systems: List[str],
        metrics: Dict[str, List[float]],
        caption: str,
        higher_better: Dict[str, bool],
    ) -> str:
        """Generate Markdown comparison table."""
        lines = []

        if caption:
            lines.append(f"**{caption}** (Bold indicates best performance)")
            lines.append("")

        # Header
        header = "| Metric |"
        separator = "|:-------|"
        for system in systems:
            header += f" {system} |"
            separator += "-------:|"

        lines.append(header)
        lines.append(separator)

        # Data rows
        for metric_name, values in metrics.items():
            if len(values) != len(systems):
                continue

            is_higher_better = higher_better.get(metric_name, True)
            if is_higher_better:
                best_idx = values.index(max(values))
            else:
                best_idx = values.index(min(values))

            row = f"| {metric_name} |"
            for i, val in enumerate(values):
                if self.style.bold_best and i == best_idx:
                    row += f" **{val:.{self.style.decimal_places}f}** |"
                else:
                    row += f" {val:.{self.style.decimal_places}f} |"
            lines.append(row)

        return "\n".join(lines)

    def format_summary_statistics(
        self,
        data: Union[List[float], Any],
        name: str,
        format: str = TableFormat.LATEX,
        label: str = "tab:summary",
    ) -> str:
        """
        Format summary statistics table.

        n, mean, std, min, Q1, median, Q3, max

        Args:
            data: Numeric data array
            name: Name of the metric
            format: Output format
            label: Table label

        Returns:
            Formatted table string
        """
        if NUMPY_AVAILABLE:
            import numpy as np
            data = np.asarray(data).flatten()

            stats = {
                "n": len(data),
                "Mean": np.mean(data),
                "SD": np.std(data, ddof=1),
                "Min": np.min(data),
                "Q1": np.percentile(data, 25),
                "Median": np.median(data),
                "Q3": np.percentile(data, 75),
                "Max": np.max(data),
            }
        else:
            data = list(data)
            data_sorted = sorted(data)
            n = len(data)

            stats = {
                "n": n,
                "Mean": sum(data) / n if n > 0 else 0,
                "SD": 0,  # Simplified
                "Min": min(data) if data else 0,
                "Q1": data_sorted[n // 4] if n > 0 else 0,
                "Median": data_sorted[n // 2] if n > 0 else 0,
                "Q3": data_sorted[3 * n // 4] if n > 0 else 0,
                "Max": max(data) if data else 0,
            }

        if format == TableFormat.LATEX:
            return self._summary_stats_latex(stats, name, label)
        elif format == TableFormat.MARKDOWN:
            return self._summary_stats_markdown(stats, name)
        else:
            return self._summary_stats_latex(stats, name, label)

    def _summary_stats_latex(
        self,
        stats: Dict[str, float],
        name: str,
        label: str,
    ) -> str:
        """Generate LaTeX summary statistics table."""
        dp = self.style.decimal_places

        lines = [
            "\\begin{table}[htbp]",
            "\\centering",
            f"\\caption{{Summary statistics for {name}}}",
            f"\\label{{{label}}}",
            "\\begin{tabular}{@{}rrrrrrrr@{}}",
            "\\toprule",
            "\\textbf{n} & \\textbf{Mean} & \\textbf{SD} & \\textbf{Min} & "
            "\\textbf{Q1} & \\textbf{Median} & \\textbf{Q3} & \\textbf{Max} \\\\",
            "\\midrule",
            f"{stats['n']} & {stats['Mean']:.{dp}f} & {stats['SD']:.{dp}f} & "
            f"{stats['Min']:.{dp}f} & {stats['Q1']:.{dp}f} & {stats['Median']:.{dp}f} & "
            f"{stats['Q3']:.{dp}f} & {stats['Max']:.{dp}f} \\\\",
            "\\bottomrule",
            "\\end{tabular}",
            "\\end{table}",
        ]

        return "\n".join(lines)

    def _summary_stats_markdown(
        self,
        stats: Dict[str, float],
        name: str,
    ) -> str:
        """Generate Markdown summary statistics table."""
        dp = self.style.decimal_places

        lines = [
            f"**Summary statistics for {name}**",
            "",
            "| n | Mean | SD | Min | Q1 | Median | Q3 | Max |",
            "|--:|-----:|---:|----:|---:|-------:|---:|----:|",
            f"| {stats['n']} | {stats['Mean']:.{dp}f} | {stats['SD']:.{dp}f} | "
            f"{stats['Min']:.{dp}f} | {stats['Q1']:.{dp}f} | {stats['Median']:.{dp}f} | "
            f"{stats['Q3']:.{dp}f} | {stats['Max']:.{dp}f} |",
        ]

        return "\n".join(lines)

    def format_effect_size_table(
        self,
        results: List[Dict[str, Any]],
        format: str = TableFormat.LATEX,
        caption: str = "Effect sizes with 95\\% confidence intervals",
        label: str = "tab:effect_sizes",
    ) -> str:
        """
        Format effect size results as publication table.

        Args:
            results: List of effect size results
            format: Output format
            caption: Table caption
            label: Table label

        Returns:
            Formatted table string
        """
        if format == TableFormat.LATEX:
            return self._effect_size_table_latex(results, caption, label)
        elif format == TableFormat.MARKDOWN:
            return self._effect_size_table_markdown(results, caption)
        else:
            return self._effect_size_table_latex(results, caption, label)

    def _effect_size_table_latex(
        self,
        results: List[Dict[str, Any]],
        caption: str,
        label: str,
    ) -> str:
        """Generate LaTeX effect size table."""
        lines = [
            "\\begin{table}[htbp]",
            "\\centering",
            f"\\caption{{{caption}}}",
            f"\\label{{{label}}}",
        ]

        if self.style.small_font:
            lines.append("\\small")

        lines.extend([
            "\\begin{tabular}{@{}llrrl@{}}",
            "\\toprule",
            "\\textbf{Hypothesis} & \\textbf{Measure} & \\textbf{Effect} & "
            "\\textbf{95\\% CI} & \\textbf{Interpretation} \\\\",
            "\\midrule",
        ])

        for result in results:
            h_id = result.get("hypothesis_id", "N/A")
            measure = result.get("measure", result.get("effect_type", "d"))
            effect = result.get("effect_size", result.get("value", 0))
            ci = result.get("confidence_interval", result.get("ci", [0, 0]))
            interp = result.get("interpretation", result.get("magnitude", ""))

            if isinstance(ci, (list, tuple)) and len(ci) >= 2:
                ci_str = f"[{ci[0]:.2f}, {ci[1]:.2f}]"
            else:
                ci_str = "N/A"

            lines.append(
                f"{h_id} & {measure} & {effect:.3f} & {ci_str} & {interp} \\\\"
            )

        lines.extend([
            "\\bottomrule",
            "\\end{tabular}",
            "\\end{table}",
        ])

        return "\n".join(lines)

    def _effect_size_table_markdown(
        self,
        results: List[Dict[str, Any]],
        caption: str,
    ) -> str:
        """Generate Markdown effect size table."""
        lines = [
            f"**{caption}**",
            "",
            "| Hypothesis | Measure | Effect | 95% CI | Interpretation |",
            "|:-----------|:--------|-------:|:-------|:---------------|",
        ]

        for result in results:
            h_id = result.get("hypothesis_id", "N/A")
            measure = result.get("measure", result.get("effect_type", "d"))
            effect = result.get("effect_size", result.get("value", 0))
            ci = result.get("confidence_interval", result.get("ci", [0, 0]))
            interp = result.get("interpretation", result.get("magnitude", ""))

            if isinstance(ci, (list, tuple)) and len(ci) >= 2:
                ci_str = f"[{ci[0]:.2f}, {ci[1]:.2f}]"
            else:
                ci_str = "N/A"

            lines.append(f"| {h_id} | {measure} | {effect:.3f} | {ci_str} | {interp} |")

        return "\n".join(lines)

    def format_domain_summary_table(
        self,
        domain_results: Dict[str, Any],
        format: str = TableFormat.LATEX,
        caption: str = "Summary of hypothesis test results by research domain",
        label: str = "tab:domain_summary",
    ) -> str:
        """
        Format domain summary table.

        Args:
            domain_results: Dictionary of domain results
            format: Output format
            caption: Table caption
            label: Table label

        Returns:
            Formatted table string
        """
        rows = []
        for domain_id, data in domain_results.items():
            if isinstance(data, dict):
                tested = data.get("hypotheses_tested", 0)
                supported = data.get("hypotheses_supported", 0)
            elif hasattr(data, "hypotheses_tested"):
                tested = data.hypotheses_tested
                supported = data.hypotheses_supported
            else:
                continue

            failed = tested - supported
            rate = supported / tested if tested > 0 else 0

            name = domain_id.replace("_", " ").title()
            rows.append((name, tested, supported, failed, rate))

        if format == TableFormat.LATEX:
            return self._domain_summary_latex(rows, caption, label)
        else:
            return self._domain_summary_markdown(rows, caption)

    def _domain_summary_latex(
        self,
        rows: List[Tuple],
        caption: str,
        label: str,
    ) -> str:
        """Generate LaTeX domain summary table."""
        lines = [
            "\\begin{table}[htbp]",
            "\\centering",
            f"\\caption{{{caption}}}",
            f"\\label{{{label}}}",
            "\\begin{tabular}{@{}lcccr@{}}",
            "\\toprule",
            "\\textbf{Domain} & \\textbf{Tested} & \\textbf{Supported} & "
            "\\textbf{Failed} & \\textbf{Rate} \\\\",
            "\\midrule",
        ]

        total_tested = 0
        total_supported = 0

        for name, tested, supported, failed, rate in rows:
            lines.append(f"{name} & {tested} & {supported} & {failed} & {rate:.1%} \\\\")
            total_tested += tested
            total_supported += supported

        total_rate = total_supported / total_tested if total_tested > 0 else 0

        lines.extend([
            "\\midrule",
            f"\\textbf{{Total}} & \\textbf{{{total_tested}}} & "
            f"\\textbf{{{total_supported}}} & \\textbf{{{total_tested - total_supported}}} & "
            f"\\textbf{{{total_rate:.1%}}} \\\\",
            "\\bottomrule",
            "\\end{tabular}",
            "\\end{table}",
        ])

        return "\n".join(lines)

    def _domain_summary_markdown(
        self,
        rows: List[Tuple],
        caption: str,
    ) -> str:
        """Generate Markdown domain summary table."""
        lines = [
            f"**{caption}**",
            "",
            "| Domain | Tested | Supported | Failed | Rate |",
            "|:-------|-------:|----------:|-------:|-----:|",
        ]

        total_tested = 0
        total_supported = 0

        for name, tested, supported, failed, rate in rows:
            lines.append(f"| {name} | {tested} | {supported} | {failed} | {rate:.1%} |")
            total_tested += tested
            total_supported += supported

        total_rate = total_supported / total_tested if total_tested > 0 else 0

        lines.append(f"| **Total** | **{total_tested}** | **{total_supported}** | "
                    f"**{total_tested - total_supported}** | **{total_rate:.1%}** |")

        return "\n".join(lines)

    @staticmethod
    def _escape_latex(text: str) -> str:
        """Escape special LaTeX characters."""
        special_chars = {
            "&": "\\&",
            "%": "\\%",
            "$": "\\$",
            "#": "\\#",
            "_": "\\_",
            "{": "\\{",
            "}": "\\}",
            "~": "\\textasciitilde{}",
            "^": "\\textasciicircum{}",
        }
        for char, replacement in special_chars.items():
            text = text.replace(char, replacement)
        return text


# Convenience functions
def format_hypothesis_table(
    results: List[Dict[str, Any]],
    format: str = TableFormat.LATEX,
) -> str:
    """Format hypothesis results as publication table."""
    formatter = PublicationTableFormatter()
    return formatter.format_hypothesis_table(results, format)


def format_comparison_table(
    systems: List[str],
    metrics: Dict[str, List[float]],
    format: str = TableFormat.LATEX,
) -> str:
    """Format system comparison table."""
    formatter = PublicationTableFormatter()
    return formatter.format_comparison_table(systems, metrics, format)


def format_summary_statistics(
    data: Union[List[float], Any],
    name: str,
    format: str = TableFormat.LATEX,
) -> str:
    """Format summary statistics table."""
    formatter = PublicationTableFormatter()
    return formatter.format_summary_statistics(data, name, format)
