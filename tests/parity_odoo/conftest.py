"""Test fixtures for Odoo parity tests."""
import json
from pathlib import Path
import pytest


@pytest.fixture
def parity_data_dir():
    """Return path to parity test data directory."""
    return Path(__file__).parent.parent / "parity" / "data"


@pytest.fixture
def raw_financial_events(parity_data_dir):
    """Load raw financial events JSON."""
    filepath = parity_data_dir / "raw_financial_events.json"
    with open(filepath, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def ground_truth(parity_data_dir):
    """Load ground truth financial summaries."""
    filepath = parity_data_dir / "financial_summary_ground_truth.json"
    with open(filepath, encoding="utf-8") as f:
        return json.load(f)
