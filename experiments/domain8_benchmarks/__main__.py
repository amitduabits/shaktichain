"""
Entry point for domain8_benchmarks module.

Usage: python -m experiments.domain8_benchmarks [command]
"""

import sys
from .cli import main

if __name__ == "__main__":
    sys.exit(main())
