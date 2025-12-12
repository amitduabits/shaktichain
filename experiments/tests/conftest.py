"""
Pytest configuration and shared fixtures for SHAKTI-CHAIN tests.
"""

import pytest
import sys
from pathlib import Path

# Add experiments module to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
