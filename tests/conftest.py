"""Test fixtures and configuration."""

import pytest
import json
import tempfile
import os
import sys

# Add parent directory to path for importing main
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def mock_data():
    """Provide mock data structure for tests."""
    return {
        "nav_lengths": {
            "1abc": 150,
            "2xyz": 200,
            "3def": 300,
        },
        "valid_pdb_ids": [
            "1abc",
            "2xyz",
            "3def",
            "4ghi",
            "5jkl",
        ],
    }


@pytest.fixture
def mock_data_file(mock_data):
    """Create a temporary mock data file."""
    fd, temp_path = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w") as f:
        json.dump(mock_data, f)

    yield temp_path

    # Cleanup
    if os.path.exists(temp_path):
        os.unlink(temp_path)


@pytest.fixture
def client(mock_data_file, monkeypatch):
    """Create a test client with mocked data."""
    # Import main after setting up the mock
    import main

    # Override the data file path
    monkeypatch.setattr(main, "DATA_FILE", mock_data_file)
    monkeypatch.setattr(main, "TEMP_FILE", mock_data_file + ".tmp")
    monkeypatch.setattr(main, "METADATA_FILE", mock_data_file + ".meta")

    # Load the mock data
    with open(mock_data_file, "r") as f:
        data = json.load(f)
        main.nav_lengths = data["nav_lengths"]
        main.valid_pdb_ids = set(data["valid_pdb_ids"])

    from fastapi.testclient import TestClient

    return TestClient(main.app)
