"""
auditoria_arquitetural.py — Geração 2

Detecta funções órfãs com baixa taxa de falsos positivos via 8 filtros em cascata:

  FP-1  Colisão de nomes   → dict {nome: str} silenciava funções homônimas em arquivos
                              distintos; corrigido com defaultdict(set).
  FP-2  Decoradores        → fixtures, routes, commands, abstractmethod… nunca são
                              chamados pelo código interno; excluídos explicitamente.
  FP-3  Padrões de nome    → test_*, run_* (despacho dinâmico iaglobal), handle_*,
                              on_*, visit_*, main, setup…
  FP-4  Callbacks          → funções passadas como argumento (executor.submit(fn),
                              [handler_a, handler_b]) sem chamada direta.
  FP-5  Despacho dinâmico  → getattr(obj, "run_node")() capturado via strings.
  FP-6  API pública        → nomes declarados em __all__.
  FP-7  Property variants  → @prop.setter / @prop.deleter acessados por atribuição.
  FP-8  visit_* genérico   → qualquer visitor, não só ast.NodeVisitor.
"""

import ast
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from collections import defaultdict

logger = logging.getLogger(__name__)

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent

# ──────────────────────────────────────────────────────────────────────────────
# CONSTANTES DE FILTRAGEM
# ──────────────────────────────────────────────────────────────────────────────

_DIRS_IGNORAR: frozenset[str] = frozenset({
    ".venv", "venv", ".git", "__pycache__", ".pytest_cache",
    "node_modules", "memory/data", "server",
})

# Dunders chamados implicitamente pelo interpretador Python
_DUNDERS: frozenset[str] = frozenset({
    "__init__", "__str__", "__repr__", "__enter__", "__exit__",
    "__new__", "__del__", "__len__", "__getitem__", "__setitem__",
    "__iter__", "__next__", "__contains__", "__call__", "__bool__",
    "__hash__", "__eq__", "__ne__", "__lt__", "__le__", "__gt__", "__ge__",
    "__delitem__", "__aenter__", "__aexit__", "__anext__", "__aiter__",
    "__post_init__", "__post_del__", "__copy__", "__deepcopy__",
    "__getstate__", "__setstate__", "__class_getitem__", "__init_subclass__",
    "__get__", "__set__", "__delete__", "__missing__", "__reversed__",
    "__format__", "__bytes__", "__fspath__", "__index__",
    "__reduce__", "__reduce_ex__", "__sizeof__",
    # aritméticos / bitwise
    "__add__", "__radd__", "__sub__", "__rsub__", "__mul__", "__rmul__",
    "__truediv__", "__rtruediv__", "__floordiv__", "__rfloordiv__",
    "__mod__", "__rmod__", "__pow__", "__rpow__",
    "__lshift__", "__rshift__", "__and__", "__or__", "__xor__",
    "__neg__", "__pos__", "__abs__", "__invert__",
    "__int__", "__float__", "__complex__",
    "__iadd__", "__isub__", "__imul__", "__itruediv__", "__ifloordiv__",
    "__imod__", "__ipow__", "__ilshift__", "__irshift__",
    "__iand__", "__ior__", "__ixor__",
})

# FP-2: leaf-names de decoradores que indicam chamador externo
_DECORADORES_EXTERNOS: frozenset[str] = frozenset({
    # pytest
    "fixture", "parametrize",
    # click / typer
    "command", "group", "argument", "option", "pass_context", "pass_obj",
    # web (Flask, FastAPI, Django, Starlette, Litestar…)
    "route", "get", "post", "put", "delete", "patch", "head", "options",
    "websocket", "before_request", "after_request", "teardown_request",
    "errorhandler", "app_errorhandler",
    # context managers
    "contextmanager", "asynccontextmanager",
    # ABC / typing
    "abstractmethod", "abstractproperty", "overload", "override",
    # eventos / sinais
    "on", "on_event", "handler", "listener", "subscriber",
    "receiver", "connect", "slot", "signal",
    # celery / arq / rq
    "task", "shared_task", "periodic_task",
    # dataclass (métodos gerados sinteticamente)
    "dataclass",
    # descritores de classe
    "staticmethod", "classmethod",
    # agendadores
    "scheduled_job",
})

# FP-3: nomes de funções que são entry points ou chamadas externas
_NOMES_EXTERNOS: frozenset[str] = frozenset({
    "main", "run", "cli", "app",
    "setup", "teardown",
    "setUp", "tearDown", "setUpClass", "tearDownClass",
    "create_app", "create_server", "app_factory",
    "lifespan", "startup", "shutdown",
    "lambda_handler", "handler",
    "wsgi_app", "asgi_app",
    "worker", "celery_worker",
    "conftest",
})

