# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
import re
import asyncio
import time
import hashlib
from dataclasses import dataclass, field
from typing import Union, Dict, List, Optional, Any

from iaglobal.models.task import Task
from iaglobal.agents.agent_base import AgentBase
from iaglobal._paths import _detect_extension
from iaglobal.utils.logger import get_logger
from iaglobal.utils.helpers import run_async_safe
from iaglobal.obsidian.epigenetic_registry import EpigeneticRegistry
from iaglobal.core.dependency_enforcer import dependency_enforcer

logger = get_logger("iaglobal")

VALID_EXTENSIONS = {
    ".py",
    ".js",
    ".html",
    ".css",
    ".yaml",
    ".json",
    ".xml",
    ".md",
    ".php",
    ".tsx",
    ".ts",
    ".sql",
}
_CACHE: Dict[str, Dict] = {}
_CACHE_TTL = 300

EXTENSION_HINTS = {
    "python": ".py",
    "flask": ".py",
    "fastapi": ".py",
    "django": ".py",
    "javascript": ".js",
    "node": ".js",
    "react": ".tsx",
    "typescript": ".ts",
    "html": ".html",
    "css": ".css",
    "yaml": ".yaml",
    "yml": ".yaml",
    "json": ".json",
    "xml": ".xml",
    "markdown": ".md",
    "md": ".md",
    "php": ".php",
    "sql": ".sql",
    "reactpy": ".py",
    "reactpy-django": ".py",
}


@dataclass
class CodeArtifact:
    code: str = ""
    files: Dict[str, str] = field(default_factory=dict)
    model_used: str = ""
    score: float = 0.0

    @staticmethod
    def from_raw(raw: Any) -> "CodeArtifact":
        """Normaliza qualquer saída de nó em CodeArtifact.

        Contrato (congelado por tests/test_code_artifact.py):
        - None / {} vazios → code="", files={}
        - str → code=str
        - dict com "code" → usa code
        - dict com "output" (str) → usa output como code
        - dict com "output" (dict) → usa output["code"] se existir
        - dict com "files" mas sem code → NÃO promove arquivo a code
        - dict arbitrário (sem code/output/files) → code="", nunca str(dict)
        - CodeArtifact → retorna o próprio objeto (passthrough, ``is``)
        - objeto com .code/.files (ex: SolutionArtifact) → copia
        - objeto sem .code → code=""
        """
        if raw is None:
            return CodeArtifact()

        if isinstance(raw, CodeArtifact):
            return raw

        # objetos com atributos .code/.files (SolutionArtifact, etc.)
        if hasattr(raw, "code") or hasattr(raw, "files"):
            code = getattr(raw, "code", "") or ""
            files = getattr(raw, "files", None) or {}
            score = getattr(raw, "score", 0.0) or 0.0
            if not isinstance(code, str):
                code = ""
            if not isinstance(files, dict):
                files = {}
            return CodeArtifact(code=code, files=dict(files), score=float(score))

        if isinstance(raw, str):
            return CodeArtifact(code=raw)

        if isinstance(raw, dict):
            code = raw.get("code")
            if code is None:
                output = raw.get("output")
                if isinstance(output, str):
                    code = output
                elif isinstance(output, dict):
                    code = output.get("code")
            if not isinstance(code, str):
                code = ""
            # Contrato (tests/test_code_artifact.py):
            # - code/output presentes -> normaliza code e PRESERVA files
            # - apenas files (sem code/output) -> code="", files={}
            files = raw.get("files") or {}
            if not isinstance(files, dict):
                files = {}
            return CodeArtifact(
                code=code,
                files=dict(files) if code else {},
                score=float(raw.get("score", 0.0) or 0.0),
            )

        # fallback seguro: nunca stringifica estruturas arbitrárias
        return CodeArtifact()


