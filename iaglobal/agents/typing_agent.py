"""TypingAgent — Simula digitação humana em caixas de texto web.

Evita bloqueios de provedores LLM web (ChatGPT, Claude, etc.)
simulando padrões de digitação realistas:
- Velocidade variável (não constante)
- Pausas ocasionais (pensamento)
- Rajadas em palavras comuns
- Delay inicial antes de começar
"""

import time
import random
import threading
from typing import Optional, Callable
from dataclasses import dataclass

from iaglobal.utils.logger import logger


@dataclass
class TypingProfile:
    """Perfil de digitação humana."""

    # Caracteres por segundo (média)
    chars_per_second: float = 8.0

    # Variação aleatória no intervalo entre caracteres (±50%)
    jitter: float = 0.5

    # Probabilidade de pausa "thinking" (0-1)
    pause_chance: float = 0.15

    # Duração da pausa em segundos
    pause_duration: tuple = (0.3, 1.5)

    # Delay inicial antes de começar a digitar (segundos)
    initial_delay: tuple = (0.5, 2.0)

    # Palavras que geram rajada (dígrafos comuns)
    burst_words: set = None

    # Fator de rajada para palavras comuns (mais rápido)
    burst_factor: float = 2.5

    # Delay após pontuação (.!?) — simula leitura
    punctuation_pause: float = 0.4

    def __post_init__(self):
        if self.burst_words is None:
            self.burst_words = {
                "the", "and", "for", "are", "but", "not", "you", "all",
                "can", "had", "her", "was", "one", "our", "out", "que",
                "com", "dos", "das", "para", "uma", "como", "mais",
                "python", "def", "return", "class", "import", "from",
                "print", "if", "else", "elif", "while", "for", "in",
                "true", "false", "none", "self", "init", "str", "int",
                "list", "dict", "set", "tuple", "lambda", "yield",
            }

    @property
    def min_interval(self) -> float:
        """Intervalo mínimo entre caracteres (segundos)."""
        return 1.0 / (self.chars_per_second * (1 + self.jitter))

    @property
    def max_interval(self) -> float:
        """Intervalo máximo entre caracteres (segundos)."""
        return 1.0 / (self.chars_per_second * (1 - self.jitter))


