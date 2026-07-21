# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
import re
import unicodedata
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional
from iaglobal.agents.agent_base import AgentBase
from iaglobal.utils.logger import logger


# --- 1. Contrato de Dados Rígido (Essencial para Pipelines) ---
@dataclass
class RequirementsOutput:
    functional: List[str] = field(default_factory=list)
    non_functional: List[str] = field(default_factory=list)
    priority: str = "low"
    drivers: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Garante serialização limpa para JSON/Mensageria."""
        return asdict(self)


class PMAgent(AgentBase):
    _FUNC_REQ_PATTERNS = [
        "cadastrar",
        "listar",
        "buscar",
        "atualizar",
        "deletar",
        "calcular",
        "gerar",
        "exportar",
        "importar",
        "processar",
        "validar",
        "autenticar",
        "notificar",
        "enviar",
        "receber",
        "armazenar",
        "consultar",
        "filtrar",
        "ordenar",
        "agrupar",
        "concatenar",
        "converter",
        "parsear",
        "serializar",
        "logar",
        "registrar",
        "monitorar",
        "simular",
        "criar",
        "gerenciar",
        "controlar",
        "vender",
        "comprar",
        "administrar",
        "adicionar",
        "remover",
        "editar",
        "configurar",
        "instalar",
        "manter",
        "visualizar",
        "imprimir",
        "agendar",
        "cancelar",
        "confirmar",
        "habilitar",
    ]

    _NON_FUNC_REQ_PATTERNS = [
        "performance",
        "seguranca",
        "escalabilidade",
        "disponibilidade",
        "latencia",
        "concorrencia",
        "cache",
        "backup",
        "logging",
        "auditoria",
        "privacidade",
        "conformidade",
        "responsivo",
        "acessibilidade",
        "usabilidade",
        "manutenibilidade",
        "monitoramento",
        "recuperacao",
        "resiliencia",
        "tolerancia",
    ]

    # Mapeia conjugações comuns → infinitivo para normalizar a saída
    _VERB_NORMALIZE = {
        "crie": "criar",
        "cria": "criar",
        "crio": "criar",
        "criamos": "criar",
        "criam": "criar",
        "criou": "criar",
        "controle": "controlar",
        "controla": "controlar",
        "controlo": "controlar",
        "controlamos": "controlar",
        "vende": "vender",
        "vendo": "vender",
        "vendemos": "vender",
        "vendem": "vender",
        "vendeu": "vender",
        "gerencia": "gerenciar",
        "gerencio": "gerenciar",
        "gerenciou": "gerenciar",
        "faca": "fazer",
        "faz": "fazer",
        "faco": "fazer",
        "desenvolva": "desenvolver",
        "desenvolve": "desenvolver",
        "construa": "construir",
        "constroi": "construir",
    }

    _STOPWORDS = {
        "o",
        "a",
        "os",
        "as",
        "um",
        "uma",
        "de",
        "da",
        "do",
        "no",
        "na",
        "em",
        "para",
        "por",
        "com",
        "sem",
        "sob",
        "sobre",
        "entre",
        "ate",
    }

    def __init__(self):
        super().__init__(agent_name="pm")

        non_func_pattern = (
            r"\b("
            + "|".join(re.escape(p) for p in self._NON_FUNC_REQ_PATTERNS)
            + r")\b"
        )
        self._non_func_regex = re.compile(non_func_pattern, re.IGNORECASE)
        self._INFINITIVE_CACHE = self._infinitive_stems()

    @staticmethod
    def _normalize_text(text: str) -> str:
        """Remove acentos para matching robusto (segurança == seguranca)."""
        nfkd = unicodedata.normalize("NFD", text)
        return nfkd.encode("ascii", "ignore").decode("utf-8").lower()

    @staticmethod
    def _infinitive_stems():
        """Retorna pares (stem_escapado, infinitivo) para cada verbo."""
        result = []
        for v in PMAgent._FUNC_REQ_PATTERNS:
            stem = re.escape(v)
            for suffix in ["ar", "er", "ir"]:
                if v.endswith(suffix):
                    stem = re.escape(v[: -len(suffix)])
                    break
            result.append((stem, v))
        return result

    def _normalize_action(self, raw_verb: str) -> str:
        lower = raw_verb.lower()
        if lower in self._VERB_NORMALIZE:
            return self._VERB_NORMALIZE[lower]
        for stem, infinitive in self._INFINITIVE_CACHE:
            if lower.startswith(stem.replace("\\", "")):
                return infinitive
        return lower

    def extract_requirements(
        self, prompt: str, enhancement: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        if not prompt or not isinstance(prompt, str):
            return RequirementsOutput().to_dict()

        clean_prompt = self._normalize_text(prompt)

        functional = set()
        non_functional = set()

        stems = self._infinitive_stems()
        stem_alt = "|".join(s + r"\w*" for s, _ in stems)

        # --- 3. Extração com Contexto (verbo + alvo) ---
        # Casamento pela raiz: "cri" → crie, cria, criou...
        # Preposição "de" opcional: "controle de estoque"
        context_search = re.compile(
            rf"\b({stem_alt})\s+(?:de\s+)?([a-z0-9_]+)", re.IGNORECASE
        )

        for match in context_search.finditer(clean_prompt):
            action = self._normalize_action(match.group(1))
            target = match.group(2).lower()
            if target not in self._STOPWORDS:
                functional.add(f"Implementar funcionalidade de {action} {target}")
            else:
                functional.add(f"Implementar funcionalidade de {action}")

        # --- 4. Fallback: verbos isolados ---
        if not functional:
            func_regex = re.compile(rf"\b(?:{stem_alt})\b", re.IGNORECASE)
            for match in func_regex.finditer(clean_prompt):
                action = self._normalize_action(match.group(0))
                functional.add(f"Implementar funcionalidade de {action}")

        if not functional:
            imp = "|".join(
                re.escape(v[: -3 if v.endswith(("ar", "er", "ir")) else 0]) + r"\w*"
                for v in ["criar", "fazer", "desenvolver", "construir"]
            )
            if re.search(rf"\b(?:{imp})\b", clean_prompt, re.IGNORECASE):
                functional.add(
                    "Implementar funcionalidade principal conforme requisitos"
                )

        # --- 5. Requisitos Não-Funcionais ---
        for match in self._non_func_regex.finditer(clean_prompt):
            non_functional.add(f"Garantir {match.group(1)}")

        # --- 6. Extração de Drivers ---
        drivers = []
        if isinstance(enhancement, dict):
            drivers = enhancement.get("intents_detected", []) or []

        # --- 7. Lógica de Prioridade ---
        func_count = len(functional)
        non_func_count = len(non_functional)

        if func_count >= 5 or non_func_count >= 3:
            priority = "high"
        elif func_count >= 2 or non_func_count >= 1:
            priority = "medium"
        else:
            priority = "low"

        logger.info(
            "[PM_AGENT] func=%d | non_func=%d | priority=%s | prompt_len=%d",
            func_count,
            non_func_count,
            priority,
            len(prompt),
        )

        return RequirementsOutput(
            functional=sorted(list(functional)),
            non_functional=sorted(list(non_functional)),
            priority=priority,
            drivers=drivers,
        ).to_dict()
