# Advanced Clevrr

Local AI computer automation project powered by Ollama and Python.

## 100% Local

The app runs inference locally once all required assets are downloaded.

### First Run Downloads (One Time Only)
The following are downloaded automatically on first run:
- Ollama models (llava + llama3) — ~8GB total
  Downloaded via: ollama pull llava && ollama pull llama3
- Sentence Transformers model (all-MiniLM-L6-v2) — ~90MB
  Downloaded automatically from HuggingFace on first run
  After first download everything works completely offline.
