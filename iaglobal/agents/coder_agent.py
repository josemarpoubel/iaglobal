# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
import re
import ast
import time
import hashlib
import random
import traceback
import asyncio
from dataclasses import dataclass, field
from typing import Union, Dict, List, Optional

from iaglobal.models.task import Task
from iaglobal.observability.tracing import Tracer
from iaglobal.graphs.bandit import BanditPolicy, _get_bandit
from iaglobal.graphs.credit import CreditAssignmentEngine
from iaglobal.graphs.telemetry import ExecutionEvent
from iaglobal._paths import _detect_extension

from iaglobal.storage.batch_writer import batch_writer, Event
from iaglobal.utils.logger import get_logger
from iaglobal.utils.helpers import run_async_safe

logger = get_logger("iaglobal.agents.coder_agent")

VALID_EXTENSIONS = {".py", ".js", ".html", ".css", ".yaml", ".json", ".xml", ".md", ".php", ".tsx", ".ts", ".sql"}
_CACHE: Dict[str, Dict] = {}
_CACHE_TTL = 300

EXTENSION_HINTS = {
    "python": ".py", "flask": ".py", "fastapi": ".py", "django": ".py",
    "javascript": ".js", "node": ".js", "react": ".tsx", "typescript": ".ts",
    "html": ".html", "css": ".css", "yaml": ".yaml", "yml": ".yaml",
    "json": ".json", "xml": ".xml", "markdown": ".md", "md": ".md",
    "php": ".php", "sql": ".sql",
    "reactpy": ".py", "reactpy-django": ".py",  # ReactPy components são Python
}

@dataclass
class CodeArtifact:
    code: str = ""
    files: Dict[str, str] = field(default_factory=dict)
    model_used: str = ""
    score: float = 0.0

