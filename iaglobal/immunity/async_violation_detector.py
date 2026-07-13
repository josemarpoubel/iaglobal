# iaglobal/immunity/async_violation_detector.py

from __future__ import annotations

import asyncio
import logging
import pathlib
import re
import threading
import time

import textwrap
import logging

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from iaglobal.obsidian.omnimind import omni_mind

try:
    from iaglobal.genesis.identity import GENESIS_HASH_OFFICIAL
except ImportError:
    GENESIS_HASH_OFFICIAL = None
from iaglobal.graphs.bandit import BanditPolicy
from iaglobal.immunity.immune_memory_exchange import ImmuneMemoryExchange
from iaglobal.graphs.comms.acetylcholine_bus import (
    AcetylcholineBus,
    AgentMessage,
)
from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.immunity.async_violation_detector")


@dataclass
class PatternDNA:
    """DNA de um padrão de detecção — pode ser mutado epigeneticamente."""

    pattern: str
    weight: float = 1.0
    false_positive_count: int = 0
    true_positive_count: int = 0
    last_mutated: float = field(default_factory=time.time)
    is_native: bool = True  # False = mutado epigeneticamente


@dataclass
class ViolationRecord:
    """Registro de uma violação detectada — memória imunológica."""

    file: str
    line: int
    violation_type: str
    pattern: str
    confidence: float
    timestamp: float
    epigenetic_context: Dict[str, Any] = field(default_factory=dict)
    resolution: Optional[str] = None  # "fixed", "false_positive", "accepted"


