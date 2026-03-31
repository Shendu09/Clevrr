#!/usr/bin/env python3
"""
Router Test Script - Verify fast routing classification works
"""
import logging
import sys
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-8s │ %(name)-25s │ %(message)s",
)

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from utils.ollama_client import OllamaClient
from core.router import Router
import yaml

# Load config
with open("config/settings.yaml", "r") as f:
    config = yaml.safe_load(f)

# Initialize
print("\n" + "=" * 70)
print("  ROUTER TEST SUITE")
print("=" * 70 + "\n")

try:
    print("[1/2] Initializing Ollama client...")
    ollama = OllamaClient(config)
    print("  ✅ Ollama connected\n")

    print("[2/2] Initializing Router...")
    router = Router(ollama)
    print("  ✅ Router ready\n")
    
except Exception as e:
    print(f"  ❌ Initialization failed: {e}")
    sys.exit(1)

# Test queries
test_queries = [
    # Direct responses
    ("What is the capital of France?", "direct_response"),
    ("How do I cook pasta?", "direct_response"),
    ("Tell me about Python programming", "direct_response"),
    
    # Vision
    ("What's on my screen?", "invoke_vision"),
    ("Click the red button", "invoke_vision"),
    ("Find the email from John", "invoke_vision"),
    
    # Browser
    ("Open google.com and search for Python", "invoke_browser"),
    ("Go to GitHub", "invoke_browser"),
    ("Find the pandas repository on GitHub", "invoke_browser"),
    
    # OS Control
    ("Open Notepad", "invoke_os_control"),
    ("Create a folder called 'test'", "invoke_os_control"),
    ("List all files on my desktop", "invoke_os_control"),
    ("Close all Chrome windows", "invoke_os_control"),
    
    # Orchestrator (complex multi-step)
    ("Organize my desktop files by date", "invoke_orchestrator"),
    ("Download all images from a webpage and resize them", "invoke_orchestrator"),
]

# Run tests
print("Running routing tests...\n")
correct = 0
incorrect = 0
results = []

for query, expected_action in test_queries:
    result = router.route(query)
    action = result["action"]
    confidence = result["confidence"]
    
    is_correct = action == expected_action
    status = "✅" if is_correct else "❌"
    
    if is_correct:
        correct += 1
    else:
        incorrect += 1
    
    results.append({
        "query": query,
        "expected": expected_action,
        "got": action,
        "confidence": confidence,
        "correct": is_correct,
    })
    
    print(f"  {status} '{query[:50]}...' → {action} (expected: {expected_action}, conf: {confidence:.2f})")

# Summary
print("\n" + "=" * 70)
print(f"  Results: {correct} correct, {incorrect} incorrect")
print(f"  Accuracy: {correct / len(test_queries) * 100:.1f}%")
print("=" * 70 + "\n")

# Detailed results
if incorrect > 0:
    print("Failed predictions:\n")
    for r in results:
        if not r["correct"]:
            print(f"  ❌ '{r['query']}'")
            print(f"     Expected: {r['expected']}")
            print(f"     Got: {r['got']} (confidence: {r['confidence']:.2f})\n")

# Router stats
print("Router Statistics:")
stats = router.get_stats()
for key, val in stats.items():
    print(f"  {key}: {val}")

print("\n" + "=" * 70)
print("  TEST SUITE COMPLETE")
print("=" * 70 + "\n")
