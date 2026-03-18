import logging
import sys
import yaml
import time
sys.path.append('.')

from agents.orchestrator import Orchestrator

# Setup logging to console
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)

try:
    with open("config/settings.yaml", "r") as f:
        config = yaml.safe_load(f)
except FileNotFoundError:
    print("Config file not found, using default.")
    config = {}

print("Initializing Orchestrator...")
try:
    orch = Orchestrator(config)
    print("Orchestrator initialized.")

    print("\nXXX Running task: 'open notepad and type hello'")
    result = orch.run_task("open notepad and type hello")

    print("\nXXX Execution Result:")
    import json
    print(json.dumps(result, indent=2, default=str))

except Exception as e:
    print(f"\nXXX detailed error: {e}")
    import traceback
    traceback.print_exc()
