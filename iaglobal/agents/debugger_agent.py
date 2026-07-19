# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/agents/debugger_agent.py

from __future__ import annotations

import hashlib
import re
import time

from dataclasses import dataclass
from typing import Optional, Dict, Any

from iaglobal.execution.executor import executar
from iaglobal.agents.agent_base import AgentBase, INSTRUCAO_COT
from iaglobal.graphs.policy import PolicyRegistry
from iaglobal.models.task import Task
from iaglobal.security.ast_gateway import ASTGateway
from iaglobal.utils.logger import get_logger


logger = get_logger("iaglobal.agents.debugger_agent")


@dataclass(slots=True)
class DebugResult:
    success: bool
    code: str
    output: Optional[str] = None
    error: Optional[str] = None
    attempts: int = 0
    model_used: Optional[str] = None
    execution_time: float = 0.0


class DebuggerAgent(AgentBase):
    """
    IA Global Self-Healing Debug Agent

    Responsabilidades:

    1. Validar AST
    2. Executar código
    3. Detectar erro
    4. Solicitar correção ao LLM
    5. Revalidar código corrigido
    6. Evitar loops infinitos
    7. Atualizar política Bandit
    8. Produzir telemetria
    """

    TRACEBACK_PATTERN = re.compile(
        r"Traceback \(most recent call last\):[\s\S]*?(?=\n[A-Za-z_].*Error:|\Z)"
    )

    CODE_BLOCK_PATTERN = re.compile(
        r"```(?:python)?\s*([\s\S]*?)```",
        re.IGNORECASE,
    )

    MAX_SELF_CRITIQUE_ITERATIONS = 2

    def __init__(
        self,
        max_attempts: int = 3,
        enable_self_healing: bool = True,
    ):
        super().__init__(agent_name="debugger")
        self.max_attempts = max_attempts
        self.enable_self_healing = enable_self_healing
        self._self_critique_count = 0

        self.ast_gateway = ASTGateway()

        self.policy_registry = PolicyRegistry()
        self.bandit = self.policy_registry.get("debugger")

    # ==========================================================
    # PUBLIC API
    # ==========================================================

    async def run(self, task: Task) -> DebugResult:
        """
        Fluxo principal do agente.
        """

        start_time = time.perf_counter()
        self._self_critique_count = 0

        # Código pode estar em task.code (atributo dinâmico) ou task.context["code"]
        code = getattr(task, "code", None) or task.context.get("code", "")

        previous_versions = set()

        last_error = None
        last_model = None

        for attempt in range(1, self.max_attempts + 1):
            logger.info(
                "Attempt=%s/%s",
                attempt,
                self.max_attempts,
            )

            try:
                self._validate(code)
            except Exception as e:
                last_error = str(e)
                logger.exception("AST validation failed")
                return DebugResult(
                    success=False,
                    code=code,
                    error=str(e),
                    attempts=attempt,
                    execution_time=time.perf_counter() - start_time,
                )

            output = await executar("", {"task": code})

            error = self.extract_error(output)

            if not error:
                self._reward_success(
                    model=last_model,
                    attempt=attempt,
                )

                return DebugResult(
                    success=True,
                    code=code,
                    output=output,
                    attempts=attempt,
                    model_used=last_model,
                    execution_time=time.perf_counter() - start_time,
                )

            last_error = error

            logger.warning(
                "Execution failed: %s",
                error[:300],
            )

            code_hash = self._hash(code)

            if code_hash in previous_versions:
                logger.error("[DebuggerAgent] Infinite correction loop detected")

                break

            previous_versions.add(code_hash)

            if not self.enable_self_healing:
                break

            code, last_model = await self._repair_code(
                task=task,
                code=code,
                error=error,
            )

        return DebugResult(
            success=False,
            code=code,
            error=last_error,
            attempts=self.max_attempts,
            model_used=last_model,
            execution_time=time.perf_counter() - start_time,
        )

    # ==========================================================
    # SELF HEALING
    # ==========================================================

    async def _repair_code(
        self,
        task: Task,
        code: str,
        error: str,
    ) -> tuple[str, Optional[str]]:
        """
        Repara código usando LLM + autocomplete Jedi (se disponível) + Auto-crítica.

        Fluxo:
          1. Usa Jedi para análise estática e sugestões
          2. Constrói prompt enriquecido com análise do Jedi
          3. Chama LLM para correção
          4. Auto-crítica avalia código corrigido
          5. Se score < 0.6, tenta refinar
          6. Valida código corrigido
        """

        # Fase 1: Análise estática com Jedi (se disponível)
        jedi_analysis = await self._analyze_with_jedi(code, error)

        # Fase 2: Constrói prompt enriquecido
        prompt = self.build_fix_prompt_enhanced(
            task=task,
            error=error,
            code=code,
            jedi_analysis=jedi_analysis,
        )

        # Fase 3: Seleciona modelo e executa
        candidates = [
            "groq/llama-3.3-70b-versatile",
            "nvidia/mistralai/mistral-large-3-675b-instruct-2512",
            "ollama/qwen2.5:0.5b",
        ]
        model = self.bandit.select_model(
            node_id="debugger_agent",
            task_type="debug",
            candidates=candidates,
        )

        logger.info("Repair model=%s", model)
        try:
            response = await self.bandit.async_execute_model(
                model_name=model,
                prompt=prompt,
                task_type="debug",
                node_id="debugger_agent",
            )
            fixed_code = self._extract_code(response)
            if not fixed_code:
                logger.warning("[DebuggerAgent] Empty model response")
                return code, model

            # Fase 4: Auto-crítica evolutiva
            auto_critica = await self._auto_critica_codigo(
                code=fixed_code,
                error=error,
                context={"jedi_analysis": jedi_analysis},
            )

            score = auto_critica.get("score", 0.0)
            precisa_refinar = auto_critica.get("precisa_refinar", False)

            # Fase 5: Se score baixo, tenta refinar (máx 1 iteração)
            if precisa_refinar and score < 0.6:
                logger.info(
                    "[DebuggerAgent] Auto-crítica: score=%.2f < 0.6, refinando...",
                    score,
                )

                sugestoes = auto_critica.get("sugestoes", [])
                if sugestoes:
                    prompt_refinamento = f"""
Você é um especialista em Python refinando código corrigido.

==================== CÓDIGO ATUAL ====================
{fixed_code}

==================== ERRO ORIGINAL ====================
{error}

==================== CRÍTICA ====================
Forças: {auto_critica.get("forças", [])}
Fraquezas: {auto_critica.get("fraquezas", [])}

==================== SUGESTÕES DE MELHORIA ====================
{chr(10).join(f"- {s}" for s in sugestoes)}

==================== TAREFA ====================
Refine o código para abordar as fraquezas acima.
Mantenha a funcionalidade, mas melhore:
- Sintaxe e imports
- Tratamento de erros
- Legibilidade

Retorne APENAS o código Python refinado, sem explicações ou markdown.
"""

                    response_refinada = await self.bandit.async_execute_model(
                        model_name=model,
                        prompt=prompt_refinamento,
                        task_type="debug",
                        node_id="debugger_agent",
                    )
                    fixed_code_refinado = self._extract_code(response_refinada)

                    if fixed_code_refinado and len(fixed_code_refinado.strip()) > 10:
                        # Re-avalia código refinado
                        auto_critica_refinada = await self._auto_critica_codigo(
                            code=fixed_code_refinado,
                            error=error,
                        )

                        if auto_critica_refinada.get("score", 0.0) > score:
                            logger.info(
                                "[DebuggerAgent] Refinamento melhorou score: %.2f → %.2f",
                                score,
                                auto_critica_refinada["score"],
                            )
                            fixed_code = fixed_code_refinado
                            score = auto_critica_refinada["score"]

            try:
                self._validate(fixed_code)
            except Exception as e:
                logger.warning(
                    "[DebuggerAgent] Generated code rejected: %s",
                    e,
                )
                return code, model

            self.bandit.update_policy(
                node="debugger_agent",
                model=model,
                strategy="debug",
                success=True,
                latency=0.5,
                reward=0.75 + (score * 0.25),  # Bonus por score alto
            )
            return fixed_code, model

        except Exception as e:
            logger.exception("[DebuggerAgent] Self-healing failure")
            self.bandit.update_policy(
                node="debugger_agent",
                model=model,
                strategy="debug",
                success=False,
                latency=1.0,
                reward=0.0,
            )
            return code, model

    # ==========================================================
    # VALIDATION
    # ==========================================================

    def _validate(self, code: str) -> None:
        result = self.ast_gateway.parse(code)
        if not result.valid:
            raise ValueError("; ".join(result.errors))

    # ==========================================================
    # ERROR EXTRACTION
    # ==========================================================

    def extract_error(
        self,
        output: Optional[str],
    ) -> Optional[str]:

        if not output:
            return None

        match = self.TRACEBACK_PATTERN.search(output)

        return match.group(0) if match else None

    # ==========================================================
    # PROMPTS
    # ==========================================================

    def build_fix_prompt(
        self,
        task: Task,
        error: str,
        code: str,
    ) -> str:
        """
        Constrói prompt específico baseado no tipo de erro.

        Detecta:
          - Erros de sintaxe (parênteses, indentação)
          - Imports não encontrados
          - Variáveis indefinidas
          - Outros erros de execução
        """
        error_lower = error.lower()

        # Detecta tipo de erro e dá instrução específica
        if "syntax" in error_lower or "'('" in error or "parêntese" in error_lower:
            tipo = "ERRO DE SINTAXE"
            instrucao = "Corrija a sintaxe Python. Verifique:\n  - Parênteses, colchetes e chaves fechados\n  - Indentação correta\n  - Dois-pontos após def, if, for, etc."
        elif "import" in error_lower or "módulo" in error_lower:
            tipo = "ERRO DE IMPORT"
            instrucao = "Corrija os imports. Verifique:\n  - Nomes de módulos corretos\n  - Remova imports não utilizados\n  - Use nomes válidos do Python"
        elif "undefined" in error_lower or "não definido" in error_lower:
            tipo = "VARIÁVEL INDEFINIDA"
            instrucao = (
                "Defina todas as variáveis antes de usá-las. Verifique nomes e escopo."
            )
        elif "name" in error_lower and "not defined" in error_lower:
            tipo = "NOME INDEFINIDO"
            instrucao = "A variável/função não está definida. Crie-a ou corrija o nome."
        else:
            tipo = "ERRO DE EXECUÇÃO"
            instrucao = (
                "Analise o erro e corrija o código para que execute sem exceptions."
            )

        # Pega descrição da tarefa
        task_desc = getattr(task, "objective", "") or task.context.get(
            "task", "Corrigir código Python"
        )

        return f"""Você é um especialista em Python.

{INSTRUCAO_COT}

TIPO DE PROBLEMA: {tipo}
INSTRUÇÃO: {instrucao}

TAREFA: {task_desc}

========================
CÓDIGO COM ERRO
========================
{code}

========================
ERRO DETECTADO
========================
{error}

========================
SAÍDA ESPERADA
========================
Siga as 4 etapas (Análise → Plano → Implementação → Revisão) antes de gerar o código final.
Retorne APENAS o código Python corrigido e válido.
NÃO inclua explicações, texto ou blocos markdown (```).
"""

    # ==========================================================
    # UTILITIES
    # ==========================================================

    def _extract_code(
        self,
        text: str,
    ) -> str:

        if not text:
            return ""

        match = self.CODE_BLOCK_PATTERN.search(text)

        if match:
            return match.group(1).strip()

        return text.strip()

    def _hash(self, content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    async def _analyze_with_jedi(
        self,
        code: str,
        error: str,
    ) -> Dict[str, Any]:
        """
        Usa Jedi para análise estática do código.

        Retorna:
            - issues: Problemas detectados
            - symbols: Símbolos disponíveis
            - type_hints: Dicas de tipo
        """
        analysis = {
            "issues": [],
            "symbols": [],
            "type_hints": {},
            "available": False,
        }

        try:
            import jedi
        except ImportError:
            logger.debug("[DebuggerAgent] Jedi não disponível")
            return analysis

        try:
            script = jedi.Script(code=code, path="example.py")

            # Analisa símbolos
            completions = script.complete()
            for c in list(completions)[:20]:
                analysis["symbols"].append(
                    {
                        "name": c.name,
                        "type": c.type,
                    }
                )

            # Detecta problemas básicos
            if "undefined" in error.lower() or "not defined" in error.lower():
                # Tenta encontrar símbolo similar
                error_name = error.split("'")[1] if "'" in error else ""
                if error_name:
                    for c in completions:
                        if error_name.lower() in c.name.lower():
                            analysis["type_hints"][error_name] = {
                                "suggestion": c.name,
                                "type": c.type,
                            }
                            break

            analysis["available"] = True

        except Exception as e:
            logger.debug("[DebuggerAgent] Jedi análise falhou: %s", e)

        return analysis

    async def _auto_critica_codigo(
        self,
        code: str,
        error: str,
        context: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Auto-crítica evolutiva: avalia código corrigido antes de retornar.

        Fluxo:
          1. SelfCritiqueEvolutivo avalia código
          2. Verifica se erros foram resolvidos
          3. Se score < 0.6, sugere nova correção

        Args:
            code: Código corrigido
            error: Erro original que motivou correção
            context: Contexto adicional

        Returns:
            Dict com score, problemas_resolvidos, precisa_refinar
        """
        self._self_critique_count += 1
        if self._self_critique_count >= self.MAX_SELF_CRITIQUE_ITERATIONS:
            logger.warning(
                "[DebuggerAgent] Limite de auto-crítica atingido (%d), forçando saída",
                self.MAX_SELF_CRITIQUE_ITERATIONS,
            )
            return {
                "score": 0.6,
                "problemas_resolvidos": True,
                "precisa_refinar": False,
                "sugestoes": [],
                "critica": {},
            }

        try:
            from iaglobal.reflection.self_critique_evolutivo import (
                SelfCritiqueEvolutivo,
            )

            critique_engine = SelfCritiqueEvolutivo()

            # Avalia código
            critica = critique_engine.evaluate(
                code,
                contexto={
                    "tipo": "codigo",
                    "erro_original": error,
                },
            )

            score = critica.get("score", 0.0)
            forcas = critica.get("forças", [])
            fraquezas = critica.get("fraquezas", [])

            logger.info(
                "[DebuggerAgent] Auto-crítica | score=%.2f | forcas=%s | fraquezas=%s",
                score,
                forcas,
                fraquezas,
            )

            # Verifica se erro foi resolvido
            erros_persistem = any(
                e in str(fraquezas).lower()
                for e in ["erro_sintaxe", "imports_problematicos"]
            )

            return {
                "score": score,
                "problemas_resolvidos": not erros_persistem,
                "precisa_refinar": score < 0.6 or erros_persistem,
                "sugestoes": critique_engine.gerar_sugestoes_refinamento(critica),
                "critica": critica,
            }

        except Exception as e:
            logger.warning("[DebuggerAgent] Auto-crítica falhou: %s", e)
            return {
                "score": 0.0,
                "problemas_resolvidos": False,
                "precisa_refinar": True,
                "sugestoes": [],
                "critica": {},
            }

    def build_fix_prompt_enhanced(
        self,
        task: Task,
        error: str,
        code: str,
        jedi_analysis: Dict[str, Any],
    ) -> str:
        """
        Constrói prompt enriquecido com análise do Jedi.

        Inclui:
          - Tipo de erro detectado
          - Símbolos disponíveis (do Jedi)
          - Sugestões de correção baseadas em tipos
        """
        # Prompt base (do build_fix_prompt original)
        base_prompt = self.build_fix_prompt(task=task, error=error, code=code)

        # Enriquece com análise do Jedi
        jedi_info = ""

        if jedi_analysis.get("available"):
            jedi_info = "\n\n========================\nANÁLISE ESTÁTICA (Jedi)\n========================\n"

            # Símbolos disponíveis
            symbols = jedi_analysis.get("symbols", [])
            if symbols:
                jedi_info += "Símbolos disponíveis:\n"
                for s in symbols[:10]:
                    jedi_info += f"  - {s['name']} ({s['type']})\n"

            # Type hints
            type_hints = jedi_analysis.get("type_hints", {})
            if type_hints:
                jedi_info += "\nSugestões:\n"
                for name, hint in type_hints.items():
                    jedi_info += (
                        f"  - '{name}' → use '{hint['suggestion']}' ({hint['type']})\n"
                    )

        return base_prompt + jedi_info

    def _reward_success(
        self,
        model: Optional[str],
        attempt: int,
    ) -> None:

        if not model:
            return

        reward = max(
            0.1,
            1.0 - (attempt * 0.1),
        )

        self.bandit.update_policy(
            node="debugger_agent",
            model=model,
            strategy="debug",
            success=True,
            latency=0.1,
            reward=reward,
        )

    # ==========================================================
    # COMPATIBILITY API
    # ==========================================================

    async def corrigir_codigo(
        self,
        codigo: str,
        erro: str,
        task: str,
    ) -> str:

        fake_task = Task(
            objective=task,
            context={"code": codigo},
        )

        repaired_code, _ = await self._repair_code(
            task=fake_task,
            code=codigo,
            error=erro,
        )

        return repaired_code
