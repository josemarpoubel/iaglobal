# ============================================================
# CHAPPIE COMPONENTE 2/4: ERROR ENRICHER
# Lei da Caridade + Axioma da Memória Imunológica
# ============================================================
"""ErrorEnricher — Transforma Falhas em Aprendizado Estruturado.

Implementa a Lei da Caridade:
  "Erros devem ser enriquecidos com contexto antes de serem repassados.
   Um erro pobre em contexto é uma oportunidade perdida de aprendizado."

E o Axioma da Memória Imunológica:
  "Erros do passado são o ativo mais valioso do sistema.
   Aprender com o erro é a forma mais eficiente de evoluir."

Funcionamento:
  1. Intercepta falhas de agents (via decorator ou middleware)
  2. Captura contexto completo (agente, task, IVM, providers, timestamps)
  3. Sintetiza lição aprendida via IA (ou fallback determinístico)
  4. Grava no Obsidian (02_Short_Term) com tags estruturadas
  5. Disparar alarme se padrão de falha recorrente detectado

Diferença para error_capture.py existente:
  - Enriquecimento automático de contexto (não requer código boilerplate)
  - Integração com Obsidian para memória de longo prazo
  - Detecção de padrões recorrentes (anti-corpos arquiteturais)
  - Logging estruturado para auditoria
"""

import asyncio
import hashlib
import logging
from datetime import datetime, UTC
from pathlib import Path
from typing import Optional, Dict, Any, List, Callable
from functools import wraps
from dataclasses import dataclass, field

from iaglobal._paths import PACKAGE_DIR
from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.chappie.error_enricher")