class TypingAgent:
    """Simula digitação humana em tempo real."""

    def __init__(self, profile: Optional[TypingProfile] = None):
        self.profile = profile or TypingProfile()
        self._chars_typed = 0
        self._total_time = 0.0
        self._running = False

    def simulate_typing(self, text: str, on_char: Optional[Callable[[str], None]] = None,
                        on_complete: Optional[Callable[[], None]] = None) -> float:
        """Simula digitação do texto completo.

        Args:
            text: Texto a ser digitado.
            on_char: Callback chamado para cada caractere (recebe o char).
            on_complete: Callback chamado ao finalizar.

        Returns:
            Tempo total gasto em segundos.
        """
        import time as t_mod
        start = t_mod.time()
        self._running = True

        # Delay inicial
        initial = random.uniform(*self.profile.initial_delay)
        logger.debug(f"[TYPING] Iniciando em {initial:.1f}s...")
        t_mod.sleep(initial)

        # Tokenização simples em palavras
        words = text.split(" ")
        for word_idx, word in enumerate(words):
            for char_idx, char in enumerate(word):
                if not self._running:
                    return t_mod.time() - start

                # Callback do caractere
                if on_char:
                    on_char(char)

                self._chars_typed += 1

                # Delay entre caracteres
                delay = self._next_char_delay(word, char_idx, word_idx)

                # Pausa ocasional "thinking"
                if char_idx == len(word) - 1 and random.random() < self.profile.pause_chance:
                    pause = random.uniform(*self.profile.pause_duration)
                    logger.debug(f"[TYPING] Pausa thinking: {pause:.1f}s")
                    delay += pause

                t_mod.sleep(max(0.001, delay))

            # Espaço entre palavras
            if word_idx < len(words) - 1:
                if on_char:
                    on_char(" ")
                self._chars_typed += 1
                t_mod.sleep(self._next_space_delay(word_idx))

        elapsed = t_mod.time() - start
        self._total_time += elapsed

        if on_complete:
            on_complete()

        logger.debug(f"[TYPING] Concluído: {len(text)} chars em {elapsed:.1f}s "
                     f"({len(text)/elapsed:.1f} cps)")
        return elapsed

    def simulate_typing_async(self, text: str, on_char: Optional[Callable] = None,
                               on_complete: Optional[Callable] = None) -> threading.Thread:
        """Simula digitação em thread separada (não bloqueante)."""
        thread = threading.Thread(
            target=self.simulate_typing,
            args=(text, on_char, on_complete),
            daemon=True,
        )
        thread.start()
        return thread

    def stop(self):
        """Para a simulação em andamento."""
        self._running = False
        logger.debug("[TYPING] Parando simulação...")

    def get_stats(self) -> dict:
        return {
            "chars_typed": self._chars_typed,
            "total_time": round(self._total_time, 2),
            "avg_speed": f"{self._chars_typed/self._total_time:.1f} cps" if self._total_time > 0 else "N/A",
            "profile_cps": self.profile.chars_per_second,
        }

    def estimate_time(self, text: str) -> float:
        """Estima tempo para digitar um texto sem executar."""
        initial = sum(self.profile.initial_delay) / 2
        words = text.split(" ")
        char_time = len(text) / self.profile.chars_per_second
        pauses = len(words) * self.profile.pause_chance * (sum(self.profile.pause_duration) / 2)
        return round(initial + char_time + pauses, 2)

    # =========================================================================
    # MÉTODOS INTERNOS
    # =========================================================================

    def _next_char_delay(self, word: str, char_idx: int, word_idx: int) -> float:
        """Calcula delay para o próximo caractere."""
        base = 1.0 / self.profile.chars_per_second

        # Rajada para palavras conhecidas
        if word.lower() in self.profile.burst_words:
            base /= self.profile.burst_factor

        # Jitter aleatório
        jitter = random.uniform(-self.profile.jitter, self.profile.jitter)
        delay = base * (1 + jitter)

        # Pausa após pontuação
        if char_idx > 0 and word[char_idx - 1] in ".!?":
            delay += self.profile.punctuation_pause

        return max(0.005, delay)

    def _next_space_delay(self, word_idx: int) -> float:
        """Delay após espaço entre palavras."""
        base = 1.0 / self.profile.chars_per_second * 0.5
        jitter = random.uniform(-0.3, 0.3)
        return max(0.01, base * (1 + jitter))


class TypingService:
    """Serviço que integra TypingAgent com provedores web."""

    def __init__(self):
        self.default_profile = TypingProfile(
            chars_per_second=10.0,
            pause_chance=0.1,
            initial_delay=(0.5, 1.5),
        )
        self.slow_profile = TypingProfile(
            chars_per_second=4.0,
            pause_chance=0.25,
            initial_delay=(1.0, 3.0),
        )
        self.agent = TypingAgent(self.default_profile)

    def web_llm_call(self, prompt: str, model_name: str = "chatgpt_web") -> str:
        """Simula chamada a LLM web com digitação humanizada.

        Útil para provedores que bloqueiam requisições muito rápidas.
        Retorna o prompt como se estivesse sendo digitado em tempo real.
        """
        logger.info(f"[TYPING-SERVICE] Chamada web: model={model_name} prompt_len={len(prompt)}")

        # Escolhe perfil baseado no tamanho
        if len(prompt) > 2000:
            self.agent.profile = self.slow_profile
        else:
            self.agent.profile = self.default_profile

        def char_callback(c: str):
            pass  # Em produção: enviaria caractere para selenium/playwright

        elapsed = self.agent.simulate_typing(prompt, on_char=char_callback)
        logger.info(f"[TYPING-SERVICE] Digitação concluída: {len(prompt)} chars em {elapsed:.1f}s")

        return prompt

    def estimate_wait(self, text: str) -> float:
        """Estima tempo de espera para digitação."""
        return self.agent.estimate_time(text)
