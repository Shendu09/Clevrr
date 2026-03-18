import os
import sys

import pytest

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))


def pytest_configure(config):
    """Configure pytest."""
    os.makedirs('data', exist_ok=True)


def pytest_collection_modifyitems(items):
    """Skip tests requiring Ollama if not running."""
    import requests
    try:
        requests.get('http://localhost:11434', timeout=2)
        ollama_running = True
    except:
        ollama_running = False

    if not ollama_running:
        skip_ollama = pytest.mark.skip(
            reason="Ollama not running - start with: ollama serve"
        )
        for item in items:
            if "ollama" in item.name.lower() or \
               "planner" in item.name.lower() or \
               "vision" in item.name.lower():
                item.add_marker(skip_ollama)
