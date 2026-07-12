# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
FewShotProvider — Retrieves real examples from system memory and injects
into prompts as few-shot demonstrations for local models (Ollama 0.5B).

Sources:
- ToolLibrary (positive code examples with source code)
- SkillRegistry (skills with run_fn source code)
- MTAPool (negative examples from failed prompts)
- DLQ (cache_poison_*.json in 00_Quarentena)

Ranking:
- sentence-transformers embeddings + cosine similarity (primary)
- TF-IDF + cosine similarity (fallback)

Cache:
- Embeddings em memória (LRU) + persistência CBOR
- Elimina cold start de 15s na primeira chamada

DLQ (NEW):
- ingests cache_poison_*.json as negative examples injected into any
  model prompt (visible to human/LLM as avoid-pattern)
"""
import ast
import asyncio
import cbor2
import hashlib
import inspect
import json
import os
import time
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple, Any, Dict
from collections import OrderedDict

from iaglobal.utils.logger import get_logger
from iaglobal._paths import PACKAGE_DIR

logger = get_logger("iaglobal.core.few_shot_provider")

# Caminho do cache de embeddings
EMBEDDING_CACHE_PATH = PACKAGE_DIR / "memory" / "data" / "json" / "fewshot_embeddings.cbor"

# Tamanho do cache LRU em memria
LRU_CACHE_SIZE = 100

# Constantes de Expiry e Monitoramento (Mutação 1C)
MAX_VACCINE_AGE_DAYS = 30
MAX_VACCINES = 100
ESTIMATED_TOKENS_PER_EXAMPLE = 300


@dataclass
class FewShotExample:
    source: str
    query: str
    answer: str
    score: float
    tags: List[str] = field(default_factory=list)
    language: str = "python"


@dataclass
class FewShotResult:
    section: str
    examples: List[FewShotExample]
    source_counts: Dict[str, int]
    latency_ms: float
    embedder: str


class FewShotProvider:
    """Retrieves and ranks examples for few-shot prompting."""

    MAX_EXAMPLES = 4
    MIN_SCORE = 0.25
    MAX_ANSWER_CHARS = 600
    DLQ_SCORE = 0.15

    def __init__(self, preload: bool = False):
        self._embed_model: Any = None
        self._tfidf: Any = None
        self._embedder_name = "none"
        # Cache LRU em memória: {text_hash: embedding}
        self._embedding_cache: "OrderedDict[str, Any]" = OrderedDict()
        # Cache de exemplos já ranqueados: {query_hash: (examples, timestamp)}
        self._example_cache: "OrderedDict[str, Tuple[List[FewShotExample], float]]" = OrderedDict()
        # Pool de exemplos negativos ingeridos da DLQ
        self._negative_examples: List[FewShotExample] = []

        self._load_embedding_cache()

        # Preload opcional no boot
        if preload:
            self._preload_embeddings()

    # --------------------------------------------------------------
    # Cache Management
    # --------------------------------------------------------------

    @staticmethod
    def _hash_text(text: str) -> str:
        """Gera hash SHA3-256 de um texto."""
        return hashlib.sha3_256(text.encode("utf-8")).hexdigest()[:16]

    def _get_or_compute_embedding(self, text: str) -> Any:
        """Retorna embedding do cache ou computa e cacheia."""
        text_hash = self._hash_text(text)

        # Check cache em memória
        if text_hash in self._embedding_cache:
            logger.debug("[FEW-SHOT] Cache hit em memória: %s", text_hash)
            return self._embedding_cache[text_hash]

        # Computa embedding
        self._ensure_embedder()

        emb_list: Any = None
        if self._embed_model and self._embedder_name.startswith("sentence"):
            import numpy as np

            emb = self._embed_model.encode(text, normalize_embeddings=True)
            emb_list = emb.tolist() if hasattr(emb, "tolist") else emb
        elif self._tfidf is not None:
            # TF-IDF no cacheia bem (depende do vocabulário)
            return None
        else:
            return None

        if emb_list is not None:
            # Adiciona ao cache LRU
            if len(self._embedding_cache) >= LRU_CACHE_SIZE:
                self._embedding_cache.popitem(last=False)
            self._embedding_cache[text_hash] = emb_list
            logger.debug("[FEW-SHOT] Cache miss, computado e cacheado: %s", text_hash)

        return emb_list

    def _save_embedding_cache(self):
        """Persiste cache de embeddings em disco (CBOR)."""
        try:
            EMBEDDING_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "embeddings": dict(self._embedding_cache),
                "count": len(self._embedding_cache),
            }
            EMBEDDING_CACHE_PATH.write_bytes(cbor2.dumps(data))
            logger.info(
                "[FEW-SHOT] Cache de embeddings salvo: %d entries em %s",
                len(self._embedding_cache), EMBEDDING_CACHE_PATH,
            )
        except Exception as e:
            logger.debug("[FEW-SHOT] Falha ao salvar cache: %s", e)

    def _load_embedding_cache(self):
        """Carrega cache de embeddings do disco."""
        if not EMBEDDING_CACHE_PATH.exists():
            logger.debug("[FEW-SHOT] Cache de embeddings no existe")
            return
        try:
            data = cbor2.loads(EMBEDDING_CACHE_PATH.read_bytes())
            embeddings = data.get("embeddings", {})
            count = data.get("count", 0)

            # Carrega em memória (respeitando LRU size)
            items = list(embeddings.items())[-LRU_CACHE_SIZE:]
            self._embedding_cache = OrderedDict(items)

            logger.info(
                "[FEW-SHOT] Cache de embeddings carregado: %d entries",
                len(self._embedding_cache),
            )
        except Exception as e:
            logger.debug("[FEW-SHOT] Falha ao carregar cache: %s", e)

    def _preload_embeddings(self):
        """Preload de embeddings no boot (carrega modelo e cacheia exemplos)."""
        logger.info("[FEW-SHOT] Preload de embeddings iniciado...")
        start = time.time()

        # Carrega modelo
        self._ensure_embedder()

        # Coleta exemplos de todas as fontes
        candidates: List[FewShotExample] = []
        candidates.extend(self._from_tool_library(""))
        candidates.extend(self._from_skill_registry(""))
        candidates.extend(self._from_mta_pool(""))

        # Gera embeddings para todos
        for ex in candidates:
            self._get_or_compute_embedding(ex.query)
            if ex.answer:
                self._get_or_compute_embedding(ex.answer[:200])

        # Salva cache
        self._save_embedding_cache()

        elapsed = (time.time() - start) * 1000
        logger.info(
            "[FEW-SHOT] Preload completo: %d embeddings em %.0fms",
            len(self._embedding_cache), elapsed,
        )

    # --------------------------------------------------------------
    # DLQ - Ingestão de exemplos negativos da Quarentena
    # --------------------------------------------------------------

    async def ingest_dlq_examples(self, quarantine_dir: Optional[Path] = None) -> int:
        """Escaneia 00_Quarentena/ por arquivos cache_poison_*.json e injeta
        como exemplos negativos no FewShotProvider.

        Esta é a conexão entre o sistema imunológico (apoptose de cache)
        e o sistema cognitivo (aprendizado por exemplos negativos).

        Todo I/O é delegado a asyncio.to_thread para não bloquear o event loop.

        Returns:
            Número de exemplos injetados.
        """
        qdir = Path(quarantine_dir or PACKAGE_DIR / "obsidian" / "00_Quarentena")
        
        # NOVO: Expiry de vacinas antigas antes de injetar novas
        expiry_stats = self._expire_old_vaccines()
        if expiry_stats["expired_by_age"] or expiry_stats["expired_by_cap"]:
            logger.debug(
                "[FEW-SHOT] Expiry pré-ingestão: %d vacinas removidas",
                expiry_stats["expired_by_age"] + expiry_stats["expired_by_cap"],
            )
        
        def _scan_and_load() -> int:
            injected = 0
            if not qdir.exists():
                return 0
            for fpath in qdir.glob("cache_poison_*.json"):
                try:
                    data = json.loads(fpath.read_text(encoding="utf-8"))
                except Exception:
                    continue
                prompt_snippet = data.get("prompt_snippet", "")
                resp_snippet = data.get("response_snippet", "")
                reason = data.get("reason", "unknown")
                if not prompt_snippet:
                    continue
                key = "dlq:{}:{:x}".format(
                    reason,
                    int(hashlib.md5(prompt_snippet.encode()).hexdigest()[:12], 16),
                )
                if key in self._example_cache:
                    continue
                ex = FewShotExample(
                    source="dlq:{}".format(reason),
                    query="[NÃO REPETIR — razão: {}] {}".format(reason, prompt_snippet[:150]),
                    answer="[RESPOSTA REJEITADA] {}".format(resp_snippet[:300]),
                    score=self.DLQ_SCORE,
                    tags=["negative", "dlq", reason],
                    language="text",
                )
                self._example_cache[key] = ([ex], time.monotonic())
                self._negative_examples.append(ex)
                injected += 1
                logger.debug("[FEW-SHOT] DLQ inject: %s | reason=%s", key[:40], reason)
            if injected:
                logger.info(
                    "[FEW-SHOT] Ingestão DLQ: %d exemplos negativos de %s",
                    injected, qdir,
                )
            return injected
        
        return await asyncio.to_thread(_scan_and_load)

    def _expire_old_vaccines(self) -> Dict[str, int]:
        """Remove vacinas com idade > MAX_VACCINE_AGE_DAYS ou excedentes do cap.
        
        Retorna estatísticas da limpeza:
        - expired_by_age: vacinas removidas por idade
        - expired_by_cap: vacinas removidas por excesso
        - remaining: vacinas restantes após limpeza
        """
        now = time.monotonic()
        max_age_seconds = MAX_VACCINE_AGE_DAYS * 86400
        
        expired_by_age = 0
        expired_by_cap = 0
        
        # 1. Expiry por idade
        expired_keys = []
        for key, (examples, timestamp) in list(self._example_cache.items()):
            if now - timestamp > max_age_seconds:
                expired_keys.append(key)
        
        for key in expired_keys:
            del self._example_cache[key]
            expired_by_age += 1
        
        # 2. Expiry por cap (remove mais antigas primeiro)
        if len(self._example_cache) > MAX_VACCINES:
            # Ordena por timestamp (mais antigas primeiro)
            sorted_items = sorted(
                self._example_cache.items(),
                key=lambda x: x[1][1],  # timestamp
            )
            excess_count = len(self._example_cache) - MAX_VACCINES
            for key, _ in sorted_items[:excess_count]:
                del self._example_cache[key]
            expired_by_cap = excess_count
        
        # 3. Sincroniza _negative_examples com _example_cache
        # Extrai chaves parciais (sem hash) para comparação
        partial_keys = {
            key.rsplit(":", 1)[0]  # Remove hash final: "dlq:reason:hash" → "dlq:reason"
            for key in self._example_cache.keys()
        }
        
        self._negative_examples = [
            ex for ex in self._negative_examples
            if ex.source in partial_keys or ex.source in self._example_cache
        ]
        
        if expired_by_age or expired_by_cap:
            logger.info(
                "[FEW-SHOT] Expiry: %d vacinas removidas (%d por idade, %d por cap), %d restantes",
                expired_by_age + expired_by_cap,
                expired_by_age,
                expired_by_cap,
                len(self._negative_examples),
            )
        
        return {
            "expired_by_age": expired_by_age,
            "expired_by_cap": expired_by_cap,
            "remaining": len(self._negative_examples),
        }

    # --------------------------------------------------------------
    # Public API
    # --------------------------------------------------------------

    def get_few_shot(
        self,
        task: str,
        max_examples: int = MAX_EXAMPLES,
        domain: str = "",
    ) -> FewShotResult:
        """
        Retrieves and ranks examples for a given task.

        Args:
            task: The task description to find similar examples for.
            max_examples: Maximum number of examples to return.
            domain: Optional domain hint for filtering.

        Returns:
            FewShotResult with formatted prompt section and metadata.
        """
        start = time.time()
        query = "{} {}".format(task, domain).strip()

        # 1. Collect candidates from all sources
        candidates: List[FewShotExample] = []
        sources_used: Dict[str, int] = {}

        tool_examples = self._from_tool_library(query)
        candidates.extend(tool_examples)

        skill_examples = self._from_skill_registry(query)
        candidates.extend(skill_examples)

        negative_examples = self._from_mta_pool(query)
        candidates.extend(negative_examples)

        dlq_examples = self._from_dlq_pool(query)
        candidates.extend(dlq_examples)

        # 2. Rank by similarity
        ranked = self._rank(query, candidates)

        # 3. Select top-k, maintaining source diversity
        selected = self._select_diverse(ranked, max_examples)

        for ex in selected:
            sources_used[ex.source] = sources_used.get(ex.source, 0) + 1

        # 4. Format
        section = self._format_section(selected)

        elapsed = (time.time() - start) * 1000.0
        logger.info(
            "[FEW-SHOT] %d candidates -> %d selected | sources=%s | embedder=%s | %.0fms",
            len(candidates), len(selected), dict(sources_used),
            self._embedder_name, elapsed,
        )

        return FewShotResult(
            section=section,
            examples=selected,
            source_counts=sources_used,
            latency_ms=elapsed,
            embedder=self._embedder_name,
        )

    # --------------------------------------------------------------
    # Sources
    # --------------------------------------------------------------

    def _from_tool_library(self, query: str) -> List[FewShotExample]:
        """Extracts examples from ToolLibrary."""
        examples: List[FewShotExample] = []
        try:
            from iaglobal.tools.tool_library import tool_library
            for name, entry in tool_library._tools.items():
                code = self._extract_callable_source(entry.fn)
                if not code or len(code.strip()) < 20:
                    continue
                description = getattr(entry, "description", "") or name
                tags = " ".join(getattr(entry, "tags", []))
                examples.append(FewShotExample(
                    source="tool_library",
                    query="{} {} {}".format(description, tags, name),
                    answer=code[:self.MAX_ANSWER_CHARS],
                    score=0.5,
                    tags=list(getattr(entry, "tags", [])),
                    language=self._detect_lang(code),
                ))
        except Exception:
            pass
        return examples

    def _from_skill_registry(self, query: str) -> List[FewShotExample]:
        """Extracts examples from SkillRegistry (run_fn source)."""
        examples: List[FewShotExample] = []
        try:
            from iaglobal.evolution.skills.skill_registry import skill_registry
            skills = skill_registry.list_skills(active_only=True)
            for skill in skills:
                code = self._extract_callable_source(skill.run_fn)
                if not code or len(code.strip()) < 20:
                    continue
                desc = getattr(skill, "description", "") or skill.name
                tags = " ".join(getattr(skill, "tags", []))
                examples.append(FewShotExample(
                    source="skill_registry",
                    query="{} {} {}".format(desc, tags, skill.name),
                    answer=code[:self.MAX_ANSWER_CHARS],
                    score=0.5,
                    tags=list(getattr(skill, "tags", [])),
                    language=self._detect_lang(code),
                ))
        except Exception:
            pass
        return examples

    def _from_mta_pool(self, query: str) -> List[FewShotExample]:
        """Extracts negative examples from MTAPool."""
        examples: List[FewShotExample] = []
        try:
            from iaglobal.recycling.mta_pool import mta_pool
            items = mta_pool.items
            for item in items[-20:]:
                content = item.get("content", "")
                if not content or len(content.strip()) < 30:
                    continue
                item_type = item.get("type", "unknown")
                metadata = item.get("metadata", {})
                task_hint = metadata.get("task", "") if isinstance(metadata, dict) else ""
                examples.append(FewShotExample(
                    source="mta_pool",
                    query=task_hint or content[:100],
                    answer="[{}] {}".format(item_type.upper(), content[:self.MAX_ANSWER_CHARS]),
                    score=0.3,
                    language="text",
                    tags=["negative"],
                ))
        except Exception:
            pass
        return examples

    def _from_dlq_pool(self, query: str) -> List[FewShotExample]:
        """Returns negative examples ingested from DLQ (00_Quarentena/cache_poison_*.json)."""
        return list(self._negative_examples)

    # --------------------------------------------------------------
    # Embedding + Ranking
    # --------------------------------------------------------------

    def _ensure_embedder(self):
        """Lazy-loads sentence-transformers or TF-IDF."""
        if self._embed_model is not None:
            return
        try:
            from sentence_transformers import SentenceTransformer
            self._embed_model = SentenceTransformer(
                "all-MiniLM-L6-v2",
                device="cpu",
            )
            self._embedder_name = "sentence-transformers/all-MiniLM-L6-v2"
            logger.info("[FEW-SHOT] Embedder carregado: %s", self._embedder_name)
            return
        except Exception as e:
            logger.debug("[FEW-SHOT] sentence-transformers indisponivel: %s", e)
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            self._tfidf = TfidfVectorizer(max_features=500, stop_words="english")
            self._embedder_name = "tfidf"
            logger.info("[FEW-SHOT] Embedder fallback: TF-IDF")
            return
        except Exception:
            pass
        self._embed_model = False
        self._embedder_name = "none"

    def _rank(
        self,
        query: str,
        candidates: List[FewShotExample],
    ) -> List[FewShotExample]:
        """Ranks candidates by semantic similarity to query."""
        if not candidates:
            return []

        self._ensure_embedder()

        if self._embed_model and self._embedder_name.startswith("sentence"):
            return self._rank_sbert(query, candidates)
        elif self._tfidf is not None:
            return self._rank_tfidf(query, candidates)
        else:
            for c in candidates:
                c.score = self._keyword_score(query, c.query)
            candidates.sort(key=lambda x: -x.score)
            return candidates

    def _rank_sbert(
        self,
        query: str,
        candidates: List[FewShotExample],
    ) -> List[FewShotExample]:
        """Ranking with sentence-transformers usando cache de embeddings."""
        try:
            import numpy as np

            # Embedding da query (com cache)
            query_emb = self._get_or_compute_embedding(query)
            if query_emb is None:
                return candidates

            # Embeddings dos candidatos (com cache)
            candidate_embs: List[Any] = []
            valid_candidates: List[FewShotExample] = []
            for c in candidates:
                emb = self._get_or_compute_embedding(c.query)
                if emb is not None:
                    candidate_embs.append(emb)
                    valid_candidates.append(c)

            if not candidate_embs:
                return candidates

            # Calcula similaridade
            query_arr = np.array(query_emb)
            candidate_arr = np.array(candidate_embs)
            similarities = np.dot(candidate_arr, query_arr)

            # Atualiza scores
            for i, c in enumerate(valid_candidates):
                c.score = float(similarities[i])

            valid_candidates.sort(key=lambda x: -x.score)
            return valid_candidates
        except Exception as e:
            logger.debug("[FEW-SHOT] Erro no ranking SBERT: %s", e)
            return candidates

    def _rank_tfidf(
        self,
        query: str,
        candidates: List[FewShotExample],
    ) -> List[FewShotExample]:
        """Ranking with TF-IDF cosine similarity."""
        try:
            from sklearn.metrics.pairwise import cosine_similarity
            all_texts = [c.query for c in candidates] + [query]
            matrix = self._tfidf.fit_transform(all_texts)
            query_vec = matrix[-1:]
            candidate_vecs = matrix[:-1]
            sims = cosine_similarity(candidate_vecs, query_vec).flatten()
            for i, c in enumerate(candidates):
                c.score = float(sims[i])
            candidates.sort(key=lambda x: -x.score)
        except Exception:
            pass
        return candidates

    @staticmethod
    def _keyword_score(query: str, candidate: str) -> float:
        """Fallback scoring when no embedder is available."""
        q_words = set(re.findall(r"\w+", query.lower()))
        c_words = set(re.findall(r"\w+", candidate.lower()))
        if not q_words or not c_words:
            return 0.0
        overlap = q_words & c_words
        return len(overlap) / max(len(q_words), len(c_words))

    @staticmethod
    def _select_diverse(
        candidates: List[FewShotExample],
        max_count: int,
    ) -> List[FewShotExample]:
        """Selects diverse top-k, preferring higher scores."""
        selected: List[FewShotExample] = []
        seen_sources: Dict[str, int] = {}
        for c in candidates:
            if c.score < 0.1:
                continue
            if seen_sources.get(c.source, 0) >= 2:
                continue
            selected.append(c)
            seen_sources[c.source] = seen_sources.get(c.source, 0) + 1
            if len(selected) >= max_count:
                break
        return selected

    # --------------------------------------------------------------
    # Formatting
    # --------------------------------------------------------------

    @staticmethod
    def _format_section(examples: List[FewShotExample]) -> str:
        """Formats examples as a few-shot prompt section."""
        if not examples:
            return ""

        lines = ["", "[EXEMPLOS DE REFERÊNCIA — aprendidos de execuções anteriores]", ""]
        for i, ex in enumerate(examples, 1):
            if ex.source == "mta_pool" or ex.source.startswith("dlq:"):
                lines.append("Exemplo {} (❌ a evitar — {}):".format(i, ex.source))
            else:
                lines.append("Exemplo {} (✅ padrão de sucesso — {}):".format(i, ex.source))
            lines.append("```{}".format(ex.language))
            lines.append(ex.answer.strip())
            lines.append("```")
            lines.append("")

        lines.append("[FIM DOS EXEMPLOS]")
        lines.append("")
        return "\n".join(lines)

    # --------------------------------------------------------------
    # Utilities
    # --------------------------------------------------------------

    @staticmethod
    def _extract_callable_source(fn: Any) -> str:
        """Extracts source code from a callable."""
        if fn is None:
            return ""
        try:
            return inspect.getsource(fn)
        except (OSError, TypeError, inspect.BlockFound):
            pass
        try:
            if hasattr(fn, "__code__"):
                import dis
                return (
                    dis.Bytecode(fn).info() if hasattr(dis.Bytecode(fn), "info") else ""
                )
        except Exception:
            pass
        return ""

    @staticmethod
    def _detect_lang(code: str) -> str:
        """Quick language detection."""
        if not code:
            return "text"
        try:
            ast.parse(code)
            return "python"
        except SyntaxError:
            pass
        if re.search(r"def |class |import |from ", code[:200]):
            return "python"
        if re.search(r"function |const |let |var |=>|require\(|import ", code[:200]):
            return "javascript"
        if re.search(r"<\w+|\<\w+\s", code[:200]):
            return "html"
        return "text"


_preload = os.getenv("FEWSHOT_PRELOAD", "").lower() in {"1", "true", "yes"}
few_shot_provider = FewShotProvider(preload=_preload)
