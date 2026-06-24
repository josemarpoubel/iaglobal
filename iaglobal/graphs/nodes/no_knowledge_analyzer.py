"""
Knowledge Analyzer — Filtra, extrai e persiste conhecimento útil do cache.
Totalmente em conformidade com as regras e diretrizes estritas do AGENTS.md.
"""
import time
import re
import logging
import asyncio
from types import MappingProxyType
from typing import Dict, Any, List, Tuple

from iaglobal.evolution.agents.knowledge_agent import knowledge
from iaglobal.memory.term_long import LongTermMemory
from iaglobal.memory.memory_vector import store as mem_vector_store, init_db as vector_init_db
from iaglobal.graphs.nodes._disk_swap import load_all_for_task
from iaglobal._paths import CORE_DB

logger = logging.getLogger(__name__)

# Inicializa o banco de vetores de forma estática protegida
vector_init_db()
_ltm = LongTermMemory(db_path=CORE_DB)

# Padrões de lixo pré-compilados para checagem ultraveloz O(1) de Regex
_GARBAGE_PATTERNS = frozenset([
    re.compile(r"Philistine city.state", re.IGNORECASE),
    re.compile(r"was a.*city.state", re.IGNORECASE),
    re.compile(r"page not found", re.IGNORECASE),
    re.compile(r"404 Not Found", re.IGNORECASE),
    re.compile(r"Mário Coluna", re.IGNORECASE),
    re.compile(r"CSV Apeldoorn", re.IGNORECASE),
    re.compile(r"Uma ilha e um amor", re.IGNORECASE),
    re.compile(r"book\)", re.IGNORECASE),
])

_RELEVANCE_KEYWORDS = MappingProxyType({
    "python": 3, "código": 3, "codigo": 3, "code": 3, "script": 3,
    "função": 3, "funcao": 3, "function": 3, "def ": 3, "import ": 3,
    "csv": 3, "pandas": 3, "numpy": 3, "api": 2, "rest": 2,
    "tutorial": 2, "exemplo": 2, "example": 2, "guide": 2,
    "documentação": 2, "documentation": 2, "como": 1, "how to": 1,
    "erro": 2, "error": 2, "solução": 2, "solution": 2,
})

# Regexes pré-compilados de limpeza contra Catastrophic Backtracking
_HTML_TAGS_REGEX = re.compile(r"<[^>]+>")
_WHITESPACE_REGEX = re.compile(r"\s+")


def _is_garbage(text: str) -> bool:
    """Verifica se o texto contém padrões de descarte usando busca compilada."""
    if not text:
        return True
    return any(pat.search(text) for pat in _GARBAGE_PATTERNS)


def _calc_relevance(text: str) -> float:
    """Calcula a densidade semântica de relevância do texto para engenharia de software."""
    if not text:
        return 0.0
    text_lower = text.lower()
    score = sum(weight for kw, weight in _RELEVANCE_KEYWORDS.items() if kw in text_lower)
    return min(score / 5.0, 1.0)


def _extract_useful(text: str, max_len: int = 500) -> str:
    """Aplica higienização atômica de strings limpando lixo de formatação HTML."""
    if not text:
        return ""
    cleaned = _HTML_TAGS_REGEX.sub("", text)
    cleaned = _WHITESPACE_REGEX.sub(" ", cleaned).strip()
    lines = [l.strip() for l in cleaned.split("\n") if len(l.strip()) > 30]
    return "\n".join(lines[:5])[:max_len]


def _sync_analyze_and_curate(task_str: str) -> Tuple[str, List[dict], int]:
    """Varre as memórias de swap em disco e aplica o filtro de curadoria de forma síncrona isolada."""
    # Carrega todo o cache bruto que o nó de busca salvou para esta tarefa específica
    raw_caches = load_all_for_task(task_str) or {}
    
    extracted_parts = []
    curated_logs = []
    processed_count = 0

    for source_name, raw_content in raw_caches.items():
        if not raw_content or _is_garbage(raw_content):
            continue
            
        relevance = _calc_relevance(raw_content)
        if relevance < 0.2:  # Filtra conteúdos com baixíssimo alinhamento técnico
            continue
            
        useful_text = _extract_useful(raw_content)
        if useful_text:
            processed_count += 1
            extracted_parts.append(f"=== KNOWLEDGE SOURCE: {source_name.upper()} (relevance: {relevance:.2f}) ===\n{useful_text}")
            curated_logs.append({"source": source_name, "relevance": relevance, "chars": len(useful_text)})
            
            # Persiste passivamente na LTM e base vetorial locais o fragmento higienizado
            try:
                _ltm.store(
                    content=f"Curated source [{source_name}] for task: {task_str}\n\n{useful_text}",
                    metadata={"source": "knowledge_analyzer", "relevance": relevance},
                    source="knowledge_analyzer"
                )
                mem_vector_store(text=useful_text, mtype="curated_knowledge")
            except Exception as db_err:
                logger.debug("[KNOWLEDGE_ANALYZER] Erro controlado ao persistir fragmento: %s", db_err)

    consolidated_knowledge = "\n\n".join(extracted_parts)
    return consolidated_knowledge, curated_logs, processed_count


async def run_knowledge_analyzer(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executa a triagem, limpeza e extração de conhecimento do cache de forma assíncrona.
    Mapeia latência acumulada e fontes curadas para o JointOptimizationLoop.
    """
    start_time = time.time()
    resolved_model = "knowledge_analyzer_deterministic_curator"
    
    task_str = str(ctx.get("input", {}).get("task", "") or ctx.get("task", ""))
    
    if not task_str or len(task_str) < 5:
        latency_ms = (time.time() - start_time) * 1000.0
        return {
            "output": "", "curated_sources": [], "source_count": 0,
            "execution_metrics": {"model": resolved_model, "success": True, "latency": latency_ms, "cost": 0.0}
        }

    logger.info("[KNOWLEDGE_ANALYZER] Iniciando ciclo assíncrono de higienização e filtragem de cache...")

    try:
        # DESPACHA INTEIRAMENTE A VARREDURA DE DISCO, ANÁLISE DE STRING E TRANSÇÃO DE BANCO PARA THREAD POOL
        consolidated_knowledge, curated_logs, source_count = await asyncio.to_thread(
            _sync_analyze_and_curate, task_str
        )

        logger.info("[KNOWLEDGE_ANALYZER] Curadoria finalizada. Extraídas %d fontes úteis de conhecimento.", source_count)
        latency_ms = (time.time() - start_time) * 1000.0

        # Retorno higienizado cumprindo as Regras 1, 3 e 5 do AGENTS.md (Sem dar dict unpack do ctx na RAM)
        return {
            "output": consolidated_knowledge,
            "curated_sources": curated_logs,
            "source_count": source_count,
            "execution_metrics": {
                "model": resolved_model,
                "success": True,
                "latency": latency_ms,
                "cost": 0.0  # Operação de infraestrutura puramente offline e local
            }
        }

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000.0
        logger.exception("[KNOWLEDGE_ANALYZER] Falha crítica no pipeline do Analyzer: %s", e)
        
        return {
            "output": "",
            "curated_sources": [],
            "source_count": 0,
            "execution_metrics": {
                "model": resolved_model,
                "success": False,
                "latency": latency_ms,
                "cost": 0.0
            }
        }

