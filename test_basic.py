import sys
import json
import time
sys.path.append('.')

from utils.ollama_client import OllamaClient
import yaml

# Load config
try:
    with open('config/settings.yaml') as f:
        config = yaml.safe_load(f)
except FileNotFoundError:
    config = {"ollama": {"url": "http://localhost:11434"}} 

print("=== Testing Ollama Connection ===")
try:
    client = OllamaClient(config)
except Exception as e:
    print(f"Failed to connect: {e}")
    sys.exit(1)

print("\n=== Test 1: Basic text generation ===")
try:
    response = client.generate("say hello in one word")
    print(f"Response: {response}")
except Exception as e:
    print(f"FAILED: {e}")

print("\n=== Test 2: JSON generation ===")
try:
    response = client.generate_json(
        prompt="""Create a plan to open notepad.
        Respond ONLY in JSON:
        {"task": "open notepad", "total_steps": 1, 
         "steps": [{"step_number": 1, "action_type": "open_app",
         "description": "Open Notepad", "target": "notepad",
         "value": null, "expected_outcome": "Notepad opens",
         "timeout": 10}]}""",
        system_prompt="Respond only in valid JSON."
    )
    print(f"JSON Response: {json.dumps(response, indent=2)}")
except Exception as e:
    print(f"FAILED: {e}")

print("\n=== Test 3: Screen capture ===")
try:
    from utils.screen_capture import ScreenCapture
    screen = ScreenCapture(config)
    path = screen.capture_primary()
    print(f"Screenshot saved: {path}")
except Exception as e:
    print(f"FAILED: {e}")

print("\n=== All tests completed! ===")
