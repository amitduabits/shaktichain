"""
SHAKTI-CHAIN Statistical Analysis Suite.

Comprehensive statistical testing framework for experiment validation.

Modules:
    - hypothesis_tester: Statistical hypothesis tests
    - power_analyzer: Power analysis and sample size determination
    - effect_size_calculator: Effect size calculations
    - assumption_checker: Statistical assumption verification
    - multiple_comparison: Multiple comparison corrections
    - bootstrap: Bootstrap confidence intervals and tests
    - bayesian_tests: Bayesian statistical alternatives
    - report_generator: Statistical report generation

Example Usage:
    >>> from experiments.statistics import HypothesisTester, EffectSizeCalculator
    >>> tester = HypothesisTester(alpha=0.05)
    >>> result = tester.one_sample_t_test(data, popmean=1.0)
    >>> print(result.interpretation)
"""

from .hypothesis_tester import (
    HypothesisTester,
    HypothesisTestResult,
    TestType,
    Alternative,
    run_hypothesis_test,
)

from .power_analyzer import (
    PowerAnalyzer,
    PowerAnalysisResult,
    PowerAnalysisType,
    calculate_sample_size,
    calculate_power,
)

from .effect_size_calculator import (
    EffectSizeCalculator,
    EffectSizeResult,
    EffectSizeType,
    EffectMagnitude,
    calculate_effect_size,
)

from .assumption_checker import (
    AssumptionChecker,
    AssumptionCheckResult,
    FullAssumptionReport,
    AssumptionStatus,
    check_parametric_assumptions,
)

from .multiple_comparison import (
    MultipleComparisonCorrector,
    CorrectionResult,
    CorrectionMethod,
    PostHocTests,
    correct_p_values,
    get_significant_tests,
)

from .bootstrap import (
    Bootstrap,
    BootstrapResult,
    BootstrapTestResult,
    BootstrapCIMethod,
    PermutationTest,
    bootstrap_ci,
    permutation_test,
)

from .bayesian_tests import (
    BayesianTester,
    BayesianTestResult,
    BayesFactorInterpretation,
    BayesFactorCalculator,
    RopeAnalysis,
    interpret_bayes_factor,
    bayesian_t_test,
    bayes_factor,
)

from .report_generator import (
    StatisticalReportGenerator,
    StatisticalReport,
    generate_report,
)

__all__ = [
    # Hypothesis Testing
    "HypothesisTester",
    "HypothesisTestResult",
    "TestType",
    "Alternative",
    "run_hypothesis_test",

    # Power Analysis
    "PowerAnalyzer",
    "PowerAnalysisResult",
    "PowerAnalysisType",
    "calculate_sample_size",
    "calculate_power",

    # Effect Sizes
    "EffectSizeCalculator",
    "EffectSizeResult",
    "EffectSizeType",
    "EffectMagnitude",
    "calculate_effect_size",

    # Assumption Checking
    "AssumptionChecker",
    "AssumptionCheckResult",
    "FullAssumptionReport",
    "AssumptionStatus",
    "check_parametric_assumptions",

    # Multiple Comparisons
    "MultipleComparisonCorrector",
    "CorrectionResult",
    "CorrectionMethod",
    "PostHocTests",
    "correct_p_values",
    "get_significant_tests",

    # Bootstrap Methods
    "Bootstrap",
    "BootstrapResult",
    "BootstrapTestResult",
    "BootstrapCIMethod",
    "PermutationTest",
    "bootstrap_ci",
    "permutation_test",

    # Bayesian Tests
    "BayesianTester",
    "BayesianTestResult",
    "BayesFactorInterpretation",
    "BayesFactorCalculator",
    "RopeAnalysis",
    "interpret_bayes_factor",
    "bayesian_t_test",
    "bayes_factor",

    # Report Generation
    "StatisticalReportGenerator",
    "StatisticalReport",
    "generate_report",
]

__version__ = "1.0.0"


def quick_analysis(
    data,
    null_value: float = 0,
    alpha: float = 0.05,
    include_bayesian: bool = True,
    include_bootstrap: bool = True,
):
    """
    Perform quick comprehensive statistical analysis.

    Args:
        data: Sample data array
        null_value: Null hypothesis value
        alpha: Significance level
        include_bayesian: Include Bayesian analysis
        include_bootstrap: Include bootstrap analysis

    Returns:
        Dictionary of results
    """
    import numpy as np
    data = np.asarray(data).flatten()

    results = {}

    # Frequentist test
    tester = HypothesisTester(alpha=alpha)
    results['frequentist'] = tester.one_sample_t_test(data, popmean=null_value)

    # Effect size
    calc = EffectSizeCalculator()
    results['effect_size'] = calc.cohens_d_paired(
        np.zeros(len(data)) + null_value, data
    )

    # Assumption checks
    checker = AssumptionChecker(alpha=alpha)
    results['normality'] = checker.check_normality_shapiro(data)
    results['outliers'] = checker.check_outliers_iqr(data)

    # Power
    analyzer = PowerAnalyzer(alpha=alpha)
    d = results['effect_size'].value
    results['power'] = analyzer.power_t_test_one_sample(
        len(data), abs(d) if d else 0.5
    )

    # Bayesian
    if include_bayesian:
        bayes = BayesianTester()
        results['bayesian'] = bayes.one_sample_t_test(data, null_value)

    # Bootstrap
    if include_bootstrap:
        bs = Bootstrap(n_bootstrap=5000)
        results['bootstrap_ci'] = bs.ci_mean(data)

    return results


def compare_groups(
    group1,
    group2,
    alpha: float = 0.05,
    paired: bool = False,
):
    """
    Compare two groups with comprehensive analysis.

    Args:
        group1: First group data
        group2: Second group data
        alpha: Significance level
        paired: Whether samples are paired

    Returns:
        Dictionary of results
    """
    import numpy as np
    group1 = np.asarray(group1).flatten()
    group2 = np.asarray(group2).flatten()

    results = {}

    # Assumption checks
    checker = AssumptionChecker(alpha=alpha)
    results['normality_g1'] = checker.check_normality_shapiro(group1)
    results['normality_g2'] = checker.check_normality_shapiro(group2)
    results['homoscedasticity'] = checker.check_homoscedasticity_levene(group1, group2)

    # Choose appropriate test based on assumptions
    tester = HypothesisTester(alpha=alpha)

    if paired:
        results['parametric'] = tester.paired_t_test(group1, group2)
        results['non_parametric'] = tester.wilcoxon_signed_rank_test(group1, group2)
    else:
        # Use Welch's t-test if variances unequal
        equal_var = results['homoscedasticity'].status == AssumptionStatus.SATISFIED
        results['parametric'] = tester.two_sample_t_test(group1, group2, equal_var=equal_var)
        results['non_parametric'] = tester.mann_whitney_u_test(group1, group2)

    # Effect sizes
    calc = EffectSizeCalculator()
    if paired:
        results['effect_size'] = calc.cohens_d_paired(group1, group2)
    else:
        results['effect_size'] = calc.cohens_d(group1, group2)
        results['cliffs_delta'] = calc.cliffs_delta(group1, group2)

    # Bayesian
    bayes = BayesianTester()
    if paired:
        results['bayesian'] = bayes.paired_t_test(group1, group2)
    else:
        results['bayesian'] = bayes.two_sample_t_test(group1, group2)

    # Bootstrap CI for mean difference
    bs = Bootstrap(n_bootstrap=5000)
    if paired:
        results['bootstrap'] = bs.ci_mean(group2 - group1)
    else:
        results['bootstrap'] = bs.ci_mean_difference(group1, group2)

    return results
