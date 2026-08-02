# ============================================================
# ARQUIVO 4: iaglobal/obsidian/consolidation.py
# CORREÇÃO: Remove imports duplicados/mortos (BUG #4, BUG #5)
#           iniciar_fase_rem e I/O tornam-se async (BUG #3)
# ============================================================
"""REMSleepEngine — Ciclo de Consolidação de Memória (Fase REM).

Simula o sono biológico:
  1. Lê memórias brutas do curto prazo (02_Short_Term)
  2. Sintetiza conhecimento via IA (ou fallback mockado)
  3. Grava no longo prazo (03_Long_Term) com links bidirecionais
  4. Remove originais (poda sináptica — Lei do Vácuo da Prosperidade)
  5. Atualiza o mapa sináptico central (MOC)

INTEGRAÇÃO CONTAMINATION_REPORT:
  - Verifica memórias de curto prazo por claims arquiteturais falsos
  - Bloqueia consolidação de contaminações no longo prazo
  - Gera report automático antes do ciclo REM

MÓDULO CENTRALIZADO: iaglobal/reflection/claim_detection.py
"""

import asyncio
import json
import logging
import sqlite3
import cbor2
from datetime import datetime, UTC, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

from iaglobal._paths import PACKAGE_DIR, MEMORIES_DB
from iaglobal.utils.life_signal_collector import instrument
from iaglobal.reflection.claim_detection import (
    detect_architectural_claims,
    verify_architectural_claims,
    create_quarantine_report,
)
from iaglobal.core.few_shot_provider import few_shot_provider

# Tabelas de staging (MEMORIES_DB) consumidas pela ponte REM. O short-name
# é usado para gerar filenames no vault (long_term) -- mantemos um map
# explícito porque rstrip por suffix é frágil (engole caracteres do
# conjunto em vez do sufixo literal).
_STAGING_TABLES = ("stm_entries", "ltm_entries")
_STAGING_SHORT_NAME = {"stm_entries": "stm", "ltm_entries": "ltm"}

logger = logging.getLogger(__name__)


