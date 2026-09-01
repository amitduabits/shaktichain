"""Smoke import of experiment CLIs. Does not run 2,000-agent studies."""

from __future__ import annotations


def test_domain1_cli_module_imports():
    import experiments.domain1_mechanism.cli as cli

    assert cli is not None
