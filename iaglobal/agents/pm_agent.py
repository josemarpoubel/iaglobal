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
    # Padrões limpos (sem espaços no final)
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
    ]

    def __init__(self):
        super().__init__(agent_name="pm")
        # --- 2. Performance: Pré-compilação de Regex ---
        # \b garante word boundary (não pega "cadastrou" quando busca "cadastrar", por exemplo)
        func_pattern = (
            r"\b(" + "|".join(re.escape(p) for p in self._FUNC_REQ_PATTERNS) + r")\b"
        )
        non_func_pattern = (
            r"\b("
            + "|".join(re.escape(p) for p in self._NON_FUNC_REQ_PATTERNS)
            + r")\b"
        )

        self._func_regex = re.compile(func_pattern, re.IGNORECASE)
        self._non_func_regex = re.compile(non_func_pattern, re.IGNORECASE)

        # Regex para capturar o "alvo" da ação (ex: cadastrar [usuário])
        self._context_regex = re.compile(r"\b({actions})\s+([a-zA-ZÀ-ú_]+)")

    @staticmethod
    def _normalize_text(text: str) -> str:
        """Remove acentos para matching robusto (segurança == seguranca)."""
        nfkd = unicodedata.normalize("NFD", text)
        return nfkd.encode("ascii", "ignore").decode("utf-8").lower()

    def extract_requirements(
        self, prompt: str, enhancement: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        if not prompt or not isinstance(prompt, str):
            return RequirementsOutput().to_dict()

        # Normaliza o prompt (tira acentos e lower)
        clean_prompt = self._normalize_text(prompt)

        functional = set()
        non_functional = set()

        # --- 3. Extração com Contexto (NLP Básico) ---
        # Em vez de só "Implementar cadastrar", tenta achar "cadastrar usuário"
        actions_pattern = "|".join(re.escape(p) for p in self._FUNC_REQ_PATTERNS)
        context_search = re.compile(
            rf"\b({actions_pattern})\s+([a-z0-9_]+)", re.IGNORECASE
        )

        for match in context_search.finditer(prompt):
            action = match.group(1).lower()
            target = match.group(2).lower()
            # Ignora palavras de ligação comuns
            if target not in ["o", "a", "os", "as", "um", "uma", "de", "da", "do"]:
                functional.add(f"Implementar funcionalidade de {action} {target}")
            else:
                functional.add(f"Implementar funcionalidade de {action}")

        # Fallback para ações sem alvo claro
        if not functional:
            for match in self._func_regex.finditer(clean_prompt):
                functional.add(f"Implementar funcionalidade de {match.group(1)}")

        if not functional and any(
            w in clean_prompt for w in ["criar", "fazer", "desenvolver", "construir"]
        ):
            functional.add("Implementar funcionalidade principal conforme requisitos")

        # --- 4. Requisitos Não-Funcionais ---
        for match in self._non_func_regex.finditer(clean_prompt):
            # Mapeia de volta para a palavra com acento se necessário, ou mantém padrão
            non_functional.add(f"Garantir {match.group(1)}")

        # --- 5. Extração de Drivers (Resiliente a erros de chave) ---
        drivers = []
        if isinstance(enhancement, dict):
            # Usa .get() para evitar KeyError se a chave vier com espaço ou não existir
            drivers = enhancement.get("intents_detected", []) or []

        # --- 6. Lógica de Prioridade ---
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

        # Retorna usando a Dataclass para garantir o schema correto
        return RequirementsOutput(
            functional=sorted(list(functional)),
            non_functional=sorted(list(non_functional)),
            priority=priority,
            drivers=drivers,
        ).to_dict()
