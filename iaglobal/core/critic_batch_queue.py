# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
CriticBatchQueue — Portão de avaliação final com validação cruzada.

Em vez de cada nó (reviewer, qa, evaluator, critic) chamar a API do LLM
individualmente, o nó crítico final (no_critic.py) coleta as avaliações
prévias da memória do pipeline e envia UM único batch com contexto
cruzado para o LLM.

Fluxo:
  1. reviewer e qa rodam independentemente (fases 6-7) com pré-processamento
  2. no_critic.py (fase 10) chama evaluate_with_context():
     - Lê memory["reviewer"] e memory["qa"]
     - Comprime tudo via LocalSummarizer
     - Envia 1 batch: "Aqui está o código. Aqui estão os achados do
       reviewer e QA. Forneça sua avaliação final com validação cruzada."
  3. Resultado inclui score + issues + sugestões integrando todos os achados

Benefícios:
  - O LLM vê TODAS as avaliações simultaneamente → cross-validation
  - Menos tokens (dados já comprimidos)
  - reviewer e qa continuam dando feedback imediato para o pipeline
"""

import json
from typing import Any, ClassVar, Dict, List, Optional

from iaglobal.search.local_summarizer import LocalSummarizer
from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.critic_batch")


class CriticBatchQueue:
    """Singleton usado pelo nó crítico final para avaliação com contexto cruzado.

    Uso:
        queue = await CriticBatchQueue.get_instance()
        result = await queue.evaluate_with_context(memory, task, output)
    """

    _instance: ClassVar[Optional["CriticBatchQueue"]] = None
    _instance_lock = __import__("asyncio").Lock()

    def __init__(self) -> None:
        pass

    @classmethod
    async def get_instance(cls) -> "CriticBatchQueue":
        async with cls._instance_lock:
            if cls._instance is None:
                cls._instance = cls()
        return cls._instance

    async def evaluate_with_context(
        self,
        memory: Dict[str, Any],
        task: str,
        coder_output: str,
        bandit: Any = None,
        prompt_built: str = "",
    ) -> Dict[str, Any]:
        """Avalia o output do coder com contexto de avaliações anteriores.

        1. Lê reviewer + qa da memória do pipeline
        2. Comprime output + contextos via LocalSummarizer
        3. Envia 1 chamada LLM com prompt de validação cruzada
        4. Retorna dict: approved, score, issues, fix_suggestions

        Args:
            memory: Estado do pipeline (ctx["memory"])
            task: Tarefa original do usuário
            coder_output: Output do coder a ser avaliado
            bandit: Instância do BanditPolicy (opcional)
            prompt_built: Contexto enriquecido com resultados de busca web

        Returns:
            Dict com "approved", "score", "issues", "fix_suggestions"
        """
        reviewer = memory.get("reviewer", {}) if isinstance(memory, dict) else {}
        qa = memory.get("qa", {})
        reviewer_summary = self._extract_evaluation_summary(reviewer, "Revisor")
        qa_summary = self._extract_evaluation_summary(qa, "QA")

        task_comp, output_comp = LocalSummarizer.compress(task, coder_output)

        prompt = self._montar_prompt_cruzado(
            task=task_comp,
            output=output_comp,
            reviewer=reviewer_summary,
            qa=qa_summary,
            prompt_built=prompt_built,
        )

        logger.info(
            "[CRITIC_BATCH] Avaliacao com contexto cruzado: "
            "task=%d output=%d chars | reviewer=%s qa=%s",
            len(task_comp),
            len(output_comp),
            "sim" if reviewer_summary else "nao",
            "sim" if qa_summary else "nao",
        )

        # 4. Aplica boost de prioridade nos agentes do batch crítico
        agentes_envolvidos: List[str] = ["critic_batch", "reviewer", "qa", "coder"]
        try:
            from iaglobal.execution.cpu_affinity import cpu_affinity

            await cpu_affinity.set_priority_boost(agentes_envolvidos, boost_percent=60)
            logger.info(
                "[CRITIC_BATCH] Boost de CPU aplicado a %d agentes do batch",
                len(agentes_envolvidos),
            )
        except Exception as e:
            logger.debug("[CRITIC_BATCH] Falha ao aplicar boost de CPU: %s", e)

        try:
            # 5. Chama LLM
            raw = await self._call_llm(prompt, bandit)
            if not raw:
                return self._fallback()

            # 6. Parseia resposta
            return self._parse_resposta(raw)
        finally:
            # 7. Garante retorno à homeostase, mesmo se der erro
            try:
                from iaglobal.execution.cpu_affinity import cpu_affinity

                await cpu_affinity.reset_budgets()
                logger.info("[CRITIC_BATCH] Homeostase de CPU restaurada")
            except Exception as e:
                logger.debug("[CRITIC_BATCH] Falha ao resetar budgets: %s", e)

    @staticmethod
    def _extract_evaluation_summary(eval_dict: Dict[str, Any], label: str) -> str:
        """Extrai resumo de uma avaliação anterior da memória."""
        if not eval_dict or not isinstance(eval_dict, dict):
            return ""

        score = eval_dict.get("score", 0)
        issues = eval_dict.get("issues", [])
        approved = eval_dict.get("approved", False)

        parts = [f"{label}: score={score} aprovado={approved}"]
        if issues:
            parts.append(f"  issues: {'; '.join(str(i) for i in issues[:3])}")
        return "\n".join(parts)

    @staticmethod
    def _montar_prompt_cruzado(
        task: str,
        output: str,
        reviewer: str,
        qa: str,
        prompt_built: str = "",
    ) -> str:
        context_parts = []
        if reviewer:
            context_parts.append(f"[Revisor]\n{reviewer}")
        if qa:
            context_parts.append(f"[QA]\n{qa}")
        if prompt_built:
            context_parts.append(f"[Contexto de Busca Web]\n{prompt_built[:1500]}")
        context = (
            "\n\n".join(context_parts)
            if context_parts
            else "Nenhuma avaliacao previa disponivel."
        )

        return (
            "Voce e o avaliador final. Faca validacao cruzada do codigo abaixo "
            "considerando as avaliacoes previas e o contexto de busca web.\n\n"
            f"[Contexto das avaliacoes previas]\n{context}\n\n"
            f"[Tarefa]\n{task}\n\n"
            f"[Codigo]\n{output}\n\n"
            "Retorne APENAS um JSON valido neste formato exato:\n"
            '{"approved": true/false, "score": 0-100, '
            '"issues": ["prob1", "prob2"], '
            '"fix_suggestions": ["sug1", "sug2"], '
            '"summary": "breve justificativa"}'
        )

    async def _call_llm(self, prompt: str, bandit: Any) -> Optional[str]:
        """Chama o LLM via BanditPolicy ou fallback."""
        if bandit:
            try:
                candidates = [
                    "groq/llama-3.3-70b-versatile",
                    "nvidia/mistralai/mistral-large-3-675b-instruct-2512",
                    "ollama/qwen2.5:0.5b",
                ]
                resultado = await bandit.generate(
                    node_id="critic_batch",
                    prompt=prompt,
                    candidates=candidates,
                    task_type="critic",
                )
                if resultado:
                    logger.info(
                        "[CRITIC_BATCH] Geração concluída (%d chars)", len(resultado)
                    )
                    return resultado
            except Exception as e:
                logger.debug("[CRITIC_BATCH] Bandit generate falhou: %s", e)

        try:
            from iaglobal.providers.provider_router import async_route_generate

            return await async_route_generate(
                "ollama/qwen2.5:0.5b",
                prompt,
                task_type="critic",
                node_id="critic_batch",
            )
        except Exception as e:
            logger.debug("[CRITIC_BATCH] Fallback falhou: %s", e)
            return None

    @staticmethod
    def _parse_resposta(raw: str) -> Dict[str, Any]:
        """Parseia resposta JSON do LLM."""
        try:
            inicio = raw.find("{")
            fim = raw.rfind("}")
            if inicio == -1 or fim == -1 or fim <= inicio:
                return CriticBatchQueue._fallback()
            data = json.loads(raw[inicio : fim + 1])
        except (json.JSONDecodeError, ValueError):
            return CriticBatchQueue._fallback()

        if not isinstance(data, dict):
            return CriticBatchQueue._fallback()

        score = max(0, min(100, float(data.get("score", 50))))
        approved = bool(data.get("approved", score >= 50))
        issues = data.get("issues", [])
        if score < 50 and not issues:
            issues = [f"Score {score:.0f}/100"]
        return {
            "approved": approved,
            "score": round(score, 1),
            "issues": issues[:5],
            "fix_suggestions": data.get("fix_suggestions", [])[:3],
            "summary": data.get("summary", ""),
        }

    @staticmethod
    def _fallback() -> Dict[str, Any]:
        return {
            "approved": False,
            "score": 0.0,
            "issues": ["Avaliação indisponível (batch falhou)"],
            "fix_suggestions": [],
            "summary": "Fallback: batch indisponível",
        }
