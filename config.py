# config.py

import os

OLLAMA_URL = "http://127.0.0.1:11434"
GROQ_API_KEY = os.getenv("SUA_CHAVE_AQUI", "")
GEMINI_API_KEY = os.getenv("SUA_CHAVE_AQUI", "")
OPENROUTER_API_KEY = os.getenv("SUA_CHAVE_AQUI", "")
NVIDIA_API_KEY = os.getenv("SUA_CHAVE_AQUI", "")

DEFAULT_OLLAMA_MODEL = "qwen2.5-coder:0.5b"
DEFAULT_GROQ_MODEL = "llama-3.1-8b-instant"
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
DEFAULT_OPENROUTER_MODEL = "meta-llama/llama-3.1-8b-instruct"
