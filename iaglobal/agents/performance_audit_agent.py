# iaglobal/agents/performance_audit_agent.py

# iaglobal/agents/performance_audit_agent.py
"""
PerformanceAuditAgent — Geração 8
Auditor de performance com arquitetura estratificada, scoring ponderado,
reincidência estrutural e integração com o ciclo biológico do iaglobal.

Camadas:
  PatternRegistry   → catálogo de regras extensível (Open/Closed)
  RecidivismTracker → memória estrutural de padrões já detectados
  AuditEngine       → núcleo de análise (regex + heurísticas AST-like)
  SeverityScorer    → scoring ponderado e normalizado
  ReportComposer    → montagem do relatório final tipado
  PerformanceAuditAgent → orquestrador com integração biológica
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol, runtime_checkable

from iaglobal.utils.logger import logger

# ---------------------------------------------------------------------------
# Domínio — tipos e enumerações
# ---------------------------------------------------------------------------

class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH     = "high"
    MEDIUM   = "medium"
    LOW      = "low"
    INFO     = "info"

    @property
    def weight(self) -> int:
        return {"critical": 40, "high": 20, "medium": 8, "low": 2, "info": 0}[self.value]


class Category(str, Enum):
    DATABASE   = "database"
    LOOP       = "loop"
    IO         = "io"
    MEMORY     = "memory"
    CONCURRENCY= "concurrency"
    COMPLEXITY = "complexity"
    STRUCTURE  = "structure"


@dataclass(frozen=True)
class AuditRule:
    """Regra de auditoria imutável — unit of detection."""
    rule_id:     str
    pattern:     str           # regex
    description: str
    severity:    Severity
    category:    Category
    remediation: str = ""
    flags:       int = re.IGNORECASE


@dataclass
class Finding:
    rule_id:     str
    description: str
    severity:    Severity
    category:    Category
    remediation: str
    recidivism:  bool = False
    line_hints:  list[int] = field(default_factory=list)

    @property
    def effective_severity(self) -> Severity:
        """Reincidência eleva a severidade em um nível."""
        if not self.recidivism:
            return self.severity
        order = [Severity.INFO, Severity.LOW, Severity.MEDIUM,
                 Severity.HIGH, Severity.CRITICAL]
        idx = order.index(self.severity)
        return order[min(idx + 1, len(order) - 1)]


@dataclass
class AuditReport:
    total_findings:    int
    severity_count:    dict[str, int]
    risk_score:        int          # 0-100 normalizado
    findings:          list[Finding]
    structural_flags:  list[str]
    recidivism_flags:  list[str]

    # Compatibilidade retroativa com contratos existentes do iaglobal
    @property
    def bottlenecks(self) -> list[dict]:
        return [
            {
                "description": f.description,
                "severity":    f.effective_severity.value,
                "category":    f.category.value,
                "remediation": f.remediation,
                "recidivism":  f.recidivism,
            }
            for f in self.findings
        ]

    def to_legacy_dict(self) -> dict:
        """Contrato retrocompatível com CoderAgent / PromptImprover."""
        return {
            "performance_audit_report": {
                "total_bottlenecks": self.total_findings,
                "severity_count":    self.severity_count,
                "risk_score":        self.risk_score,
                "bottlenecks":       self.bottlenecks,
                "structural_flags":  self.structural_flags,
                "recidivism_flags":  self.recidivism_flags,
            },
            "bottlenecks": self.bottlenecks,
        }


# ---------------------------------------------------------------------------
# PatternRegistry — Open/Closed: adicione regras sem tocar no engine
# ---------------------------------------------------------------------------

class PatternRegistry:
    """
    Catálogo centralizado de AuditRule.
    Extensível via register() — nenhuma modificação no engine necessária.
    """

    _DEFAULT_RULES: list[AuditRule] = [
        # ── Database ────────────────────────────────────────────────────────
        AuditRule(
            rule_id="DB001",
            pattern=r"for\s+\w+\s+in\s+\w+\.objects\.all\(\)",
            description="N+1 query: iteração sobre QuerySet sem select_related/prefetch_related",
            severity=Severity.HIGH,
            category=Category.DATABASE,
            remediation="Use select_related() ou prefetch_related() antes do loop.",
        ),
        AuditRule(
            rule_id="DB002",
            pattern=r"\.all\(\)(?![\s\S]*?select_related|prefetch_related).*(?:for|list\()",
            description="QuerySet .all() sem otimização de JOIN detectado",
            severity=Severity.HIGH,
            category=Category.DATABASE,
            remediation="Adicione .select_related() ou .only() para limitar colunas.",
        ),
        AuditRule(
            rule_id="DB003",
            pattern=r"\.filter\(.*\).*\.count\(\)",
            description="Potencial .filter().count() — prefira .exists() para verificação booleana",
            severity=Severity.LOW,
            category=Category.DATABASE,
            remediation="Substitua por .exists() quando apenas verificar existência.",
        ),

        # ── Loop ─────────────────────────────────────────────────────────────
        AuditRule(
            rule_id="LP001",
            pattern=r"for\s+\w+\s+in\s+range\s*\(\s*len\s*\(",
            description="Anti-pattern: for i in range(len(...)) — use enumerate()",
            severity=Severity.MEDIUM,
            category=Category.LOOP,
            remediation="Substitua por: for i, item in enumerate(collection)",
        ),
        AuditRule(
            rule_id="LP002",
            pattern=r"while\s+True\s*:",
            description="Loop infinito sem break explícito visível — possível runaway",
            severity=Severity.HIGH,
            category=Category.LOOP,
            remediation="Garanta condição de saída clara ou use itertools/geradores.",
        ),
        AuditRule(
            rule_id="LP003",
            pattern=r"\.append\s*\(.*\)\s*$",
            description="Loop com .append() — list comprehension ou extend() pode ser mais eficiente",
            severity=Severity.LOW,
            category=Category.LOOP,
            remediation="Considere: result = [expr for item in collection]",
        ),

        # ── I/O ──────────────────────────────────────────────────────────────
        AuditRule(
            rule_id="IO001",
            pattern=r"time\.sleep\s*\(",
            description="sleep() bloqueante em thread principal — considere asyncio.sleep()",
            severity=Severity.MEDIUM,
            category=Category.IO,
            remediation="Use asyncio.sleep() em contexto assíncrono; se síncrono, justifique.",
        ),
        AuditRule(
            rule_id="IO002",
            pattern=r"print\s*\(",
            description="print() em produção — overhead de I/O e ausência de structured logging",
            severity=Severity.LOW,
            category=Category.IO,
            remediation="Substitua por logger.debug/info do iaglobal.",
        ),
        AuditRule(
            rule_id="IO003",
            pattern=r"(?:pandas|pd)\.read_csv\s*\([^)]*\)(?!.*chunksize)",
            description="read_csv() sem chunksize — risco de OOM em arquivos grandes",
            severity=Severity.MEDIUM,
            category=Category.IO,
            remediation="Use pd.read_csv(path, chunksize=10_000) e processe iterativamente.",
        ),
        AuditRule(
            rule_id="IO004",
            pattern=r"json\.loads?\s*\(",
            description="json.load() síncrono — sem streaming para payloads grandes",
            severity=Severity.MEDIUM,
            category=Category.IO,
            remediation="Para payloads > 1MB, use ijson para streaming ou valide tamanho antes.",
        ),
        AuditRule(
            rule_id="IO005",
            pattern=r"open\s*\(.*\)(?!.*with\b)",
            description="open() fora de context manager — risco de file descriptor leak",
            severity=Severity.HIGH,
            category=Category.IO,
            remediation="Sempre use: with open(...) as f:",
        ),

        # ── Memory ───────────────────────────────────────────────────────────
        AuditRule(
            rule_id="MM001",
            pattern=r"copy\.deepcopy\s*\(",
            description="deepcopy() é O(n) e caro para objetos complexos",
            severity=Severity.MEDIUM,
            category=Category.MEMORY,
            remediation="Avalie se shallow copy ou imutabilidade (dataclass frozen) resolve.",
        ),
        AuditRule(
            rule_id="MM002",
            pattern=r"list\s*\(\s*\w+\.objects\.",
            description="Materialização de QuerySet inteiro em list() — risco de OOM",
            severity=Severity.HIGH,
            category=Category.MEMORY,
            remediation="Use iterator() ou paginação com Paginator.",
        ),
        AuditRule(
            rule_id="MM003",
            pattern=r"\.sort\s*\(\s*\)",
            description=".sort() in-place em lista potencialmente grande — avaliar sorted()",
            severity=Severity.LOW,
            category=Category.MEMORY,
            remediation="Use sorted() para preservar original; heapq para top-K.",
        ),

        # ── Concurrency ──────────────────────────────────────────────────────
        AuditRule(
            rule_id="CC001",
            pattern=r"threading\.Lock\s*\(\s*\)",
            description="Lock em hot path — possível contenção e serialização de threads",
            severity=Severity.MEDIUM,
            category=Category.CONCURRENCY,
            remediation="Considere RLock, asyncio.Lock, ou estruturas lock-free (queue.Queue).",
        ),
        AuditRule(
            rule_id="CC002",
            pattern=r"global\s+\w+",
            description="Variável global mutável — risco de race condition em multi-threading",
            severity=Severity.MEDIUM,
            category=Category.CONCURRENCY,
            remediation="Use threading.local() ou encapsule em classe com lock.",
        ),
    ]

    def __init__(self) -> None:
        self._rules: dict[str, AuditRule] = {r.rule_id: r for r in self._DEFAULT_RULES}

    def register(self, rule: AuditRule) -> None:
        """Registra regra customizada — sem modificar o engine."""
        if rule.rule_id in self._rules:
            logger.warning("⚠️  [REGISTRY] Sobrescrevendo regra existente: %s", rule.rule_id)
        self._rules[rule.rule_id] = rule
        logger.debug("✅ [REGISTRY] Regra registrada: %s", rule.rule_id)

    def all_rules(self) -> list[AuditRule]:
        return list(self._rules.values())

    def by_category(self, category: Category) -> list[AuditRule]:
        return [r for r in self._rules.values() if r.category == category]


# ---------------------------------------------------------------------------
# RecidivismTracker — memória estrutural de padrões
# ---------------------------------------------------------------------------

class RecidivismTracker:
    """
    Extrai rule_ids de padrões já detectados a partir do error_context.
    Substitui o string matching frágil do agente original.
    """

    _CONTEXT_SIGNALS: dict[str, list[str]] = {
        "n+1":         ["DB001", "DB002"],
        "query":       ["DB001", "DB002", "DB003"],
        "loop":        ["LP001", "LP002", "LP003"],
        "sleep":       ["IO001"],
        "deepcopy":    ["MM001"],
        "lock":        ["CC001"],
        "global":      ["CC002"],
        "read_csv":    ["IO003"],
        "json":        ["IO004"],
        "open(":       ["IO005"],
        "oom":         ["MM002"],
        "memory":      ["MM001", "MM002"],
    }

    def extract_recidivism_ids(self, error_context: str) -> set[str]:
        if not error_context:
            return set()
        ctx_lower = error_context.lower()
        recidivism: set[str] = set()
        for signal, rule_ids in self._CONTEXT_SIGNALS.items():
            if signal in ctx_lower:
                recidivism.update(rule_ids)
        return recidivism


# ---------------------------------------------------------------------------
# AuditEngine — núcleo de detecção
# ---------------------------------------------------------------------------

@runtime_checkable
class IAuditEngine(Protocol):
    def scan(self, code: str, rules: list[AuditRule],
             recidivism_ids: set[str]) -> list[Finding]: ...


class RegexAuditEngine:
    """
    Engine primário: regex com line-hint tracking.
    Detecta ocorrências linha a linha para rastreabilidade.
    """

    def scan(
        self,
        code: str,
        rules: list[AuditRule],
        recidivism_ids: set[str],
    ) -> list[Finding]:
        lines = code.splitlines()
        findings: list[Finding] = []

        for rule in rules:
            compiled = re.compile(rule.pattern, rule.flags)
            line_hints: list[int] = []

            for lineno, line in enumerate(lines, start=1):
                if compiled.search(line):
                    line_hints.append(lineno)

            if line_hints:
                findings.append(Finding(
                    rule_id=rule.rule_id,
                    description=rule.description,
                    severity=rule.severity,
                    category=rule.category,
                    remediation=rule.remediation,
                    recidivism=(rule.rule_id in recidivism_ids),
                    line_hints=line_hints,
                ))

        return findings


class StructuralAnalyzer:
    """
    Análise estrutural além de regex: tamanho, complexidade ciclomática,
    profundidade de aninhamento, densidade de comentários.
    """

    CONTROL_FLOW_TOKENS = frozenset({
        "for ", "while ", "if ", "elif ", "except",
        "with ", "def ", "class ", "async def", "async for",
        "async with",
    })

    def analyze(self, code: str) -> list[str]:
        flags: list[str] = []
        lines = [l.rstrip() for l in code.splitlines()]
        non_empty = [l for l in lines if l.strip()]

        # Tamanho
        if len(lines) > 500:
            flags.append(
                f"STRUCT001: Arquivo com {len(lines)} linhas — modularize em sub-agentes "
                f"seguindo o padrão PhospholipidRegistry do iaglobal."
            )

        # Complexidade ciclomática aproximada
        cc = sum(
            1 for l in lines
            if any(l.lstrip().startswith(tok) for tok in self.CONTROL_FLOW_TOKENS)
        )
        if cc > 40:
            flags.append(
                f"STRUCT002: Complexidade ciclomática ≈ {cc} — "
                f"limite recomendado é 15 por função. Extraia métodos."
            )

        # Profundidade de aninhamento (heurística por indentação)
        max_depth = max(
            (len(l) - len(l.lstrip())) // 4
            for l in non_empty if l.strip()
        ) if non_empty else 0
        if max_depth > 5:
            flags.append(
                f"STRUCT003: Profundidade de aninhamento ≈ {max_depth} níveis — "
                f"refatore com early return ou decomposição de funções."
            )

        # Densidade de comentários
        comment_lines = sum(1 for l in lines if l.lstrip().startswith("#"))
        if non_empty and (comment_lines / len(non_empty)) < 0.05 and len(lines) > 100:
            flags.append(
                "STRUCT004: Baixa densidade de comentários (< 5%) em arquivo extenso — "
                "docstrings e comentários são parte do contrato de manutenibilidade."
            )

        # Funções longas (heurística: defs seguidas de muitas linhas sem nova def)
        def_positions = [i for i, l in enumerate(lines) if l.lstrip().startswith("def ")]
        for i, pos in enumerate(def_positions):
            end = def_positions[i + 1] if i + 1 < len(def_positions) else len(lines)
            func_len = end - pos
            if func_len > 60:
                flags.append(
                    f"STRUCT005: Função em linha {pos + 1} com ≈ {func_len} linhas — "
                    f"extraia responsabilidades menores (SRP)."
                )
                break  # reportar apenas o primeiro para não sobrecarregar

        return flags


# ---------------------------------------------------------------------------
# SeverityScorer — scoring ponderado e normalizado
# ---------------------------------------------------------------------------

class SeverityScorer:
    """
    Calcula risk_score normalizado (0-100) com base em severidade efetiva.
    Penaliza reincidências multiplicativamente.
    """

    _MAX_SCORE = 200  # teto teórico para normalização

    def compute(self, findings: list[Finding]) -> tuple[dict[str, int], int]:
        severity_count: dict[str, int] = {s.value: 0 for s in Severity}
        raw_score = 0

        for f in findings:
            eff = f.effective_severity
            severity_count[eff.value] += 1
            pts = eff.weight
            if f.recidivism:
                pts = int(pts * 1.5)  # penalidade de 50% por reincidência
            raw_score += pts

        risk_score = min(100, int((raw_score / self._MAX_SCORE) * 100))
        return severity_count, risk_score


# ---------------------------------------------------------------------------
# ReportComposer — montagem do relatório final
# ---------------------------------------------------------------------------

class ReportComposer:
    def compose(
        self,
        findings: list[Finding],
        severity_count: dict[str, int],
        risk_score: int,
        structural_flags: list[str],
        recidivism_ids: set[str],
    ) -> AuditReport:
        recidivism_flags = [
            f"⚠️  Reincidência detectada: {f.rule_id} — {f.description}"
            for f in findings if f.recidivism
        ]
        return AuditReport(
            total_findings=len(findings),
            severity_count=severity_count,
            risk_score=risk_score,
            findings=findings,
            structural_flags=structural_flags,
            recidivism_flags=recidivism_flags,
        )


# ---------------------------------------------------------------------------
# PerformanceAuditAgent — orquestrador com integração biológica
# ---------------------------------------------------------------------------

class PerformanceAuditAgent:
    """
    Agente de auditoria de performance — Geração 8.

    Integração biológica:
      - Loga via GlutathioneLayer (proteção/imunidade contra regressões)
      - Emite reincidências ao MTARecycler via error_context estruturado
      - Regras extensíveis via PatternRegistry (AcetylcholineBus-ready)
      - Relatório tipado compatível com SkillStore e CoderAgent

    Responsabilidades orquestradas (não acopladas):
      PatternRegistry    → catálogo de regras
      RecidivismTracker  → memória de padrões anteriores
      RegexAuditEngine   → detecção primária
      StructuralAnalyzer → análise estrutural
      SeverityScorer     → scoring ponderado
      ReportComposer     → relatório final
    """

    def __init__(
        self,
        registry:   PatternRegistry   | None = None,
        engine:     IAuditEngine       | None = None,
        structural: StructuralAnalyzer | None = None,
        scorer:     SeverityScorer     | None = None,
        composer:   ReportComposer     | None = None,
    ) -> None:
        self._registry   = registry   or PatternRegistry()
        self._engine     = engine     or RegexAuditEngine()
        self._structural = structural or StructuralAnalyzer()
        self._scorer     = scorer     or SeverityScorer()
        self._composer   = composer   or ReportComposer()
        self._recidivism = RecidivismTracker()

    # ── Public API ──────────────────────────────────────────────────────────

    def register_rule(self, rule: AuditRule) -> None:
        """Extensão em runtime — adicione regras sem reinicializar o agente."""
        self._registry.register(rule)

    def audit(
        self,
        code: str,
        performance_requirements: list,
        knowledge_context: str = "",
        error_context: str = "",
    ) -> dict:
        """
        Audita código contra requisitos de performance.

        Returns:
            dict retrocompatível com o contrato legado do iaglobal
            (performance_audit_report + bottlenecks).
        """
        logger.info("📊 [PERF-AUDIT] Iniciando auditoria — %d bytes de código", len(code))

        # 1. Extração de reincidências estruturais
        recidivism_ids = self._recidivism.extract_recidivism_ids(error_context)
        if recidivism_ids:
            logger.warning(
                "🔴 [PERF-AUDIT] Reincidências detectadas via error_context: %s",
                recidivism_ids,
            )

        # 2. Logging de contextos disponíveis
        if knowledge_context:
            logger.debug(
                "📚 [PERF-AUDIT] knowledge_context disponível: %d chars",
                len(knowledge_context),
            )
        if error_context:
            logger.debug(
                "🧬 [PERF-AUDIT] error_context disponível: %d chars — alimentando RecidivismTracker",
                len(error_context),
            )

        # 3. Varredura de padrões
        rules    = self._registry.all_rules()
        findings = self._engine.scan(code, rules, recidivism_ids)
        logger.info("🔍 [PERF-AUDIT] %d findings detectados", len(findings))

        # 4. Análise estrutural
        structural_flags = self._structural.analyze(code)
        if structural_flags:
            logger.info("🏗️  [PERF-AUDIT] %d flags estruturais", len(structural_flags))

        # 5. Scoring
        severity_count, risk_score = self._scorer.compute(findings)
        logger.info(
            "🎯 [PERF-AUDIT] Risk score: %d/100 | Severos: %d | Médios: %d | Baixos: %d",
            risk_score,
            severity_count.get(Severity.HIGH.value, 0) + severity_count.get(Severity.CRITICAL.value, 0),
            severity_count.get(Severity.MEDIUM.value, 0),
            severity_count.get(Severity.LOW.value, 0),
        )

        # 6. Composição do relatório
        report = self._composer.compose(
            findings, severity_count, risk_score, structural_flags, recidivism_ids
        )

        # 7. Alerta de imunidade (GlutathioneLayer)
        if risk_score >= 70:
            logger.critical(
                "🚨 [GLUTATHIONE] Risk score crítico (%d) — ativando camada de proteção",
                risk_score,
            )
        elif risk_score >= 40:
            logger.warning(
                "⚠️  [GLUTATHIONE] Risk score elevado (%d) — revisão recomendada",
                risk_score,
            )

        return report.to_legacy_dict()
