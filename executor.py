import requests
import json
from config import *
import cache

# ---------------- OLLAMA ----------------
def ollama(prompt):
    cached = cache.get("ollama:" + prompt)
    if cached:
        return cached

    url = f"{OLLAMA_URL}/api/chat"

    payload = {
        "model": DEFAULT_OLLAMA_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False
    }

    r = requests.post(url, json=payload)
    data = r.json()
    result = data["message"]["content"]

    cache.set("ollama:" + prompt, result)
    return result


# ---------------- GROQ ----------------
def groq(prompt):
    cached = cache.get("groq:" + prompt)
    if cached:
        return cached

    url = "https://api.groq.com/openai/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": DEFAULT_GROQ_MODEL,
        "messages": [{"role": "user", "content": prompt}]
    }

    r = requests.post(url, headers=headers, json=payload)
    result = r.json()["choices"][0]["message"]["content"]

    cache.set("groq:" + prompt, result)
    return result


# ---------------- GEMINI ----------------
def gemini(prompt):
    cached = cache.get("gemini:" + prompt)
    if cached:
        return cached

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{DEFAULT_GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"

    payload = {
        "contents": [{"parts": [{"text": prompt}]}]
    }

    r = requests.post(url, json=payload)
    result = r.json()["candidates"][0]["content"]["parts"][0]["text"]

    cache.set("gemini:" + prompt, result)
    return result


# ---------------- OPENROUTER ----------------
def openrouter(prompt):
    cached = cache.get("or:" + prompt)
    if cached:
        return cached

    url = "https://openrouter.ai/api/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": DEFAULT_OPENROUTER_MODEL,
        "messages": [{"role": "user", "content": prompt}]
    }

    r = requests.post(url, headers=headers, json=payload)
    result = r.json()["choices"][0]["message"]["content"]

    cache.set("or:" + prompt, result)
    return result


# ---------------- ROUTER FINAL ----------------
def executar(modelo, prompt):
    if modelo == "ollama":
        return ollama(prompt)
    if modelo == "groq":
        return groq(prompt)
    if modelo == "gemini":
        return gemini(prompt)
    if modelo == "openrouter":
        return openrouter(prompt)

    return ollama(prompt)
