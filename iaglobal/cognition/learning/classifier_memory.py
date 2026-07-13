from collections import defaultdict


class ClassifierMemory:
    """
    Memória simples de performance do TaskClassifier
    """

    def __init__(self):
        self.memory = defaultdict(list)

    def record(self, fingerprint: dict, reward: float):
        key = self._key(fingerprint)
        self.memory[key].append(reward)

    def get_bias(self, fingerprint: dict) -> float:
        key = self._key(fingerprint)
        values = self.memory.get(key, [])

        if not values:
            return 0.0

        return sum(values) / len(values)

    def _key(self, fp: dict) -> str:
        return f"{fp.get('domain')}:{fp.get('intent')}:{fp.get('language')}"