class REMSleepEngine:
    """Motor de consolidação de memória — Ciclo do Sono.

    Deve ser executado periodicamente (ex: a cada 1 hora ou
    quando o fluxo de requisições estiver baixo).
    Todo I/O de disco é delegado para asyncio.to_thread para
    não bloquear o event loop durante a consolidação.
    """

    def __init__(self, vault_path: Optional[Path] = None, ai_client=None):
        self.vault_path = Path(vault_path or PACKAGE_DIR / "obsidian")
        self.short_term_dir = self.vault_path / "02_Short_Term"
        self.long_term_dir = self.vault_path / "03_Long_Term"
        self.synapses_dir = self.vault_path / "04_Synapses"
        self.quarantine_dir = self.vault_path / "00_Quarentena"
        self.ai_client = ai_client

        # Thresholds de DLQ
        self.DLQ_THRESHOLD = 3  # Mínimo de ocorrências para padrão significativo

        for d in [
            self.short_term_dir,
            self.long_term_dir,
            self.synapses_dir,
            self.quarantine_dir,
        ]:
            d.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _extract_domain(prompt_snippet: str) -> str:
        """Extrai domínio aproximado do prompt para agrupamento.

        Tolerante a null/empty strings — retorna 'general' como fallback.
        """
        if not prompt_snippet or not isinstance(prompt_snippet, str):
            return "general"

        snippet = prompt_snippet.lower()

        # Palavras-chave por domínio
        domains = {
            "api": ["api", "endpoint", "http", "rest", "graphql", "request"],
            "database": ["sql", "query", "database", "table", "insert", "select"],
            "frontend": ["react", "component", "jsx", "html", "css", "dom"],
            "security": ["auth", "token", "permission", "xss", "injection", "csrf"],
            "testing": ["test", "assert", "mock", "fixture", "pytest"],
            "async": ["async", "await", "event loop", "coroutine"],
        }

        for domain, keywords in domains.items():
            if any(kw in snippet for kw in keywords):
                return domain

        return "general"

    async def _process_quarantine_dlq(self) -> Dict[str, Any]:
        """Varre a DLQ, consolida padrões e prepara vacinas para o sistema.

        Retorna estatísticas do processamento:
        - total_files_scanned: número de arquivos JSON varridos
        - significant_patterns: padrões que atingiram o threshold
        - vaccines_injected: vacinas injetadas no FewShotProvider
        """

        def _scan_quarantine() -> Dict[str, Any]:
            """I/O síncrono isolado em thread pool."""
            if not self.quarantine_dir.exists():
                return {"total_files": 0, "patterns": []}

            patterns: Dict[str, Dict] = {}
            total_files = 0
            for fpath in self.quarantine_dir.glob("cache_poison_*.json"):
                total_files += 1
                try:
                    data = json.loads(fpath.read_text(encoding="utf-8"))
                    reason = data.get("reason", "unknown")
                    domain = REMSleepEngine._extract_domain(
                        data.get("prompt_snippet", "")
                    )

                    key = f"{reason}:{domain}"
                    if key not in patterns:
                        patterns[key] = {
                            "reason": reason,
                            "domain": domain,
                            "count": 0,
                            "snippets": [],
                            "first_seen": data.get("timestamp"),
                            "last_seen": data.get("timestamp"),
                        }
                    patterns[key]["count"] += 1
                    patterns[key]["snippets"].append(
                        data.get("prompt_snippet", "")[:100]
                    )
                    patterns[key]["last_seen"] = data.get("timestamp")
                except Exception:
                    continue

            return {
                "total_files": total_files,
                "patterns": list(patterns.values()),
            }

        # Executa I/O em thread pool (non-blocking)
        scan_result = await asyncio.to_thread(_scan_quarantine)
        patterns = scan_result["patterns"]
        total_files = scan_result["total_files"]

        # Filtra por threshold (padrões recorrentes)
        significant = [p for p in patterns if p["count"] >= self.DLQ_THRESHOLD]

        # Injeta no FewShotProvider como vacinas
        ingested = await few_shot_provider.ingest_dlq_examples(self.quarantine_dir)

        return {
            "total_files_scanned": total_files,
            "significant_patterns": len(significant),
            "vaccines_injected": ingested,
        }

    @instrument(name="remsleep.iniciar_fase_rem")
    async def iniciar_fase_rem(self) -> Dict[str, Any]:
        """Executa o ciclo completo de consolidação de forma assíncrona.

        CONTAMINATION CHECK:
          - Verifica cada memória por claims arquiteturais falsos (claim_detection.py)
          - Bloqueia consolidação se detectar contaminação
          - Move para quarentena com relatório
        """
        resultado: Dict[str, Any] = {
            "iniciado_em": datetime.now(UTC).isoformat(),
            "memorias_processadas": 0,
            "memorias_consolidadas": 0,
            "contaminacoes_bloqueadas": 0,
            "dlq_processed": None,  # NOVO: processamento da DLQ
            "erros": [],
        }

        # === NOVO: Processamento da DLQ (antes da consolidação) ===
        try:
            dlq_result = await self._process_quarantine_dlq()
            resultado["dlq_processed"] = dlq_result
            if dlq_result["vaccines_injected"]:
                logger.info(
                    "[REMSleep] DLQ vaccinated: %d padrões significativos, %d vacinas injetadas",
                    dlq_result["significant_patterns"],
                    dlq_result["vaccines_injected"],
                )

            # NOVO: Alertas de token overhead (Mutação 1C)
            from iaglobal.core.few_shot_provider import (
                few_shot_provider,
                ESTIMATED_TOKENS_PER_EXAMPLE,
            )

            negative_count = len(few_shot_provider._negative_examples)
            token_overhead = negative_count * ESTIMATED_TOKENS_PER_EXAMPLE
            resultado["token_overhead"] = token_overhead  # Métrica no retorno

            if token_overhead > 5000:
                logger.warning(
                    "[REMSleep] ⚠️ Token overhead elevado: %d tokens (%d vacinas). "
                    "Considere reduzir MAX_VACCINES ou MAX_VACCINE_AGE_DAYS.",
                    token_overhead,
                    negative_count,
                )
        except Exception as e:
            logger.exception("[REMSleep] Falha ao processar DLQ: %s", e)
            resultado["erros"].append(f"dlq_processing: {e}")
        # =========================================================

        # === NOVO: Segunda fonte de consolidacao (staging MEMORIES_DB) ===
        # O CognitiveProxy escreve em MEMORIES_DB sem saber do Obsidian.
        # Esta ponte puxa essas entradas e aplica o mesmo pipeline de
        # sintese -> grava em 03_Long_Term. Watermark "consolidated_at"
        # marca "revisado" (sucesso OU falha); autofagia separada
        # apaga o que ficou estagnado alem do horizonte.
        try:
            staging_result = await self._processar_staging_db()
            resultado["staging_processed"] = staging_result
            if staging_result.get("watermarked", 0) > 0:
                logger.info(
                    "[REMSleep] Staging DB: %d stm + %d ltm processadas, "
                    "%d sintetizadas, %d marcadas.",
                    staging_result.get("stm_entries", 0),
                    staging_result.get("ltm_entries", 0),
                    staging_result.get("synthesized", 0),
                    staging_result.get("watermarked", 0),
                )
        except Exception as e:
            logger.exception("[REMSleep] Falha ao processar staging DB: %s", e)
            resultado["staging_processed"] = {"error": str(e)}
        # =========================================================

        experiencias = await self._listar_memorias_curto_prazo()
        if not experiencias:
            resultado["status"] = "sem_memorias"
            logger.info("[REMSleep] Nenhuma memória de curto prazo para consolidar.")
            return resultado

        resultado["memorias_processadas"] = len(experiencias)
        logger.info(
            "[REMSleep] Iniciando consolidação de %d memórias.", len(experiencias)
        )

        for arquivo, conteudo in experiencias.items():
            try:
                # === CONTAMINATION CHECK PRÉ-CONSOLIDAÇÃO ===
                # 1. Detecta claims suspeitos (fonte única: claim_detection.py)
                claims_suspeitos = detect_architectural_claims(conteudo)

                if claims_suspeitos:
                    logger.warning(
                        "🚨 [REMSleep] Claims suspeitos detectados | arquivo=%s | count=%d",
                        arquivo,
                        len(claims_suspeitos),
                    )

                    # 2. Verifica claims contra código-fonte
                    verified, unverified = verify_architectural_claims(claims_suspeitos)

                    if not verified and unverified:
                        # CONTAMINAÇÃO DETECTADA!
                        logger.error(
                            "🚨 [REMSleep] Memória contaminada | arquivo=%s | claims=%d",
                            arquivo,
                            len(unverified),
                        )

                        # 3. Move para quarentena (NÃO consolida!)
                        await self._mover_para_quarentena(
                            arquivo, conteudo, claims_suspeitos
                        )

                        # 4. Remove do curto prazo
                        await self._remover_curto_prazo(arquivo)

                        resultado["contaminacoes_bloqueadas"] += 1
                        continue

                # Prossegue com consolidação normal (sem claims)
                insight = await self._solicitar_sintese_ia(conteudo)
                if insight:
                    await self._gravar_longo_prazo(arquivo, insight)
                    await self._remover_curto_prazo(arquivo)
                    resultado["memorias_consolidadas"] += 1
            except Exception as e:
                logger.exception("[REMSleep] Falha ao consolidar '%s': %s", arquivo, e)
                resultado["erros"].append(f"{arquivo}: {e}")

        await self._atualizar_mapa_conexoes()

        ingested = await few_shot_provider.ingest_dlq_examples(
            self.vault_path / "00_Quarentena"
        )
        if ingested:
            logger.info(
                "[REMSleep] DLQ vaccinated: %d exemplos negativos para FewShotProvider",
                ingested,
            )

        resultado["status"] = "concluido"
        resultado["concluido_em"] = datetime.now(UTC).isoformat()
        logger.info(
            "[REMSleep] Ciclo concluído: %d consolidadas, %d bloqueadas, %d erros.",
            resultado["memorias_consolidadas"],
            resultado["contaminacoes_bloqueadas"],
            len(resultado["erros"]),
        )
        return resultado

    async def _listar_memorias_curto_prazo(self) -> Dict[str, str]:
        """Coleta todas as notas Markdown do curto prazo de forma não-bloqueante."""

        def _read_all() -> Dict[str, str]:
            memorias = {}
            if not self.short_term_dir.exists():
                return memorias
            for f in self.short_term_dir.glob("*.md"):
                memorias[f.name] = f.read_text(encoding="utf-8")
            return memorias

        return await asyncio.to_thread(_read_all)

    async def _mover_para_quarentena(
        self,
        arquivo: str,
        conteudo: str,
        claims_suspeitos: list[Dict[str, str]],
    ) -> Path:
        """
        Move memória contaminada para quarentena em vez de consolidar.

        Usa create_quarantine_report() do módulo centralizado.

        Args:
            arquivo: Nome do arquivo
            conteudo: Conteúdo bruto
            claims_suspeitos: Lista de claims detectados

        Returns:
            Caminho do arquivo em quarentena
        """
        return create_quarantine_report(
            arquivo=arquivo,
            conteudo=conteudo,
            claims=claims_suspeitos,
            vault_path=self.vault_path,
        )

    async def _solicitar_sintese_ia(self, conteudo_bruto: str) -> Optional[str]:
        """Solicita síntese do conteúdo via IA ou usa fallback mockado."""
        if self.ai_client:
            prompt = self._montar_prompt_sintese(conteudo_bruto)
            try:
                # Suporte a clientes sync e async
                if asyncio.iscoroutinefunction(self.ai_client.generate):
                    return await self.ai_client.generate(prompt)
                return await asyncio.to_thread(self.ai_client.generate, prompt)
            except Exception as e:
                logger.warning("[REMSleep] IA indisponível, usando mock: %s", e)
                return self._mock_sintese(conteudo_bruto)
        return self._mock_sintese(conteudo_bruto)

    def _montar_prompt_sintese(self, conteudo_bruto: str) -> str:
        return f"""Você atua como o Córtex Subconsciente de um sistema multiagente biológico-digital (iaglobal).
Sua tarefa é processar uma memória bruta do curto prazo, eliminar o ruído
e extrair apenas o DNA do conhecimento obtido.

Regras Cruciais:
1. Identifique a raiz do problema ou o motivo do sucesso.
2. Crie ou sugira links conceituais usando o padrão do Obsidian [[Nome_Do_Conceito]].
3. Formate a saída contendo um YAML Frontmatter no início e o resumo em markdown depois.

Memória Bruta do Dia:
---
{conteudo_bruto}
---

"""

    def _mock_sintese(self, conteudo_bruto: str) -> str:
        """Fallback mockado quando IA está indisponível."""
        return f"""---
tags: [subconsciente, rem, {datetime.now(UTC).strftime("%Y-%m-%d")}]
insight_type: mock_fallback
---

# Insight Sintetizado (Mock)

*Processamento automático sem IA.*

## Resumo
{conteudo_bruto[:200]}...

## Links
[[Processamento_Automático]]
"""

    async def _gravar_longo_prazo(self, arquivo: str, conteudo: str) -> Path:
        """Grava conteúdo sintetizado no longo prazo de forma não-bloqueante."""

        def _write() -> Path:
            destino = self.long_term_dir / arquivo
            destino.write_text(conteudo, encoding="utf-8")
            return destino

        caminho = await asyncio.to_thread(_write)
        logger.debug("[REMSleep] Memória consolidada: %s", caminho)
        return caminho

    async def _remover_curto_prazo(self, arquivo: str) -> None:
        """Remove arquivo do curto prazo após processamento."""

        def _delete() -> None:
            origem = self.short_term_dir / arquivo
            if origem.exists():
                origem.unlink()

        await asyncio.to_thread(_delete)

    async def _atualizar_mapa_conexoes(self) -> None:
        """Atualiza o MOC (Map of Content) com links entre memórias."""

        def _update_moc() -> None:
            moc_path = self.synapses_dir / "00_MAPA_SINAPTICO.md"

            # Coleta todas as notas de longo prazo
            if not self.long_term_dir.exists():
                return

            links = []
            for f in self.long_term_dir.glob("*.md"):
                conteudo = f.read_text(encoding="utf-8")
                # Extrai links [[...]]
                import re

                links.extend(re.findall(r"\[\[(.*?)\]\]", conteudo))

            # Atualiza MOC
            moc_content = f"""---
tipo: MOC
ultima_atualizacao: "{datetime.now(UTC).isoformat()}"
total_conexoes: {len(links)}
---

# 🧠 Mapa Sináptico do Conhecimento

Conexões extraídas das memórias consolidadas:

"""
            for link in sorted(set(links)):
                moc_content += f"- [[{link}]]\n"

            moc_path.write_text(moc_content, encoding="utf-8")

        await asyncio.to_thread(_update_moc)

    # =====================================================================
    # PONTE: MEMORIES_DB (STAGING) → OBSIDIAN VAULT (LONG_TERM)
    # =====================================================================
    # O CognitiveProxy escreve em MEMORIES_DB sem saber do Obsidian.
    # Esta ponte puxa essas entradas e reaproveita o pipeline de sintese
    # (_solicitar_sintese_ia + _gravar_longo_prazo) sem duplicar logica.
    # Watermark "consolidated_at" marca "revisado" -- sucesso OU falha
    # (poison-pill: uma entrada corrompida nao pode ficar eternamente no
    # topo da fila FIFO). Autofagia separada apaga o que ficou estagnado
    # alem do horizonte.

    def _open_memories_conn(self) -> sqlite3.Connection:
        """Conexao a MEMORIES_DB com WAL defensivo.

        WAL eh propriedade do arquivo (outras conexoes herdam), mas setar
        a pragma aqui garante o modo mesmo num banco recem-criado sem o
        proxy ter rodado antes.
        """
        conn = sqlite3.connect(str(MEMORIES_DB), timeout=30.0)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _fetch_unconsolidated(
        self, table: str, limit: int
    ) -> List[Tuple[int, bytes, Optional[str]]]:
        """FIFO por created_at -- nao penaliza entradas por REM ter ficado
        offline; so limita quanto processa por ciclo."""
        conn = self._open_memories_conn()
        try:
            cur = conn.execute(
                f"SELECT id, data, created_at FROM {table} "
                f"WHERE consolidated_at IS NULL ORDER BY created_at ASC LIMIT ?",
                (limit,),
            )
            return cur.fetchall()
        finally:
            conn.close()

    def _mark_consolidated_batch(self, table: str, row_ids: List[int]) -> None:
        """1 commit por lote -- reduz contention contra o write de alta
        frequencia do proxy."""
        if not row_ids:
            return
        conn = self._open_memories_conn()
        try:
            now = datetime.now(timezone.utc).isoformat()
            conn.executemany(
                f"UPDATE {table} SET consolidated_at = ? WHERE id = ?",
                [(now, rid) for rid in row_ids],
            )
            conn.commit()
        finally:
            conn.close()

    async def _processar_staging_db(self, max_batch: int = 50) -> Dict[str, int]:
        """Segunda fonte de consolidacao REM: le stm_entries/ltm_entries
        de MEMORIES_DB e aplica o mesmo pipeline de sintese.

        Watermark incondicional (poison-pill safe): sucesso OU falha,
        toda entrada processada recebe consolidated_at -- nunca bloqueia
        a fila FIFO por estar sempre no topo.
        """
        stats = {
            "stm_entries": 0,
            "ltm_entries": 0,
            "synthesized": 0,
            "watermarked": 0,
            "failed": 0,
        }

        for table in _STAGING_TABLES:
            rows = await asyncio.to_thread(
                self._fetch_unconsolidated, table, max_batch
            )
            stats[table] = len(rows)

            watermarked_ids: List[int] = []
            for row_id, blob, _created_at in rows:
                synthesized = False
                try:
                    entry = cbor2.loads(blob)
                    conteudo = entry.get("content", "")
                    if conteudo:
                        insight = await self._solicitar_sintese_ia(conteudo)
                        if insight:
                            arquivo = (
                                f"stg_{_STAGING_SHORT_NAME[table]}_{row_id}.md"
                            )
                            await self._gravar_longo_prazo(arquivo, insight)
                            synthesized = True
                except Exception as e:
                    logger.warning(
                        "Falha ao consolidar %s#%s (marcado como revisado "
                        "mesmo assim): %s",
                        table,
                        row_id,
                        e,
                    )
                    stats["failed"] += 1
                finally:
                    watermarked_ids.append(row_id)

                if synthesized:
                    stats["synthesized"] += 1

            if watermarked_ids:
                await asyncio.to_thread(
                    self._mark_consolidated_batch, table, watermarked_ids
                )
                stats["watermarked"] += len(watermarked_ids)

        # Visibilidade agregada: uma falha isolada eh ignoravel; varias
        # falhas no mesmo ciclo indicam causa comum (banco corrompido,
        # mudanca de schema, IA fora do ar) que precisa de atencao.
        if stats["failed"] > 0:
            total_processed = stats["stm_entries"] + stats["ltm_entries"]
            logger.warning(
                "[REMSleep] Staging: %d/%d entries falharam consolidacao "
                "(poison-pill safe -- todas watermarked, nao bloqueiam fila).",
                stats["failed"],
                total_processed,
            )

        return stats

    async def _autofagia_staging_estagnado(self, dias_limite: int = 60) -> Dict[str, int]:
        """Ciclo SEPARADO (nao roda em iniciar_fase_rem). Apaga apenas
        linhas que ja foram revisadas (consolidated_at preenchido) e
        estao alem do horizonte -- nunca toca no que ainda nao teve
        chance de sintese.

        Entrada via ``iaglobal learn prune-staging [--days N]``.

        Guard obrigatorio: ``dias_limite > 0``. Valor <= 0 viraria
        ``DELETE ... WHERE created_at < agora`` -- apaga tudo revisado
        independente de idade. Defesa em profundidade: o CLI tambem
        guarda, mas este metodo pode ganhar outro chamador no futuro.
        """
        if dias_limite <= 0:
            raise ValueError(
                f"dias_limite deve ser positivo, recebido {dias_limite}"
            )
        cutoff = (
            datetime.now(timezone.utc) - timedelta(days=dias_limite)
        ).isoformat()
        stats = {"stm_deleted": 0, "ltm_deleted": 0}

        def _run() -> None:
            conn = self._open_memories_conn()
            try:
                for table in _STAGING_TABLES:
                    cur = conn.execute(
                        f"DELETE FROM {table} "
                        f"WHERE consolidated_at IS NOT NULL "
                        f"AND created_at < ?",
                        (cutoff,),
                    )
                    stats[
                        "stm_deleted" if table == "stm_entries" else "ltm_deleted"
                    ] = cur.rowcount
                conn.commit()
            finally:
                conn.close()

        await asyncio.to_thread(_run)
        logger.info(
            "[REMSleep] Autofagia staging: %d stm + %d ltm removidos "
            "(horizonte=%d dias).",
            stats["stm_deleted"],
            stats["ltm_deleted"],
            dias_limite,
        )
        return stats
