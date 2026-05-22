# brain.py

import sys
import os
import requests
import json
import time

def escolher_modelo(prompt: str):
    p = prompt.lower()

    if len(p) < 30:
        return "groq"

    if any(k in p for k in ["código", "python", "api", "erro"]):
        return "ollama"

    if any(k in p for k in ["explica", "conceito", "teoria"]):
        return "gemini"

    if any(k in p for k in ["comparar", "análise", "research"]):
        return "openrouter"

    return "ollama"
