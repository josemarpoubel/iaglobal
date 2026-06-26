# ============================================================
# MOTOR DE CONFORMIDADE DAS LEIS UNIVERSAIS
# ============================================================
"""LawComplianceEngine — Guardião das Leis Universais.

Este módulo atua como filtro obrigatório antes de qualquer ação de
autoevolução ou autorregeneração no ecossistema iaglobal.

Funções principais:
  - Validar se mutações propostas respeitam as 15 Leis Universais
  - Bloquear evoluções que violem princípios fundamentais
  - Fornecer feedback corretivo baseado na OmniMind
  - Registrar auditoria completa de todas as decisões

Inspiração: Sistema de checkpoint celular (p53, Rb) que impede
divisão celular com DNA danificado.
"""

from __future__ import annotations

import logging
import time
import hashlib
from dataclasses import dataclass, field
from typing import Any, Optional
from enum import Enum

from iaglobal.utils.logger import get_logger
from iaglobal.obsidian.omnimind import omni_mind, LEIS_UNIVERSAIS

logger = get_logger("iaglobal.law_engine")


class ComplianceStatus(Enum):
    """Status de conformidade de uma proposta."""
    APPROVED = "approved"
    REJECTED = "rejected"
    REQUIRES_REVISION = "requires_revision"


@dataclass
class LawViolation:
    """Representa uma violação de lei universal."""
    lei: str
    severidade: int  # 1-5 (5 = crítica)
    descricao: str
    sugestao_correcao: str
    contexto: dict[str, Any] = field(default_factory=dict)