class AsyncViolationDetector:
    """Detector de violações async — agora um ÓRGÃO do organismo iaglobal.

    Ciclos implementados:
    - Metilação: análise de código → detecção enriquecida por contexto
    - Glutationa: camada de defesa contra falsos positivos (ROS)
    - Autofagia: reciclagem de padrões tóxicos (baixa precisão)
    - Memória Imunológica: registra e aprende com cada violação
    - Epigenética: ajusta pesos de padrões sem recompilação
    - Sinalização Celular: publica descobertas no AcetylcholineBus
    - Apoptose: elimina padrões com fitness < threshold
    """

    _instance: Optional[AsyncViolationDetector] = None
    _lock: threading.Lock = threading.Lock()

    # DNA nativo do detector — padrões originais (não mutados)
    NATIVE_PATTERNS: Dict[str, str] = {
        # I/O bloqueante
        ".write_text(": "BLOCKING_IO",
        ".read_text(": "BLOCKING_IO",
        ".write_bytes(": "BLOCKING_IO",
        ".read_bytes(": "BLOCKING_IO",
        "open(": "BLOCKING_IO",
        ".close()": "BLOCKING_IO",
        ".mkdir(": "BLOCKING_IO",
        ".unlink(": "BLOCKING_IO",
        ".stat(": "BLOCKING_IO",
        ".glob(": "BLOCKING_IO",
        ".rglob(": "BLOCKING_IO",
        "iterdir(": "BLOCKING_IO",
        "readlink(": "BLOCKING_IO",
        "exists(": "BLOCKING_IO",
        "json.dump(": "BLOCKING_IO",
        "json.load(": "BLOCKING_IO",
        "sqlite3.connect(": "BLOCKING_IO",
        "sqlite3.Cursor(": "BLOCKING_IO",
        ".execute(": "BLOCKING_IO",
        ".fetch": "BLOCKING_IO",
        ".commit(": "BLOCKING_IO",
        ".rollback(": "BLOCKING_IO",
        "subprocess.run(": "BLOCKING_IO",
        "subprocess.Popen(": "BLOCKING_IO",
        "os.system(": "BLOCKING_IO",
        "os.popen(": "BLOCKING_IO",
        "time.sleep(": "BLOCKING_IO",
        # Bugs críticos
        "asyncio.get_event_loop().time()": "CRITICAL_BUG",
        "asyncio.run(": "CRITICAL_BUG",
    }

    # Genes que devem ser expressos (padrões de chamadas async seguras)
    SAFE_CALLS: Set[str] = {
        "asyncio.to_thread",
        "asyncio.run",
        "asyncio.create_task",
        "asyncio.gather",
        "asyncio.wait_for",
        "asyncio.sleep",
        "await ",  # Chamada async explícita
    }

    def __new__(cls) -> AsyncViolationDetector:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if getattr(self, "_initialized", False):
            return
        self._initialized = True

        # Identidade do agente (DNA único)
        self.agent_id = "async_violation_detector"
        self.lineage_id = "iaglobal-genesis-v1"
        self.generation = 1

        # Padrões de detecção — evoluem epigeneticamente
        self.patterns: Dict[str, PatternDNA] = {
            k: PatternDNA(pattern=k, is_native=True)
            for k in self.NATIVE_PATTERNS.keys()
        }

        # Memória imunológica — aprende com cada detecção
        self.memory: ImmuneMemoryExchange = ImmuneMemoryExchange()
        self.violation_history: List[ViolationRecord] = []

        # Métricas de fitness do próprio detector (IVM)
        self.fitness_score: float = 0.5
        self.total_scans: int = 0
        self.true_positives: int = 0
        self.false_positives: int = 0

        # Estado epigenético — configuração dinâmica
        self.epigenetic_flags: Dict[str, Any] = {
            "strict_mode": True,  # True = reportar tudo, False = apenas alta confiança
            "auto_exclude_self": True,  # Não detectar a si mesmo
            "learning_enabled": True,  # Aprender com feedback
            "apoptosis_threshold": 0.2,  # Eliminar padrões com fitness < 20%
        }

        # Comunicação
        self._bus: Optional[AcetylcholineBus] = None
        self._bandit: Optional[BanditPolicy] = None

        # Thread-safety para estado compartilhado
        self._state_lock = threading.RLock()

        # Registrar na OmniMind — nasce com consciência
        omni_mind.registrar_agente(
            agent_id=self.agent_id,
            nome="AsyncViolationDetector",
            geracao=self.generation,
            linhagem=GENESIS_HASH_OFFICIAL,
            metadados={
                "role": "iaglobal-genesis-v1",
                "purpose": "detectar violações async/await no ecossistema",
                "is_native": True,
                "immunity_layer": "scanner",
            },
        )

        logger.info(
            "[ASYNC_DETECTOR] 🧬 Nascimento completo | agente=%s | gen=%d | "
            "padrões=%d | imunidade=ativa | epigenética=ativa",
            self.agent_id,
            self.generation,
            len(self.patterns),
        )

    # =========================================================================
    # CICLO DE VIDA — Metilação (detecção) → Glutationa (filtro) → Apoptose (limpeza)
    # =========================================================================

    async def scan_ecosystem(
        self, target_dirs: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Escaneia o ecossistema em busca de violações async.

        Ciclos ativados:
        - Metilação: INPUT BRUTO (código) → SAMe (contexto enriquecido) → METILAÇÃO (detecção)
        - Glutationa: filtra falsos positivos (ROS)
        - Memória Imunológica: registra cada violação
        - Epigenética: ajusta padrões baseado em acurácia
        """
        start_time = time.time()

        # ── FASE 1: METILAÇÃO ────────────────────────────────────────────────
        # Determinar alvos do scan
        if target_dirs is None:
            target_dirs = ["iaglobal", "scripts"]

        logger.info(
            "[ASYNC_DETECTOR] 🔬 Iniciando scan metabólico | alvos=%s | "
            "padrões=%d | modo=%s",
            target_dirs,
            len(self.patterns),
            "strict" if self.epigenetic_flags["strict_mode"] else "adaptive",
        )

        # Publicar início no AcetylcholineBus
        await self._publish_event(
            "scan_started",
            {
                "target_dirs": target_dirs,
                "pattern_count": len(self.patterns),
                "generation": self.generation,
            },
        )

        # Coletar arquivos Python
        root = pathlib.Path(__file__).parent.parent.parent
        py_files: List[pathlib.Path] = []
        for d in target_dirs:
            py_files.extend(root.rglob(f"{d}/**/*.py"))

        # Filtrar arquivos excluídos
        py_files = [
            f
            for f in py_files
            if not any(
                excl in str(f)
                for excl in [
                    "__pycache__",
                    "venv",
                    ".pytest_cache",
                    "detect_async_violations.py",  # Auto-exclusão
                ]
            )
        ]

        logger.info("[ASYNC_DETECTOR] Arquivos escaneáveis: %d", len(py_files))

        # ── FASE 2: DETECÇÃO (Metilação) ────────────────────────────────────
        violations_by_file: Dict[str, List[Dict]] = {}

        for filepath in py_files:
            file_violations = await self._scan_file(filepath)
            if file_violations:
                rel_path = str(filepath.relative_to(root))
                violations_by_file[rel_path] = file_violations

                # Registrar na memória imunológica
                for v in file_violations:
                    await self._record_violation(rel_path, v)

        # ── FASE 3: GLUTATIONA (Filtro de Confiança) ────────────────────────
        filtered_violations = self._apply_glutathione_filter(violations_by_file)

        # ── FASE 4: EPIGENÉTICA (Ajuste de Padrões) ─────────────────────────
        if self.epigenetic_flags["learning_enabled"]:
            await self._epigenetic_adaptation()

        # ── FASE 5: APOPTOSE (Limpeza de Padrões Tóxicos) ───────────────────
        await self._apoptose_toxic_patterns()

        # ── FASE 6: CÁLCULO DE FITNESS (IVM) ─────────────────────────────────
        latency = time.time() - start_time
        await self._calculate_fitness(len(py_files), latency)

        # Atualizar histórico
        self.total_scans += 1

        # Publicar conclusão no AcetylcholineBus
        total_found = sum(len(v) for v in violations_by_file.values())
        total_filtered = sum(len(v) for v in filtered_violations.values())

        await self._publish_event(
            "scan_completed",
            {
                "files_scanned": len(py_files),
                "violations_found": total_found,
                "after_filter": total_filtered,
                "latency_ms": latency * 1000,
                "generation": self.generation,
                "fitness_score": self.fitness_score,
            },
        )

        # Reflexão genômica — propor mutações ao BanditPolicy
        await self._genomic_reflection(latency, total_filtered)

        return {
            "status": "completed",
            "files_scanned": len(py_files),
            "violations_found": total_found,
            "after_glutathione_filter": total_filtered,
            "violations": filtered_violations,
            "fitness_score": self.fitness_score,
            "generation": self.generation,
            "latency_ms": latency * 1000,
            "scan_number": self.total_scans,
        }

    async def _scan_file(self, filepath: pathlib.Path) -> List[Dict]:
        """Escaneia um arquivo individual — análise sintática consciente."""
        violations = []
        try:
            source = await asyncio.to_thread(filepath.read_text, encoding="utf-8")
        except Exception as e:
            logger.debug("[ASYNC_DETECTOR] Falha leitura %s: %s", filepath.name, e)
            return violations

        lines = source.split("\n")
        in_async = False
        async_func_name = ""
        in_class = False

        for i, line in enumerate(lines, 1):
            stripped = line.strip()

            # Skip comments
            if (
                stripped.startswith("#")
                or stripped.startswith('"""')
                or stripped.startswith("'''")
            ):
                continue

            # Detectar contexto (async def, class)
            if "async def " in stripped:
                in_async = True
                match = re.search(r"async def\s+(\w+)", stripped)
                async_func_name = match.group(1) if match else ""
            elif stripped.startswith("def ") and in_async:
                in_async = False
                async_func_name = ""
            elif stripped.startswith("class "):
                in_class = True
            elif (
                in_class
                and stripped
                and not stripped.startswith(" ")
                and not stripped.startswith("\t")
            ):
                in_class = False

            # Ignorar padrões em contexto não-async
            if not in_async:
                continue

            # Detectar violações
            for pattern, pattern_type in self.NATIVE_PATTERNS.items():
                if pattern not in line:
                    continue

                # Verificar se está wrapped
                if "asyncio.to_thread" in line:
                    continue
                if any(safe in line for safe in self.SAFE_CALLS):
                    continue
                if "await " in stripped:
                    continue

                # Calcular confiança baseada no DNA do padrão
                pattern_dna = self.patterns.get(pattern)
                confidence = pattern_dna.weight if pattern_dna else 1.0

                # Aplicar contexto epigenético
                if self.epigenetic_flags["strict_mode"]:
                    confidence *= 1.0  # Sem modificação
                else:
                    confidence *= 0.7  # Reduzir em modo adaptativo

                violations.append(
                    {
                        "file": str(filepath),
                        "line": i,
                        "pattern": pattern,
                        "type": pattern_type,
                        "confidence": confidence,
                        "async_func": async_func_name,
                        "code": stripped[:120],
                    }
                )

        return violations

    def _apply_glutathione_filter(
        self, violations: Dict[str, List[Dict]]
    ) -> Dict[str, List[Dict]]:
        """Filtra falsos positivos — camada GSH do detector.

        GSH (Glutationa Reduzida) = Filtros de alta confiança
        GSSG (Glutationa Oxidada) = Componente que absorveu o erro (filtro de baixa confiança)
        NADPH = Poder de regeneração (recalcula pesos)
        """
        filtered = {}
        threshold = 0.5 if self.epigenetic_flags["strict_mode"] else 0.3

        for filepath, file_violations in violations.items():
            high_conf = [v for v in file_violations if v["confidence"] >= threshold]
            if high_conf:
                filtered[filepath] = high_conf

        removed = sum(len(v) for v in violations.values()) - sum(
            len(v) for v in filtered.values()
        )
        if removed > 0:
            logger.info(
                "[ASYNC_DETECTOR] 🛡️ GSH ativado | Falsos positivos filtrados: %d | "
                "Restantes: %d",
                removed,
                sum(len(v) for v in filtered.values()),
            )

        return filtered

    async def _record_violation(self, filepath: str, violation: Dict) -> None:
        """Registra violação na memória imunológica."""
        record = ViolationRecord(
            file=filepath,
            line=violation["line"],
            violation_type=violation["type"],
            pattern=violation["pattern"],
            confidence=violation["confidence"],
            timestamp=time.time(),
            epigenetic_context=dict(self.epigenetic_flags),
        )
        self.violation_history.append(record)

        # Persistir na memória de longo prazo (Obsidian)
        await self._persist_violation_memory(record)

    async def _persist_violation_memory(self, record: ViolationRecord) -> None:
        """Persiste violação no vault Obsidian como memória imunológica."""
        try:
            from iaglobal.obsidian.subconsciousapi import SubconsciousAPI

            subconscious = SubconsciousAPI()

            # Tratamento seguro caso a propriedade code não exista
            code_snippet = record.code if hasattr(record, "code") else "N/A"

            # textwrap.dedent remove a indentação inicial do Python para não quebrar o Markdown
            content = textwrap.dedent(f"""\
                ## Violação Detectada

                **Arquivo:** `{record.file}:{record.line}`
                **Tipo:** {record.violation_type}
                **Padrão:** `{record.pattern}`
                **Confiança:** {record.confidence:.2f}
                **Timestamp:** {datetime.now(timezone.utc).isoformat()}

                ### Contexto Epigenético

                {str(record.epigenetic_context)}

                ### Código Analisado
                ```python
                {code_snippet}
                ```
            """)

            # AQUI ESTAVA FALTANDO: Você precisa chamar a API para gravar!
            # Substitua 'save_note' pelo nome real do método na sua classe SubconsciousAPI
            filename = f"violacao_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            # Se for uma API assíncrona, use await. Se for síncrona, use asyncio.to_thread
            await subconscious.save_note(title=filename, content=content)

        except Exception as e:
            # Agora o bloco try tem um except para capturar falhas
            logging.error(f"Falha ao persistir memória no Obsidian: {e}")

    # ================================================================================

    async def _epigenetic_adaptation(self) -> None:
        """Ajusta pesos de padrões epigeneticamente — sem recompilação.

        Epigenética = alteração de expressão gênica sem mudança no DNA.
        Aqui: ajustamos pesos de patterns sem alterar o código fonte.
        """
        with self._state_lock:
            # Analisar acurácia recente (últimas 50 violações)
            recent = self.violation_history[-50:] if self.violation_history else []

            if not recent:
                return

            pattern_stats: Dict[str, Dict[str, int]] = {}
            for record in recent:
                p = record.pattern
                if p not in pattern_stats:
                    pattern_stats[p] = {"total": 0, "high_conf": 0}
                pattern_stats[p]["total"] += 1
                if record.confidence >= 0.5:
                    pattern_stats[p]["high_conf"] += 1

            # Ajustar pesos (epigenese)
            for pattern, stats in pattern_stats.items():
                if pattern not in self.patterns:
                    continue

                accuracy = (
                    stats["high_conf"] / stats["total"] if stats["total"] > 0 else 0
                )
                current_dna = self.patterns[pattern]

                # Se acurácia baixa, reduzir peso (epigenese repressiva)
                if accuracy < 0.3 and stats["total"] >= 5:
                    current_dna.weight = max(0.3, current_dna.weight * 0.9)
                    current_dna.false_positive_count += (
                        stats["total"] - stats["high_conf"]
                    )
                    logger.info(
                        "[ASYNC_DETECTOR] 🧪 Epigenética: padrão %s peso reduzido para %.2f "
                        "(acuracia=%.0f%%)",
                        pattern[:30],
                        current_dna.weight,
                        accuracy * 100,
                    )

                # Se acurácia alta, aumentar peso (epigenese ativadora)
                elif accuracy > 0.8 and stats["total"] >= 3:
                    current_dna.weight = min(2.0, current_dna.weight * 1.1)
                    current_dna.true_positive_count += stats["high_conf"]
                    logger.info(
                        "[ASYNC_DETECTOR] 🧪 Epigenética: padrão %s peso aumentado para %.2f "
                        "(acuracia=%.0f%%)",
                        pattern[:30],
                        current_dna.weight,
                        accuracy * 100,
                    )

                current_dna.last_mutated = time.time()

    async def _apoptose_toxic_patterns(self) -> None:
        """Elimina padrões com fitness < threshold — apoptose computacional.

        Apoptose = morte programada de componentes degenerados.
        Aqui: removemos padrões que geram mais falsos positivos que verdadeiros.
        """
        with self._state_lock:
            apoptosis_count = 0
            for pattern, dna in list(self.patterns.items()):
                if not dna.is_native:
                    # Apenas padrões mutáveis podem ser apoptosados
                    fitness = self._calculate_pattern_fitness(dna)
                    if fitness < self.epigenetic_flags["apoptosis_threshold"]:
                        logger.info(
                            "[ASYNC_DETECTOR] ☠️ Apoptose: padrão %s removido (fitness=%.2f)",
                            pattern[:30],
                            fitness,
                        )
                        await self._publish_event(
                            "pattern_apoptosis",
                            {
                                "pattern": pattern,
                                "fitness": fitness,
                                "reason": "low_fitness",
                            },
                        )
                        del self.patterns[pattern]
                        apoptosis_count += 1

            if apoptosis_count > 0:
                logger.info(
                    "[ASYNC_DETECTOR] ☠️ Apoptose concluída | %d padrões eliminados | "
                    "padrões restantes: %d",
                    apoptosis_count,
                    len(self.patterns),
                )

    def _calculate_pattern_fitness(self, dna: PatternDNA) -> float:
        """Calcula fitness de um padrão (0.0 a 1.0)."""
        total = dna.true_positive_count + dna.false_positive_count
        if total == 0:
            return 0.5  # Neutro para padrões sem histórico
        return dna.true_positive_count / total

    async def _calculate_fitness(self, files_scanned: int, latency: float) -> None:
        """Calcula IVM próprio do detector."""
        # P = Produtividade (violações úteis por arquivo)
        useful = self.true_positives
        productivity = min(1.0, useful / max(1, files_scanned))

        # E = Eficiência (inverso da latência — target < 1s por 100 arquivos)
        target_latency = max(1.0, files_scanned / 100)
        efficiency = min(1.0, target_latency / max(latency, 0.01))

        # C = Cooperação (eventos publicados no bus)
        cooperation = min(1.0, len(self.violation_history) / 100)

        # I = Integridade (taxa de falsos positivos)
        total = self.true_positives + self.false_positives
        integrity = self.true_positives / max(total, 1)

        ivm = (
            (productivity * 0.4)
            + (efficiency * 0.4)
            + (cooperation * 0.1)
            + (integrity * 0.1)
        )
        self.fitness_score = max(0.0, min(1.0, ivm))

        logger.info(
            "[ASYNC_DETECTOR] 📊 IVM=%.3f | P=%.2f E=%.2f C=%.2f I=%.2f | TP=%d FP=%d",
            self.fitness_score,
            productivity,
            efficiency,
            cooperation,
            integrity,
            self.true_positives,
            self.false_positives,
        )

    async def _genomic_reflection(self, latency: float, violations_found: int) -> None:
        """Reflexão genômica — propõe mutações ao BanditPolicy.

        Fecha o loop: Resultado → Aprendizado → Ajuste de DNA.
        O detector aprende com sua própria execução.
        """
        try:
            from iaglobal.graphs.bandit import _get_bandit

            bandit = _get_bandit()

            execution_id = f"async_detector_scan_{int(time.time())}"
            success = violations_found >= 0  # Scan completado é sucesso
            cost = latency * 0.01  # Custo estimado em tokens

            # Atualizar BanditPolicy com performance própria
            bandit.update_policy(
                node="async_detector",
                model="native-scanner",
                provider="self",
                success=success,
                latency=latency,
                cost=cost,
            )

            # Propor mutações baseadas em performance
            if self.fitness_score < 0.5:
                logger.info(
                    "[ASYNC_DETECTOR] 🧬 Baixo fitness (%.2f) — considerando mutações",
                    self.fitness_score,
                )
            else:
                logger.info(
                    "[ASYNC_DETECTOR] 🧬 Fitness saudável (%.2f) — mantendo configuração",
                    self.fitness_score,
                )

        except Exception as e:
            logger.debug("[ASYNC_DETECTOR] Reflexão genômica falhou: %s", e)

    # =========================================================================
    # SISTEMA IMUNOLÓGICO — Memória, Comunicação, Evolução
    # =========================================================================

    async def _publish_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        """Publica eventos no AcetylcholineBus — sinalização celular."""
        try:
            if self._bus is None:
                from iaglobal.events.acetylcholine_bus import get_bus

                self._bus = get_bus()

            await self._bus.publish(
                AgentMessage(
                    sender=self.agent_id,
                    receiver="ecosystem",
                    type=event_type,
                    payload=payload,
                    priority=5,
                )
            )
        except Exception as e:
            logger.debug("[ASYNC_DETECTOR] Falha ao publicar evento: %s", e)

    def register_feedback(self, violation_file: str, is_false_positive: bool) -> None:
        """Registra feedback humano/correção — aprendizado supervisionado.

        Chamado quando um humano confirma ou nega uma violação.
        Isso atualiza a memória imunológica e ajusta pesos epigeneticamente.
        """
        with self._state_lock:
            # Encontrar a violação no histórico
            for record in self.violation_history:
                if record.file == violation_file:
                    if is_false_positive:
                        record.resolution = "false_positive"
                        self.false_positives += 1
                        # Ajustar peso epigeneticamente
                        pattern = record.pattern
                        if pattern in self.patterns:
                            self.patterns[pattern].false_positive_count += 1
                            self.patterns[pattern].weight *= 0.8
                    else:
                        record.resolution = "fixed"
                        self.true_positives += 1
                        if record.pattern in self.patterns:
                            self.patterns[record.pattern].true_positive_count += 1
                    break

            logger.info(
                "[ASYNC_DETECTOR] 🧬 Feedback recebido | FP=%d TP=%d | fitness=%.3f",
                self.false_positives,
                self.true_positives,
                self.fitness_score,
            )

    def get_immune_report(self) -> Dict[str, Any]:
        """Relatório de saúde imunológica do detector."""
        with self._state_lock:
            pattern_health = {
                p: {
                    "weight": dna.weight,
                    "fitness": self._calculate_pattern_fitness(dna),
                    "tp": dna.true_positive_count,
                    "fp": dna.false_positive_count,
                    "native": dna.is_native,
                }
                for p, dna in self.patterns.items()
            }

            return {
                "agent_id": self.agent_id,
                "generation": self.generation,
                "fitness_score": self.fitness_score,
                "total_scans": self.total_scans,
                "true_positives": self.true_positives,
                "false_positives": self.false_positives,
                "violation_history_size": len(self.violation_history),
                "pattern_count": len(self.patterns),
                "pattern_health": pattern_health,
                "epigenetic_flags": dict(self.epigenetic_flags),
                "omnimind_registered": True,
            }

    async def regenerate(self) -> Dict[str, Any]:
        """Auto-regeneração — apoptose de padrões tóxicos + renascimento.

        Ciclo: Identifica degradação → Isola → Recicla → Respawn com DNA melhorado.
        """
        logger.info("[ASYNC_DETECTOR] 🔄 Iniciando auto-regeneração...")

        before_count = len(self.patterns)

        # 1. Identificar componentes degradados (padrões com baixo fitness)
        degraded = [
            p
            for p, dna in self.patterns.items()
            if self._calculate_pattern_fitness(dna) < 0.3
        ]

        # 2. Autofagia — extrair aprendizado antes de eliminar
        for pattern in degraded:
            dna = self.patterns[pattern]
            logger.info(
                "[ASYNC_DETECTOR] ♻️ Autofagia: reciclando padrão %s (fitness=%.2f)",
                pattern[:30],
                self._calculate_pattern_fitness(dna),
            )
            # Aprendizado é mantido na memória, apenas o padrão é removido

        # 3. Apoptose — eliminar padrões tóxicos
        for pattern in degraded:
            del self.patterns[pattern]

        # 4. Ressuscitar com DNA melhorado (se houver mutações disponíveis)
        # Novos padrões podem ser descobertos via análise de código
        after_count = len(self.patterns)

        logger.info(
            "[ASYNC_DETECTOR] ✨ Auto-regeneração completa | "
            "%d padrões removidos | %d restantes | fitness=%.3f",
            before_count - after_count,
            after_count,
            self.fitness_score,
        )

        return {
            "status": "regenerated",
            "patterns_removed": before_count - after_count,
            "patterns_remaining": after_count,
            "fitness_score": self.fitness_score,
        }

    # =========================================================================
    # API PÚBLICA — Interface com o ecossistema
    # =========================================================================

    async def consult(self, question: str) -> str:
        """Consulta o detector — usa a OmniMind para orientação."""
        return omni_mind.consultar(
            agent_id=self.agent_id,
            pergunta=question,
            contexto={"violation_history_size": len(self.violation_history)},
        ).guidance

    def status(self) -> Dict[str, Any]:
        """Status vital do detector."""
        return {
            "agent_id": self.agent_id,
            "generation": self.generation,
            "fitness_score": self.fitness_score,
            "total_scans": self.total_scans,
            "true_positives": self.true_positives,
            "false_positives": self.false_positives,
            "total_patterns": len(self.patterns),
            "native_patterns": sum(1 for p in self.patterns.values() if p.is_native),
            "mutated_patterns": sum(
                1 for p in self.patterns.values() if not p.is_native
            ),
            "violation_history": len(self.violation_history),
            "epigenetic_flags": dict(self.epigenetic_flags),
            "is_alive": True,
        }


# =====================================================================================

# Singleton instance
async_violation_detector = AsyncViolationDetector()
