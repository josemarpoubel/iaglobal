# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
iaglobal/interface/chat_agent.py

MEMBRANA DE SINALIZAÇÃO EXTERNA — ponte entre linguagem natural (ligante externo)
e a colônia de EvoAgents (células). Esta camada NUNCA fala diretamente com um
provedor de LLM: ela delega toda geração de texto para arbitrar_geracao(),
preservando o ponto único de passagem (chokepoint) exigido pela BanditPolicy,
pelo portão crítico e pela seletividade de membrana já implementados no núcleo
do sistema.

Ajuste os imports abaixo para os caminhos reais do seu projeto — foram
inferidos a partir da arquitetura descrita (arbitrar_geracao, EvoAgent.genesis,
genesis DNA tribunal). Onde a assinatura real divergir, adapte apenas a função
`_modelo_roteado_por_bandit` e `EvoAgentColony.registrar`.
"""

from __future__ import annotations

import time
import asyncio
from dataclasses import dataclass, field
from typing import Optional

from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart
from pydantic_ai.models.function import FunctionModel, AgentInfo

from iaglobal.utils.logger import get_logger

# --- ajustar para os módulos reais do projeto ---
from iaglobal.evolution.evo_agent import EvoAgent
from iaglobal.agents.critic_agent import _get_critic
from iaglobal.genesis.identity import GENESIS_HASH_OFFICIAL

logger = get_logger("iaglobal")

LINEAGE_MARKER = "cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136"


def _is_valid_lineage(lineage: object) -> bool:
    """Valida se um marcador de linhagem é um DNA próprio válido.

    Um agente válido carrega seu próprio lineage_marker de 16 chars hex,
    derivado do seu DNA (não o marcador global do sistema).
    """
    return (
        isinstance(lineage, str)
        and len(lineage) == 16
        and all(c in "0123456789abcdef" for c in lineage.lower())
    )


# ---------------------------------------------------------------------------
# SAMe Activation — modelo de intenção estruturada (doador de metila cognitivo)
# ---------------------------------------------------------------------------


class IntencaoBiologica(BaseModel):
    """Sinal externo já traduzido e validado antes de tocar qualquer EvoAgent."""

    comando: str = Field(..., description="A ação ou tarefa solicitada")
    urgencia: str = Field("normal", description="baixa | normal | alta | critica")
    familia_alvo: Optional[str] = Field(
        None,
        description="Especialização/lineage do EvoAgent alvo, se o usuário indicou uma",
    )
    contexto_adicional: dict = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Receptor de membrana: transforma o pydantic_ai Model em um proxy fino sobre
# arbitrar_geracao(), em vez de chamar 'openai:gpt-4o' (ou qualquer provedor)
# diretamente. Isso é o que mantém a Regra de Ouro nº 3 (tudo passa pela
# BanditPolicy) e o portão crítico intactos mesmo com uma lib de terceiros.
# ---------------------------------------------------------------------------


async def _modelo_roteado_por_bandit(
    messages: list[ModelMessage], info: AgentInfo
) -> ModelResponse:
    prompt = "\n".join(
        part.content
        for msg in messages
        for part in msg.parts
        if hasattr(part, "content")
    )

    try:
        resultado = await _get_critic().arbitrar_geracao(
            node_id="interface.chat_agent",
            prompt=prompt,
            context={"origem": "pydantic_ai_bridge"},
        )
    except Exception:
        logger.exception("Falha ao rotear geração via arbitrar_geracao()")
        raise

    texto = (
        resultado.get("texto", "") if isinstance(resultado, dict) else str(resultado)
    )
    return ModelResponse(parts=[TextPart(texto)])


def _criar_agente_extrator() -> Agent:
    """Agente pydantic_ai cujo 'modelo' é, na prática, o roteador interno do iaglobal."""
    return Agent(
        FunctionModel(_modelo_roteado_por_bandit),
        output_type=IntencaoBiologica,
        system_prompt=(
            "Você é a membrana de sinalização do ecossistema iaglobal. "
            "Traduza a entrada em linguagem natural para uma IntencaoBiologica "
            "estruturada. Não invente campos fora do schema."
        ),
    )


_extrator = _criar_agente_extrator()


# ---------------------------------------------------------------------------
# Mitose / Diferenciação — colônia de múltiplas instâncias EvoAgent
# ---------------------------------------------------------------------------


@dataclass
class RegistroEvoAgent:
    instancia: EvoAgent
    lineage_marker: str
    especializacao: str = "generalista"
    execucoes: int = 0
    falhas: int = 0
    latencia_media: float = 0.0


class EvoAgentColony:
    """
    Pool de EvoAgents vivos, indexados por especialização. A colônia não
    conhece detalhes de provedores de LLM — apenas decide QUAL célula deve
    processar o sinal, com base em DNA válido e fitness observado.
    """

    def __init__(self) -> None:
        self._agentes: dict[str, RegistroEvoAgent] = {}
        self._lock = asyncio.Lock()

    async def registrar(
        self, agente: EvoAgent, especializacao: str = "generalista"
    ) -> str:
        lineage = getattr(agente, "lineage_marker", None)
        # DNA válido = marcador de linhagem próprio (16 chars hex), não vazio.
        # O marcador global do sistema (LINEAGE_MARKER) NÃO é aceito como
        # identidade de agente — cada célula deve carregar seu próprio DNA.
        if not _is_valid_lineage(lineage):
            logger.warning(
                "DNA divergente/ausente no registro de '%s' — rejeitado pelo tribunal Genesis.",
                especializacao,
            )
            raise ValueError("Falha na verificação de DNA (Genesis tribunal).")

        async with self._lock:
            self._agentes[especializacao] = RegistroEvoAgent(
                instancia=agente,
                lineage_marker=lineage,
                especializacao=especializacao,
            )
        logger.info("EvoAgent '%s' registrado na colônia.", especializacao)
        return especializacao

    async def selecionar(
        self, especializacao: Optional[str] = None
    ) -> RegistroEvoAgent:
        async with self._lock:
            if not self._agentes:
                raise RuntimeError("Colônia vazia — nenhum EvoAgent disponível.")

            if especializacao and especializacao in self._agentes:
                return self._agentes[especializacao]

            # fallback: menor taxa de falha observada (proxy simples de fitness)
            return min(
                self._agentes.values(),
                key=lambda r: (r.falhas / r.execucoes) if r.execucoes else 0.0,
            )

    async def registrar_resultado(
        self, especializacao: str, sucesso: bool, latencia: float
    ) -> None:
        async with self._lock:
            registro = self._agentes.get(especializacao)
            if not registro:
                return
            registro.execucoes += 1
            if not sucesso:
                registro.falhas += 1
            n = registro.execucoes
            registro.latencia_media += (latencia - registro.latencia_media) / n


# ---------------------------------------------------------------------------
# Ponto de entrada único da membrana de chat
# ---------------------------------------------------------------------------


async def interagir_com_colonia(colonia: EvoAgentColony, user_input: str) -> dict:
    """
    1) Traduz linguagem natural -> IntencaoBiologica (via proxy roteado pelo bandit)
    2) Seleciona a célula (EvoAgent) apta a responder
    3) Dispara agente.handle() — que já deve chamar arbitrar_geracao() internamente
    4) Retorna payload com "execution_metrics" para o JointOptimizationLoop
    """
    execution_metrics: dict = {
        "success": False,
        "latency": None,
        "cost": 0.0,
        "model": None,
    }
    inicio = time.monotonic()

    try:
        extraido = await _extrator.run(user_input)
        intencao = extraido.output
    except Exception:
        logger.exception("Falha na extração de intenção via camada pydantic_ai")
        execution_metrics["latency"] = time.monotonic() - inicio
        return {"erro": "falha_extracao", "execution_metrics": execution_metrics}

    try:
        registro = await colonia.selecionar(intencao.familia_alvo)
    except RuntimeError as exc:
        logger.error("Nenhum EvoAgent disponível: %s", exc)
        execution_metrics["latency"] = time.monotonic() - inicio
        return {"erro": "colonia_vazia", "execution_metrics": execution_metrics}

    sucesso = False
    expressao = None
    try:
        expressao = await registro.instancia.handle(intencao.comando)
        sucesso = True
    except Exception:
        logger.exception(
            "EvoAgent '%s' falhou ao processar comando", registro.especializacao
        )

    latencia = time.monotonic() - inicio
    await colonia.registrar_resultado(registro.especializacao, sucesso, latencia)

    execution_metrics.update(
        success=sucesso, latency=latencia, model=registro.especializacao
    )

    return {
        "resposta": expressao,
        "synthesis": expressao.synthesis if expressao else None,
        "intencao": intencao.model_dump(),
        "agente_utilizado": registro.especializacao,
        "execution_metrics": execution_metrics,
    }


# ---------------------------------------------------------------------------
# Fábrica de conveniência
# ---------------------------------------------------------------------------


async def criar_colonia_evoagents(
    especializacoes: list[str],
    nadph_reserve: float = 0.5,
) -> EvoAgentColony:
    """Instancia e registra um EvoAgent por especialização informada.

    Ponte de compatibilidade: repassa nadph_reserve para EvoAgent.genesis()
    preservando a reserva de auto-reparo por agente (não por colônia).
    """
    colonia = EvoAgentColony()
    for especializacao in especializacoes:
        agente = await EvoAgent.genesis(
            task_hint=especializacao,
            name=f"evo-{especializacao}",
            nadph_reserve=nadph_reserve,
        )
        await colonia.registrar(agente, especializacao)
    return colonia
