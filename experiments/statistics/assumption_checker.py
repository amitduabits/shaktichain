"""
Statistical Assumption Checker Module.

Provides tests and diagnostics for statistical assumptions:
- Normality tests (Shapiro-Wilk, D'Agostino-Pearson, Anderson-Darling)
- Homoscedasticity tests (Levene, Bartlett, Brown-Forsythe)
- Independence tests
- Outlier detection
- Sphericity test (Mauchly)
- Linearity assessment
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from scipy import stats

logger = logging.getLogger(__name__)


class AssumptionStatus(Enum):
    """Status of assumption check."""
    SATISFIED = "satisfied"
    VIOLATED = "violated"
    MARGINAL = "marginal"
    UNTESTABLE = "untestable"


@dataclass
class AssumptionCheckResult:
    """
    Result of an assumption check.

    Attributes:
        assumption: Name of assumption
        status: Whether assumption is satisfied
        test_name: Name of test used
        statistic: Test statistic
        p_value: P-value
        threshold: Significance threshold used
        interpretation: Human-readable interpretation
        recommendation: What to do if violated
        additional_info: Extra information
    """
    assumption: str
    status: AssumptionStatus
    test_name: str
    statistic: float
    p_value: float
    threshold: float = 0.05
    interpretation: str = ""
    recommendation: str = ""
    additional_info: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "assumption": self.assumption,
            "status": self.status.value,
            "test_name": self.test_name,
            "statistic": self.statistic,
            "p_value": self.p_value,
            "threshold": self.threshold,
            "interpretation": self.interpretation,
            "recommendation": self.recommendation,
            "additional_info": self.additional_info,
        }


@dataclass
class FullAssumptionReport:
    """
    Full report of all assumption checks.

    Attributes:
        checks: List of individual check results
        overall_status: Overall assessment
        summary: Summary statistics
        recommendations: Combined recommendations
    """
    checks: List[AssumptionCheckResult]
    overall_status: AssumptionStatus
    summary: Dict[str, int]
    recommendations: List[str]

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "checks": [c.to_dict() for c in self.checks],
            "overall_status": self.overall_status.value,
            "summary": self.summary,
            "recommendations": self.recommendations,
        }


class AssumptionChecker:
    """
    Comprehensive assumption checker.

    Tests statistical assumptions required for parametric tests.
    """

    def __init__(self, alpha: float = 0.05):
        """
        Initialize checker.

        Args:
            alpha: Significance level for tests
        """
        self.alpha = alpha

    def check_normality_shapiro(
        self,
        data: np.ndarray,
        alpha: Optional[float] = None,
    ) -> AssumptionCheckResult:
        """
        Test normality using Shapiro-Wilk test.

        Best for small to medium samples (n < 5000).

        Args:
            data: Sample data
            alpha: Significance level

        Returns:
            AssumptionCheckResult
        """
        alpha = alpha or self.alpha
        data = np.asarray(data).flatten()
        n = len(data)

        if n < 3:
            return AssumptionCheckResult(
                assumption="Normality",
                status=AssumptionStatus.UNTESTABLE,
                test_name="Shapiro-Wilk",
                statistic=0.0,
                p_value=1.0,
                threshold=alpha,
                interpretation="Sample too small for Shapiro-Wilk test (n < 3)",
                recommendation="Collect more data or use non-parametric methods",
            )

        if n > 5000:
            # Shapiro-Wilk not recommended for large samples
            data_sample = np.random.choice(data, 5000, replace=False)
        else:
            data_sample = data

        stat, p_value = stats.shapiro(data_sample)

        if p_value >= alpha:
            status = AssumptionStatus.SATISFIED
            interpretation = f"Data appears normally distributed (W={stat:.4f}, p={p_value:.4f})"
            recommendation = "Parametric tests appropriate"
        elif p_value >= alpha / 2:
            status = AssumptionStatus.MARGINAL
            interpretation = f"Normality is marginal (W={stat:.4f}, p={p_value:.4f})"
            recommendation = "Consider robust methods or verify with additional tests"
        else:
            status = AssumptionStatus.VIOLATED
            interpretation = f"Data is not normally distributed (W={stat:.4f}, p={p_value:.4f})"
            recommendation = "Use non-parametric alternatives or transform data"

        return AssumptionCheckResult(
            assumption="Normality",
            status=status,
            test_name="Shapiro-Wilk",
            statistic=float(stat),
            p_value=float(p_value),
            threshold=alpha,
            interpretation=interpretation,
            recommendation=recommendation,
            additional_info={
                "n": n,
                "skewness": float(stats.skew(data)),
                "kurtosis": float(stats.kurtosis(data)),
            },
        )

    def check_normality_dagostino(
        self,
        data: np.ndarray,
        alpha: Optional[float] = None,
    ) -> AssumptionCheckResult:
        """
        Test normality using D'Agostino-Pearson omnibus test.

        Better for larger samples (n >= 20).

        Args:
            data: Sample data
            alpha: Significance level

        Returns:
            AssumptionCheckResult
        """
        alpha = alpha or self.alpha
        data = np.asarray(data).flatten()
        n = len(data)

        if n < 20:
            return AssumptionCheckResult(
                assumption="Normality",
                status=AssumptionStatus.UNTESTABLE,
                test_name="D'Agostino-Pearson",
                statistic=0.0,
                p_value=1.0,
                threshold=alpha,
                interpretation="Sample too small for D'Agostino test (n < 20)",
                recommendation="Use Shapiro-Wilk test for smaller samples",
            )

        stat, p_value = stats.normaltest(data)

        if p_value >= alpha:
            status = AssumptionStatus.SATISFIED
            interpretation = f"Data appears normally distributed (K2={stat:.4f}, p={p_value:.4f})"
            recommendation = "Parametric tests appropriate"
        elif p_value >= alpha / 2:
            status = AssumptionStatus.MARGINAL
            interpretation = f"Normality is marginal (K2={stat:.4f}, p={p_value:.4f})"
            recommendation = "Consider robust methods"
        else:
            status = AssumptionStatus.VIOLATED
            interpretation = f"Data is not normally distributed (K2={stat:.4f}, p={p_value:.4f})"
            recommendation = "Use non-parametric alternatives"

        return AssumptionCheckResult(
            assumption="Normality",
            status=status,
            test_name="D'Agostino-Pearson",
            statistic=float(stat),
            p_value=float(p_value),
            threshold=alpha,
            interpretation=interpretation,
            recommendation=recommendation,
            additional_info={
                "n": n,
                "skewness": float(stats.skew(data)),
                "kurtosis": float(stats.kurtosis(data)),
            },
        )

    def check_normality_anderson(
        self,
        data: np.ndarray,
    ) -> AssumptionCheckResult:
        """
        Test normality using Anderson-Darling test.

        Provides critical values for different significance levels.

        Args:
            data: Sample data

        Returns:
            AssumptionCheckResult
        """
        data = np.asarray(data).flatten()
        n = len(data)

        if n < 8:
            return AssumptionCheckResult(
                assumption="Normality",
                status=AssumptionStatus.UNTESTABLE,
                test_name="Anderson-Darling",
                statistic=0.0,
                p_value=1.0,
                interpretation="Sample too small for Anderson-Darling test",
                recommendation="Use Shapiro-Wilk for small samples",
            )

        result = stats.anderson(data, dist='norm')

        # Find appropriate significance level
        # Critical values are for 15%, 10%, 5%, 2.5%, 1%
        sig_levels = [0.15, 0.10, 0.05, 0.025, 0.01]
        stat = result.statistic

        # Determine status based on critical values
        if stat < result.critical_values[2]:  # 5% level
            status = AssumptionStatus.SATISFIED
            p_approx = "> 0.05"
        elif stat < result.critical_values[1]:  # 10% level
            status = AssumptionStatus.MARGINAL
            p_approx = "0.05 - 0.10"
        else:
            status = AssumptionStatus.VIOLATED
            p_approx = "< 0.05"

        interpretation = f"Anderson-Darling A2={stat:.4f}, p {p_approx}"

        if status == AssumptionStatus.SATISFIED:
            recommendation = "Parametric tests appropriate"
        else:
            recommendation = "Consider non-parametric alternatives"

        return AssumptionCheckResult(
            assumption="Normality",
            status=status,
            test_name="Anderson-Darling",
            statistic=float(stat),
            p_value=-1.0,  # AD test doesn't give exact p-value
            threshold=0.05,
            interpretation=interpretation,
            recommendation=recommendation,
            additional_info={
                "n": n,
                "critical_values": dict(zip(sig_levels, result.critical_values.tolist())),
            },
        )

    def check_homoscedasticity_levene(
        self,
        *groups: np.ndarray,
        center: str = 'median',
        alpha: Optional[float] = None,
    ) -> AssumptionCheckResult:
        """
        Test homogeneity of variances using Levene's test.

        Robust to non-normality when using median.

        Args:
            *groups: Variable number of group arrays
            center: 'median' (Brown-Forsythe), 'mean', or 'trimmed'
            alpha: Significance level

        Returns:
            AssumptionCheckResult
        """
        alpha = alpha or self.alpha

        if len(groups) < 2:
            return AssumptionCheckResult(
                assumption="Homoscedasticity",
                status=AssumptionStatus.UNTESTABLE,
                test_name="Levene",
                statistic=0.0,
                p_value=1.0,
                interpretation="Need at least 2 groups for Levene's test",
                recommendation="Cannot test variance equality with one group",
            )

        groups = [np.asarray(g).flatten() for g in groups]

        stat, p_value = stats.levene(*groups, center=center)

        variances = [np.var(g, ddof=1) for g in groups]
        var_ratio = max(variances) / min(variances) if min(variances) > 0 else float('inf')

        if p_value >= alpha:
            status = AssumptionStatus.SATISFIED
            interpretation = f"Variances are homogeneous (W={stat:.4f}, p={p_value:.4f})"
            recommendation = "Equal variance assumption satisfied"
        elif p_value >= alpha / 2:
            status = AssumptionStatus.MARGINAL
            interpretation = f"Variance homogeneity is marginal (W={stat:.4f}, p={p_value:.4f})"
            recommendation = "Consider Welch's t-test or robust methods"
        else:
            status = AssumptionStatus.VIOLATED
            interpretation = f"Variances are not homogeneous (W={stat:.4f}, p={p_value:.4f})"
            recommendation = "Use Welch's correction or non-parametric tests"

        return AssumptionCheckResult(
            assumption="Homoscedasticity",
            status=status,
            test_name=f"Levene ({center})",
            statistic=float(stat),
            p_value=float(p_value),
            threshold=alpha,
            interpretation=interpretation,
            recommendation=recommendation,
            additional_info={
                "group_variances": variances,
                "variance_ratio": float(var_ratio),
                "n_groups": len(groups),
                "group_sizes": [len(g) for g in groups],
            },
        )

    def check_homoscedasticity_bartlett(
        self,
        *groups: np.ndarray,
        alpha: Optional[float] = None,
    ) -> AssumptionCheckResult:
        """
        Test homogeneity of variances using Bartlett's test.

        More powerful but sensitive to non-normality.

        Args:
            *groups: Variable number of group arrays
            alpha: Significance level

        Returns:
            AssumptionCheckResult
        """
        alpha = alpha or self.alpha

        if len(groups) < 2:
            return AssumptionCheckResult(
                assumption="Homoscedasticity",
                status=AssumptionStatus.UNTESTABLE,
                test_name="Bartlett",
                statistic=0.0,
                p_value=1.0,
                interpretation="Need at least 2 groups",
                recommendation="Cannot test with one group",
            )

        groups = [np.asarray(g).flatten() for g in groups]

        stat, p_value = stats.bartlett(*groups)

        if p_value >= alpha:
            status = AssumptionStatus.SATISFIED
            interpretation = f"Variances are homogeneous (chi2={stat:.4f}, p={p_value:.4f})"
            recommendation = "Equal variance assumption satisfied"
        else:
            status = AssumptionStatus.VIOLATED
            interpretation = f"Variances are not homogeneous (chi2={stat:.4f}, p={p_value:.4f})"
            recommendation = "Use Welch's correction (note: Bartlett is sensitive to non-normality)"

        return AssumptionCheckResult(
            assumption="Homoscedasticity",
            status=status,
            test_name="Bartlett",
            statistic=float(stat),
            p_value=float(p_value),
            threshold=alpha,
            interpretation=interpretation,
            recommendation=recommendation,
            additional_info={
                "warning": "Bartlett is sensitive to non-normality; use Levene if data is not normal",
            },
        )

    def check_outliers_zscore(
        self,
        data: np.ndarray,
        threshold: float = 3.0,
    ) -> AssumptionCheckResult:
        """
        Detect outliers using z-score method.

        Args:
            data: Sample data
            threshold: Z-score threshold for outliers

        Returns:
            AssumptionCheckResult
        """
        data = np.asarray(data).flatten()
        n = len(data)

        mean = np.mean(data)
        std = np.std(data, ddof=1)

        if std == 0:
            return AssumptionCheckResult(
                assumption="No Outliers",
                status=AssumptionStatus.SATISFIED,
                test_name="Z-score",
                statistic=0.0,
                p_value=1.0,
                interpretation="No variance in data (all values identical)",
                recommendation="Check data validity",
            )

        z_scores = np.abs((data - mean) / std)
        outliers = np.sum(z_scores > threshold)
        outlier_pct = outliers / n * 100

        if outliers == 0:
            status = AssumptionStatus.SATISFIED
            interpretation = f"No outliers detected (|z| > {threshold})"
            recommendation = "Data quality is acceptable"
        elif outlier_pct < 5:
            status = AssumptionStatus.MARGINAL
            interpretation = f"{outliers} potential outlier(s) ({outlier_pct:.1f}%)"
            recommendation = "Consider robust methods or investigate outliers"
        else:
            status = AssumptionStatus.VIOLATED
            interpretation = f"{outliers} outliers detected ({outlier_pct:.1f}%)"
            recommendation = "Use robust methods or remove outliers with justification"

        outlier_indices = np.where(z_scores > threshold)[0].tolist()
        outlier_values = data[z_scores > threshold].tolist()

        return AssumptionCheckResult(
            assumption="No Outliers",
            status=status,
            test_name="Z-score",
            statistic=float(np.max(z_scores)),
            p_value=-1.0,  # Not a p-value based test
            threshold=threshold,
            interpretation=interpretation,
            recommendation=recommendation,
            additional_info={
                "n_outliers": outliers,
                "outlier_pct": float(outlier_pct),
                "outlier_indices": outlier_indices[:10],  # Limit to first 10
                "outlier_values": outlier_values[:10],
                "max_zscore": float(np.max(z_scores)),
            },
        )

    def check_outliers_iqr(
        self,
        data: np.ndarray,
        k: float = 1.5,
    ) -> AssumptionCheckResult:
        """
        Detect outliers using IQR method (Tukey's fences).

        More robust to non-normality than z-score.

        Args:
            data: Sample data
            k: IQR multiplier (1.5 for outliers, 3 for extreme)

        Returns:
            AssumptionCheckResult
        """
        data = np.asarray(data).flatten()
        n = len(data)

        q1 = np.percentile(data, 25)
        q3 = np.percentile(data, 75)
        iqr = q3 - q1

        lower_fence = q1 - k * iqr
        upper_fence = q3 + k * iqr

        outliers_low = np.sum(data < lower_fence)
        outliers_high = np.sum(data > upper_fence)
        total_outliers = outliers_low + outliers_high
        outlier_pct = total_outliers / n * 100

        if total_outliers == 0:
            status = AssumptionStatus.SATISFIED
            interpretation = f"No outliers detected (IQR method, k={k})"
            recommendation = "Data quality is acceptable"
        elif outlier_pct < 5:
            status = AssumptionStatus.MARGINAL
            interpretation = f"{total_outliers} potential outlier(s) ({outlier_pct:.1f}%)"
            recommendation = "Consider robust methods"
        else:
            status = AssumptionStatus.VIOLATED
            interpretation = f"{total_outliers} outliers detected ({outlier_pct:.1f}%)"
            recommendation = "Use robust methods or transform data"

        return AssumptionCheckResult(
            assumption="No Outliers",
            status=status,
            test_name="IQR (Tukey)",
            statistic=float(iqr),
            p_value=-1.0,
            threshold=k,
            interpretation=interpretation,
            recommendation=recommendation,
            additional_info={
                "q1": float(q1),
                "q3": float(q3),
                "iqr": float(iqr),
                "lower_fence": float(lower_fence),
                "upper_fence": float(upper_fence),
                "n_outliers_low": int(outliers_low),
                "n_outliers_high": int(outliers_high),
            },
        )

    def check_independence_runs(
        self,
        data: np.ndarray,
        alpha: Optional[float] = None,
    ) -> AssumptionCheckResult:
        """
        Test independence using Wald-Wolfowitz runs test.

        Tests for randomness in sequence.

        Args:
            data: Sample data (order matters)
            alpha: Significance level

        Returns:
            AssumptionCheckResult
        """
        alpha = alpha or self.alpha
        data = np.asarray(data).flatten()
        n = len(data)

        if n < 10:
            return AssumptionCheckResult(
                assumption="Independence",
                status=AssumptionStatus.UNTESTABLE,
                test_name="Runs Test",
                statistic=0.0,
                p_value=1.0,
                interpretation="Sample too small for runs test (n < 10)",
                recommendation="Collect more data",
            )

        # Convert to binary based on median
        median = np.median(data)
        binary = (data > median).astype(int)

        # Count runs
        runs = 1
        for i in range(1, n):
            if binary[i] != binary[i-1]:
                runs += 1

        # Expected runs and variance
        n1 = np.sum(binary)
        n2 = n - n1

        if n1 == 0 or n2 == 0:
            return AssumptionCheckResult(
                assumption="Independence",
                status=AssumptionStatus.UNTESTABLE,
                test_name="Runs Test",
                statistic=float(runs),
                p_value=1.0,
                interpretation="All values on one side of median",
                recommendation="Check data validity",
            )

        expected_runs = (2 * n1 * n2 / n) + 1
        var_runs = (2 * n1 * n2 * (2 * n1 * n2 - n)) / (n**2 * (n - 1))

        if var_runs > 0:
            z = (runs - expected_runs) / np.sqrt(var_runs)
            p_value = 2 * (1 - stats.norm.cdf(abs(z)))
        else:
            z = 0
            p_value = 1.0

        if p_value >= alpha:
            status = AssumptionStatus.SATISFIED
            interpretation = f"Data appears independent (R={runs}, z={z:.2f}, p={p_value:.4f})"
            recommendation = "Independence assumption satisfied"
        else:
            status = AssumptionStatus.VIOLATED
            interpretation = f"Data may not be independent (R={runs}, z={z:.2f}, p={p_value:.4f})"
            recommendation = "Consider time series methods or adjust for autocorrelation"

        return AssumptionCheckResult(
            assumption="Independence",
            status=status,
            test_name="Runs Test",
            statistic=float(z),
            p_value=float(p_value),
            threshold=alpha,
            interpretation=interpretation,
            recommendation=recommendation,
            additional_info={
                "n_runs": runs,
                "expected_runs": float(expected_runs),
                "n_above_median": int(n1),
                "n_below_median": int(n2),
            },
        )

    def check_independence_durbin_watson(
        self,
        residuals: np.ndarray,
    ) -> AssumptionCheckResult:
        """
        Test independence using Durbin-Watson statistic.

        Tests for autocorrelation in residuals.

        Args:
            residuals: Residual values from regression

        Returns:
            AssumptionCheckResult
        """
        residuals = np.asarray(residuals).flatten()
        n = len(residuals)

        if n < 5:
            return AssumptionCheckResult(
                assumption="Independence (No Autocorrelation)",
                status=AssumptionStatus.UNTESTABLE,
                test_name="Durbin-Watson",
                statistic=0.0,
                p_value=-1.0,
                interpretation="Sample too small",
                recommendation="Collect more data",
            )

        # Calculate Durbin-Watson statistic
        diff = np.diff(residuals)
        dw = np.sum(diff**2) / np.sum(residuals**2)

        # DW ranges from 0 to 4
        # DW near 2 = no autocorrelation
        # DW < 2 = positive autocorrelation
        # DW > 2 = negative autocorrelation

        if 1.5 <= dw <= 2.5:
            status = AssumptionStatus.SATISFIED
            interpretation = f"No significant autocorrelation (DW={dw:.3f})"
            recommendation = "Independence assumption satisfied"
        elif 1.0 <= dw < 1.5 or 2.5 < dw <= 3.0:
            status = AssumptionStatus.MARGINAL
            interpretation = f"Possible autocorrelation (DW={dw:.3f})"
            recommendation = "Consider autocorrelation-robust standard errors"
        else:
            status = AssumptionStatus.VIOLATED
            if dw < 1.0:
                interpretation = f"Positive autocorrelation detected (DW={dw:.3f})"
            else:
                interpretation = f"Negative autocorrelation detected (DW={dw:.3f})"
            recommendation = "Use time series methods or HAC standard errors"

        return AssumptionCheckResult(
            assumption="Independence (No Autocorrelation)",
            status=status,
            test_name="Durbin-Watson",
            statistic=float(dw),
            p_value=-1.0,  # DW doesn't have simple p-value
            interpretation=interpretation,
            recommendation=recommendation,
            additional_info={
                "interpretation_guide": {
                    "0-1.5": "Positive autocorrelation",
                    "1.5-2.5": "No autocorrelation",
                    "2.5-4": "Negative autocorrelation",
                },
            },
        )

    def check_linearity(
        self,
        x: np.ndarray,
        y: np.ndarray,
        alpha: Optional[float] = None,
    ) -> AssumptionCheckResult:
        """
        Check linearity assumption using RESET test.

        Tests if non-linear terms would improve fit.

        Args:
            x: Predictor variable
            y: Response variable
            alpha: Significance level

        Returns:
            AssumptionCheckResult
        """
        alpha = alpha or self.alpha
        x = np.asarray(x).flatten()
        y = np.asarray(y).flatten()
        n = len(x)

        if n < 10:
            return AssumptionCheckResult(
                assumption="Linearity",
                status=AssumptionStatus.UNTESTABLE,
                test_name="RESET-like",
                statistic=0.0,
                p_value=1.0,
                interpretation="Sample too small",
                recommendation="Collect more data",
            )

        # Fit linear model
        slope, intercept, r_value, p_value_linear, std_err = stats.linregress(x, y)
        y_pred = intercept + slope * x
        residuals = y - y_pred

        # Fit model with squared predictor
        X = np.column_stack([np.ones(n), x, x**2])
        try:
            coeffs, residuals_quad, _, _ = np.linalg.lstsq(X, y, rcond=None)
            y_pred_quad = X @ coeffs
            ss_linear = np.sum(residuals**2)
            ss_quad = np.sum((y - y_pred_quad)**2)

            # F-test for improvement
            df1 = 1  # One additional parameter
            df2 = n - 3
            f_stat = ((ss_linear - ss_quad) / df1) / (ss_quad / df2) if ss_quad > 0 else 0
            p_value = 1 - stats.f.cdf(f_stat, df1, df2) if f_stat > 0 else 1.0
        except:
            f_stat = 0
            p_value = 1.0

        if p_value >= alpha:
            status = AssumptionStatus.SATISFIED
            interpretation = f"Linearity assumption satisfied (F={f_stat:.3f}, p={p_value:.4f})"
            recommendation = "Linear model is appropriate"
        else:
            status = AssumptionStatus.VIOLATED
            interpretation = f"Non-linear relationship detected (F={f_stat:.3f}, p={p_value:.4f})"
            recommendation = "Consider polynomial terms or non-linear transformation"

        return AssumptionCheckResult(
            assumption="Linearity",
            status=status,
            test_name="RESET-like",
            statistic=float(f_stat),
            p_value=float(p_value),
            threshold=alpha,
            interpretation=interpretation,
            recommendation=recommendation,
            additional_info={
                "r_squared_linear": float(r_value**2),
                "correlation": float(r_value),
            },
        )

    def check_all_assumptions(
        self,
        data: np.ndarray,
        groups: Optional[List[np.ndarray]] = None,
        test_type: str = "t_test",
    ) -> FullAssumptionReport:
        """
        Run comprehensive assumption checks for a given test type.

        Args:
            data: Primary data array
            groups: Optional list of group arrays
            test_type: Type of test ('t_test', 'anova', 'regression')

        Returns:
            FullAssumptionReport
        """
        checks = []
        recommendations = []

        # Normality
        normality = self.check_normality_shapiro(data)
        checks.append(normality)
        if normality.status == AssumptionStatus.VIOLATED:
            recommendations.append(normality.recommendation)

        # Outliers
        outliers = self.check_outliers_iqr(data)
        checks.append(outliers)
        if outliers.status == AssumptionStatus.VIOLATED:
            recommendations.append(outliers.recommendation)

        # Group-specific checks
        if groups is not None and len(groups) >= 2:
            # Homoscedasticity
            homoscedasticity = self.check_homoscedasticity_levene(*groups)
            checks.append(homoscedasticity)
            if homoscedasticity.status == AssumptionStatus.VIOLATED:
                recommendations.append(homoscedasticity.recommendation)

            # Check normality for each group
            for i, group in enumerate(groups):
                group_normality = self.check_normality_shapiro(group)
                group_normality.assumption = f"Normality (Group {i+1})"
                checks.append(group_normality)

        # Independence (if data appears sequential)
        independence = self.check_independence_runs(data)
        checks.append(independence)
        if independence.status == AssumptionStatus.VIOLATED:
            recommendations.append(independence.recommendation)

        # Determine overall status
        statuses = [c.status for c in checks]
        if AssumptionStatus.VIOLATED in statuses:
            overall_status = AssumptionStatus.VIOLATED
        elif AssumptionStatus.MARGINAL in statuses:
            overall_status = AssumptionStatus.MARGINAL
        else:
            overall_status = AssumptionStatus.SATISFIED

        # Summary
        summary = {
            "satisfied": sum(1 for s in statuses if s == AssumptionStatus.SATISFIED),
            "marginal": sum(1 for s in statuses if s == AssumptionStatus.MARGINAL),
            "violated": sum(1 for s in statuses if s == AssumptionStatus.VIOLATED),
            "untestable": sum(1 for s in statuses if s == AssumptionStatus.UNTESTABLE),
            "total": len(checks),
        }

        return FullAssumptionReport(
            checks=checks,
            overall_status=overall_status,
            summary=summary,
            recommendations=list(set(recommendations)),
        )


def check_parametric_assumptions(
    group1: np.ndarray,
    group2: Optional[np.ndarray] = None,
    alpha: float = 0.05,
) -> FullAssumptionReport:
    """
    Convenience function to check assumptions for parametric tests.

    Args:
        group1: First group data
        group2: Second group data (optional)
        alpha: Significance level

    Returns:
        FullAssumptionReport
    """
    checker = AssumptionChecker(alpha=alpha)

    if group2 is not None:
        all_data = np.concatenate([group1, group2])
        groups = [np.asarray(group1), np.asarray(group2)]
    else:
        all_data = np.asarray(group1)
        groups = None

    return checker.check_all_assumptions(all_data, groups=groups)