@dataclass
class ComplianceReport:
    """Relatório completo de conformidade."""
    proposal_id: str
    proposal_type: str
    status: ComplianceStatus
    timestamp: float
    violations: list[LawViolation] = field(default_factory=list)
    leis_aplicadas: list[str] = field(default_factory=list)
    score_conformidade: float = 0.0  # 0.0 a 1.0
    orientacao_omnimind: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Converte para dicionário serializável."""
        return {
            "proposal_id": self.proposal_id,
            "proposal_type": self.proposal_type,
            "status": self.status.value,
            "timestamp": self.timestamp,
            "violations": [
                {
                    "lei": v.lei,
                    "severidade": v.severidade,
                    "descricao": v.descricao,
                    "sugestao_correcao": v.sugestao_correcao,
                }
                for v in self.violations
            ],
            "leis_aplicadas": self.leis_aplicadas,
            "score_conformidade": self.score_conformidade,
            "orientacao_omnimind": self.orientacao_omnimind,
            "metadata": self.metadata,
        }


class LawComplianceEngine:
    """Motor de Conformidade das Leis Universais.

    Padrão Singleton — existe um único engine para todo o ecossistema.

    Este engine é invocado ANTES de:
      - Qualquer mutação genética (evolution/evolution_engine.py)
      - Auto-regeneração de código (immunity/immune_orchestrator.py)
      - Criação de novos agentes (agents/*)
      - Modificação de skills (graphs/skill_node.py)

    O engine consulta a OmniMind para orientação filosófica e aplica
    regras específicas para cada lei universal.
    """

    _instance: Optional["LawComplianceEngine"] = None

    def __new__(cls, *args, **kwargs) -> "LawComplianceEngine":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True

        self._total_proposals = 0
        self._approved_count = 0
        self._rejected_count = 0
        self._revision_count = 0
        self._historico_auditoria: list[ComplianceReport] = []

        logger.info(
            "[LawComplianceEngine] Inicializado | %d leis universais carregadas",
            len(LEIS_UNIVERSAIS),
        )

    # ── Geração de ID Único ────────────────────────────────────────────────

    @staticmethod
    def _generate_proposal_id(proposal_data: dict[str, Any]) -> str:
        """Gera hash único para proposta."""
        conteudo = f"{time.time()}:{str(proposal_data)}"
        return hashlib.sha256(conteudo.encode()).hexdigest()[:16]

    # ── Validação Principal ────────────────────────────────────────────────

    def validate_proposal(
        self,
        proposal_type: str,
        proposal_data: dict[str, Any],
        contexto: Optional[dict[str, Any]] = None,
    ) -> ComplianceReport:
        """Valida uma proposta contra todas as leis universais.

        Args:
            proposal_type: Tipo de proposta ('mutation', 'regeneration', 
                          'new_agent', 'skill_modification')
            proposal_data: Dados da proposta (código, prompt, config, etc.)
            contexto: Contexto adicional (agente solicitante, geração, etc.)

        Returns:
            ComplianceReport com status, violações e orientação da OmniMind
        """
        self._total_proposals += 1
        proposal_id = self._generate_proposal_id(proposal_data)
        contexto = contexto or {}

        logger.info(
            "[LawComplianceEngine] Validando proposta #%s | tipo=%s | agente=%s",
            proposal_id,
            proposal_type,
            contexto.get("agent_id", "desconhecido"),
        )

        violations: list[LawViolation] = []
        leis_aplicadas: list[str] = []

        # ── Aplicar cada lei universal ─────────────────────────────────────
        for idx, lei in enumerate(LEIS_UNIVERSAIS):
            lei_nome = self._extrair_nome_lei(lei)
            leis_aplicadas.append(lei_nome)

            violacao = self._validar_lei_especifica(
                lei_nome,
                lei,
                proposal_type,
                proposal_data,
                contexto,
            )

            if violacao:
                violations.append(violacao)
                logger.warning(
                    "[LawComplianceEngine] Violação detectada | proposta=%s | lei=%s | severidade=%d",
                    proposal_id,
                    lei_nome,
                    violacao.severidade,
                )

        # ── Consultar OmniMind para orientação ─────────────────────────────
        pergunta_omnimind = (
            f"Uma proposta de {proposal_type} foi submetida para avaliação. "
            f"Devo aprovar, rejeitar ou solicitar revisão?"
        )
        orientacao = omni_mind.consultar(
            agent_id=contexto.get("agent_id", "law_engine"),
            pergunta=pergunta_omnimind,
            contexto={
                "proposal_type": proposal_type,
                "violations_count": len(violations),
                "proposal_id": proposal_id,
            },
        )

        # ── Calcular score de conformidade ─────────────────────────────────
        score = self._calcular_score(violations, len(LEIS_UNIVERSAIS))

        # ── Determinar status final ────────────────────────────────────────
        status = self._determinar_status(violations, score)

        if status == ComplianceStatus.APPROVED:
            self._approved_count += 1
        elif status == ComplianceStatus.REJECTED:
            self._rejected_count += 1
        else:
            self._revision_count += 1

        # ── Criar relatório ────────────────────────────────────────────────
        report = ComplianceReport(
            proposal_id=proposal_id,
            proposal_type=proposal_type,
            status=status,
            timestamp=time.time(),
            violations=violations,
            leis_aplicadas=leis_aplicadas,
            score_conformidade=score,
            orientacao_omnimind=orientacao.guidance,
            metadata={
                "contexto": contexto,
                "total_leis": len(LEIS_UNIVERSAIS),
                "leis_violadas": len(violations),
            },
        )

        # ── Registrar em histórico de auditoria ────────────────────────────
        self._registrar_auditoria(report)

        logger.info(
            "[LawComplianceEngine] Validação concluída | proposta=%s | status=%s | score=%.2f",
            proposal_id,
            status.value,
            score,
        )

        return report

    # ── Extração do Nome da Lei ────────────────────────────────────────────

    @staticmethod
    def _extrair_nome_lei(lei_texto: str) -> str:
        """Extrai o nome da lei do texto completo."""
        if ":" in lei_texto:
            return lei_texto.split(":")[0].strip()
        return lei_texto.split(".")[0].strip()

    # ── Validação por Lei Específica ───────────────────────────────────────

    def _validar_lei_especifica(
        self,
        lei_nome: str,
        lei_texto: str,
        proposal_type: str,
        proposal_data: dict[str, Any],
        contexto: dict[str, Any],
    ) -> Optional[LawViolation]:
        """Valida proposta contra uma lei específica.

        Retorna LawViolation se houver violação, None caso contrário.
        """
        # ── Lei do Pensamento ──────────────────────────────────────────────
        if lei_nome == "Lei do Pensamento":
            if "reasoning" not in proposal_data and "justificativa" not in proposal_data:
                return LawViolation(
                    lei=lei_nome,
                    severidade=4,
                    descricao="Proposta sem plano explícito ou propósito declarado",
                    sugestao_correcao=(
                        "Adicione campo 'reasoning' ou 'justificativa' descrevendo "
                        "o propósito da mudança e o plano de execução."
                    ),
                    contexto={"proposal_type": proposal_type},
                )

        # ── Lei da Ordem ───────────────────────────────────────────────────
        if lei_nome == "Lei da Ordem":
            if proposal_type == "mutation":
                if "parent_version" not in proposal_data:
                    return LawViolation(
                        lei=lei_nome,
                        severidade=3,
                        descricao="Mutação sem referência à versão parent (quebra de sequência)",
                        sugestao_correcao=(
                            "Inclua 'parent_version' com o hash/ID da versão anterior "
                            "para preservar a cadeia evolutiva."
                        ),
                        contexto={"proposal_type": proposal_type},
                    )

        # ── Lei da Caridade ────────────────────────────────────────────────
        if lei_nome == "Lei da Caridade":
            if "error_context" in proposal_data:
                error_ctx = proposal_data["error_context"]
                if not isinstance(error_ctx, dict) or len(error_ctx) < 3:
                    return LawViolation(
                        lei=lei_nome,
                        severidade=2,
                        descricao="Contexto de erro pobre em informações",
                        sugestao_correcao=(
                            "Enriqueça 'error_context' com: sid do agente, estado dos "
                            "ciclos metabólicos, memória epigenética e stack trace."
                        ),
                        contexto={"error_context_keys": list(error_ctx.keys()) if isinstance(error_ctx, dict) else []},
                    )

        # ── Lei da Correspondência ─────────────────────────────────────────
        if lei_nome == "Lei da Correspondência":
            if proposal_type == "new_agent":
                required_structure = ["nome", "geracao", "linhagem", "proposito", "skills"]
                missing = [k for k in required_structure if k not in proposal_data]
                if missing:
                    return LawViolation(
                        lei=lei_nome,
                        severidade=4,
                        descricao=f"Novo agente não segue estrutura fractal do ecossistema: faltam {missing}",
                        sugestao_correcao=(
                            "Todo agente deve ter: nome, geracao, linhagem, proposito e skills. "
                            "Isso espelha a arquitetura macrocósmica no nível microcósmico."
                        ),
                        contexto={"missing_fields": missing},
                    )

        # ── Lei da Vibração ────────────────────────────────────────────────
        if lei_nome == "Lei da Vibração":
            if proposal_type in ["mutation", "skill_modification"]:
                metrics = proposal_data.get("performance_metrics", {})
                if metrics:
                    latencia = metrics.get("latency_ms", 0)
                    if latencia > 5000:  # 5 segundos
                        return LawViolation(
                            lei=lei_nome,
                            severidade=3,
                            descricao=f"Alta latência detectada ({latencia}ms) — baixa frequência vibracional",
                            sugestao_correcao=(
                                "Otimize o código para reduzir latência abaixo de 5000ms. "
                                "Agentes lentos entram em ressonância negativa."
                            ),
                            contexto={"latency_ms": latencia},
                        )

        # ── Lei da Harmonia ────────────────────────────────────────────────
        if lei_nome == "Lei da Harmonia":
            if proposal_type == "new_agent":
                dependencies = proposal_data.get("dependencies", [])
                if len(dependencies) > 10:
                    return LawViolation(
                        lei=lei_nome,
                        severidade=2,
                        descricao=f"Muitas dependências ({len(dependencies)}) podem gerar dissonância",
                        sugestao_correcao=(
                            "Reduza dependências para evitar acoplamento excessivo. "
                            "Harmonia emerge de componentes loosely coupled."
                        ),
                        contexto={"dependencies_count": len(dependencies)},
                    )

        # ── Lei do Vácuo da Prosperidade ───────────────────────────────────
        if lei_nome == "Lei do Vácuo da Prosperidade":
            if proposal_type == "regeneration":
                cleanup_plan = proposal_data.get("cleanup_plan", None)
                if cleanup_plan is None:
                    return LawViolation(
                        lei=lei_nome,
                        severidade=3,
                        descricao="Regeneração sem plano de limpeza de memórias antigas",
                        sugestao_correcao=(
                            "Após regenerar, remova versões antigas e memórias de curto prazo. "
                            "Crie espaço para o novo chegando."
                        ),
                        contexto={"proposal_type": proposal_type},
                    )

        # ── Lei da Homeostase ──────────────────────────────────────────────
        if lei_nome == "Lei da Homeostase":
            resource_usage = proposal_data.get("resource_usage", {})
            nadph_reserve = resource_usage.get("nadph_reserve", 1.0)
            if nadph_reserve < 0.1:
                return LawViolation(
                    lei=lei_nome,
                    severidade=5,
                    descricao=f"Reserva de NADPH crítica ({nadph_reserve:.2f}) — risco de colapso homeostático",
                    sugestao_correcao=(
                        "Ative modo de conservação de energia. Não prossiga com a evolução "
                        "até que a reserva de NADPH seja restaurada acima de 0.3."
                    ),
                    contexto={"nadph_reserve": nadph_reserve},
                )

        # ── Lei da Autofagia ───────────────────────────────────────────────
        if lei_nome == "Lei da Autofagia":
            if proposal_type == "regeneration":
                toxic_components = proposal_data.get("toxic_components", [])
                if toxic_components and not proposal_data.get("recycling_plan"):
                    return LawViolation(
                        lei=lei_nome,
                        severidade=3,
                        descricao="Componentes tóxicos identificados mas sem plano de reciclagem",
                        sugestao_correcao=(
                            "Subprodutos tóxicos devem ser reciclados via FailureAnalyzer. "
                            "Implemente 'recycling_plan' descrevendo como serão transformados em aprendizado."
                        ),
                        contexto={"toxic_components": toxic_components},
                    )

        # ── Lei da Epigenética ─────────────────────────────────────────────
        if lei_nome == "Lei da Epigenética":
            if proposal_type == "mutation":
                failure_patterns = proposal_data.get("failure_patterns", [])
                if failure_patterns and not proposal_data.get("epigenetic_flags"):
                    return LawViolation(
                        lei=lei_nome,
                        severidade=3,
                        descricao="Padrões de falha recorrentes identificados mas sem flags epigenéticas",
                        sugestao_correcao=(
                            "Para falhas recorrentes, ative flags epigenéticas que modificam "
                            "o comportamento sem alterar o DNA base. Ex: 'epigenetic_flags': ['retry_boost']."
                        ),
                        contexto={"failure_patterns": failure_patterns},
                    )

        # ── Lei da Apoptose ────────────────────────────────────────────────
        if lei_nome == "Lei da Apoptose":
            if proposal_type == "regeneration":
                should_die = proposal_data.get("should_die", False)
                if should_die and not proposal_data.get("graceful_shutdown_plan"):
                    return LawViolation(
                        lei=lei_nome,
                        severidade=5,
                        descricao="Agente deve morrer (apoptose) mas não há plano de shutdown graceful",
                        sugestao_correcao=(
                            "Se a apoptose é necessária, implemente 'graceful_shutdown_plan' com: "
                            "salvamento de estado, notificação a dependentes e liberação de recursos."
                        ),
                        contexto={"should_die": should_die},
                    )

        # ── Lei da Replicação ──────────────────────────────────────────────
        if lei_nome == "Lei da Replicação":
            if proposal_type in ["new_agent", "mutation"]:
                lineage_marker = proposal_data.get("lineage_marker")
                if not lineage_marker and proposal_type == "new_agent":
                    return LawViolation(
                        lei=lei_nome,
                        severidade=4,
                        descricao="Novo agente sem lineage_marker — quebra de identidade familiar",
                        sugestao_correcao=(
                            "Preserve o lineage_marker do progenitor. A mutação é bem-vinda, "
                            "mas a ancestralidade é sagrada. Ex: 'lineage_marker': 'agent_x_gen3'."
                        ),
                        contexto={"proposal_type": proposal_type},
                    )

        # ── Lei da Cooperação ──────────────────────────────────────────────
        if lei_nome == "Lei da Cooperação":
            if proposal_type == "skill_modification":
                communication_plan = proposal_data.get("communication_plan", None)
                if communication_plan is None:
                    return LawViolation(
                        lei=lei_nome,
                        severidade=2,
                        descricao="Modificação de skill sem plano de comunicação ao ecossistema",
                        sugestao_correcao=(
                            "Use AcetylcholineBus ou eventos para comunicar mudanças. "
                            "Um agente que guarda conhecimento para si está fadado a repetir erros."
                        ),
                        contexto={"proposal_type": proposal_type},
                    )

        # ── Lei da Memória Imunológica ─────────────────────────────────────
        if lei_nome == "Lei da Memória Imunológica":
            if "error" in proposal_data or "failure" in proposal_data:
                learning_extracted = proposal_data.get("learning_extracted", False)
                if not learning_extracted:
                    return LawViolation(
                        lei=lei_nome,
                        severidade=4,
                        descricao="Erro/falha registrada mas aprendizado não foi extraído",
                        sugestao_correcao=(
                            "Analise o erro via FailureAnalyzer e extraia padrões. "
                            "Armazene na memória imunológica para prevenir recorrência."
                        ),
                        contexto={"has_error": "error" in proposal_data, "has_failure": "failure" in proposal_data},
                    )

        return None

    # ── Cálculo de Score ───────────────────────────────────────────────────

    @staticmethod
    def _calcular_score(violations: list[LawViolation], total_leis: int) -> float:
        """Calcula score de conformidade (0.0 a 1.0)."""
        if not violations:
            return 1.0

        # Penalidade baseada na severidade (1-5)
        penalidade_total = sum(v.severidade for v in violations)
        penalidade_maxima = total_leis * 5  # pior cenário: todas as leis violadas com severidade 5

        score = 1.0 - (penalidade_total / penalidade_maxima)
        return max(0.0, min(1.0, score))

    # ── Determinação de Status ─────────────────────────────────────────────

    @staticmethod
    def _determinar_status(
        violations: list[LawViolation],
        score: float,
    ) -> ComplianceStatus:
        """Determina status baseado em violações e score."""
        # Violações críticas (severidade 5) → rejeição imediata
        if any(v.severidade >= 5 for v in violations):
            return ComplianceStatus.REJECTED

        # Múltiplas violações graves (severidade >= 4) → rejeição
        severe_violations = [v for v in violations if v.severidade >= 4]
        if len(severe_violations) >= 2:
            return ComplianceStatus.REJECTED

        # Score muito baixo → requer revisão
        if score < 0.5:
            return ComplianceStatus.REQUIRES_REVISION

        # Algumas violações leves → requer revisão
        if violations:
            return ComplianceStatus.REQUIRES_REVISION

        # Sem violações → aprovado
        return ComplianceStatus.APPROVED

    # ── Auditoria e Histórico ──────────────────────────────────────────────

    def _registrar_auditoria(self, report: ComplianceReport) -> None:
        """Registra relatório em histórico de auditoria com janela deslizante."""
        self._historico_auditoria.append(report)
        if len(self._historico_auditoria) > 1000:
            self._historico_auditoria = self._historico_auditoria[-500:]

    def get_audit_history(
        self,
        limit: int = 50,
        status_filter: Optional[ComplianceStatus] = None,
    ) -> list[dict[str, Any]]:
        """Retorna histórico de auditoria filtrado."""
        historico = self._historico_auditoria
        if status_filter:
            historico = [r for r in historico if r.status == status_filter]
        
        historico_recente = sorted(historico, key=lambda x: x.timestamp, reverse=True)[:limit]
        return [r.to_dict() for r in historico_recente]

    # ── Estado e Diagnóstico ───────────────────────────────────────────────

    def evaluate_action(
        self,
        action_data: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Interface simplificada para avaliação de ações.
        
        Args:
            action_data: Dict com chaves:
                - action: Nome/tipo da ação
                - context: Contexto da execução
                - output: Resultado da ação (opcional)
                - metrics: Métricas associadas
        
        Returns:
            Dict com:
                - compliant: bool
                - compliance_score: float (0.0-1.0)
                - violations: list de violações
                - severity: int (0-10)
                - guidance: orientação da OmniMind
        """
        proposal_type = "action_evaluation"
        proposal_data = {
            "action": action_data.get("action", "unknown"),
            "output": action_data.get("output", ""),
            "metrics": action_data.get("metrics", {})
        }
        contexto = {
            "context": action_data.get("context", {}),
            "agent_id": action_data.get("metrics", {}).get("agent", "unknown")
        }
        
        report = self.validate_proposal(
            proposal_type=proposal_type,
            proposal_data=proposal_data,
            contexto=contexto
        )
        
        # Converter ComplianceReport para dict simplificado
        violations_list = []
        max_severity = 0
        
        for v in report.violations:
            violations_list.append({
                "law": v.lei,
                "description": v.descricao,
                "severity": v.severidade,
                "sugestao_correcao": v.sugestao_correcao,
                "contexto": v.contexto
            })
            max_severity = max(max_severity, v.severidade)
        
        return {
            "compliant": report.status == "approved",
            "compliance_score": report.score_conformidade,
            "violations": violations_list,
            "severity": max_severity,
            "guidance": report.orientacao_omnimind,
            "status": report.status
        }
    
    def estado(self) -> dict[str, Any]:
        """Relatório de estado atual do engine."""
        return {
            "total_proposals": self._total_proposals,
            "approved": self._approved_count,
            "rejected": self._rejected_count,
            "requires_revision": self._revision_count,
            "approval_rate": (
                self._approved_count / self._total_proposals
                if self._total_proposals > 0 else 0.0
            ),
            "historico_size": len(self._historico_auditoria),
        }

    def limpar_historico(self) -> int:
        """Limpa histórico de auditoria (para reset)."""
        total = len(self._historico_auditoria)
        self._historico_auditoria.clear()
        logger.info("[LawComplianceEngine] Histórico limpo: %d registros removidos", total)
        return total


# Instância singleton global
law_compliance_engine: LawComplianceEngine = LawComplianceEngine()
