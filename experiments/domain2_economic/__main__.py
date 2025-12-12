"""
Entry point for running domain2_economic as a module.

Usage:
    python -m experiments.domain2_economic run --num-runs 100
    python -m experiments.domain2_economic quick-test
    python -m experiments.domain2_economic hypotheses
"""

from .cli import main

if __name__ == "__main__":
    main()
