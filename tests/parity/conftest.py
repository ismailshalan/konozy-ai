"""Test fixtures for parity tests."""
import json
from pathlib import Path
import pytest


@pytest.fixture
def fixtures_dir():
    """Return path to parity test data directory."""
    return Path(__file__).parent / "data"


@pytest.fixture
def raw_financial_events(fixtures_dir):
    """Load raw financial events JSON."""
    filepath = fixtures_dir / "raw_financial_events.json"
    with open(filepath, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def ground_truth(fixtures_dir):
    """Load ground truth financial summaries."""
    filepath = fixtures_dir / "financial_summary_ground_truth.json"
    with open(filepath, encoding="utf-8") as f:
        return json.load(f)
