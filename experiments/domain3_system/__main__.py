"""
Entry point for running domain3_system as a module.

Usage:
    python -m experiments.domain3_system run --num-runs 10
    python -m experiments.domain3_system quick-test
    python -m experiments.domain3_system hypotheses
    python -m experiments.domain3_system benchmark --load-levels 100,500,1000
"""

from .cli import main

if __name__ == "__main__":
    main()