@dataclass
class ErrorContext:
    """Contexto completo de um erro para enriquecimento."""

    # Dados básicos do erro
    error_type: str
    error_message: str
    traceback: str

    # Contexto do agente
    agent_name: str
    agent_generation: int = 0
    agent_lineage: str = ""

    # Contexto da task
    task_description: str = ""
    task_id: str = ""

    # Contexto metabólico
    ivm_at_failure: float = 0.0
    providers_attempted: List[str] = field(default_factory=list)
    provider_errors: Dict[str, str] = field(default_factory=dict)

    # Timestamps
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    # Metadata adicional
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário (para serialização)."""
        return {
            "error_type": self.error_type,
            "error_message": self.error_message,
            "traceback": self.traceback,
            "agent_name": self.agent_name,
            "agent_generation": self.agent_generation,
            "agent_lineage": self.agent_lineage[:16] if self.agent_lineage else "",
            "task_description": self.task_description,
            "task_id": self.task_id,
            "ivm_at_failure": self.ivm_at_failure,
            "providers_attempted": self.providers_attempted,
            "provider_errors": self.provider_errors,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


class ErrorEnricher:
    """Enriquecedor Automático de Erros — Lei da Caridade.

    Decorador e middleware que captura falhas de agents, enriquece
    com contexto completo, e grava no Obsidian para aprendizado futuro.

    Uso como decorator:
        error_enricher = ErrorEnricher()

        @error_enricher.capture
        async def minha_funcao_agente():
            ...

    Uso programático:
        await error_enricher.enriquecer_e_gravar(error_context)
    """

    def __init__(
        self,
        vault_path: Optional[Path] = None,
        auto_learn: bool = True,
       pattern_threshold: int = 3,
    ):
        """Inicializa o Error Enricher.

        Args:
            vault_path: Caminho para vault Obsidian (default: PACKAGE_DIR/obsidian)
            auto_learn: Se True, sintetiza lição aprendida via IA
            pattern_threshold: Número de falhas similares para disparar alarme
        """
        self.vault_path = Path(vault_path or PACKAGE_DIR / "obsidian")
        self.short_term_dir = self.vault_path / "02_Short_Term"
        self.auto_learn = auto_learn
        self.pattern_threshold = pattern_threshold

        # Cache de falhas para detecção de padrões
        self._error_cache: Dict[str, List[ErrorContext]] = {}
        self._total_errors = 0
        self._patterns_detected = 0

        # Garante que diretórios existem
        self.short_term_dir.mkdir(parents=True, exist_ok=True)

        logger.info(
            "[ErrorEnricher] Inicializado | vault=%s | auto_learn=%s | pattern_threshold=%d",
            self.vault_path,
            auto_learn,
            pattern_threshold,
        )

    def capture(self, func: Callable) -> Callable:
        """Decorator que captura erros de funções async automaticamente.

        Uso:
            @error_enricher.capture
            async def minha_funcao():
                ...
        """

        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                # Extrai contexto da função
                agent_name = func.__module__.split(".")[-1]
                error_context = ErrorContext(
                    error_type=type(e).__name__,
                    error_message=str(e),
                    traceback=self._extract_traceback(e),
                    agent_name=agent_name,
                )

                # Enriquece e grava
                await self.enriquecer_e_gravar(error_context)

                # Re-lança o erro (não suprime)
                raise

        return wrapper

    async def enriquecer_e_gravar(self, contexto: ErrorContext) -> str:
        """Enriquece erro com contexto e grava no Obsidian.

        Retorna:
            str: ID único do erro gravado (para referência futura)
        """
        logger.info(
            "[ErrorEnricher] Enriquecendo erro | agent=%s | type=%s",
            contexto.agent_name,
            contexto.error_type,
        )

        # Gera ID único baseado no hash do erro
        error_id = self._generate_error_id(contexto)

        # Se auto_learn estiver ativo, sintetiza lição aprendida
        licao_aprendida = ""
        if self.auto_learn:
            licao_aprendida = await self._sintetizar_licao_aprendida(contexto)

        # Monta conteúdo Markdown para Obsidian
        markdown_content = self._montar_markdown(contexto, error_id, licao_aprendida)

        # Grava no curto prazo (vai ser consolidado pelo VacuumDaemon depois)
        arquivo_path = self.short_term_dir / f"{error_id}.md"
        await asyncio.to_thread(arquivo_path.write_text, markdown_content, encoding="utf-8")

        # Atualiza cache para detecção de padrões
        await self._atualizar_cache_e_detectar_padroes(contexto)

        self._total_errors += 1
        logger.info(
            "[ErrorEnricher] Erro gravado | id=%s | path=%s | total=%d",
            error_id,
            arquivo_path,
            self._total_errors,
        )

        return error_id

    def _generate_error_id(self, contexto: ErrorContext) -> str:
        """Gera ID único baseado no hash do erro."""
        # Hash baseado em: agent + error_type + error_message + task_id
        dados = f"{contexto.agent_name}:{contexto.error_type}:{contexto.error_message}:{contexto.task_id}"
        hash_digest = hashlib.sha256(dados.encode()).hexdigest()[:16]
        timestamp = contexto.timestamp.strftime("%Y%m%d%H%M%S%f")
        return f"erro_{contexto.agent_name}_{timestamp}_{hash_digest}"

    def _extract_traceback(self, error: Exception) -> str:
        """Extrai traceback formatado."""
        import traceback
        return "".join(traceback.format_exception(type(error), error, error.__traceback__))

    async def _sintetizar_licao_aprendida(self, contexto: ErrorContext) -> str:
        """Sintetiza lição aprendida via IA (ou fallback determinístico).

        TODO: Integrar com BanditPolicy para chamar LLM de forma eficiente.
        Por enquanto, usa fallback determinístico baseado no tipo de erro.
        """
        # Fallback determinístico (pode ser melhorado com IA depois)
        licoes = {
            "TimeoutError": "Implementar retry com backoff exponencial ou aumentar timeout.",
            "ConnectionError": "Verificar healthcheck de providers antes de executar. Adicionar fallback chain.",
            "RateLimitError": "Implementar rate limiting local ou aumentar delay entre chamadas.",
            "MemoryError": "Otimizar uso de memória ou dividir task em batches menores.",
            "ValidationError": "Adicionar validação de input antes de processar.",
            "AuthenticationError": "Verificar credenciais e tokens antes de executar.",
        }

        licao = licoes.get(contexto.error_type, "Analisar causa raiz e implementar guardrail preventivo.")

        # Adiciona contexto específico
        licao_completa = (
            f"**Lição Aprendida (Auto-Sintetizada):**\n\n"
            f"{licao}\n\n"
            f"**Contexto Específico:**\n"
            f"- Agente: {contexto.agent_name}\n"
            f"- Task: {contexto.task_description or 'N/A'}\n"
            f"- IVM no momento: {contexto.ivm_at_failure:.2f}\n"
            f"- Providers tentados: {', '.join(contexto.providers_attempted) or 'N/A'}\n\n"
            f"**Ação Preventiva Sugerida:**\n"
            f"1. Adicionar validação pré-execução para este tipo de erro\n"
            f"2. Implementar circuit breaker específico para {contexto.error_type}\n"
            f"3. Criar teste automatizado que reproduza este erro\n"
            f"4. Documentar no Obsidian como padrão conhecido (#padrao #imunologico)"
        )

        return licao_completa

    def _montar_markdown(
        self, contexto: ErrorContext, error_id: str, licao_aprendida: str
    ) -> str:
        """Monta conteúdo Markdown para gravação no Obsidian."""
        frontmatter = f"""---
