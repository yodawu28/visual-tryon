"""
Pytest configuration and shared fixtures.
"""

import pytest
import os
from pathlib import Path


@pytest.fixture(scope="session")
def test_data_dir():
    """Return path to test data directory"""
    return Path(__file__).parent / "fixtures" / "sample_images"


@pytest.fixture(scope="session", autouse=True)
def setup_test_env():
    """Setup test environment variables"""
    os.environ["ENVIRONMENT"] = "test"
    os.environ["DEBUG"] = "true"
    os.environ["OPENAI_API_KEY"] = "sk-test-key-for-testing"
