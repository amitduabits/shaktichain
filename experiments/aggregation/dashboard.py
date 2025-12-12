"""
Interactive Dashboard for SHAKTI-CHAIN Experiment Results.

Provides both a Streamlit web interface and CLI for viewing results.

Usage:
    CLI Mode:
        python -m experiments.aggregation.dashboard --results-dir ./results --mode cli

    Streamlit Mode:
        python -m experiments.aggregation.dashboard --results-dir ./results --port 8501
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum
import os

# Check for optional dependencies
try:
    import streamlit as st
    STREAMLIT_AVAILABLE = True
except ImportError:
    STREAMLIT_AVAILABLE = False

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

try:
    import plotly.express as px
    import plotly.graph_objects as go
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False


class DashboardMode(Enum):
    """Dashboard operation modes."""
    CLI = "cli"
    STREAMLIT = "streamlit"


@dataclass
class DashboardConfig:
    """Dashboard configuration."""
    results_dir: Path
    mode: DashboardMode
    port: int = 8501
    host: str = "localhost"
    theme: str = "light"


class ResultsLoader:
    """Load and parse experiment results."""

    def __init__(self, results_dir: Path):
        """Initialize loader with results directory."""
        self.results_dir = Path(results_dir)
        self._cache: Dict[str, Any] = {}

    def load_all(self) -> Dict[str, Any]:
        """Load all available results."""
        if "all" in self._cache:
            return self._cache["all"]

        results = {
            "domains": self._load_domain_results(),
            "summary": self._load_summary(),
            "failures": self._load_failure_analysis(),
            "recommendations": self._load_recommendations(),
            "cross_domain": self._load_cross_domain(),
        }

        self._cache["all"] = results
        return results

    def _load_domain_results(self) -> Dict[str, Any]:
        """Load results from each domain."""
        domains = {}

        # Check for domain-specific result files
        domain_dirs = [
            "domain1_system",
            "domain2_token",
            "domain3_data",
            "domain4_agent",
            "domain5_stress",
            "domain6_forecast",
        ]

        for domain_dir in domain_dirs:
            domain_path = self.results_dir / domain_dir
            if domain_path.exists():
                results_file = domain_path / "results.json"
                if results_file.exists():
                    with open(results_file) as f:
                        domains[domain_dir] = json.load(f)

        # Also check for aggregated domain results
        agg_file = self.results_dir / "domain_results.json"
        if agg_file.exists():
            with open(agg_file) as f:
                agg_data = json.load(f)
                domains.update(agg_data)

        return domains

    def _load_summary(self) -> Optional[Dict[str, Any]]:
        """Load executive summary."""
        summary_file = self.results_dir / "executive_summary.json"
        if summary_file.exists():
            with open(summary_file) as f:
                return json.load(f)
        return None

    def _load_failure_analysis(self) -> Optional[Dict[str, Any]]:
        """Load failure analysis."""
        failure_file = self.results_dir / "failure_analysis.json"
        if failure_file.exists():
            with open(failure_file) as f:
                return json.load(f)
        return None

    def _load_recommendations(self) -> Optional[Dict[str, Any]]:
        """Load recommendations."""
        rec_file = self.results_dir / "recommendations.json"
        if rec_file.exists():
            with open(rec_file) as f:
                return json.load(f)
        return None

    def _load_cross_domain(self) -> Optional[Dict[str, Any]]:
        """Load cross-domain analysis."""
        cd_file = self.results_dir / "cross_domain_analysis.json"
        if cd_file.exists():
            with open(cd_file) as f:
                return json.load(f)
        return None


class CLIDashboard:
    """Command-line interface dashboard."""

    def __init__(self, loader: ResultsLoader):
        """Initialize CLI dashboard."""
        self.loader = loader
        self.results = loader.load_all()

    def run(self) -> None:
        """Run interactive CLI dashboard."""
        self._print_header()

        while True:
            self._print_menu()
            choice = input("\nEnter choice (q to quit): ").strip().lower()

            if choice == "q":
                print("\nExiting dashboard. Goodbye!")
                break
            elif choice == "1":
                self._show_overview()
            elif choice == "2":
                self._show_domain_results()
            elif choice == "3":
                self._show_failures()
            elif choice == "4":
                self._show_recommendations()
            elif choice == "5":
                self._show_cross_domain()
            elif choice == "6":
                self._export_report()
            else:
                print("\nInvalid choice. Please try again.")

    def _print_header(self) -> None:
        """Print dashboard header."""
        print("\n" + "=" * 60)
        print("  SHAKTI-CHAIN Experiment Results Dashboard")
        print("=" * 60)

    def _print_menu(self) -> None:
        """Print main menu."""
        print("\n" + "-" * 40)
        print("Main Menu:")
        print("-" * 40)
        print("1. Overview & Summary")
        print("2. Domain Results")
        print("3. Failure Analysis")
        print("4. Recommendations")
        print("5. Cross-Domain Analysis")
        print("6. Export Report")
        print("q. Quit")

    def _show_overview(self) -> None:
        """Show overview and executive summary."""
        print("\n" + "=" * 50)
        print("OVERVIEW & EXECUTIVE SUMMARY")
        print("=" * 50)

        summary = self.results.get("summary")
        if not summary:
            print("\nNo executive summary available.")
            self._generate_basic_overview()
            return

        print(f"\nOverall Verdict: {summary.get('overall_verdict', 'N/A')}")
        print(f"Total Hypotheses: {summary.get('total_hypotheses', 'N/A')}")
        print(f"Success Rate: {summary.get('success_rate', 0):.1%}")
        print(f"Critical Failures: {len(summary.get('critical_failures', []))}")

        if summary.get("key_findings"):
            print("\nKey Findings:")
            for i, finding in enumerate(summary["key_findings"][:5], 1):
                print(f"  {i}. {finding}")

        if summary.get("critical_issues"):
            print("\nCritical Issues:")
            for i, issue in enumerate(summary["critical_issues"][:5], 1):
                print(f"  {i}. {issue}")

    def _generate_basic_overview(self) -> None:
        """Generate basic overview from available data."""
        domains = self.results.get("domains", {})
        if domains:
            print(f"\nLoaded {len(domains)} domain(s): {', '.join(domains.keys())}")

        failures = self.results.get("failures", {})
        if failures:
            summary = failures.get("summary", {})
            print(f"Total failures analyzed: {summary.get('total_failures', 0)}")
            print(f"Critical failures: {summary.get('critical_failures', 0)}")

    def _show_domain_results(self) -> None:
        """Show domain-specific results."""
        print("\n" + "=" * 50)
        print("DOMAIN RESULTS")
        print("=" * 50)

        domains = self.results.get("domains", {})
        if not domains:
            print("\nNo domain results available.")
            return

        # List available domains
        print("\nAvailable domains:")
        domain_list = list(domains.keys())
        for i, domain in enumerate(domain_list, 1):
            print(f"  {i}. {domain}")
        print("  a. Show all")
        print("  b. Back to menu")

        choice = input("\nSelect domain: ").strip().lower()

        if choice == "b":
            return
        elif choice == "a":
            for domain, data in domains.items():
                self._print_domain_summary(domain, data)
        else:
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(domain_list):
                    domain = domain_list[idx]
                    self._print_domain_details(domain, domains[domain])
                else:
                    print("Invalid selection.")
            except ValueError:
                print("Invalid input.")

    def _print_domain_summary(self, domain: str, data: Dict[str, Any]) -> None:
        """Print summary for a domain."""
        print(f"\n--- {domain} ---")
        if isinstance(data, dict):
            tested = data.get("hypotheses_tested", data.get("total", "N/A"))
            supported = data.get("hypotheses_supported", data.get("passed", "N/A"))
            print(f"  Tested: {tested}, Supported: {supported}")
        else:
            print(f"  Data: {type(data)}")

    def _print_domain_details(self, domain: str, data: Dict[str, Any]) -> None:
        """Print detailed results for a domain."""
        print(f"\n{'=' * 50}")
        print(f"DOMAIN: {domain}")
        print("=" * 50)

        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, list):
                    print(f"\n{key}:")
                    for item in value[:10]:
                        if isinstance(item, dict):
                            print(f"  - {item.get('hypothesis_id', item.get('id', item))}")
                        else:
                            print(f"  - {item}")
                elif isinstance(value, dict):
                    print(f"\n{key}: {len(value)} items")
                else:
                    print(f"{key}: {value}")

    def _show_failures(self) -> None:
        """Show failure analysis."""
        print("\n" + "=" * 50)
        print("FAILURE ANALYSIS")
        print("=" * 50)

        failures = self.results.get("failures", {})
        if not failures:
            print("\nNo failure analysis available.")
            return

        summary = failures.get("summary", {})
        print(f"\nTotal Failures: {summary.get('total_failures', 0)}")
        print(f"Critical: {summary.get('critical_failures', 0)}")

        # Categories
        categories = summary.get("categories", {})
        if categories:
            print("\nBy Category:")
            for cat, count in categories.items():
                print(f"  {cat}: {count}")

        # Severities
        severities = summary.get("severities", {})
        if severities:
            print("\nBy Severity:")
            for sev, count in severities.items():
                print(f"  {sev}: {count}")

        # Detailed failures
        failure_list = failures.get("failures", [])
        if failure_list:
            print(f"\nShowing first 5 of {len(failure_list)} failures:")
            for f in failure_list[:5]:
                crit = " [CRITICAL]" if f.get("is_critical") else ""
                print(f"\n  {f.get('hypothesis_id', 'N/A')}{crit}")
                print(f"    Domain: {f.get('domain', 'N/A')}")
                print(f"    Category: {f.get('category', 'N/A')}")
                print(f"    Root cause: {f.get('root_cause', 'N/A')[:60]}...")

        # Patterns
        patterns = failures.get("patterns", [])
        if patterns:
            print(f"\nDetected Patterns ({len(patterns)}):")
            for p in patterns[:3]:
                print(f"  - {p.get('description', 'N/A')}")

    def _show_recommendations(self) -> None:
        """Show recommendations."""
        print("\n" + "=" * 50)
        print("RECOMMENDATIONS")
        print("=" * 50)

        recs = self.results.get("recommendations", {})
        if not recs:
            print("\nNo recommendations available.")
            return

        plan = recs.get("action_plan", {})
        print(f"\nOverall Verdict: {plan.get('overall_verdict', 'N/A')}")
        print(f"\n{plan.get('summary', '')}")

        # Count by urgency
        all_recs = recs.get("all_recommendations", recs.get("recommendations", []))
        if all_recs:
            urgency_counts = {}
            for r in all_recs:
                urg = r.get("urgency", "unknown")
                urgency_counts[urg] = urgency_counts.get(urg, 0) + 1

            print(f"\nTotal Recommendations: {len(all_recs)}")
            for urg, count in sorted(urgency_counts.items()):
                print(f"  {urg}: {count}")

        # Critical actions
        critical = plan.get("critical_actions", [])
        if critical:
            print(f"\nCritical Actions ({len(critical)}):")
            for i, action in enumerate(critical[:5], 1):
                title = action.get("title", action) if isinstance(action, dict) else action
                print(f"  {i}. {title}")

        # Timeline
        immediate = plan.get("immediate_phase", [])
        if immediate:
            print(f"\nImmediate Phase ({len(immediate)} actions):")
            for action in immediate[:3]:
                print(f"  - {action}")

    def _show_cross_domain(self) -> None:
        """Show cross-domain analysis."""
        print("\n" + "=" * 50)
        print("CROSS-DOMAIN ANALYSIS")
        print("=" * 50)

        cd = self.results.get("cross_domain", {})
        if not cd:
            print("\nNo cross-domain analysis available.")
            return

        # Correlations
        correlations = cd.get("correlations", {})
        if correlations:
            print("\nDomain Correlations:")
            for key, value in list(correlations.items())[:5]:
                if isinstance(value, dict):
                    corr = value.get("correlation", 0)
                else:
                    corr = value
                print(f"  {key}: {corr:.3f}")

        # Tradeoffs
        tradeoffs = cd.get("tradeoffs", [])
        if tradeoffs:
            print(f"\nIdentified Tradeoffs ({len(tradeoffs)}):")
            for t in tradeoffs[:3]:
                d1 = t.get("domain1", "?")
                d2 = t.get("domain2", "?")
                print(f"  - {d1} vs {d2}")

        # Clusters
        clusters = cd.get("failure_clusters", {})
        if clusters:
            print(f"\nFailure Clusters: {len(clusters)} identified")

    def _export_report(self) -> None:
        """Export report to file."""
        print("\n" + "=" * 50)
        print("EXPORT REPORT")
        print("=" * 50)

        print("\nExport formats:")
        print("1. JSON")
        print("2. Markdown")
        print("3. Text summary")
        print("b. Back")

        choice = input("\nSelect format: ").strip()

        if choice == "b":
            return

        filename = input("Output filename (without extension): ").strip()
        if not filename:
            filename = "shakti_report"

        if choice == "1":
            self._export_json(filename + ".json")
        elif choice == "2":
            self._export_markdown(filename + ".md")
        elif choice == "3":
            self._export_text(filename + ".txt")
        else:
            print("Invalid format.")

    def _export_json(self, filename: str) -> None:
        """Export as JSON."""
        with open(filename, "w") as f:
            json.dump(self.results, f, indent=2, default=str)
        print(f"\nExported to {filename}")

    def _export_markdown(self, filename: str) -> None:
        """Export as Markdown."""
        lines = [
            "# SHAKTI-CHAIN Experiment Results Report",
            "",
            "## Overview",
            "",
        ]

        summary = self.results.get("summary", {})
        if summary:
            lines.append(f"**Verdict**: {summary.get('overall_verdict', 'N/A')}")
            lines.append(f"**Success Rate**: {summary.get('success_rate', 0):.1%}")
            lines.append("")

        lines.append("## Domains")
        lines.append("")
        for domain, data in self.results.get("domains", {}).items():
            lines.append(f"### {domain}")
            if isinstance(data, dict):
                for k, v in data.items():
                    if not isinstance(v, (list, dict)):
                        lines.append(f"- {k}: {v}")
            lines.append("")

        with open(filename, "w") as f:
            f.write("\n".join(lines))
        print(f"\nExported to {filename}")

    def _export_text(self, filename: str) -> None:
        """Export as plain text."""
        lines = [
            "SHAKTI-CHAIN EXPERIMENT RESULTS REPORT",
            "=" * 50,
            "",
        ]

        summary = self.results.get("summary", {})
        if summary:
            lines.append(f"Verdict: {summary.get('overall_verdict', 'N/A')}")
            lines.append(f"Success Rate: {summary.get('success_rate', 0):.1%}")
            lines.append("")

        failures = self.results.get("failures", {})
        if failures:
            fsummary = failures.get("summary", {})
            lines.append(f"Total Failures: {fsummary.get('total_failures', 0)}")
            lines.append(f"Critical Failures: {fsummary.get('critical_failures', 0)}")

        with open(filename, "w") as f:
            f.write("\n".join(lines))
        print(f"\nExported to {filename}")


def create_streamlit_app(loader: ResultsLoader) -> None:
    """Create and run Streamlit dashboard."""
    if not STREAMLIT_AVAILABLE:
        print("Error: Streamlit is not installed. Install with: pip install streamlit")
        sys.exit(1)

    results = loader.load_all()

    # Page config
    st.set_page_config(
        page_title="SHAKTI-CHAIN Results Dashboard",
        page_icon="⚡",
        layout="wide",
    )

    # Sidebar
    st.sidebar.title("⚡ SHAKTI-CHAIN")
    st.sidebar.markdown("---")

    page = st.sidebar.radio(
        "Navigate to",
        ["Overview", "Domain Results", "Failure Analysis", "Recommendations", "Cross-Domain"],
    )

    # Main content
    if page == "Overview":
        render_overview(results)
    elif page == "Domain Results":
        render_domain_results(results)
    elif page == "Failure Analysis":
        render_failure_analysis(results)
    elif page == "Recommendations":
        render_recommendations(results)
    elif page == "Cross-Domain":
        render_cross_domain(results)


def render_overview(results: Dict[str, Any]) -> None:
    """Render overview page."""
    st.title("📊 Experiment Results Overview")

    summary = results.get("summary", {})

    # Key metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        verdict = summary.get("overall_verdict", "N/A")
        color = "green" if verdict == "pass" else "red" if verdict == "fail" else "orange"
        st.metric("Overall Verdict", verdict.upper())

    with col2:
        st.metric("Success Rate", f"{summary.get('success_rate', 0):.1%}")

    with col3:
        st.metric("Total Hypotheses", summary.get("total_hypotheses", "N/A"))

    with col4:
        critical = len(summary.get("critical_failures", []))
        st.metric("Critical Failures", critical)

    st.markdown("---")

    # Key findings
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("🔑 Key Findings")
        findings = summary.get("key_findings", [])
        if findings:
            for finding in findings[:5]:
                st.markdown(f"- {finding}")
        else:
            st.info("No key findings available")

    with col2:
        st.subheader("⚠️ Critical Issues")
        issues = summary.get("critical_issues", [])
        if issues:
            for issue in issues[:5]:
                st.error(issue)
        else:
            st.success("No critical issues identified")


def render_domain_results(results: Dict[str, Any]) -> None:
    """Render domain results page."""
    st.title("🔬 Domain Results")

    domains = results.get("domains", {})

    if not domains:
        st.warning("No domain results available")
        return

    # Domain selector
    selected_domain = st.selectbox("Select Domain", list(domains.keys()))

    if selected_domain:
        data = domains[selected_domain]

        st.subheader(f"Results for {selected_domain}")

        if isinstance(data, dict):
            # Display metrics
            cols = st.columns(3)
            if "hypotheses_tested" in data:
                cols[0].metric("Tested", data["hypotheses_tested"])
            if "hypotheses_supported" in data:
                cols[1].metric("Supported", data["hypotheses_supported"])
            if "success_rate" in data:
                cols[2].metric("Success Rate", f"{data['success_rate']:.1%}")

            # Display as table if pandas available
            if PANDAS_AVAILABLE and "raw_results" in data:
                st.subheader("Raw Results")
                df = pd.DataFrame(data["raw_results"])
                st.dataframe(df)


def render_failure_analysis(results: Dict[str, Any]) -> None:
    """Render failure analysis page."""
    st.title("❌ Failure Analysis")

    failures = results.get("failures", {})

    if not failures:
        st.warning("No failure analysis available")
        return

    summary = failures.get("summary", {})

    # Summary metrics
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Failures", summary.get("total_failures", 0))
    col2.metric("Critical", summary.get("critical_failures", 0))

    avg_effect = summary.get("average_effect_size", 0)
    col3.metric("Avg Effect Size", f"{avg_effect:.3f}")

    st.markdown("---")

    # Category breakdown
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("By Category")
        categories = summary.get("categories", {})
        if categories and PANDAS_AVAILABLE:
            df = pd.DataFrame(list(categories.items()), columns=["Category", "Count"])
            st.bar_chart(df.set_index("Category"))
        elif categories:
            for cat, count in categories.items():
                st.write(f"- {cat}: {count}")

    with col2:
        st.subheader("By Severity")
        severities = summary.get("severities", {})
        if severities and PANDAS_AVAILABLE:
            df = pd.DataFrame(list(severities.items()), columns=["Severity", "Count"])
            st.bar_chart(df.set_index("Severity"))
        elif severities:
            for sev, count in severities.items():
                st.write(f"- {sev}: {count}")

    # Detailed failures
    st.markdown("---")
    st.subheader("Detailed Failures")

    failure_list = failures.get("failures", [])
    if failure_list:
        for f in failure_list:
            with st.expander(f"{'🔴' if f.get('is_critical') else '🟡'} {f.get('hypothesis_id', 'N/A')}"):
                st.write(f"**Domain**: {f.get('domain', 'N/A')}")
                st.write(f"**Category**: {f.get('category', 'N/A')}")
                st.write(f"**Severity**: {f.get('severity', 'N/A')}")
                st.write(f"**Root Cause**: {f.get('root_cause', 'N/A')}")

                if f.get("remediation_options"):
                    st.write("**Remediation Options:**")
                    for opt in f["remediation_options"]:
                        st.write(f"- {opt}")


def render_recommendations(results: Dict[str, Any]) -> None:
    """Render recommendations page."""
    st.title("💡 Recommendations")

    recs = results.get("recommendations", {})

    if not recs:
        st.warning("No recommendations available")
        return

    plan = recs.get("action_plan", {})

    # Verdict banner
    verdict = plan.get("overall_verdict", "N/A")
    if verdict == "READY":
        st.success(f"✅ {plan.get('summary', 'Ready for deployment')}")
    elif verdict == "CONDITIONAL":
        st.warning(f"⚠️ {plan.get('summary', 'Conditional readiness')}")
    else:
        st.error(f"❌ {plan.get('summary', 'Not ready')}")

    st.markdown("---")

    # Recommendations by urgency
    tabs = st.tabs(["Critical", "High Priority", "Medium", "Low"])

    all_recs = recs.get("all_recommendations", recs.get("recommendations", []))

    urgency_map = {
        "critical": 0,
        "high": 1,
        "medium": 2,
        "low": 3,
        "informational": 3,
    }

    for rec in all_recs:
        urgency = rec.get("urgency", "medium")
        tab_idx = urgency_map.get(urgency, 2)

        with tabs[tab_idx]:
            with st.expander(f"{rec.get('recommendation_id', 'N/A')}: {rec.get('title', 'N/A')}"):
                st.write(rec.get("description", ""))
                st.write(f"**Type**: {rec.get('type', 'N/A')}")
                st.write(f"**Effort**: {rec.get('effort_estimate', 'N/A')}")
                st.write(f"**Impact**: {rec.get('impact_score', 0):.0%}")

                if rec.get("action_items"):
                    st.write("**Action Items:**")
                    for item in rec["action_items"]:
                        st.write(f"- {item}")


def render_cross_domain(results: Dict[str, Any]) -> None:
    """Render cross-domain analysis page."""
    st.title("🔗 Cross-Domain Analysis")

    cd = results.get("cross_domain", {})

    if not cd:
        st.warning("No cross-domain analysis available")
        return

    # Correlations
    st.subheader("Domain Correlations")
    correlations = cd.get("correlations", {})

    if correlations and PANDAS_AVAILABLE:
        # Try to create correlation matrix
        corr_data = []
        for key, value in correlations.items():
            if isinstance(value, dict):
                corr = value.get("correlation", 0)
            else:
                corr = value
            corr_data.append({"pair": key, "correlation": corr})

        df = pd.DataFrame(corr_data)
        st.dataframe(df)

    # Tradeoffs
    st.markdown("---")
    st.subheader("Identified Tradeoffs")

    tradeoffs = cd.get("tradeoffs", [])
    if tradeoffs:
        for t in tradeoffs:
            with st.expander(f"{t.get('domain1', '?')} vs {t.get('domain2', '?')}"):
                st.write(f"**Correlation**: {t.get('correlation', 'N/A')}")
                st.write(f"**Type**: {t.get('tradeoff_type', 'N/A')}")
                st.write(f"**Recommendation**: {t.get('recommendation', 'N/A')}")
    else:
        st.info("No tradeoffs identified")


def run_streamlit_server(config: DashboardConfig) -> None:
    """Run Streamlit server."""
    import subprocess

    # Get the path to this file
    script_path = Path(__file__).absolute()

    # Build command
    cmd = [
        sys.executable, "-m", "streamlit", "run",
        str(script_path),
        "--server.port", str(config.port),
        "--server.address", config.host,
        "--",
        "--results-dir", str(config.results_dir),
        "--mode", "streamlit-app",
    ]

    print(f"Starting Streamlit server at http://{config.host}:{config.port}")
    subprocess.run(cmd)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="SHAKTI-CHAIN Experiment Results Dashboard"
    )
    parser.add_argument(
        "--results-dir",
        type=str,
        default="./results",
        help="Directory containing experiment results",
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=["cli", "streamlit", "streamlit-app"],
        default="cli",
        help="Dashboard mode (cli or streamlit)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8501,
        help="Port for Streamlit server",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="localhost",
        help="Host for Streamlit server",
    )

    args = parser.parse_args()

    results_dir = Path(args.results_dir)

    if not results_dir.exists():
        print(f"Warning: Results directory {results_dir} does not exist.")
        results_dir.mkdir(parents=True, exist_ok=True)

    loader = ResultsLoader(results_dir)

    if args.mode == "cli":
        dashboard = CLIDashboard(loader)
        dashboard.run()
    elif args.mode == "streamlit":
        config = DashboardConfig(
            results_dir=results_dir,
            mode=DashboardMode.STREAMLIT,
            port=args.port,
            host=args.host,
        )
        run_streamlit_server(config)
    elif args.mode == "streamlit-app":
        # Running inside Streamlit
        create_streamlit_app(loader)


if __name__ == "__main__":
    main()
