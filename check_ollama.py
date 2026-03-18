import requests
import sys
import subprocess
import os

OLLAMA_URL = "http://localhost:11434/api/tags"
OLLAMA_EXE = r"C:\Users\bharu\AppData\Local\Programs\Ollama\ollama.exe"

def check_models():
    print("Checking Ollama status...")
    try:
        response = requests.get(OLLAMA_URL)
        if response.status_code == 200:
            models = [m['name'] for m in response.json().get('models', [])]
            print(f"Ollama is running. Models found: {models}")
            
            required = ['llava', 'llama3']
            missing = [m for m in required if not any(rm.startswith(m) for rm in models)]
            
            if missing:
                print(f"Missing models: {missing}. Attempting to pull...")
                for model in missing:
                    print(f"Pulling {model}...")
                    # stream output to stdout
                    process = subprocess.Popen([OLLAMA_EXE, "pull", model], stdout=sys.stdout, stderr=sys.stderr)
                    process.wait()
                print("All models pulled.")
            else:
                print("All required models are present.")
            return True
        else:
            print(f"Ollama returned status code: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("Ollama is NOT running. Please start it via Start Menu or 'ollama serve'.")
        return False
    except Exception as e:
        print(f"Error: {e}")
        return False

if __name__ == "__main__":
    check_models()
