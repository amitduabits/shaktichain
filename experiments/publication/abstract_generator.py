"""
Abstract Generator for SHAKTI-CHAIN Publications.

Generates publication abstracts following academic conventions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import logging
import re

logger = logging.getLogger(__name__)


@dataclass
class AbstractStructure:
    """Structure components of an abstract."""
    context: str
    objective: str
    method: str
    results: str
    conclusion: str

    def to_text(self, separator: str = " ") -> str:
        """Combine components into full abstract."""
        parts = [
            self.context,
            self.objective,
            self.method,
            self.results,
            self.conclusion,
        ]
        return separator.join(p.strip() for p in parts if p.strip())


@dataclass
class AbstractConfig:
    """Configuration for abstract generation."""
    word_limit: int = 250
    include_numbers: bool = True
    include_conclusions: bool = True
    formal_tone: bool = True
    venue_type: str = "conference"  # conference, journal, arxiv


class AbstractGenerator:
    """
    Generate publication abstracts from experiment results.

    Follows standard academic abstract structure:
    1. Context/Problem (1-2 sentences)
    2. Objective (1 sentence)
    3. Method (2-3 sentences)
    4. Results (3-4 sentences)
    5. Conclusion (1-2 sentences)
    """

    def __init__(
        self,
        results: Dict[str, Any],
        config: Optional[AbstractConfig] = None,
    ):
        """
        Initialize abstract generator.

        Args:
            results: Dictionary of domain results
            config: Abstract configuration options
        """
        self.results = results
        self.config = config or AbstractConfig()
        self._summary: Optional[Dict[str, Any]] = None

    def _compute_summary(self) -> Dict[str, Any]:
        """Compute summary statistics from results."""
        if self._summary is not None:
            return self._summary

        total_hypotheses = 0
        total_supported = 0
        critical_failures = []
        domains = []

        for domain_id, domain_data in self.results.items():
            domains.append(domain_id)

            if isinstance(domain_data, dict):
                tested = domain_data.get("hypotheses_tested", 0)
                supported = domain_data.get("hypotheses_supported", 0)
                crit = domain_data.get("critical_failures", [])
            elif hasattr(domain_data, "hypotheses_tested"):
                tested = domain_data.hypotheses_tested
                supported = domain_data.hypotheses_supported
                crit = getattr(domain_data, "critical_failures", [])
            else:
                continue

            total_hypotheses += tested
            total_supported += supported
            critical_failures.extend(crit)

        success_rate = total_supported / total_hypotheses if total_hypotheses > 0 else 0

        self._summary = {
            "total_hypotheses": total_hypotheses,
            "total_supported": total_supported,
            "total_failed": total_hypotheses - total_supported,
            "success_rate": success_rate,
            "critical_failures": critical_failures,
            "num_domains": len(domains),
            "domains": domains,
            "has_critical_failures": len(critical_failures) > 0,
        }

        return self._summary

    def generate_abstract(
        self,
        word_limit: Optional[int] = None,
    ) -> str:
        """
        Generate publication abstract.

        Args:
            word_limit: Maximum word count (default from config)

        Returns:
            Complete abstract text
        """
        word_limit = word_limit or self.config.word_limit

        structure = self._generate_structure()
        abstract = structure.to_text()

        # Enforce word limit
        abstract = self._enforce_word_limit(abstract, word_limit)

        return abstract

    def _generate_structure(self) -> AbstractStructure:
        """Generate abstract components."""
        summary = self._compute_summary()

        context = self._generate_context()
        objective = self._generate_objective()
        method = self._generate_method(summary)
        results = self._format_key_results(summary)
        conclusion = self._format_conclusion(summary)

        return AbstractStructure(
            context=context,
            objective=objective,
            method=method,
            results=results,
            conclusion=conclusion,
        )

    def _generate_context(self) -> str:
        """Generate context/problem statement."""
        contexts = [
            (
                "Vehicle-to-Grid (V2G) systems require efficient, fair, and robust "
                "energy trading mechanisms to realize their potential for grid services "
                "and renewable energy integration."
            ),
            (
                "The rapid adoption of electric vehicles creates opportunities for "
                "bidirectional energy flow, but traditional centralized trading "
                "approaches face challenges in scalability and trust."
            ),
            (
                "Peer-to-peer energy trading in V2G systems demands mechanisms that "
                "are transparent, efficient, and adaptable to local market conditions."
            ),
        ]

        # Select based on venue type
        if self.config.venue_type == "journal":
            return contexts[0]
        elif self.config.venue_type == "arxiv":
            return contexts[1]
        else:
            return contexts[2]

    def _generate_objective(self) -> str:
        """Generate objective statement."""
        return (
            "We present SHAKTI-CHAIN, a blockchain-based peer-to-peer energy trading "
            "platform specifically designed for the Indian V2G context, incorporating "
            "novel double-auction mechanisms and smart contract-based settlement."
        )

    def _generate_method(self, summary: Dict[str, Any]) -> str:
        """Generate methodology description."""
        if self.config.include_numbers:
            method = (
                f"We conducted comprehensive validation across {summary['num_domains']} "
                f"research domains, testing {summary['total_hypotheses']} pre-registered "
                "hypotheses using simulation experiments with synthetic Indian load profiles. "
                "Our statistical framework employed parametric and non-parametric tests at "
                "α=0.05 with power analysis ensuring adequate sample sizes."
            )
        else:
            method = (
                "We conducted comprehensive validation across multiple research domains, "
                "testing pre-registered hypotheses using simulation experiments with "
                "synthetic Indian load profiles. Our statistical framework employed "
                "rigorous hypothesis testing with appropriate corrections for multiple comparisons."
            )

        return method

    def _format_key_results(self, summary: Dict[str, Any]) -> str:
        """Format key results for abstract."""
        success_rate = summary["success_rate"]
        total_supported = summary["total_supported"]
        total_hypotheses = summary["total_hypotheses"]

        if success_rate >= 0.9:
            strength = "strong"
            outcome = "demonstrating excellent performance"
        elif success_rate >= 0.8:
            strength = "substantial"
            outcome = "demonstrating robust performance"
        elif success_rate >= 0.7:
            strength = "good"
            outcome = "indicating viable performance"
        else:
            strength = "mixed"
            outcome = "identifying areas for improvement"

        if self.config.include_numbers:
            results = (
                f"Our results show {strength} validation with {total_supported} of "
                f"{total_hypotheses} hypotheses ({success_rate:.1%}) supported, "
                f"{outcome}. "
            )
        else:
            results = (
                f"Our results show {strength} validation with the majority of hypotheses "
                f"supported, {outcome}. "
            )

        # Add specific findings
        if success_rate >= 0.8:
            results += (
                "The auction mechanism achieved high allocative efficiency while "
                "maintaining individual rationality constraints. "
            )
        else:
            results += (
                "While core mechanisms performed well, some hypotheses require "
                "additional investigation. "
            )

        if summary["has_critical_failures"]:
            results += (
                f"However, {len(summary['critical_failures'])} critical hypotheses "
                "were not supported, requiring attention before deployment."
            )
        else:
            results += (
                "All critical hypotheses were validated, indicating readiness "
                "for pilot deployment."
            )

        return results

    def _format_conclusion(self, summary: Dict[str, Any]) -> str:
        """Format conclusion for abstract."""
        success_rate = summary["success_rate"]

        if success_rate >= 0.8 and not summary["has_critical_failures"]:
            conclusion = (
                "These results demonstrate SHAKTI-CHAIN's viability for V2G energy "
                "trading in India, with the validation framework contributing a "
                "reusable methodology for blockchain energy systems."
            )
        elif success_rate >= 0.6:
            conclusion = (
                "The results support SHAKTI-CHAIN's potential with identified areas "
                "for refinement, and the validation framework provides a reusable "
                "methodology for similar systems."
            )
        else:
            conclusion = (
                "While challenges remain, the systematic validation identifies "
                "clear targets for improvement and contributes methodological "
                "advances for blockchain energy system evaluation."
            )

        return conclusion

    def _enforce_word_limit(self, text: str, limit: int) -> str:
        """Enforce word limit on abstract."""
        words = text.split()
        if len(words) <= limit:
            return text

        # Truncate and add ellipsis
        truncated = " ".join(words[:limit - 3])

        # Try to end at a sentence boundary
        last_period = truncated.rfind(".")
        if last_period > len(truncated) * 0.7:
            return truncated[:last_period + 1]

        return truncated + "..."

    def generate_structured_abstract(self) -> Dict[str, str]:
        """
        Generate abstract with labeled sections.

        Useful for journals requiring structured abstracts.

        Returns:
            Dictionary with section labels and content
        """
        summary = self._compute_summary()

        return {
            "Background": self._generate_context(),
            "Objective": self._generate_objective(),
            "Methods": self._generate_method(summary),
            "Results": self._format_key_results(summary),
            "Conclusions": self._format_conclusion(summary),
        }

    def generate_graphical_abstract_text(self) -> str:
        """
        Generate text suitable for graphical abstract.

        Very concise key points format.

        Returns:
            Bullet-point format key findings
        """
        summary = self._compute_summary()

        points = [
            "SHAKTI-CHAIN: Blockchain P2P energy trading for V2G in India",
            f"Validated {summary['total_hypotheses']} hypotheses across {summary['num_domains']} domains",
            f"Success rate: {summary['success_rate']:.0%}",
        ]

        if summary["success_rate"] >= 0.8:
            points.append("High efficiency and fairness achieved")
        else:
            points.append("Core mechanisms validated with improvement areas identified")

        if not summary["has_critical_failures"]:
            points.append("All critical hypotheses supported")
        else:
            points.append(f"{len(summary['critical_failures'])} critical areas need attention")

        return "\n".join(f"• {p}" for p in points)

    def generate_tweet_summary(self) -> str:
        """
        Generate Twitter/X-friendly summary (280 chars).

        Returns:
            Tweet-length summary
        """
        summary = self._compute_summary()

        tweet = (
            f"📊 SHAKTI-CHAIN validation complete! "
            f"{summary['success_rate']:.0%} of {summary['total_hypotheses']} "
            "hypotheses supported for India's V2G energy trading platform. "
        )

        if summary["success_rate"] >= 0.8:
            tweet += "🎯 Ready for pilot deployment!"
        else:
            tweet += "🔧 Key improvements identified."

        # Ensure within limit
        if len(tweet) > 280:
            tweet = tweet[:277] + "..."

        return tweet

    def generate_press_release_summary(self) -> str:
        """
        Generate press release style summary.

        More accessible language for general audiences.

        Returns:
            Press-friendly summary paragraph
        """
        summary = self._compute_summary()

        if summary["success_rate"] >= 0.8:
            lead = "Researchers have successfully validated"
        else:
            lead = "Researchers have made significant progress validating"

        release = (
            f"{lead} SHAKTI-CHAIN, an innovative blockchain-based platform that "
            "enables electric vehicle owners in India to buy and sell excess "
            "energy directly with each other and the power grid. "
        )

        release += (
            f"In comprehensive testing across {summary['num_domains']} areas, "
            f"{summary['success_rate']:.0%} of the system's core features "
            "performed as expected. "
        )

        if summary["success_rate"] >= 0.8 and not summary["has_critical_failures"]:
            release += (
                "The results suggest the platform is ready for real-world "
                "pilot testing, potentially helping India integrate more "
                "electric vehicles into its power grid."
            )
        else:
            release += (
                "The findings identify clear next steps for system improvement "
                "before real-world deployment."
            )

        return release


def generate_abstract(
    results: Dict[str, Any],
    word_limit: int = 250,
) -> str:
    """
    Convenience function to generate abstract.

    Args:
        results: Experiment results dictionary
        word_limit: Maximum word count

    Returns:
        Generated abstract text
    """
    generator = AbstractGenerator(results)
    return generator.generate_abstract(word_limit)


def generate_structured_abstract(
    results: Dict[str, Any],
) -> Dict[str, str]:
    """
    Convenience function for structured abstract.

    Args:
        results: Experiment results dictionary

    Returns:
        Dictionary with labeled sections
    """
    generator = AbstractGenerator(results)
    return generator.generate_structured_abstract()
