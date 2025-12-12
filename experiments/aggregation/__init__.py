"""
SHAKTI-CHAIN Results Aggregation System.

Comprehensive system for collecting, analyzing, and presenting experiment results
from all domains of the SHAKTI-CHAIN validation framework.

Modules:
    - result_collector: Gather results from all experiment domains
    - cross_domain_analyzer: Find patterns and correlations across domains
    - summary_generator: Generate executive summaries and reports
    - failure_analyzer: Analyze failed hypotheses and identify root causes
    - recommendation_engine: Generate actionable recommendations
    - dashboard: Interactive results dashboard (Streamlit + CLI)

Example Usage:
    >>> from experiments.aggregation import ResultCollector, SummaryGenerator
    >>> collector = ResultCollector(results_dir="./results")
    >>> results = collector.collect_all_results()
    >>>
    >>> generator = SummaryGenerator(results)
    >>> summary = generator.generate_executive_summary()
    >>> print(summary.overall_verdict)

CLI Usage:
    # Interactive CLI dashboard
    python -m experiments.aggregation.dashboard --results-dir ./results --mode cli

    # Streamlit web dashboard
    python -m experiments.aggregation.dashboard --results-dir ./results --port 8501
"""

from .result_collector import (
    ResultCollector,
    DomainResults,
    HypothesisResult,
    collect_results,
    CRITICAL_HYPOTHESES,
)

from .cross_domain_analyzer import (
    CrossDomainAnalyzer,
    CorrelationResult,
    TradeoffAnalysis,
    analyze_cross_domain,
)

from .summary_generator import (
    SummaryGenerator,
    ExecutiveSummary,
    generate_summary,
)

from .failure_analyzer import (
    FailureAnalyzer,
    FailureAnalysis,
    FailurePattern,
    FailureCategory,
    FailureSeverity,
    RemediationPlan,
    RemediationPriority,
    analyze_failures,
)

from .recommendation_engine import (
    RecommendationEngine,
    Recommendation,
    RecommendationSet,
    ActionPlan,
    RecommendationType,
    RecommendationUrgency,
    StakeholderType,
    generate_recommendations,
)

from .dashboard import (
    CLIDashboard,
    ResultsLoader,
    DashboardConfig,
    DashboardMode,
)

__all__ = [
    # Result Collection
    "ResultCollector",
    "DomainResults",
    "HypothesisResult",
    "collect_results",
    "CRITICAL_HYPOTHESES",

    # Cross-Domain Analysis
    "CrossDomainAnalyzer",
    "CorrelationResult",
    "TradeoffAnalysis",
    "analyze_cross_domain",

    # Summary Generation
    "SummaryGenerator",
    "ExecutiveSummary",
    "generate_summary",

    # Failure Analysis
    "FailureAnalyzer",
    "FailureAnalysis",
    "FailurePattern",
    "FailureCategory",
    "FailureSeverity",
    "RemediationPlan",
    "RemediationPriority",
    "analyze_failures",

    # Recommendations
    "RecommendationEngine",
    "Recommendation",
    "RecommendationSet",
    "ActionPlan",
    "RecommendationType",
    "RecommendationUrgency",
    "StakeholderType",
    "generate_recommendations",

    # Dashboard
    "CLIDashboard",
    "ResultsLoader",
    "DashboardConfig",
    "DashboardMode",
]

__version__ = "1.0.0"


