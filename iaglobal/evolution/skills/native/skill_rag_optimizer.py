# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/evolution/skills/skill_rag_optimizer.py

import logging
from typing import Dict, Any

from iaglobal.evolution.skills.native.skill import Skill, ExecutionPolicy
from iaglobal.evolution.skills.native.skill_registry import skill_registry
from iaglobal.utils.logger import logger

logger = logging.getLogger(__name__)

LOCAL_MODELS = {"qwen2.5:0.5b", "llama3.2:1b", "tinyllama"}


async def run_rag_optimizer(ctx: Dict[str, Any]) -> Dict[str, Any]:
    model_decision = ctx.get("model_decision", {})
    selected_model = ""
    if isinstance(model_decision, dict):
        selected_model = model_decision.get("selected_model", "qwen2.5:0.5b")
    elif isinstance(model_decision, str):
        selected_model = model_decision

    is_local = (
        any(m in selected_model for m in LOCAL_MODELS) or "qwen" in selected_model
    )

    if is_local:
        rag_config = {
            "max_documents": 2,
            "chunk_size_tokens": 250,
            "strategy": "strict_filter",
            "model_type": "local_short_context",
        }
        logger.info("[RAG_OPTIMIZER] Modelo local detectado: chunk=250, max_docs=2")
    else:
        rag_config = {
            "max_documents": 7,
            "chunk_size_tokens": 1000,
            "strategy": "expansive",
            "model_type": "cloud_long_context",
        }
        logger.info("[RAG_OPTIMIZER] Modelo nuvem detectado: chunk=1000, max_docs=7")

    return {"rag_config": rag_config}


skill_rag_optimizer = Skill(
    name="optimize_rag_pipeline",
    version="v1",
    description="Otimiza dinamicamente as buscas RAG baseado no modelo selecionado. Modelos locais usam chunks pequenos (250t, 2 docs), nuvem usa chunks grandes (1000t, 7 docs).",
    run_fn=run_rag_optimizer,
    inputs=["model_decision"],
    outputs=["rag_config"],
    constraints=["deterministic", "no_llm"],
    execution_policy=ExecutionPolicy.ON_DEMAND,
    author="applied-ai-engineer",
    tags=["applied-ai", "rag", "optimization"],
)

skill_registry.register(skill_rag_optimizer)
