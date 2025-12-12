"""
Entry point for running domain1_mechanism as a module.

Usage:
    python -m experiments.domain1_mechanism run --num-runs 100
    python -m experiments.domain1_mechanism quick-test
"""

from .cli import main

if __name__ == "__main__":
    main()
