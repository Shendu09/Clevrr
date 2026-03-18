import requests
import sys
import json

def check_ollama(description="Ollama Service"):
    print(f"Checking {description}...", end=" ", flush=True)
    try:
        response = requests.get("http://localhost:11434/")
        if response.status_code == 200:
            print("✅ Running")
            return True
        else:
            print(f"❌ Error (Status {response.status_code})")
            return False
    except requests.exceptions.ConnectionError:
        print("❌ Not Reachable (Is Ollama running?)")
        return False

def check_model(model_name):
    print(f"Checking model '{model_name}'...", end=" ", flush=True)
    try:
        response = requests.get("http://localhost:11434/api/tags")
        if response.status_code == 200:
            models = [m['name'] for m in response.json().get('models', [])]
            # Ollama model names can be 'llama3:latest' or just 'llama3'
            if any(model_name in m for m in models):
                print("✅ Installed")
                return True
            else:
                print(f"❌ Missing (Found: {models})")
                return False
        else:
            print("❌ Error listing models")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    if not check_ollama():
        sys.exit(1)
    
    missing = []
    if not check_model("llama3"): missing.append("llama3")
    if not check_model("llava"): missing.append("llava")
    
    if missing:
        print(f"\nMissing models: {', '.join(missing)}")
        print("Attempting to pull missing models via API...")
        
        for m in missing:
            print(f"  Pulling {m}...")
            try:
                # Use stream=True to handle long-running request
                with requests.post("http://localhost:11434/api/pull", json={"name": m}, stream=True) as r:
                    r.raise_for_status()
                    for line in r.iter_lines():
                        if line:
                            decoded = json.loads(line.decode('utf-8'))
                            status = decoded.get('status', '')
                            total = decoded.get('total')
                            completed = decoded.get('completed')
                            if total and completed:
                                percent = int(completed / total * 100)
                                print(f"\r    {status}: {percent}%", end="")
                            else:
                                print(f"\r    {status}", end="")
                    print("\n  ✅ Download complete!")
            except Exception as e:
                print(f"\n  ❌ Failed to pull {m}: {e}")
                sys.exit(1)
    
    print("\nAll systems go! 🚀")
    sys.exit(0)