# FP-3: prefixos que indicam despacho externo ou dinâmico
_PREFIXOS_EXTERNOS: tuple[str, ...] = (
    "test_",    # pytest — coletado pelo runner
    "run_",     # iaglobal: dynamic dispatch via getattr no Nodes singleton
    "handle_",  # event handlers
    "on_",      # callbacks de evento
    "visit_",   # FP-8: qualquer visitor, não só NodeVisitor
    "do_",      # BaseHTTPRequestHandler e frameworks similares
    "emit_",    # emissores de evento
)

# FP-3: sufixos que indicam hook / callback
_SUFIXOS_EXTERNOS: tuple[str, ...] = (
    "_handler",
    "_callback",
    "_hook",
    "_listener",
    "_middleware",
    "_filter",
    "_factory",
)


# ──────────────────────────────────────────────────────────────────────────────
# UTILITÁRIOS AST
# ──────────────────────────────────────────────────────────────────────────────

def _nomes_decorator(dec: ast.expr) -> set[str]:
    """
    Extrai todos os identificadores simples de uma expressão de decorador.

    Exemplos:
      @property           → {'property'}
      @pytest.fixture     → {'pytest', 'fixture'}
      @app.route("/")     → {'app', 'route'}
      @pytest.mark.slow   → {'pytest', 'mark', 'slow'}
    """
    nomes: set[str] = set()
    node: ast.expr = dec
    while isinstance(node, ast.Call):
        node = node.func  # type: ignore[assignment]
    while isinstance(node, ast.Attribute):
        nomes.add(node.attr)
        node = node.value  # type: ignore[assignment]
    if isinstance(node, ast.Name):
        nomes.add(node.id)
    return nomes


def _is_property_variant(dec: ast.expr) -> bool:
    """FP-7: Retorna True para @prop.setter, @prop.deleter ou @prop.getter."""
    node: ast.expr = dec
    if isinstance(node, ast.Call):
        node = node.func  # type: ignore[assignment]
    return isinstance(node, ast.Attribute) and node.attr in ("setter", "deleter", "getter")


def _extrair_all_exports(arvore: ast.AST) -> set[str]:
    """FP-6: Extrai nomes declarados em __all__ = [...] ou __all__ += [...]."""
    exports: set[str] = set()
    for node in ast.walk(arvore):
        if isinstance(node, (ast.Assign, ast.AugAssign)):
            target = node.targets[0] if isinstance(node, ast.Assign) else node.target
            if isinstance(target, ast.Name) and target.id == "__all__":
                value = node.value
                if isinstance(value, (ast.List, ast.Tuple, ast.Set)):
                    for elt in value.elts:
                        if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                            exports.add(elt.value)
    return exports


def _extrair_referencias_callback(arvore: ast.AST) -> set[str]:
    """
    FP-4: Coleta nomes passados como valor (callback, higher-order) sem serem
    o alvo direto de uma chamada.

    Cobre:
      executor.submit(func)
      bus.subscribe("evt", self.on_event)
      handlers = [func_a, func_b]
      dispatch = {"key": func}
    """
    refs: set[str] = set()
    for node in ast.walk(arvore):
        if isinstance(node, ast.Call):
            for arg in node.args:
                if isinstance(arg, ast.Name):
                    refs.add(arg.id)
                elif isinstance(arg, ast.Attribute):
                    refs.add(arg.attr)
            for kw in node.keywords:
                if isinstance(kw.value, ast.Name):
                    refs.add(kw.value.id)
                elif isinstance(kw.value, ast.Attribute):
                    refs.add(kw.value.attr)
        elif isinstance(node, (ast.List, ast.Tuple, ast.Set)):
            for elt in node.elts:
                if isinstance(elt, ast.Name):
                    refs.add(elt.id)
        elif isinstance(node, ast.Dict):
            for v in node.values:
                if v and isinstance(v, ast.Name):
                    refs.add(v.id)
    return refs


def _extrair_strings_getattr(arvore: ast.AST) -> set[str]:
    """
    FP-5: Coleta nomes resolvidos via getattr/hasattr/setattr com string literal.

    Cobre:
      getattr(self, "run_coder")()      → 'run_coder'
      getattr(obj, f"run_{name}")       → não capturável (f-string), aceitável
    """
    nomes: set[str] = set()
    for node in ast.walk(arvore):
        if not isinstance(node, ast.Call):
            continue
        if not (isinstance(node.func, ast.Name) and node.func.id in ("getattr", "hasattr", "setattr")):
            continue
        if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant):
            val = node.args[1].value
            if isinstance(val, str) and val.isidentifier():
                nomes.add(val)
    return nomes