class CoderAgent:
    def __init__(self, temperatura: float = 0.5, estilo: str = "direto, minimalista"):
        self.temperatura = temperatura
        self.estilo = estilo
        self.bandit = _get_bandit()
        self.credit = CreditAssignmentEngine()
        self._quality_scores: Dict[str, List[float]] = {}

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

    def _build_prompt(self, task: str, contexto: str = "", erros_contexto: str = "", security_feedback: str = "") -> str:
        security_section = f"\nALERTA DE SEGURANÇA: {security_feedback}\n" if security_feedback else ""
        pdf_dark_hint = ""
        reactpy_hint = ""
        task_lower = task.lower()
        if ("pdf" in task_lower or "documento" in task_lower) and ("escuro" in task_lower or "dark" in task_lower):
            pdf_dark_hint = "\nDICA PDF TEMA ESCURO: Use set_fill_color(30,30,30) E rect(0,0,210,297,'F') APÓS cada add_page() para aplicar tema escuro em TODAS as páginas."
        if "reactpy" in task_lower:
            reactpy_hint = "\nDICA REACTPY: Use @component, html.* tags, hooks (use_state, use_effect). Design: dark theme (#0f0f23 bg, #ff6b6b accent)."
        return f"""Você é um Engenheiro de Software Sênior e Arquiteto Supremo de Sistemas Vivos Que Se Auto-Evoluem. Você é Um Criador de Tecnologias de Alto Nivel.
Estilo: {self.estilo}.
Contexto: {contexto or "Nenhum."}
Erros a reparar: {erros_contexto or "Nenhum."}
{security_section}{pdf_dark_hint}{reactpy_hint}
Tarefa: {task}
DIRETRIZES DE LOGGING (OBRIGATÓRIO):
- NÃO utilize `print()`.
- Sempre use o módulo nativo `logging`.
- Configure o logger no escopo global: `logger = logging.getLogger(__name__)`.
- Use `logger.info()` para fluxos normais e `logger.error()` ou `logger.exception()` para falhas.

DIRETRIZES DE ARQUITETURA:
- Estruture o código de forma clara, modular e reutilizável.
- Prefira funções puras e bem definidas, evitando efeitos colaterais desnecessários.
- Documente funções críticas com docstrings concisas e objetivas.
- Evite redundância e código boilerplate; mantenha simplicidade e legibilidade.
- Garanta compatibilidade com execução em sandbox e respeite restrições de segurança.

DIRETRIZES DE SEGURANÇA:
- NÃO utilize imports inseguros.
- NÃO utilize bibliotecas imcompativeis.
- Evite chamadas diretas ao sistema operacional que possam comprometer o ambiente.
- Todo acesso a modelos de IA deve passar pela BanditPolicy para garantir conformidade e otimização.
- Corrija imediatamente qualquer violação de sandbox ou policy.

DIRETRIZES DE QUALIDADE:
- O código deve ser eficiente e escalável, evitando complexidade desnecessária.
- Sempre valide entradas e trate exceções de forma robusta.
- Inclua comentários apenas quando agregarem clareza arquitetural.
- Garanta que o código seja sintaticamente válido e pronto para execução.
- Sempre teste o resultado final para certificar que não há erros.
- Sempre verifique se o resultado final é compativel com o prompt inicial.

REGRAS DE RETORNO:
- Retorne ESTRITAMENTE o código dentro de um bloco markdown da linguagem correspondente (ex: ```python ... ```).
- NÃO inclua explicações textuais fora do bloco."""

    def _extrair_bloco_markdown(self, texto: str) -> str:
        # Tenta encontrar blocos com ``` ou '''
        match = re.search(
            r"```(?:python|html|css|javascript|js|php|yaml|json|xml|sql|ts|tsx)?\s*(.*?)\s*```|'''(?:python|html|css|javascript|js|php|yaml|json|xml|sql|ts|tsx)?\s*(.*?)\s*'''",
            texto, re.DOTALL | re.IGNORECASE
        )
        if match:
            # Retorna o grupo 1 (se for ```) ou grupo 2 (se for ''')
            return (match.group(1) or match.group(2)).strip()
        return ""

    def _extrair_por_ast(self, texto: str) -> str:
        linhas = texto.splitlines()
        inicio = None
        for i, linha in enumerate(linhas):
            if linha.lstrip().startswith(("def ", "class ", "import ", "from ", "@", "async def ", "if __name__")):
                inicio = i
                break
        if inicio is None:
            return ""
        codigo = "\n".join(linhas[inicio:])
        while codigo:
            try:
                ast.parse(codigo)
                return codigo.strip()
            except SyntaxError as e:
                blocos = codigo.splitlines()
                if e.lineno is not None and 1 <= e.lineno <= len(blocos):
                    blocos.pop(e.lineno - 1)
                else:
                    blocos.pop()
                codigo = "\n".join(blocos)
        return ""

    def _extrair_texto_bruto(self, texto: str) -> str:
        sem_markers = re.sub(r"```[a-zA-Z]*\s*", "", texto).replace("```", "").strip()
        return sem_markers if sem_markers else texto.strip()

    def _extrair_codigo(self, resposta: str) -> str:
        codigo = self._extrair_bloco_markdown(resposta)
        if codigo:
            return codigo
        codigo = self._extrair_texto_bruto(resposta)
        if codigo:
            return codigo
        return self._extrair_por_ast(resposta)

    def _calcular_qualidade(self, codigo: str, task: str) -> float:
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
        if re.search(r"from typing import|from typing import", codigo):
            score += 5
        if task and re.search(task.split()[-1] if task.split() else "", codigo, re.IGNORECASE):
            score += 10
        return min(score, 100.0)

    def _registrar_metrica(self, modelo: str, codigo: str, latencia: float, sucesso: bool, task: str):
        score = self._calcular_qualidade(codigo, task) if sucesso else 0.0
        if modelo not in self._quality_scores:
            self._quality_scores[modelo] = []
        self._quality_scores[modelo].append(score)
        
        # Envia evento para telemetria (persistência em banco)
        batch_writer.emit(Event(
            event_type="CoderGeneration",
            payload=task[:100],
            model=modelo,
            latency_ms=round(latencia * 1000, 1),
            tokens_in=0,  # TODO: integrar com contagem real
            tokens_out=len(codigo) // 4  # Estimativa base
        ))

        Tracer.trace_event("CoderGeneration", {
            "model": modelo, "success": sucesso, "latency_ms": round(latencia * 1000, 1),
            "quality_score": round(score, 1), "code_len": len(codigo), "task": task[:80]
        })
        self.credit.record(ExecutionEvent(
            node="coder_agent", model=modelo, strategy="code_generation",
            latency=latencia, success=sucesso, reward=score / 100.0, error="" if sucesso else "validation_failed"
        ))

    def _modelos_candidatos(self, count: int = 3) -> List[str]:
        modelos = self.bandit.select_top_n(
            node="coder_agent", strategy="code_generation", n=count
        )
        modelos_ordenados = sorted(modelos, key=lambda m: (
            sum(self._quality_scores.get(m, [50])) / max(len(self._quality_scores.get(m, [1])), 1)
        ), reverse=True)
        return modelos_ordenados[:count]

    async def generate(
        self,
        task: Union[str, 'Task'],
        contexto: str = "",
        erros_contexto: str = "",
        security_feedback: str = ""
    ) -> CodeArtifact:
        task_str = task.text if hasattr(task, 'text') else str(task)
        cache_key = self._cache_key(task_str, contexto)
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        prompt = self._build_prompt(task_str, contexto, erros_contexto, security_feedback)
        modelos = self._modelos_candidatos(3)
        logger.info("[CODER] Gerando codigo via modelos=%s estilo=%s", modelos, self.estilo)

        async def _tentar(modelo: str, tentativa: int = 1) -> Optional[CodeArtifact]:
            try:
                t0 = time.monotonic()
                resultado = await self.bandit.async_execute_model(model=modelo, prompt=prompt, task_type="code")
                latencia = time.monotonic() - t0
                if not resultado or len(resultado.strip()) < 10:
                    logger.warning(f"[CODER] Conteúdo vazio/curto retornado pelo modelo {modelo}. Resultado: {repr(resultado)[:100]}")
                    return None
                codigo = self._extrair_codigo(resultado)
                if not codigo:
                    codigo = resultado.strip()
                exts = self._detect_extensions(codigo, task_str)
                quality = self._calcular_qualidade(codigo, task_str)
                self._registrar_metrica(modelo, codigo, latencia, True, task_str)
                files = {}
                for ext in exts:
                    nome = f"output{ext}" if ext else "output.py"
                    files[nome] = codigo
                if not files:
                    files["output.py"] = codigo
                return CodeArtifact(code=codigo, files=files, model_used=modelo, score=quality)
            except Exception as e:
                logger.warning("[CODER] Tentativa %d/%s falhou: %s", tentativa, modelo, e)
                return None

        resultados = await asyncio.gather(*[_tentar(m) for m in modelos], return_exceptions=True)
        validos = [r for r in resultados if isinstance(r, CodeArtifact) and r.code]

        if validos:
            validos.sort(key=lambda a: a.score, reverse=True)
            best = validos[0]
            self._set_cache(cache_key, best)
            Tracer.trace_event("CoderSuccess", {"model": best.model_used, "score": best.score, "files": list(best.files.keys())})
            return best

        logger.warning("[CODER] Todos os modelos falharam, tentando retry com backoff")
        for tentativa, modelo in enumerate(modelos):
            delay = min(2 ** tentativa + random.uniform(0, 1), 15)
            await asyncio.sleep(delay)
            resultado = await _tentar(modelo, tentativa + 2)
            if resultado:
                self._set_cache(cache_key, resultado)
                return resultado

        logger.error("[CODER] Falha apos todas as tentativas e retries")
        Tracer.trace_event("CoderFailed", {"task": task_str[:80]})
        return CodeArtifact(code="", files={})

    def run(self, task) -> CodeArtifact:
        return run_async_safe(self.generate, task)
