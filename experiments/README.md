# SHAKTI-CHAIN Experimental Infrastructure

Comprehensive experimental framework for validating the V2G energy trading platform.

## Directory Structure

```
experiments/
├── config/                      # Configuration files
│   ├── experiment_config.yaml   # Global configuration
│   ├── agent_configs/           # Agent type configurations
│   ├── scenario_configs/        # Market scenario definitions
│   └── baseline_configs/        # Baseline system configurations
├── core/                        # Core experiment components
│   ├── experiment_runner.py     # Main experiment orchestrator
│   ├── data_collector.py        # Metrics collection
│   ├── statistical_analyzer.py  # Hypothesis testing
│   └── result_aggregator.py     # Cross-experiment analysis
├── agents/                      # Agent implementations
│   ├── base_agent.py            # Abstract agent class
│   ├── rational_agent.py        # Utility-maximizing agent
│   ├── bounded_rational_agent.py # Satisficing agent
│   ├── zero_intelligence_agent.py # Random bidding agent
│   ├── adversarial_agent.py     # Strategic manipulator
│   └── behavioral_agent.py      # Prospect theory agent
├── baselines/                   # Baseline mechanisms
│   ├── fixed_tariff.py          # DISCOM fixed rates
│   ├── uniform_auction.py       # Single clearing price
│   ├── continuous_double_auction.py # CDA baseline
│   └── random_bidding.py        # Zero-intelligence baseline
├── scenarios/                   # Market scenarios
│   ├── normal_demand.py
│   ├── peak_demand.py
│   ├── supply_shock.py
│   ├── high_volatility.py
│   └── manipulation_attack.py
├── utils/                       # Utility modules
│   ├── synthetic_data_generator.py
│   ├── india_load_profiles.py
│   ├── metrics_calculator.py
│   └── visualization.py
└── tests/                       # Test infrastructure
    └── test_infrastructure.py
```

## Quick Start

### Installation

```bash
pip install -r requirements.txt
```

### Running an Experiment

```python
import asyncio
from experiments.core import ExperimentRunner, ExperimentConfig

async def run():
    runner = ExperimentRunner()

    config = ExperimentConfig(
        name="my_experiment",
        run_mode="quick",
        scenario="normal_demand",
        agent_distribution="default",
    )

    result = await runner.run_experiment(config)
    print(f"Efficiency: {result.metrics['efficiency']['mean']:.2%}")

asyncio.run(run())
```

### Running Tests

```bash
pytest experiments/tests/ -v
```

## Agent Types

| Agent Type | Description | Key Parameters |
|------------|-------------|----------------|
| Rational | Utility-maximizing with full information | risk_aversion, bid_shading |
| Bounded Rational | Satisficing with limited computation | aspiration_level, max_alternatives |
| Behavioral | Prospect theory biases | loss_aversion, anchoring |
| Zero Intelligence | Random bidding (ZI-C/ZI-U) | budget_constraint |
| Adversarial | Market manipulation | strategy, detection_evasion |

## Scenarios

| Scenario | Description |
|----------|-------------|
| Normal Demand | Typical diurnal patterns |
| Peak Demand | Extreme summer afternoon conditions |
| Supply Shock | Sudden supply reduction |
| High Volatility | Rapid price swings, GARCH effects |
| Manipulation Attack | Coordinated market manipulation |

## Statistical Tests

The framework includes comprehensive statistical testing:

- One-sample and two-sample t-tests
- One-way ANOVA with Tukey HSD
- Chi-square tests
- Kolmogorov-Smirnov tests
- Bootstrap confidence intervals
- Augmented Dickey-Fuller (stationarity)
- TOST equivalence testing
- Multiple comparison corrections (Bonferroni, Benjamini-Hochberg)

## Output Format

Results are saved in:
```
experiments/results/{experiment_id}/
├── config.yaml
├── raw_data/
│   ├── trades.parquet
│   ├── bids.parquet
│   └── market_state.parquet
├── metrics/
│   ├── efficiency_metrics.json
│   └── welfare_metrics.json
├── statistical_tests/
│   └── hypothesis_results.json
└── visualizations/
    ├── price_series.png
    └── welfare_distribution.png
```

## License

Part of the SHAKTI-CHAIN V2G Energy Trading Platform.