class CoderAgent(AgentBase):
    def __init__(self, temperatura: float = 0.5, estilo: str = "direto, minimalista"):
        super().__init__(agent_name="coder")
        self.temperatura = temperatura
        self.estilo = estilo
        self._quality_scores: Dict[str, List[float]] = {}
        self.epigenetic_registry = EpigeneticRegistry()
        self.agent_id = f"coder_agent_{id(self) % 10000}"

    def _cache_key(self, task: str, contexto: str = "") -> str:
        raw = f"{task}|{contexto}|{self.estilo}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def _get_cached(self, key: str) -> Optional[CodeArtifact]:
        entry = _CACHE.get(key)
        if entry and (time.monotonic() - entry["ts"]) < _CACHE_TTL:
            logger.debug("[CACHE] HIT for key=%s", key[:12])
            return entry["artifact"]
        return None

    def _set_cache(self, key: str, artifact: CodeArtifact):
        _CACHE[key] = {"artifact": artifact, "ts": time.monotonic()}
        if len(_CACHE) > 512:
            oldest = min(_CACHE.keys(), key=lambda k: _CACHE[k]["ts"])
            _CACHE.pop(oldest, None)

    def _detect_extensions(self, code: str, task: str = "") -> List[str]:
        detected = _detect_extension(code, task)
        exts = [detected] if detected else []
        task_lower = task.lower()
        for keyword, ext in EXTENSION_HINTS.items():
            if keyword in task_lower and ext not in exts:
                exts.append(ext)
        return exts or [".py"]

    async def _consultar_librarian(self, task: str) -> Dict[str, Any]:
        try:
            from iaglobal.tools.tool_library import tool_library

            tool_entry, score = tool_library.match(task)
            if tool_entry and score >= 0.5:
                logger.info(
                    "[LIBRARIAN] Componente reutilizavel: %s (score=%.2f)",
                    tool_entry.name,
                    score,
                )
                return {"components": [tool_entry], "reused_count": 1}
            return {"components": [], "reused_count": 0}
        except Exception as e:
            logger.debug("[LIBRARIAN] Erro: %s", e)
            return {"components": [], "reused_count": 0}

    @staticmethod
    def _parece_codigo(texto: str) -> bool:
        """Verifica se o texto parece código executável, não relatório/diagnóstico."""
        if not texto or len(texto) < 20:
            return False
        # Rejeita relatórios que começam com cabeçalhos de diagnóstico
        cabecalhos_ruido = [
            "=== architecture",
            "=== validation",
            "=== report",
            "análise",
            "analise",
            "diagnóstico",
            "diagnostico",
            "problemas detectados",
            "issues found",
            "relatório",
        ]
        for h in cabecalhos_ruido:
            if texto.lower().startswith(h) or h in texto.lower()[:80]:
                return False
        # Aceita se tiver marcadores de código
        markers = [
            "<!DOCTYPE",
            "<html",
            "<head",
            "<body",
            "<div",
            "<script",
            "<style",
            "def ",
            "class ",
            "import ",
            "from ",
            "async def",
            "function ",
            "const ",
            "let ",
            "var ",
            "app =",
            "return ",
            "if __name__",
        ]
        return any(m in texto for m in markers)

    async def _consultar_skill_registry(self, task: str) -> str:
        try:
            from iaglobal.evolution.skills.native.skill_registry import skill_registry

            skills = skill_registry.list_skills(active_only=True)
            task_lower = task.lower()
            candidates = []
            for skill in skills:
                if not callable(skill.run_fn):
                    continue
                tags = " ".join(skill.tags).lower()
                desc = skill.description.lower()
                name = skill.name.lower()
                for keyword in task_lower.split():
                    if len(keyword) < 3:
                        continue
                    if keyword in tags or keyword in desc or keyword in name:
                        candidates.append((skill, 1.0))
                        break
            if not candidates:
                return ""
            best = max(candidates, key=lambda x: x[1])
            skill = best[0]
            logger.info(
                "[SKILL] Match: %s (v%s, %s)",
                skill.name,
                skill.version,
                skill.description[:60],
            )
            result = skill.run_fn({"task": task, "code": "", "input": {"task": task}})
            if hasattr(result, "__await__"):
                result = await result
            if isinstance(result, dict):
                codigo = ""
                for key in (
                    "code",
                    "output",
                    "fixed_code",
                    "integrated_code",
                    "frontend_code",
                    "backend_code",
                ):
                    val = result.get(key)
                    if val and isinstance(val, str) and len(val.strip()) > 10:
                        candidate = val.strip()
                        if self._parece_codigo(candidate):
                            codigo = candidate
                            break
                if codigo:
                    logger.info(
                        "[SKILL] Output validado como codigo: %d chars", len(codigo)
                    )
                    return codigo
                logger.info("[SKILL] Output rejeitado — nao parece codigo executavel")
            return ""
        except Exception as e:
            logger.debug("[SKILL] Erro: %s", e)
            return ""

    async def _validar_com_syntax_sentinel(self, codigo: str) -> str:
        try:
            from iaglobal.graphs.nodes.syntax_sentinel import run_syntax_sentinel

            result = await run_syntax_sentinel(
                {"memory": {"coder": {"output": codigo}}}
            )
            fixed = result.get("output", "")
            if fixed and len(fixed.strip()) > 10:
                return fixed.strip()
            return codigo
        except Exception as e:
            logger.debug("[SYNTAX] Erro: %s", e)
            return codigo

    async def _gerar_esqueleto(self, task: str) -> str:
        task_lower = task.lower()
        linhas = []
        # HTML/Frontend primeiro — tem precedência sobre keywords genéricas
        if "html" in task_lower or any(
            w in task_lower
            for w in ["pagina", "pagina web", "site", "frontend", "interface", "web"]
        ):
            estilo_escuro = any(
                w in task_lower for w in ["escuro", "dark", "preto", "black", "noturno"]
            )
            bg = "#1a1a2e" if estilo_escuro else "#ffffff"
            surface = "#16213e" if estilo_escuro else "#f5f5f5"
            text = "#e0e0e0" if estilo_escuro else "#333333"
            primary = "#e94560" if estilo_escuro else "#007bff"
            input_bg = "#0f3460" if estilo_escuro else "#ffffff"
            input_border = "#e94560" if estilo_escuro else "#ced4da"
            linhas.extend(
                [
                    "<!DOCTYPE html>",
                    '<html lang="pt-BR">',
                    "<head>",
                    '    <meta charset="UTF-8">',
                    '    <meta name="viewport" content="width=device-width, initial-scale=1.0">',
                    f"    <title>Aplicacao</title>",
                    "    <style>",
                    f"        * {{ margin: 0; padding: 0; box-sizing: border-box; }}",
                    f"        body {{ background: {bg}; color: {text}; font-family: system-ui, sans-serif; line-height: 1.6; }}",
                    f"        .container {{ max-width: 600px; margin: 40px auto; padding: 24px; background: {surface}; border-radius: 12px; }}",
                    f"        h1 {{ font-size: 1.5rem; margin-bottom: 16px; }}",
                    f"        input, select, textarea {{ width: 100%; padding: 10px; margin: 8px 0; background: {input_bg}; color: {text}; border: 1px solid {input_border}; border-radius: 6px; font-size: 1rem; }}",
                    f"        button {{ background: {primary}; color: #fff; padding: 10px 20px; border: none; border-radius: 6px; cursor: pointer; font-size: 1rem; }}",
                    f"        button:hover {{ opacity: 0.9; }}",
                    f"        .result {{ margin-top: 16px; padding: 16px; background: {input_bg}; border-radius: 6px; }}",
                    "    </style>",
                    "</head>",
                    "<body>",
                    '    <div class="container">',
                    "        <h1>Calculadora</h1>",
                    '        <input type="number" id="valor" placeholder="Valor">',
                    '        <button onclick="calcular()">Calcular</button>',
                    '        <div id="resultado" class="result"></div>',
                    "    </div>",
                    "    <script>",
                    "        function calcular() {",
                    "            const v = parseFloat(document.getElementById('valor').value) || 0;",
                    "            document.getElementById('resultado').innerHTML = 'Resultado: R$ ' + v.toFixed(2);",
                    "        }",
                    "    </script>",
                    "</body>",
                    "</html>",
                ]
            )
        elif "flask" in task_lower or "api" in task_lower:
            linhas.extend(
                [
                    "from flask import Flask, jsonify, request",
                    "",
                    "app = Flask(__name__)",
                    "",
                    "@app.route('/health', methods=['GET'])",
                    "def health():",
                    "    return jsonify({'status': 'ok'})",
                    "",
                    "if __name__ == '__main__':",
                    "    app.run(debug=True)",
                ]
            )
        elif "class" in task_lower or "classe" in task_lower:
            linhas.extend(
                [
                    "class AppService:",
                    "    def __init__(self):",
                    "        pass",
                    "",
                    "    def process(self, data):",
                    "        return data",
                ]
            )
        elif (
            "script" in task_lower or "funcao" in task_lower or "function" in task_lower
        ):
            linhas.extend(
                [
                    "def main():",
                    "    pass",
                    "",
                    "if __name__ == '__main__':",
                    "    main()",
                ]
            )
        else:
            return ""
        return "\n".join(linhas)

    async def _registrar_no_tool_library(self, codigo: str, task: str) -> None:
        try:
            from iaglobal.tools.tool_library import tool_library

            tags = [w.lower() for w in task.split() if len(w) > 3][:5]
            tool_library.register_from_code(
                name=f"auto_{hashlib.sha256(codigo.encode()).hexdigest()[:8]}",
                code=codigo,
                tags=tags,
            )
            logger.info("[EVOLUCAO] Coder registrou ToolLibrary | tags=%s", tags)
        except Exception as e:
            logger.debug("[EVOLUCAO] ToolLibrary: %s", e)

    async def _avaliar_qualidade(self, codigo: str, task: str) -> float:
        try:
            from iaglobal.validation.scoring import calculate_score

            score = await asyncio.to_thread(calculate_score, codigo)
            return score
        except Exception:
            pass
        score = 50.0
        if not codigo:
            return 0.0
        linhas = codigo.splitlines()
        if len(linhas) >= 5:
            score += 10
        if re.search(r"def |class ", codigo):
            score += 10
        if re.search(r"logger\.(info|error|warning|exception)", codigo):
            score += 10
        if re.search(r"try:\s*\n.*\n\s*except", codigo):
            score += 10
        if re.search(r'"""|"""', codigo):
            score += 5
        if task and re.search(
            task.split()[-1] if task.split() else "", codigo, re.IGNORECASE
        ):
            score += 10
        return min(score, 100.0)

    async def generate(
        self,
        task: Union[str, "Task"],
        contexto: str = "",
        erros_contexto: str = "",
        security_feedback: str = "",
        search_results: str = "",
    ) -> CodeArtifact:
        task_str = task.text if hasattr(task, "text") else str(task)
        task_hash = hashlib.sha3_512(task_str.encode()).hexdigest()[:16]

        cache_key = self._cache_key(task_str, contexto)
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        logger.info("[CODER] Processando com recursos locais | estilo=%s", self.estilo)
        codigo = ""

        # Layer 1: ToolLibrary — componente reutilizavel
        try:
            librarian = await self._consultar_librarian(task_str)
            if librarian["reused_count"] > 0 and librarian["components"]:
                tool = librarian["components"][0]
                codigo = (
                    getattr(tool, "code", "") or getattr(tool, "template", "") or ""
                ).strip()
                if codigo:
                    logger.info("[CODER] Layer 1: ToolLibrary hit — %s", tool.name)
        except Exception as e:
            logger.debug("[CODER] Layer 1: %s", e)

        # Layer 1.5: SearchCodeAssembler — monta codigo de resultados de busca
        if not codigo and search_results:
            try:
                from iaglobal.search.search_code_extractor import (
                    extract_from_search_results,
                )
                from iaglobal.core.code_assembler import CodeAssembler

                blocks = extract_from_search_results(search_results, min_lines=1)
                if blocks:
                    lang = (
                        "html"
                        if any(
                            "html" in task_str.lower() or w in task_str.lower()
                            for w in [
                                "pagina",
                                "pagina web",
                                "site",
                                "frontend",
                                "interface",
                                "pagina",
                                "web",
                            ]
                        )
                        else "python"
                    )
                    assembler = CodeAssembler()
                    result = assembler.assemble(blocks, language=lang)
                    if result.valid and result.code and len(result.code.strip()) > 50:
                        codigo = result.code
                        logger.info(
                            "[CODER] Layer 1.5: SearchCodeAssembler hit — %d blocos usados de %d (lang=%s)",
                            result.blocks_used,
                            result.blocks_total,
                            lang,
                        )
            except Exception as e:
                logger.debug("[CODER] Layer 1.5: %s", e)

        # Layer 2: SkillRegistry — skill registrada
        if not codigo:
            try:
                codigo_skill = await self._consultar_skill_registry(task_str)
                if codigo_skill:
                    codigo = codigo_skill
                    logger.info("[CODER] Layer 2: SkillRegistry hit")
            except Exception as e:
                logger.debug("[CODER] Layer 2: %s", e)

        # Layer 3: SyntaxSentinel — valida e corrige sintaxe se ja gerou
        if codigo:
            validated = await self._validar_com_syntax_sentinel(codigo)
            if validated and len(validated.strip()) > 10:
                codigo = validated
                logger.info("[CODER] Layer 3: SyntaxSentinel validado")
        else:
            # Layer 3b: esqueleto baseado na task
            codigo = await self._gerar_esqueleto(task_str)
            if codigo:
                logger.info("[CODER] Layer 3b: Esqueleto gerado")

        # Layer 4: CodeScorer — qualidade + evolução
        if codigo and len(codigo.strip()) > 10:
            quality = await self._avaliar_qualidade(codigo, task_str)

            # Layer 5: Auto-Correção — lê o código como compilador e corrige
            from iaglobal.core.auto_correction import auto_correction

            correcao = await asyncio.to_thread(
                auto_correction.corrigir, codigo, task_str
            )
            if correcao.foi_corrigido:
                codigo = correcao.codigo_final
                quality = await self._avaliar_qualidade(codigo, task_str)
                logger.info(
                    "[CODER] Layer 5: Auto-correcao aplicada | issues=%d fixes=%d lang=%s quality=%.1f",
                    len(correcao.issues),
                    len(correcao.fixes_aplicados),
                    correcao.linguagem,
                    quality,
                )

            # Layer 6: DependencyEnforcer — verifica imports contra stdlib/instalados
            enforce_result = await asyncio.to_thread(
                dependency_enforcer.enforce, codigo
            )
            if enforce_result.was_modified:
                codigo = enforce_result.modified
                quality = await self._avaliar_qualidade(codigo, task_str)
                logger.info(
                    "[CODER] Layer 6: DependencyEnforcer aplicado | wrapped=%d unknown=%d quality=%.1f",
                    len(enforce_result.wrapped_imports),
                    len(enforce_result.unknown_imports),
                    quality,
                )
                for imp in enforce_result.wrapped_imports:
                    logger.info("[CODER]   >> Import envolvido em try/except: %s", imp)

            exts = self._detect_extensions(codigo, task_str)
            files = {}
            for ext in exts:
                nome = f"output{ext}" if ext else "output.py"
                files[nome] = codigo
            if not files:
                files["output.py"] = codigo

            stripped = codigo.strip()
            if (
                stripped.endswith("class ")
                or stripped.endswith("def ")
                or stripped.endswith("class :")
                or stripped.endswith("def :")
            ):
                logger.warning(
                    "[CODER] Código gerado parece truncado em bloco incompleto | len=%d | suffix=%s",
                    len(stripped),
                    stripped[-80:],
                )

            artifact = CodeArtifact(
                code=codigo, files=files, model_used="local_tools", score=quality
            )
            self._set_cache(cache_key, artifact)
            await self.epigenetic_registry.record_success(self.agent_id, task_hash)

            # Evolução: registra código de alta qualidade no ToolLibrary
            if quality >= 70:
                await self._registrar_no_tool_library(codigo, task_str)

            return artifact

        logger.info("[CODER] Recursos locais insuficientes — gap delegado ao Critic")
        await self.epigenetic_registry.record_failure(
            self.agent_id, task_hash, "local_only", {"task": task_str[:200]}
        )
        return CodeArtifact(code="", files={})

    def run(self, task) -> CodeArtifact:
        return run_async_safe(self.generate, task)

    # REPAIR SIGNAL — Ciclo Debugger ↔ Coder (anti-apoptose)
    _signal_repair_requested: bool = False
    _last_syntax_error: Optional[str] = None

    def request_repair(self, error: str) -> None:
        self._signal_repair_requested = True
        self._last_syntax_error = error
        logger.warning(
            "[CODER] Solicitando reparo ao DebuggerAgent | erro=%s", error[:120]
        )

    def acknowledge_repair(self) -> None:
        self._signal_repair_requested = False
        self._last_syntax_error = None
        logger.info("[CODER] Reparo concluido — agente reabilitado")

    @property
    def needs_repair(self) -> bool:
        return self._signal_repair_requested
