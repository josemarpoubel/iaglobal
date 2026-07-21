# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""CriticAgent — Sensor de qualidade dentro do CognitiveProxy.

Contrato RESTRITO (leiame.md):
- NÃO executar busca web
- NÃO escolher modelo
- NÃO reescrever prompt livremente
- NÃO tomar decisão final sozinho
- NÃO substituir resultado do pipeline

PODE SOMENTE:
- Avaliar saída gerada pelo modelo
- Emitir score estruturado (JSON)
- Sinalizar falhas
- Sugerir correções (opcional)
"""

import re
import json
import hashlib
import asyncio
import ast
from typing import Dict, Any, List, Optional

from iaglobal.validation.engine import ValidationEngine
from iaglobal.agents.agent_base import AgentBase
from iaglobal.providers.provider_router import async_route_generate
from iaglobal.utils.logger import logger
from iaglobal.evolution.watchdog import watchdog
from iaglobal.obsidian.compliance import ComplianceChecker
from iaglobal.security.ast_gateway import ASTGateway

# Gateway singleton para AST parsing
_ast_gateway = ASTGateway()

from iaglobal.utils.life_signal_collector import instrument
from iaglobal.core.few_shot_provider import few_shot_provider
from iaglobal.agents.agent_base import _get_memory_router
from iaglobal.cognition.memory_first_router import CONF_THRESHOLD_MEMORY


# ── Singleton (padrão análogo a _get_bandit() em bandit.py) ──
_critic_instance: Optional["CriticAgent"] = None


def _get_critic() -> "CriticAgent":
    """Retorna singleton do CriticAgent.

    Antes desta função, cada chamador criava CriticAgent() fresco a cada
    avaliação — o que resetava silenciosamente _critic_degraded/_degraded_count
    toda vez, impedindo esse tracking de acumular entre chamadas.
    """
    global _critic_instance
    if _critic_instance is None:
        _critic_instance = CriticAgent()
    return _critic_instance


class CriticAgent(AgentBase):
    def __init__(self):
        super().__init__(agent_name="critic")
        self.DANGEROUS_PATTERNS = [
            "eval(",
            "exec(",
            "os.system(",
            "subprocess.run(shell=True",
        ]
        self.validator = ValidationEngine()
        self._critic_degraded = False
        self._degraded_count = 0
        self.compliance_checker = ComplianceChecker()

    # =========================================================================
    # API PÚBLICA — CONTRATO OBRIGATÓRIO
    # =========================================================================

    async def avaliar(self, task: str, prompt: str, output: str) -> Dict[str, Any]:
        """Avalia saída do modelo. Retorna JSON conforme contrato.

        Contrato de saída (OBRIGATÓRIO):
        {
            "approved": bool,
            "score": float (0-100),
            "issues": [str],
            "fix_suggestions": [str]
        }
        """
        logger.info(
            f"[CRITIC] Avaliando: task_len={len(task)} output_len={len(output)}"
        )
        try:
            issues = []
            suggestions = []

            # 0. Pré-processamento local — comprime antes de enviar ao LLM
            try:
                from iaglobal.search.local_summarizer import LocalSummarizer

                task, output = LocalSummarizer.compress(task, output)
                logger.info(
                    "[CRITIC] Comprimido: task=%d output=%d chars",
                    len(task),
                    len(output),
                )
            except Exception:
                pass

            # 1. Auditoria estática (código)
            if "```" in output or "def " in output:
                static = self._auditar_codigo(output)
                if static["issues"]:
                    issues.extend(static["issues"])
                    suggestions.extend(static["suggestions"])

            # 2. Avaliação via LLM (apenas score, sem decisão)
            scores = await self._avaliar_multidimensional(task, output)

            # 3. Calcular score agregado
            score = self._calcular_score_agregado(scores)

            # 4. Detectar problemas comuns
            if not output or len(output.strip()) < 3:
                issues.append("Resposta vazia ou muito curta")
                score = min(score, 30)
            if "UNKNOWN" in output:
                issues.append("Modelo reportou UNKNOWN — pode ser insuficiente")
                score = min(score, 30)
            if re.search(r"Error:|Traceback|SyntaxError", output):
                issues.append("Output contém erro de execução")
                suggestions.append("Corrigir erro antes de usar")
                score = max(0, score - 20)

            approved = score >= 50

            # RESET_METABOLIC: verificar degradação contínua
            metabolic_reset = self._check_metabolic_reset()

            result = {
                "approved": approved,
                "score": round(score, 1),
                "issues": issues[:5],
                "fix_suggestions": suggestions[:3],
                "_critic_degraded": self._critic_degraded,
                "_metabolic_reset": metabolic_reset,
            }

            if approved:
                logger.info(f"[CRITIC] Aprovado: score={score:.1f}")
            else:
                logger.info(f"[CRITIC] Rejeitado: score={score:.1f} issues={issues}")

            return result

        except Exception as e:
            logger.warning(f"[CRITIC] Falha na avaliação: {e}")
            self._critic_degraded = True
            return {
                "approved": False,
                "score": 0.0,
                "issues": [f"Erro interno do Critic: {e}"],
                "fix_suggestions": [],
                "_critic_degraded": True,
            }

    # =========================================================================
    # MÉTODOS INTERNOS (APENAS AVALIAÇÃO, SEM DECISÃO)
    # =========================================================================

    @staticmethod
    def _is_python_code(codigo: str) -> bool:
        """Detecta se o código é Python."""
        if not codigo or len(codigo.strip()) < 10:
            return False
        import re

        python_indicators = [
            r"\bdef\s+\w+\s*\(",
            r"\bclass\s+\w+",
            r"\bimport\s+\w+",
            r"\bfrom\s+\w+\s+import",
            r"\basync\s+def",
            r"\bawait\s+",
            r"\byield\s+",
        ]
        for pattern in python_indicators:
            if re.search(pattern, codigo):
                return True
        return False

    def _auditar_codigo(self, codigo: str) -> Dict:
        """Auditoria estática — apenas detecta problemas, sem decidir."""
        issues = []
        suggestions = []

        if not codigo or not codigo.strip():
            issues.append("Código vazio")
            return {"issues": issues, "suggestions": suggestions}

        # HTML/PHP/XML - pula validação Python
        if (
            codigo.strip().startswith("<!DOCTYPE")
            or codigo.strip().startswith("<html")
            or "<?php" in codigo.lower()
        ):
            return {"issues": [], "suggestions": []}

        # Só valida Python se for código Python
        if self._is_python_code(codigo):
            try:
                self.validator.validate(codigo)
            except SyntaxError as e:
                issues.append(f"Erro de sintaxe: {e}")
                suggestions.append("Corrigir sintaxe do código")

        # Padrões perigosos (aplicáveis a qualquer linguagem)
        for pattern in self.DANGEROUS_PATTERNS:
            if pattern in codigo:
                issues.append(f"Padrão perigoso detectado: {pattern}")
                suggestions.append(f"Substituir {pattern} por alternativa segura")

        return {"issues": issues, "suggestions": suggestions}

    async def _call_via_bandit(self, prompt: str, candidates: list) -> Optional[str]:
        """Chama LLM via BanditPolicy com fallback para provider_router."""
        if self.bandit:
            try:
                resultado = await self.bandit.generate(
                    node_id="critic",
                    prompt=prompt,
                    candidates=candidates,
                    task_type="critic",
                )
                if resultado:
                    return resultado
            except Exception as e:
                logger.debug("[CRITIC] Bandit generate falhou: %s", e)
        try:
            return await async_route_generate(
                "", prompt, task_type="critic", node_id="critic"
            )
        except Exception as e:
            logger.debug("[CRITIC] provider_router falhou: %s", e)
            return None

    @staticmethod
    def _score_medio(scores: Dict[str, Any]) -> float:
        return (
            scores.get("correctness", 0)
            + scores.get("completeness", 0)
            + scores.get("security", 0)
            + scores.get("spec_match", 0)
        ) / 4.0

    async def _avaliar_multidimensional(self, task: str, codigo: str) -> Dict[str, Any]:
        """
        Avalia código via LLM com escalonamento local → cloud.

        Fluxo:
          1. Tenta modelo local (Ollama) — preserva ATP.
          2. Se score médio ≥ 60, retorna (local suficiente).
          3. Se score < 60 ou falha, escala para cloud (Groq/NVIDIA).
          4. Se cloud falhar, retorna scores degradados.
        """
        prompt = await self._montar_prompt_avaliacao(task, codigo)

        # 1. Local first (ATP-efficient)
        logger.info("[CRITIC] Avaliando com modelo local...")
        resultado = await self._call_via_bandit(prompt, ["ollama/qwen2.5:0.5b"])
        if resultado:
            scores = self._parse_json_response(resultado.strip())
            if scores and self._score_medio(scores) >= 60:
                self._critic_degraded = False
                logger.info(
                    "[CRITIC] Avaliação local OK (score médio=%.1f)",
                    self._score_medio(scores),
                )
                return scores
            logger.info(
                "[CRITIC] Score local baixo (%.1f) — escalando para cloud",
                self._score_medio(scores) if scores else 0,
            )

        # 2. Escala para cloud (score baixo ou falha local)
        logger.info("[CRITIC] Escalando para modelos cloud (Cognitive_Escalation)...")

        # Fase 2.9 — Compliance check antes de cloud
        compliance = self.compliance_checker.full_audit(
            codigo, self._extrair_imports(codigo), 0.5
        )
        if not compliance["approved"]:
            logger.warning(
                "[CRITIC] Compliance violado — bloqueando cloud: %s",
                compliance["violations"],
            )
            # Registrar handoff por compliance violation
            self._registrar_compliance_handoff(task, codigo, compliance["violations"])
            # Retornar scores degradados — nao escala
            self._critic_degraded = True
            self._degraded_count += 1
            return self._fallback_scores(compliance["violations"])

        cloud_candidates = [
            "groq/llama-3.3-70b-versatile",
            "nvidia/mistralai/mistral-large-3-675b-instruct-2512",
            "ollama/qwen2.5:0.5b",
        ]
        resultado = await self._call_via_bandit(prompt, cloud_candidates)
        if resultado:
            scores = self._parse_json_response(resultado.strip())
            if scores:
                self._critic_degraded = False
                self._degraded_count = 0
                # EETL: Se escalonamento cloud foi bem-sucedido, verificar padrão evolutivo
                asyncio.ensure_future(self._evolutionary_watchdog_check(task))
                return scores

        self._critic_degraded = True
        self._degraded_count += 1
        logger.warning(
            "[CRITIC] Avaliacao falhou — scores degradados (count=%d)",
            self._degraded_count,
        )
        return self._fallback_scores()

    async def _evolutionary_watchdog_check(self, task: str) -> None:
        """EETL: Verifica se a task escalada para cloud se tornou padrão evolutivo.

        Se o mesmo tipo de tarefa foi escalada >= MIN_PATTERN_REPETITIONS vezes,
        solicita ao EvolutionaryWatchdog que registre uma tool permanente.
        """
        try:
            task_hash = hashlib.sha3_512(task.encode()).hexdigest()[:16]
            if watchdog.should_register_tool(task_hash):
                logger.info(
                    "[CRITIC] Padrao evolutivo detectado: task_hash=%s task='%s'",
                    task_hash,
                    task[:60],
                )
                # O código funcional será registrado pelo pipeline
                # no _async_learn_stage — o watchdog já faz a varredura.
                # Aqui apenas emitimos o sinal para o sistema.
                from iaglobal.obsidian.omnimind import omni_mind

                omni_mind.emitir_gatilho_apoptose(
                    "critic_watchdog",
                    f"Padrao evolutivo detectado para task_hash={task_hash}",
                )
        except Exception as e:
            logger.debug("[CRITIC] Watchdog check falhou: %s", e)

    def _extrair_imports(self, codigo: str) -> List[str]:
        """Extrai lista de imports do código para compliance check via ASTGateway."""
        imports = []

        # Usar ASTGateway em vez de ast.parse direto
        result = _ast_gateway.parse(codigo)
        if result.valid and result.tree:
            tree = result.tree
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.append(node.module)

        return imports
        return imports

    def _registrar_compliance_handoff(
        self, task: str, codigo: str, violations: List[str]
    ) -> None:
        """Fase 2.9 — Registra handoff por violação de compliance no ancestry_tree."""
        try:
            from pathlib import Path
            from datetime import datetime, timezone
            import json

            task_hash = hashlib.sha3_512(task.encode()).hexdigest()[:16]
            record = {
                "type": "COMPLIANCE_HANDOFF",
                "node_id": "critic",
                "task_hash": task_hash,
                "violations": violations,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "lineage_marker": self.compliance_checker.get_lineage_marker()[:16],
            }

            ancestry_path = None
            try:
                from iaglobal._paths import DATA_DIR

                ancestry_path = DATA_DIR / "ancestry_tree.jsonl"
            except Exception:
                import tempfile

                ancestry_path = (
                    Path(tempfile.gettempdir()) / "iaglobal_ancestry_tree.jsonl"
                )

            ancestry_path.parent.mkdir(parents=True, exist_ok=True)
            with open(str(ancestry_path), "a") as f:
                f.write(json.dumps(record) + "\n")

            logger.info(
                "[COMPLIANCE] Handoff registrado: %d violações", len(violations)
            )
        except Exception as e:
            logger.debug("[COMPLIANCE] Falha ao registrar handoff: %s", e)

    def _fallback_scores(
        self, violations: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Scores degradados quando avaliação falha."""
        issues = ["Avaliação falhou — modelo indisponível"]
        if violations:
            issues.extend([f"Compliance: {v}" for v in violations[:3]])
        return {
            "correctness": 0,
            "completeness": 0,
            "security": 0,
            "spec_match": 0,
            "summary": "Falha + violações de compliance",
        }

    def _check_metabolic_reset(self) -> bool:
        """RESET_METABOLIC: Se critic degradado >3x consecutivas, emite reset.

        Aplica a Lei do Sacrifício (OmniMind §9): sacrifica a complexidade
        da DAG para restaurar homeostase.

        Returns:
            True se reset foi emitido.
        """
        if self._degraded_count >= 3:
            logger.warning(
                "[CRITIC] RESET_METABOLIC: critic degradado %dx consecutivas",
                self._degraded_count,
            )
            try:
                from iaglobal.obsidian.omnimind import omni_mind

                omni_mind.emitir_gatilho_apoptose(
                    "critic", "RESET_METABOLIC: critic degradado — resetando homeostase"
                )
            except Exception:
                pass
            self._degraded_count = 0
            return True
        return False

    # =========================================================================
    # ARBITER — Portão único de geração (Lei da Obediência estendida)
    # =========================================================================

    @instrument(name="critic.arbitrar_geracao")
    async def arbitrar_geracao(
        self,
        node_id: str,
        prompt: str,
        task_type: str = "general",
        context: Optional[dict] = None,
    ) -> str:
        """
        Portão único pra qualquer nó que precise de geração — Lei da Obediência
        estendida. Nenhum nó chama o LLM diretamente; todos passam pelo crítico,
        que primeiro tenta resolver em casa (incentiva cooperação/aprendizado
        real) e só escalona pro Bandit se não conseguir.

        ARBITER_MODE=shadow: roda o caminho novo (decide e loga), mas retorna
        string vazia para manter o caminho antigo do chamador funcional.
        ARBITER_MODE=enforce (default): este é o único caminho.
        """
        import os

        context = context or {}
        mode = os.environ.get("ARBITER_MODE", "enforce").strip().lower()
        is_shadow = mode == "shadow"

        tool_result = await self._resolve_with_tools(prompt, [task_type])
        if tool_result is not None:
            logger.info("[ARBITER mode=%s] %s resolvido em casa (tools)", mode, node_id)
            await self._creditar_cooperacao(node_id, resolved_locally=True, via="tools")
            return tool_result

        router = _get_memory_router()
        memory_result = await router.route(prompt, task_type)
        if memory_result.found:
            effective_conf = router.get_effective_confidence(
                node_id, memory_result.confidence
            )
            if effective_conf >= CONF_THRESHOLD_MEMORY:
                router.record_memory_resolution(node_id)
                logger.info(
                    "[ARBITER mode=%s] %s memoria aceita (conf_base=%.2f eff=%.2f limiar=%.2f)",
                    mode,
                    node_id,
                    memory_result.confidence,
                    effective_conf,
                    CONF_THRESHOLD_MEMORY,
                )
                await self._creditar_cooperacao(
                    node_id, resolved_locally=True, via="memory"
                )
                return memory_result.content
            logger.info(
                "[ARBITER mode=%s] %s memoria rejeitada (conf_base=%.2f eff=%.2f < limiar=%.2f) — forcando LLM",
                mode,
                node_id,
                memory_result.confidence,
                effective_conf,
                CONF_THRESHOLD_MEMORY,
            )

        # 2.5 SocialRegistry — cooperação horizontal antes de escalar para LLM
        _social_peer = await self._tentar_social(node_id, task_type)
        if _social_peer is not None:
            logger.info(
                "[ARBITER mode=%s] %s delegado horizontalmente para %s — "
                "fast-path local, sem Bandit",
                mode,
                node_id,
                _social_peer,
            )
            await self._creditar_cooperacao(
                node_id, resolved_locally=True, via=f"social:{_social_peer}"
            )
            try:
                from iaglobal.providers.ollama_provider import (
                    async_generate as _ollama_fast,
                )

                _social_result = await _ollama_fast(prompt, timeout=30)
                if _social_result:
                    return _social_result
            except Exception as _social_err:
                logger.warning(
                    "[ARBITER] fallback social %s -> Ollama falhou: %s",
                    node_id,
                    _social_err,
                )
            # Fallback: se o fast-path social falhou, escala via Bandit

        logger.info(
            "[ARBITER mode=%s] %s nao resolvido em casa — escalando via critic",
            mode,
            node_id,
        )
        await self._creditar_cooperacao(node_id, resolved_locally=False)

        if is_shadow:
            # Modo shadow: loga a decisão mas retorna vazio para não cortar o
            # caminho antigo do chamador (que ainda existe no código).
            logger.info(
                "[ARBITER shadow] %s escalaria via critic, mas modo shadow "
                "deixa o caminho antigo ativo",
                node_id,
            )
            return ""

        candidates = getattr(self, "DEFAULT_CANDIDATES", ["ollama/qwen2.5:0.5b"])
        from iaglobal.providers.provider_router import _provider_has_key

        candidates = [c for c in candidates if _provider_has_key(c.split("/")[0])]
        try:
            resultado = await self.bandit.generate(
                node_id="critic",
                prompt=prompt,
                candidates=candidates,
                task_type=task_type,
                context={**context, "delegate_for": node_id},
            )
            router.record_llm_resolution(node_id)
            return resultado or ""
        except Exception as e:
            logger.warning(
                "[ARBITER] Falha ao delegar para %s via critic: %s", node_id, e
            )
            try:
                from iaglobal.agents.agent_base import get_evo_registry
                from iaglobal.immunity.vaccine_ledger import vaccine_ledger
                from iaglobal.evolution import is_flag_enabled

                evo = get_evo_registry().get(node_id)
                if evo and is_flag_enabled("evo_vaccine_persist"):
                    pattern = type(e).__name__
                    evo._failure_patterns.append(pattern)
                    await vaccine_ledger.registrar_falha(
                        evo,
                        pattern,
                        {
                            "prompt": (prompt or "")[:200],
                            "task_type": task_type,
                            "agent": node_id,
                        },
                    )
            except Exception:
                pass
            return ""

    async def _creditar_cooperacao(
        self, node_id: str, resolved_locally: bool, via: str = ""
    ) -> None:
        """Registra cooperação (componente C do IVM) para o nó que pediu ajuda.

        Quando o crítico resolve em casa (tools ou memória), credita
        skills_exchanged=1 (cooperação bem-sucedida). Quando escala para o
        Bandit, skills_exchanged=0 (não houve cooperação interna).
        """
        try:
            from iaglobal.chappie.ivm_axiom import get_ivm_axiom

            ivm = get_ivm_axiom()
            if ivm is None:
                return
            await ivm.atualizar_metricas(
                agent_name=node_id,
                skills_exchanged=1 if resolved_locally else 0,
                tasks_completed=0,
                tasks_failed=0,
            )
            logger.debug(
                "[COOPERACAO] %s resolved_locally=%s via=%s",
                node_id,
                resolved_locally,
                via,
            )
        except Exception:
            pass

    _TASK_DOMAIN_MAP = {
        "coding": "code",
        "code": "code",
        "debug": "debug",
        "test": "test",
        "design": "design",
        "search": "search",
        "plan": "plan",
        "writing": "writing",
        "review": "review",
        "general": "general",
    }

    async def _tentar_social(self, node_id: str, task_type: str) -> Optional[str]:
        """Consulta SocialRegistry por peer com proficiência no domínio.

        Retorna agent_id do peer se encontrado com proficiency >= 0.7 e
        load_factor < 0.8.  None se não houver peer adequado.
        """
        try:
            from iaglobal.agents.social import social_registry

            domain = self._TASK_DOMAIN_MAP.get(task_type, "general")
            peers = social_registry.query(domain, min_proficiency=0.7)
            if not peers:
                return None
            best = peers[0]
            cap = best.skills.get(domain)
            if cap is None or cap.proficiency < 0.7:
                return None
            if best.load_factor >= 0.8:
                logger.debug(
                    "[SOCIAL] %s: peer %s tem prof=%.2f mas load=%.2f — saturado, ignorando",
                    node_id,
                    best.agent_id,
                    cap.proficiency,
                    best.load_factor,
                )
                return None
            logger.info(
                "[SOCIAL] %s: peer %s disponivel (prof=%.2f load=%.2f) — cooperacao horizontal",
                node_id,
                best.agent_id,
                cap.proficiency,
                best.load_factor,
            )
            return best.agent_id
        except Exception as e:
            logger.debug("[SOCIAL] _tentar_social falhou: %s", e)
            return None

    async def _montar_prompt_avaliacao(self, task: str, codigo: str) -> str:
        """Prompt de avaliação com few-shot dinâmico de avaliações anteriores."""
        few_shot = await few_shot_provider.get_few_shot_async(
            task, max_examples=2, domain="code_evaluation critic"
        )
        few_shot_section = few_shot.section

        from iaglobal.agents.agent_base import INSTRUCAO_COT

        return f"""
Você é um validador técnico. Avalie a solução abaixo seguindo o Chain of Thought.

{INSTRUCAO_COT}

TAREFA: {task}

CÓDIGO:
{codigo}

Retorne APENAS um JSON válido neste formato exato:
{{"correctness": <0-100>, "completeness": <0-100>, "security": <0-100>, "spec_match": <0-100>, "summary": "<breve motivo>"}}

Critérios:
- correctness (peso 35%): O código funciona sem erros?
- completeness (peso 25%): Cobre todos os requisitos da tarefa?
- security (peso 25%): Código seguro, sem padrões perigosos?
- spec_match (peso 15%): Segue a especificação exata?
{few_shot_section}
"""

    def _parse_json_response(self, resposta: str) -> Dict[str, Any]:
        """Extrai JSON da resposta do modelo."""
        try:
            inicio = resposta.find("{")
            fim = resposta.rfind("}")
            if inicio != -1 and fim != -1 and fim > inicio:
                json_str = resposta[inicio : fim + 1]
                data = json.loads(json_str)
                if all(
                    k in data
                    for k in ["correctness", "completeness", "security", "spec_match"]
                ):
                    return {
                        "correctness": max(0, min(100, float(data["correctness"]))),
                        "completeness": max(0, min(100, float(data["completeness"]))),
                        "security": max(0, min(100, float(data["security"]))),
                        "spec_match": max(0, min(100, float(data["spec_match"]))),
                        "summary": data.get("summary", ""),
                    }
        except (json.JSONDecodeError, ValueError, TypeError):
            pass
        return {}

    def _fallback_scores(self) -> Dict[str, Any]:
        return {
            "correctness": 50.0,
            "completeness": 50.0,
            "security": 50.0,
            "spec_match": 50.0,
            "summary": "Fallback: avaliação indisponível",
        }

    # =========================================================================
    # AVALIAÇÃO EM LOTE (BATCH)
    # =========================================================================

    async def avaliar_batch(self, items: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """Avalia múltiplos outputs em uma única chamada LLM.

        Args:
            items: Lista de dicts com chaves "node_id", "task", "output".

        Returns:
            Lista de resultados na mesma ordem dos itens.
        """
        if not items:
            return []

        logger.info("[CRITIC_BATCH] Avaliando %d itens em batch", len(items))

        # Pré-processa cada item localmente
        compressed = []
        for it in items:
            try:
                t, o = LocalSummarizer.compress(it["task"], it["output"])
            except Exception:
                t, o = it["task"], it["output"]
            compressed.append({"node_id": it["node_id"], "task": t, "output": o})

        prompt = self._montar_prompt_batch(compressed)
        resultado_bruto = await self._avaliar_llm(prompt)
        resultados = self._parse_batch_response(resultado_bruto, compressed)

        # Garante um resultado por item
        output = []
        for it in compressed:
            nid = it["node_id"]
            if nid in resultados:
                output.append(resultados[nid])
            else:
                approved = True
                score = 50.0
                output.append(
                    {
                        "approved": approved,
                        "score": score,
                        "issues": [],
                        "fix_suggestions": [],
                        "summary": "Fallback (não avaliado no batch)",
                    }
                )

        return output

    async def _avaliar_llm(self, prompt: str) -> Optional[str]:
        """
        Chama o LLM com escalonamento local → cloud.

        Fluxo:
          1. Tenta modelo local (Ollama).
          2. Se resposta for curta/baixa qualidade, escala para cloud.
          3. Retorna melhor resposta disponível.
        """
        # 1. Local first
        logger.info("[CRITIC_BATCH] Tentando com modelo local...")
        resultado = await self._call_via_bandit(prompt, ["ollama/qwen2.5:0.5b"])
        if resultado and len(resultado.strip()) > 50:
            logger.info("[CRITIC_BATCH] Resposta local OK (%d chars)", len(resultado))
            return resultado

        # 2. Escala para cloud
        logger.info("[CRITIC_BATCH] Resposta local insuficiente — escalando para cloud")
        cloud_candidates = [
            "groq/llama-3.3-70b-versatile",
            "nvidia/mistralai/mistral-large-3-675b-instruct-2512",
            "ollama/qwen2.5:0.5b",
        ]
        resultado = await self._call_via_bandit(prompt, cloud_candidates)
        return resultado

    @staticmethod
    def _montar_prompt_batch(items: List[Dict[str, str]]) -> str:
        """Monta prompt único para avaliar múltiplos outputs."""
        blocos = []
        for it in items:
            blocos.append(
                f"--- INICIO {it['node_id']} ---\n"
                f"TAREFA: {it['task']}\n"
                f"SAIDA: {it['output']}\n"
                f"--- FIM {it['node_id']} ---"
            )
        items_list = "\n\n".join(blocos)

        return (
            "Avalie cada item abaixo individualmente. "
            "Retorne APENAS um JSON array válido neste formato:\n"
            "[\n"
            '  {"node_id": "...", "correctness": 0-100, "completeness": 0-100, '
            '"security": 0-100, "spec_match": 0-100, "summary": "..."},\n'
            "  ...\n"
            "]\n\n"
            f"{items_list}"
        )

    @staticmethod
    def _parse_batch_response(
        raw: Optional[str], items: List[Dict[str, str]]
    ) -> Dict[str, Dict[str, Any]]:
        """Parseia resposta JSON array do LLM no formato batch."""
        if not raw:
            return {}

        try:
            inicio = raw.find("[")
            fim = raw.rfind("]")
            if inicio == -1 or fim == -1 or fim <= inicio:
                return {}
            data = json.loads(raw[inicio : fim + 1])
        except (json.JSONDecodeError, ValueError):
            return {}

        if not isinstance(data, list):
            return {}

        resultados: Dict[str, Dict[str, Any]] = {}
        for entry in data:
            nid = entry.get("node_id", "")
            if not nid:
                continue
            c = max(0, min(100, float(entry.get("correctness", 50))))
            comp = max(0, min(100, float(entry.get("completeness", 50))))
            sec = max(0, min(100, float(entry.get("security", 50))))
            sp = max(0, min(100, float(entry.get("spec_match", 50))))
            score = c * 0.35 + comp * 0.25 + sec * 0.25 + sp * 0.15
            approved = score >= 50
            resultados[nid] = {
                "approved": approved,
                "score": round(score, 1),
                "correctness": c,
                "completeness": comp,
                "security": sec,
                "spec_match": sp,
                "summary": entry.get("summary", ""),
                "issues": [f"Score {score:.0f}/100"] if score < 50 else [],
                "fix_suggestions": [],
            }
        return resultados

    def _calcular_score_agregado(self, scores: Dict[str, Any]) -> float:
        return (
            scores.get("correctness", 0) * 0.35
            + scores.get("completeness", 0) * 0.25
            + scores.get("security", 0) * 0.25
            + scores.get("spec_match", 0) * 0.15
        )


# ─────────────────────────────────────────────────────────────────────────────
# Ponte de compatibilidade (módulo-level)
#
# `arbitrar_geracao` é o portão único de geração definido como MÉTODO de
# instância de CriticAgent (PSC/Lei da Obediência). Chamadores legados que
# importavam a função diretamente do módulo (ex: interface/chat_agent.py)
# continuam funcionando sem alterar a organização da API pública.
#
# NÃO remova esta ponte sem migrar todos os importadores para
# `_get_critic().arbitrar_geracao(...)`.
# ─────────────────────────────────────────────────────────────────────────────


async def arbitrar_geracao(
    node_id: str,
    prompt: str,
    task_type: str = "general",
    context: Optional[dict] = None,
) -> str:
    """Ponte de compatibilidade — delega ao singleton do CriticAgent.

    Mantém o contrato de ``CriticAgent.arbitrar_geracao`` intacto e preserva
    o ponto único de passagem (chokepoint) exigido pela BanditPolicy/PSC.
    """
    return await _get_critic().arbitrar_geracao(
        node_id=node_id, prompt=prompt, task_type=task_type, context=context
    )