tipo: ErroEnriquecido
id: {error_id}
agente: {contexto.agent_name}
geracao: {contexto.agent_generation}
linhagem: {contexto.agent_lineage[:16] if contexto.agent_lineage else "N/A"}
tipo_erro: {contexto.error_type}
timestamp: {contexto.timestamp.isoformat()}
ivm_no_momento: {contexto.ivm_at_failure:.2f}
tags: ["#erro", "#aprendizado", "#imunologico", "#{contexto.agent_name}"]
---

# Erro Enriquecido: {contexto.error_type}

## Metadados do Erro

- **ID**: `{error_id}`
- **Agente**: `{contexto.agent_name}` (Geração {contexto.agent_generation})
- **Tipo**: `{contexto.error_type}`
- **Mensagem**: {contexto.error_message}
- **Timestamp**: {contexto.timestamp.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]} UTC

## Contexto da Task

- **Task ID**: `{contexto.task_id or "N/A"}`
- **Descrição**: {contexto.task_description or "N/A"}
- **IVM no Momento**: {contexto.ivm_at_failure:.2f}

## Providers Tentados

{self._format_providers(contexto.providers_attempted, contexto.provider_errors)}

## Traceback

```
{contexto.traceback}
```

## Lição Aprendida (Auto-Sintetizada)

{licao_aprendida if licao_aprendida else "Aguardando síntese manual..."}

## Links

- [[Mapa_Mental_Subconsciente]]
- [[success_log]]
"""
        return frontmatter

    def _format_providers(self, providers: List[str], errors: Dict[str, str]) -> str:
        """Formata lista de providers e erros associados."""
        if not providers:
            return "Nenhum provider tentado."

        linhas = []
        for provider in providers:
            error = errors.get(provider, "Sem erro específico")
            linhas.append(f"- **{provider}**: {error}")

        return "\n".join(linhas)

    async def _atualizar_cache_e_detectar_padroes(self, contexto: ErrorContext) -> None:
        """Atualiza cache e detecta padrões recorrentes."""
        # Chave de padrão: agent_name + error_type
        pattern_key = f"{contexto.agent_name}:{contexto.error_type}"

        if pattern_key not in self._error_cache:
            self._error_cache[pattern_key] = []

        self._error_cache[pattern_key].append(contexto)

        # Verifica se ultrapassou threshold
        if len(self._error_cache[pattern_key]) >= self.pattern_threshold:
            await self._disparar_alarme_padrao(pattern_key, self._error_cache[pattern_key])
            self._patterns_detected += 1

    async def _disparar_alarme_padrao(
        self, pattern_key: str, erros: List[ErrorContext]
    ) -> None:
        """Dispara alarme para padrão recorrente detectado."""
        agente, erro_tipo = pattern_key.split(":")
        logger.critical(
            "[ErrorEnricher] 🚨 PADRÃO RECORRENTE DETECTADO | agent=%s | error_type=%s | ocorrencias=%d",
            agente,
            erro_tipo,
            len(erros),
        )

        # TODO: Enviar notificação para dashboard / webhook
        # TODO: Sugerir ação corretiva automática

    def get_status(self) -> Dict[str, Any]:
        """Retorna status atual do ErrorEnricher."""
        return {
            "total_errors": self._total_errors,
            "patterns_detected": self._patterns_detected,
            "unique_patterns": len(self._error_cache),
            "auto_learn_enabled": self.auto_learn,
            "pattern_threshold": self.pattern_threshold,
        }


# Singleton global
error_enricher: Optional[ErrorEnricher] = None


def get_error_enricher() -> ErrorEnricher:
    """Retorna singleton do ErrorEnricher."""
    global error_enricher
    if error_enricher is None:
        error_enricher = ErrorEnricher()
    return error_enricher