import ast
import difflib
import hashlib
import math
import os
import pickle
import struct
from typing import Callable, Dict, List, Optional, Tuple
from dataclasses import dataclass

from iaglobal.utils.logger import get_logger
from iaglobal.security.ast_gateway import ASTGateway

logger = get_logger("iaglobal.tools.library")

_ast_gateway = ASTGateway()

_TOOLS_DB = None


def _get_tools_db():
    global _TOOLS_DB
    if _TOOLS_DB is None:
        try:
            from iaglobal._paths import DATA_DIR

            _TOOLS_DB = os.path.join(str(DATA_DIR), "tools_registry.pkl")
        except Exception:
            _TOOLS_DB = "/tmp/iaglobal_tools_registry.pkl"
    return _TOOLS_DB


@dataclass
class ToolEntry:
    name: str
    fn: Callable
    tags: List[str]
    description: str
    confidence: float = 0.95
    embedding: Optional[bytes] = None
    parameter_schema: Optional[Dict[str, str]] = None


_embed_model = None


def _get_embedder():
    global _embed_model
    if _embed_model is None:
        try:
            from fastembed import TextEmbedding

            _embed_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
        except Exception:
            logger.debug(
                "[TOOL_LIBRARY] fastembed nao disponivel — semantica desativada"
            )
            _embed_model = False
    return _embed_model if _embed_model is not False else None


def _embed_text(text: str) -> Optional[bytes]:
    model = _get_embedder()
    if model is None:
        return None
    try:
        emb = list(model.embed(text))[0]
        return struct.pack(f"{len(emb)}f", *emb)
    except Exception as e:
        logger.debug("[TOOL_LIBRARY] Erro no embedding: %s", e)
        return None


def _cosine_sim(a: bytes, b: bytes) -> float:
    try:
        fa = struct.unpack(f"{len(a) // 4}f", a)
        fb = struct.unpack(f"{len(b) // 4}f", b)
        dot = sum(x * y for x, y in zip(fa, fb))
        na = math.sqrt(sum(x * x for x in fa))
        nb = math.sqrt(sum(x * x for x in fb))
        if na * nb == 0:
            return 0.0
        return dot / (na * nb)
    except Exception:
        return 0.0