# ──────────────────────────────────────────────────────────────────────────────
# DATACLASS DE RESULTADO
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class ResultadoAnalise:
    """Agrega todos os artefatos produzidos pela análise multi-passo."""
    funcoes: set[str] = field(default_factory=set)
    chamadas: defaultdict[str, set[str]] = field(
        default_factory=lambda: defaultdict(set)
    )
    funcoes_externas: set[str] = field(default_factory=set)   # nomes simples
    refs_callback: set[str] = field(default_factory=set)
    strings_dinamicas: set[str] = field(default_factory=set)
    exportacoes: set[str] = field(default_factory=set)


# ──────────────────────────────────────────────────────────────────────────────
# ANALYZER
# ──────────────────────────────────────────────────────────────────────────────

class Analyzer(ast.NodeVisitor):
    """
    Visita um módulo e coleta funções, chamadas e metadados de exclusão.

    Campos produzidos:
      funcoes           — conjunto de 'arquivo::nome' de toda função encontrada
      chamadas          — origem → {nomes simples chamados diretamente}
      funcoes_externas  — nomes simples marcados para exclusão do relatório de órfãs
    """

    def __init__(self, arquivo: Path, propriedades_globais: set[str]) -> None:
        self.arquivo = arquivo
        self.funcao_atual: str | None = None
        self.funcoes: set[str] = set()
        self.propriedades = propriedades_globais        # referência compartilhada
        self.chamadas: defaultdict[str, set[str]] = defaultdict(set)
        self.funcoes_externas: set[str] = set()
        self.class_stack: list[ast.ClassDef] = []

    # ── visitantes de estrutura ───────────────────────────────────────────────

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.class_stack.append(node)
        self.generic_visit(node)
        self.class_stack.pop()

    # ── visitantes de função ──────────────────────────────────────────────────

    def _processar_funcao(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        nome_completo = f"{self.arquivo}::{node.name}"
        self.funcoes.add(nome_completo)

        for dec in node.decorator_list:
            dec_nomes = _nomes_decorator(dec)

            # Rastreia @property para o visitor_Attribute poder detectar acessos
            if "property" in dec_nomes:
                self.propriedades.add(node.name)

            # FP-7: setter/deleter são acionados por atribuição, nunca por chamada
            if _is_property_variant(dec):
                self.funcoes_externas.add(node.name)

            # FP-2: decorador externo → chamada vem do framework
            if dec_nomes & _DECORADORES_EXTERNOS:
                self.funcoes_externas.add(node.name)

        # FP-3: padrão de nome indica chamador externo ou despacho dinâmico
        nome = node.name
        if (
            nome in _NOMES_EXTERNOS
            or nome.startswith(_PREFIXOS_EXTERNOS)
            or nome.endswith(_SUFIXOS_EXTERNOS)
        ):
            self.funcoes_externas.add(nome)

        anterior = self.funcao_atual
        self.funcao_atual = nome_completo
        self.generic_visit(node)
        self.funcao_atual = anterior

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._processar_funcao(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._processar_funcao(node)

    # ── visitantes de uso ─────────────────────────────────────────────────────

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if (
            self.funcao_atual
            and isinstance(node.ctx, ast.Load)
            and node.attr in self.propriedades
        ):
            self.chamadas[self.funcao_atual].add(node.attr)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        if self.funcao_atual:
            if isinstance(node.func, ast.Name):
                self.chamadas[self.funcao_atual].add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                self.chamadas[self.funcao_atual].add(node.func.attr)
        self.generic_visit(node)


# ──────────────────────────────────────────────────────────────────────────────
# INFRAESTRUTURA DE VARREDURA
# ──────────────────────────────────────────────────────────────────────────────

def _listar_pastas_ignorar(raiz: Path) -> set[Path]:
    """Retorna paths absolutos de diretórios a ignorar dentro de `raiz`."""
    ignorar: set[Path] = set()
    for sub in _DIRS_IGNORAR:
        caminho = (raiz / sub).resolve()
        if caminho.exists():
            ignorar.add(caminho)
    return ignorar


def _deve_ignorar(arquivo: Path, ignorar_dirs: set[Path]) -> bool:
    resolved = arquivo.resolve()
    return any(resolved.is_relative_to(ignorar) for ignorar in ignorar_dirs)


# ──────────────────────────────────────────────────────────────────────────────
# ANÁLISE DO PROJETO
# ──────────────────────────────────────────────────────────────────────────────

def analisar_projeto(pasta: str) -> ResultadoAnalise:
    """
    Varre o projeto em dois passos:
      1. Indexação global de @property (necessária para visit_Attribute)
      2. Análise de chamadas + coleta de metadados de exclusão
    """
    pasta_path = Path(pasta).resolve()
    ignorar_dirs = _listar_pastas_ignorar(pasta_path)
    resultado = ResultadoAnalise()
    propriedades_globais: set[str] = set()

    arquivos_py = [
        arq for arq in Path(pasta).rglob("*.py")
        if not _deve_ignorar(arq, ignorar_dirs)
    ]

    # Passo 1 — indexar @property globalmente
    for arquivo in arquivos_py:
        try:
            arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
            for node in ast.walk(arvore):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if any("property" in _nomes_decorator(d) for d in node.decorator_list):
                        propriedades_globais.add(node.name)
        except Exception as exc:
            logger.error("Falha ao indexar propriedades em %s: %s", arquivo, exc)

    # Passo 2 — análise completa
    for arquivo in arquivos_py:
        try:
            codigo = arquivo.read_text(encoding="utf-8")
            arvore = ast.parse(codigo)
            rel = arquivo.resolve().relative_to(pasta_path)

            analisador = Analyzer(rel, propriedades_globais)
            analisador.visit(arvore)

            resultado.funcoes.update(analisador.funcoes)
            for origem, destinos in analisador.chamadas.items():
                resultado.chamadas[origem].update(destinos)
            resultado.funcoes_externas.update(analisador.funcoes_externas)

            # FP-4, FP-5, FP-6: coleta global por arvore
            resultado.refs_callback.update(_extrair_referencias_callback(arvore))
            resultado.strings_dinamicas.update(_extrair_strings_getattr(arvore))
            resultado.exportacoes.update(_extrair_all_exports(arvore))

        except Exception as exc:
            logger.error("Falha ao analisar %s: %s", arquivo, exc)

    return resultado


# ──────────────────────────────────────────────────────────────────────────────
# CLASSIFICAÇÃO DE ÓRFÃS
# ──────────────────────────────────────────────────────────────────────────────

def _motivo_exclusao(
    nome: str,
    chamadas_recebidas: dict[str, set[str]],
    resultado: ResultadoAnalise,
) -> str | None:
    """
    Retorna o motivo pelo qual `nome` NÃO é órfã, ou None se for órfã real.
    Usado no mapa de funções para auditabilidade dos filtros.
    """
    if nome in _DUNDERS:
        return "dunder"
    if nome in resultado.funcoes_externas:
        return "decorador/padrão de nome externo"
    if nome in chamadas_recebidas:
        return "chamada direta detectada"
    if nome in resultado.refs_callback:
        return "referência como callback"
    if nome in resultado.strings_dinamicas:
        return "getattr dinâmico"
    if nome in resultado.exportacoes:
        return "__all__"
    return None


def _classificar_orfas(resultado: ResultadoAnalise) -> list[dict]:
    """
    FP-1 (colisão de nomes): usa defaultdict(set) em vez de dict para mapear
    nome simples → todos os nomes completos. Um nome chamado em qualquer arquivo
    protege TODAS as funções homônimas no projeto.
    """
    # nome_simples → {nome_completo, ...}
    nomes_para_completos: defaultdict[str, set[str]] = defaultdict(set)
    for f in resultado.funcoes:
        nomes_para_completos[f.split("::")[-1]].add(f)

    # nome_simples → {chamadores}
    chamadas_recebidas: dict[str, set[str]] = {}
    for origem, destinos in resultado.chamadas.items():
        for destino in destinos:
            if destino in nomes_para_completos:
                if destino not in chamadas_recebidas:
                    chamadas_recebidas[destino] = set()
                chamadas_recebidas[destino].add(origem)

    orfas: list[dict] = []
    for nome_simples, nomes_completos in sorted(nomes_para_completos.items()):
        motivo = _motivo_exclusao(nome_simples, chamadas_recebidas, resultado)
        if motivo is not None:
            continue  # excluída por algum filtro
        for nome_completo in sorted(nomes_completos):
            orfas.append({
                "funcao": nome_completo,
                "nome": nome_simples,
                "arquivo": nome_completo.split("::")[0],
            })

    return orfas


# ──────────────────────────────────────────────────────────────────────────────
# GERAÇÃO DE RELATÓRIO
# ──────────────────────────────────────────────────────────────────────────────

_FILTROS_DESCRICAO = [
    "FP-1  Colisão de nomes: múltiplas funções homônimas tratadas corretamente",
    "FP-2  Decoradores externos: fixtures, routes, commands, abstractmethod...",
    "FP-3  Padrões de nome: test_*, run_*, handle_*, on_*, visit_*, main...",
    "FP-4  Referências como callback: funções passadas como argumento",
    "FP-5  Despacho dinâmico: getattr(obj, 'func') resolvido via string literal",
    "FP-6  API pública: nomes exportados via __all__",
    "FP-7  Property variants: @prop.setter e @prop.deleter",
    "FP-8  Visitor hooks genéricos: visit_* em qualquer classe visitor",
]


AUDITORIA_DIR = SCRIPT_DIR / "memory" / "data" / "auditoria"
AUDITORIA_DIR.mkdir(parents=True, exist_ok=True)
_DEFAULT_OUTPUT = str(AUDITORIA_DIR / "relatorio_funcoes.txt")


def gerar_relatorio(pasta: str, saida: str = _DEFAULT_OUTPUT, formato: str = "txt") -> None:
    """
    Analisa `pasta` e gera relatório de funções órfãs com 8 filtros anti-falso-positivo.
    """
    resultado = analisar_projeto(pasta)
    orfas = _classificar_orfas(resultado)

    # Reconstrói chamadas_recebidas para o mapa de funções no TXT
    nomes_para_completos: defaultdict[str, set[str]] = defaultdict(set)
    for f in resultado.funcoes:
        nomes_para_completos[f.split("::")[-1]].add(f)

    chamadas_recebidas: defaultdict[str, set[str]] = defaultdict(set)
    for origem, destinos in resultado.chamadas.items():
        for destino in destinos:
            if destino in nomes_para_completos:
                chamadas_recebidas[destino].add(origem)

    if formato == "json":
        relatorio = {
            "pasta_analisada": pasta,
            "total_funcoes": len(resultado.funcoes),
            "total_orfas": len(orfas),
            "filtros_aplicados": _FILTROS_DESCRICAO,
            "orfas": orfas,
            "todas_funcoes": sorted(resultado.funcoes),
        }
        if saida == "-":
            import sys
            sys.stdout.write(json.dumps(relatorio, indent=2, ensure_ascii=False) + "\n")
        else:
            with open(saida, "w", encoding="utf-8") as f:
                json.dump(relatorio, f, indent=2, ensure_ascii=False)
            logger.info("Relatório JSON salvo em %s", saida)
        return

    with open(saida, "w", encoding="utf-8") as f:
        f.write(f"Pasta analisada : {pasta}\n")
        f.write(f"Total de funções: {len(resultado.funcoes)}\n")
        f.write(f"Total de órfãs  : {len(orfas)}\n\n")

        f.write("=== FILTROS APLICADOS ===\n")
        for filtro in _FILTROS_DESCRICAO:
            f.write(f"  {filtro}\n")
        f.write("\n")

        f.write("=== MAPA DE FUNÇÕES ===\n\n")
        for func in sorted(resultado.funcoes):
            nome = func.split("::")[-1]
            f.write(f"FUNCAO: {func}\n")
            quem_chama = chamadas_recebidas.get(nome, set())
            if quem_chama:
                f.write("  CHAMADA POR:\n")
                for caller in sorted(quem_chama):
                    f.write(f"    - {caller}\n")
            else:
                motivo = _motivo_exclusao(nome, chamadas_recebidas, resultado)
                sufixo = f" (excluída: {motivo})" if motivo else ""
                f.write(f"  CHAMADA POR: NINGUÉM{sufixo}\n")
            f.write("\n")

        f.write("\n=== POSSÍVEIS ÓRFÃS ===\n\n")
        for item in orfas:
            f.write(f"{item['funcao']}\n")

    logger.info(
        "Relatório salvo em %s  (%d órfãs / %d funções)",
        saida, len(orfas), len(resultado.funcoes),
    )


# ──────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ──────────────────────────────────────────────────────────────────────────────

def main() -> None:
    import argparse
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    parser = argparse.ArgumentParser(
        description="Auditoria Arquitetural — detecta funções órfãs com baixa taxa de falsos positivos"
    )
    parser.add_argument(
        "pasta", nargs="?", default=str(PROJECT_DIR),
        help="Diretório raiz para analisar (default: projeto inteiro)",
    )
    parser.add_argument(
        "-o", "--output", default=_DEFAULT_OUTPUT,
        help=f"Arquivo de saída (default: {_DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "-f", "--formato", choices=["txt", "json"], default="txt",
        help="Formato de saída (default: txt)",
    )
    args = parser.parse_args()
    gerar_relatorio(args.pasta, args.output, args.formato)


if __name__ == "__main__":
    main()
