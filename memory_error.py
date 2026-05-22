import os
import json
from datetime import datetime

PASTA = os.path.expanduser("~/.ia-global")
ARQ = os.path.join(PASTA, "error_memory.json")


def load():
    if not os.path.exists(ARQ):
        return []
    with open(ARQ, "r") as f:
        return json.load(f)


def save(data):
    os.makedirs(PASTA, exist_ok=True)
    with open(ARQ, "w") as f:
        json.dump(data, f, indent=2)


def store_error(prompt, response, critique, corrected):
    db = load()

    db.append({
        "time": datetime.now().isoformat(),
        "prompt": prompt,
        "response": response,
        "critique": critique,
        "corrected": corrected
    })

    save(db)