class ToolLibrary:
    def __init__(self):
        self._tools: Dict[str, ToolEntry] = {}
        self._dirty = False
        self._load()

    def _save(self):
        if not self._dirty:
            return
        path = _get_tools_db()
        try:
            serializable = {}
            for name, entry in self._tools.items():
                serializable[name] = {
                    "name": entry.name,
                    "tags": entry.tags,
                    "description": entry.description,
                    "confidence": entry.confidence,
                    "parameter_schema": entry.parameter_schema,
                }
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as f:
                pickle.dump(serializable, f)
            logger.debug(
                "[TOOL_LIBRARY] Registry persistido: %s (%d tools)",
                path,
                len(serializable),
            )
        except Exception as e:
            logger.debug("[TOOL_LIBRARY] Falha ao persistir: %s", e)
        self._dirty = False

    def _load(self):
        path = _get_tools_db()
        if not os.path.exists(path):
            return
        try:
            with open(path, "rb") as f:
                serializable = pickle.load(f)
            for name, data in serializable.items():
                if name not in self._tools:
                    entry = ToolEntry(
                        name=data["name"],
                        fn=None,
                        tags=data["tags"],
                        description=data["description"],
                        confidence=data.get("confidence", 0.95),
                        parameter_schema=data.get("parameter_schema"),
                    )
                    self._tools[name] = entry
            logger.info(
                "[TOOL_LIBRARY] Carregados %d tools do disco", len(serializable)
            )
        except Exception as e:
            logger.debug("[TOOL_LIBRARY] Falha ao carregar: %s", e)

    def register(
        self, name: str, fn: Callable, tags: List[str], description: str = ""
    ) -> None:
        text_for_embed = f"{name} {' '.join(tags)} {description}"
        embedding = _embed_text(text_for_embed)
        schema = self._extract_schema(fn) if description else None
        entry = ToolEntry(
            name=name,
            fn=fn,
            tags=tags,
            description=description,
            embedding=embedding,
            parameter_schema=schema,
        )
        self._tools[name] = entry
        self._dirty = True
        self._save()
        logger.info(
            "[TOOL_LIBRARY] Registrada: %s | tags=%s | emb=%s",
            name,
            tags,
            "sim" if embedding else "nao",
        )

    @staticmethod
    def _extract_schema(fn: Callable) -> Dict[str, str]:
        try:
            source = getattr(fn, "__code__", None)
            if source is None:
                return {}
            import inspect

            sig = inspect.signature(fn)
            schema = {}
            for pname, param in sig.parameters.items():
                if pname == "self":
                    continue
                hint = "str"
                if param.annotation is not inspect.Parameter.empty:
                    hint = str(param.annotation)
                schema[pname] = hint
            return schema
        except Exception:
            return {}

    def register_from_code(self, task: str, code: str) -> Optional[str]:
        # Use SHA-256 instead of MD5 for security
        name = f"auto_tool_{hashlib.sha256(task.encode()).hexdigest()[:8]}"
        tags = [w.lower() for w in task.split() if len(w) > 3][:10]
        # Extrair nome real da função via AST
        result = _ast_gateway.parse(code)
        if result.valid and result.tree:
            for node in ast.iter_child_nodes(result.tree):
                if isinstance(node, ast.FunctionDef):
                    tags.append(node.name)
                    break
        try:
            compiled = compile(code, f"<{name}>", "exec")
            ns = {"__builtins__": {}}  # Restringir builtins para segurança
            exec(compiled, ns)
            fn = None
            for k, v in ns.items():
                if callable(v) and not k.startswith("_"):
                    fn = v
                    break
            if fn:
                desc = f"Auto-registrada da task: {task[:80]}"
                self.register(name, fn, tags, desc)
                return name
        except Exception as e:
            logger.warning("[TOOL_LIBRARY] Falha ao registrar tool do código: %s", e)
        return None

    # Formatos de saída conhecidos — usados para discriminação de tool match
    _FORMAT_HINTS = {
        "pdf": ["pdf", "documento"],
        "html": ["html", "pagina web", "site", "blog", "pagina"],
        "py": ["python", "script", "funcao", "função", "algoritmo"],
        "json": ["json", "api", "dados"],
        "csv": ["csv", "planilha", "tabela"],
    }

    @classmethod
    def _detect_format(cls, task: str) -> Optional[str]:
        task_lower = task.lower()
        for fmt, hints in cls._FORMAT_HINTS.items():
            for hint in hints:
                if hint in task_lower:
                    return fmt
        return None

    def match(
        self, task: str, tags: Optional[List[str]] = None
    ) -> Tuple[Optional[ToolEntry], float]:
        task_lower = task.lower()
        all_tags = list(tags or [])
        all_tags.extend(w for w in task_lower.split() if len(w) > 3)

        query_emb = _embed_text(task)
        task_format = self._detect_format(task)

        best: Optional[ToolEntry] = None
        best_score = 0.0

        for entry in self._tools.values():
            tag_score = self._entry_tag_score(entry, task_lower, all_tags)

            sem_score = 0.0
            if query_emb is not None and entry.embedding is not None:
                sem_score = _cosine_sim(query_emb, entry.embedding)

            # Penalidade de formato: se o prompt pede HTML e a tool não menciona HTML, penaliza
            format_penalty = 0.0
            if task_format:
                all_entry_text = " ".join(entry.tags) + " " + entry.description
                if task_format not in all_entry_text.lower():
                    format_penalty = 0.25

            # Penalidade de domínio: task dev (criar app/sistema) vs tool não-dev
            _DEV_KEYWORDS = [
                "criar",
                "app",
                "sistema",
                "código",
                "codigo",
                "api",
                "desenvolver",
                "construir",
                "aplicativo",
                "programa",
                "site",
                "página",
                "pagina",
                "função",
                "funcao",
                "aplicação",
                "aplicacao",
                "implementar",
                "código-fonte",
                "codigo-fonte",
            ]
            domain_penalty = 0.0
            task_has_dev_intent = any(k in task_lower for k in _DEV_KEYWORDS)
            if task_has_dev_intent:
                entry_text = " ".join(entry.tags) + " " + entry.description
                entry_has_dev_tags = any(k in entry_text.lower() for k in _DEV_KEYWORDS)
                if not entry_has_dev_tags:
                    domain_penalty = 0.35

            combo = max(tag_score, sem_score) - format_penalty - domain_penalty

            if combo > best_score:
                best_score = combo
                best = entry

        if best and best_score > 0.5:
            logger.info("[TOOL_LIBRARY] Match: %s (score=%.2f)", best.name, best_score)
            return best, best_score
        return None, 0.0

    @staticmethod
    def _entry_tag_score(
        entry: ToolEntry, task_lower: str, prompt_tags: List[str]
    ) -> float:
        score = 0.0
        for tag in prompt_tags:
            if tag in entry.tags:
                score += 0.3
        if score > 0:
            ratio = difflib.SequenceMatcher(
                None, task_lower, " ".join(entry.tags)
            ).ratio()
            score += ratio * 0.4
        if entry.description:
            desc_score = difflib.SequenceMatcher(
                None, task_lower, entry.description.lower()
            ).ratio()
            score += desc_score * 0.3
        return min(score, 1.0)

    def get(self, name: str) -> Optional[ToolEntry]:
        return self._tools.get(name)

    def list_tools(self) -> Dict[str, ToolEntry]:
        return dict(self._tools)


tool_library = ToolLibrary()