def full_analysis_pipeline(
    results_dir: str,
    output_dir: str = None,
    include_dashboard: bool = False,
):
    """
    Run the complete analysis pipeline.

    This function orchestrates the full analysis workflow:
    1. Collect results from all domains
    2. Perform cross-domain analysis
    3. Analyze failures
    4. Generate recommendations
    5. Create executive summary
    6. Optionally launch dashboard

    Args:
        results_dir: Directory containing experiment results
        output_dir: Directory for output reports (optional)
        include_dashboard: Whether to launch interactive dashboard

    Returns:
        Dictionary containing all analysis results
    """
    from pathlib import Path

    results_path = Path(results_dir)
    output_path = Path(output_dir) if output_dir else results_path / "analysis"
    output_path.mkdir(parents=True, exist_ok=True)

    # Step 1: Collect results
    print("Step 1/5: Collecting results from all domains...")
    collector = ResultCollector(results_dir=results_path)
    domain_results = collector.collect_all_results()
    overall = collector.get_overall_summary()

    # Step 2: Cross-domain analysis
    print("Step 2/5: Performing cross-domain analysis...")
    cross_analyzer = CrossDomainAnalyzer(domain_results)
    cross_domain_report = cross_analyzer.generate_cross_domain_report()

    # Step 3: Failure analysis
    print("Step 3/5: Analyzing failures...")
    failed_hypotheses = collector.identify_critical_failures()
    failure_analyzer = FailureAnalyzer()

    for failure in failed_hypotheses:
        failure_analyzer.analyze_failure(
            hypothesis_id=failure.get("hypothesis_id", "UNKNOWN"),
            domain=failure.get("domain", "unknown"),
            p_value=failure.get("p_value", 1.0),
            effect_size=failure.get("effect_size", 0.0),
            sample_size=failure.get("sample_size", 30),
        )

    failure_report = failure_analyzer.generate_failure_report()

    # Step 4: Generate recommendations
    print("Step 4/5: Generating recommendations...")
    rec_engine = RecommendationEngine(
        domain_results={k: v.__dict__ if hasattr(v, '__dict__') else v for k, v in domain_results.items()},
        failure_analysis=failure_report,
        cross_domain_analysis=cross_domain_report,
    )
    action_plan = rec_engine.generate_action_plan()

    # Step 5: Executive summary
    print("Step 5/5: Generating executive summary...")
    summary_gen = SummaryGenerator(domain_results)
    executive_summary = summary_gen.generate_executive_summary()

    # Save reports
    import json

    with open(output_path / "domain_results.json", "w") as f:
        json.dump({k: v.__dict__ if hasattr(v, '__dict__') else v for k, v in domain_results.items()}, f, indent=2, default=str)

    with open(output_path / "cross_domain_analysis.json", "w") as f:
        json.dump(cross_domain_report, f, indent=2, default=str)

    with open(output_path / "failure_analysis.json", "w") as f:
        json.dump(failure_report, f, indent=2, default=str)

    with open(output_path / "recommendations.json", "w") as f:
        json.dump({
            "action_plan": action_plan.to_dict(),
            "all_recommendations": [r.to_dict() for r in rec_engine.recommendations],
        }, f, indent=2, default=str)

    with open(output_path / "executive_summary.json", "w") as f:
        json.dump(executive_summary.to_dict(), f, indent=2, default=str)

    # Save markdown reports
    failure_analyzer.save_report(output_path / "failure_analysis.md", format="markdown")
    rec_engine.save_report(output_path / "recommendations.md", format="markdown")
    summary_gen.save_reports(output_path, formats=["markdown"])

    print(f"\nAnalysis complete! Reports saved to: {output_path}")

    # Launch dashboard if requested
    if include_dashboard:
        print("\nLaunching interactive dashboard...")
        dashboard = CLIDashboard(ResultsLoader(output_path))
        dashboard.run()

    return {
        "domain_results": domain_results,
        "overall_summary": overall,
        "cross_domain": cross_domain_report,
        "failures": failure_report,
        "action_plan": action_plan,
        "executive_summary": executive_summary,
    }


def quick_summary(results_dir: str) -> str:
    """
    Generate a quick text summary of experiment results.

    Args:
        results_dir: Directory containing experiment results

    Returns:
        Text summary string
    """
    from pathlib import Path

    collector = ResultCollector(results_dir=Path(results_dir))
    results = collector.collect_all_results()
    overall = collector.get_overall_summary()

    lines = [
        "=" * 50,
        "SHAKTI-CHAIN EXPERIMENT RESULTS SUMMARY",
        "=" * 50,
        "",
        f"Total Hypotheses: {overall.get('total_hypotheses', 'N/A')}",
        f"Supported: {overall.get('total_supported', 'N/A')}",
        f"Success Rate: {overall.get('overall_success_rate', 0):.1%}",
        "",
        "Domain Breakdown:",
    ]

    for domain_id, domain_results in results.items():
        if hasattr(domain_results, 'hypotheses_tested'):
            tested = domain_results.hypotheses_tested
            supported = domain_results.hypotheses_supported
            rate = supported / tested if tested > 0 else 0
            lines.append(f"  {domain_id}: {supported}/{tested} ({rate:.1%})")

    critical = overall.get("critical_failures", [])
    if critical:
        lines.extend([
            "",
            f"CRITICAL FAILURES ({len(critical)}):",
        ])
        for cf in critical[:5]:
            lines.append(f"  - {cf}")

    lines.extend([
        "",
        "=" * 50,
    ])

    return "\n".join(lines)
