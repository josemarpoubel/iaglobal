# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/auditoria_arquitetural.py
"""
Auditoria arquitetural — detecção e classificação de colisões nominais.

Escaneia todos os arquivos Python do projeto, coleta símbolos (classes e funções)
e reporta aqueles que aparecem em mais de um módulo, classificando cada caso como:

  ✅ DOMÍNIOS DISTINTOS              — mesmo nome, responsabilidades diferentes
  🟩 IMPLEMENTAÇÃO DE PROTOCOLO       — contrato compartilhado, N implementações
  ⚠️ COLISÃO DE VOCABULÁRIO          — mesmo nome, semântica diferente (renomear)
  ❌ CONFIRMADA (AST hash idêntico)   — código estruturalmente igual
  ❌ DUPLICAÇÃO FUNCIONAL             — mesmo conceito, mesmo diretório

Uso:
    python -m iaglobal.auditoria_arquitetural
    python -m iaglobal.auditoria_arquitetural --include-functions
    python -m iaglobal.auditoria_arquitetural --json
"""

from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Tuple

PROJECT_DIR = Path(__file__).parent
EXCLUDE_DIRS = {"venv", ".git", "__pycache__", "node_modules"}
EXCLUDE_PARTS = {".deprecated", "tests", "temp", "scripts"}


# ── AST utilities ─────────────────────────────────────────────────────────


def _strip_ast_position(node: ast.AST) -> ast.AST:
    """Retorna cópia do AST sem posições (linha/coluna)."""
    for attr in ("lineno", "col_offset", "end_lineno", "end_col_offset"):
        if hasattr(node, attr):
            setattr(node, attr, None)
    for _field, value in ast.iter_fields(node):
        if isinstance(value, list):
            for item in value:
                if isinstance(item, ast.AST):
                    _strip_ast_position(item)
        elif isinstance(value, ast.AST):
            _strip_ast_position(value)
    return node


def _ast_hash(node: ast.AST) -> str:
    """Hash estrutural de 8 chars — ignora posições."""
    clean = _strip_ast_position(copy.deepcopy(node))
    raw = ast.dump(clean, indent=None)
    return hashlib.md5(raw.encode()).hexdigest()[:8]


def _function_signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    params: list[str] = []
    for arg in node.args.args:
        if arg.arg in ("self", "cls"):
            continue
        ann = ast.dump(arg.annotation) if arg.annotation else "?"
        params.append(f"{arg.arg}:{ann}")
    returns = ast.dump(node.returns) if node.returns else "?"
    prefix = "async " if isinstance(node, ast.AsyncFunctionDef) else ""
    return f"{prefix}({', '.join(params)}) -> {returns}"


def _class_signature(node: ast.ClassDef) -> str:
    bases = [ast.dump(b) for b in node.bases] if node.bases else []
    methods: list[str] = []
    for item in node.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not item.name.startswith("_"):
                methods.append(item.name)
    sig = f"[{', '.join(bases)}]" if bases else "[]"
    return f"{{{', '.join(sorted(methods))}}} | bases={sig}"


# ── Collection ────────────────────────────────────────────────────────────


def _should_skip(rel_path: str) -> bool:
    parts = rel_path.replace("\\", "/").split("/")
    if any(p in EXCLUDE_DIRS for p in parts):
        return True
    if any(ex in parts for ex in EXCLUDE_PARTS):
        return True
    return False


# Tupla: (caminho_relativo, linha, assinatura, ast_hash)
Location = Tuple[str, int, str, str]

_FUNCTION_MIN_LENGTH = 14


def collect_classes(root: Path) -> Dict[str, List[Location]]:
    classes: Dict[str, List[Location]] = defaultdict(list)
    for py_file in sorted(root.rglob("*.py")):
        rel = str(py_file.relative_to(root))
        if _should_skip(rel):
            continue
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                if node.name.startswith("_"):
                    continue
                sig = _class_signature(node)
                ah = _ast_hash(node)
                classes[node.name].append((rel, node.lineno, sig, ah))
    return classes


def collect_functions(root: Path) -> Dict[str, List[Location]]:
    funcs: Dict[str, List[Location]] = defaultdict(list)
    for py_file in sorted(root.rglob("*.py")):
        rel = str(py_file.relative_to(root))
        if _should_skip(rel):
            continue
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name.startswith("_") or len(node.name) < _FUNCTION_MIN_LENGTH:
                    continue
                sig = _function_signature(node)
                ah = _ast_hash(node)
                funcs[node.name].append((rel, node.lineno, sig, ah))
    return funcs


# ── Knowledge base ────────────────────────────────────────────────────────

_KNOWN_DISTINCT: Dict[str, str] = {
    "ASTResult": "security.ast_gateway=Resultado do parse AST (sandbox) | "
    "validation.gateway=Resultado de validação de AST",
    "Decision": "core.decision_engine=Decisão de roteamento de tarefas | "
    "validation.engine=Decisão de validação",
    "ExecutionEvent": "graphs.telemetry=Evento de execução de nós | "
    "observability.execution_events=Evento de execução persistido",
    "MetricsCollector": "cognition.awareness=Coletor de métricas de estado cognitivo | "
    "observability=Coletor de métricas de sistema",
    "NodeStatus": "cognition.awareness.models=Estado de nó cognitivo | "
    "evolution.execution_registry=Estado de nó evolutivo",
    "Severity": "agents.performance_audit=Severidade de auditoria | "
    "agents.performance_design=Severidade de design | "
    "agents.security_design=Severidade de segurança",
    "Task": "graphs.task=Modelo de tarefa do grafo | "
    "models.task=Modelo de tarefa de domínio",
    "Event": "models.event_bus=Evento genérico do barramento | "
    "storage.batch_writer=Evento de escrita em lote",
    "SecurityViolation": "graphs.bandit=Violacao PSC no Bandit | "
    "security.runtime_sandbox=Violacao de sandbox",
    "Signal": "core.acetylcholine_bus=Sinal do barramento | "
    "evolution.evo_agent=Sinal evolutivo",
    "get_execution_history": "api.mcp_server=Histórico via MCP | "
    "ui.data_converter=Histórico para UI",
    "ExecutionContext": "pipeline.context=Contexto do Pipeline | "
    "graphs=Estado operacional do Grafo | "
    "evolution=Replay Evolutivo | "
    "cognition.awareness=Estado Cognitivo",
    "ProviderRegistry": "DEPRECATED — use LLMProviderRegistry (providers.contract) ou ContextProviderRegistry (pipeline.context)",
    "LLMProviderRegistry": "providers.contract=Registry de LLM Providers (Groq, NVIDIA, Ollama, etc.)",
    "ContextProviderRegistry": "pipeline.context=Registry de ContextProviders por nó do pipeline",
    "FusionEngine": "genesis=Fusão Genética | memory=Fusão de Memórias",
    "RewardAggregator": "evolution=Recompensa Evolutiva | "
    "feedback=Recompensa de Feedback",
    "MetaLearner": "agents.ingestion=Meta-aprendizado de Ingestão | "
    "meta=Meta-aprendizado Geral",
    "ValidationResult": "validation.engine=Validação de Engine | "
    "agents.validator=Validação de Agentes | "
    "agents.semantic_validator=Validação Semântica | "
    "chappie.lineage_guardian=Guardião de Linhagem",
    "EventType": "events=Eventos de Decisão | models=Event Bus Genérico",
    "EventBus": "events=Barramento de Decisões | models=Pub-Sub Genérico",
    "get_db_connection": "_paths=Path resolver (retorna str) | "
    "memory.db_utils=Context manager de conexão SQLite",
    "load_skill_template": "evolution.skills.utils.__init__=Delegação lazy p/ evitar circularidade | "
    "evolution.skills.utils.template_loader=Implementação real com cache",
    "ensure_structure": "_paths=Garantia de diretórios + coleta de falhas | "
    "core.structure=Re-export (linha 10 sobrescreve com no-op — BUG)",
    # Resolvidos no Commit 7 (Vocabulary Cleanup):
    "RouterIndividual": "evolution.ga_router_optimizer=Vetor de pesos IVM com dict nomeado (uso interno)",
    "verify_genesis_blueprint_consistency": "genesis.certify_block=Compara 2 arquivos CBOR (evolutiva vs blueprint) — sync, bool",
}

_COLLISION_VOCABULARY: Dict[str, str] = {
    # Resolvidos no Commit 7:
    # - Individual → RouterIndividual (ga_router_optimizer.py)
    # - MCPPlaceholder → módulo compartilhado (mcp/placeholder.py)
    # - RuleResult → unificado (importado de semantic_validator.py)
    # - verify_genesis_integrity → verify_genesis_blueprint_consistency (certify_block.py)
    # Pendente (alto risco — requer testes):
    "SemanticValidatorAgent": "agents.semantic_validator=Sequencial, sem timeout | "
    "agents.validator=Paralelo, timeout, fail-fast (substitui o original) | "
    "→ consolidar: validator.py substitui ou estende semantic_validator.py",
}

_GENERIC_NAMES = {"Config", "Manager", "Handler", "Provider", "Base", "Error"}

_PROTOCOL_IMPLEMENTATIONS: Dict[str, str] = {
    "async_generate": "providers/*_provider.py=ProviderProtocol (12 implementações)",
}

_ALLOWED_DUPLICATES: Dict[str, int] = {
    "ExecutionContext": 4,
}


# ── Classification ────────────────────────────────────────────────────────


def _domain(path: str) -> str:
    parts = path.replace("\\", "/").split("/")
    return "/".join(parts[:2])


def _is_re_export_in_init(tree: ast.Module, name: str) -> bool:
    """True se o __init__.py apenas reexporta o símbolo (não o define)."""
    has_def = False
    has_reexport = False
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name == name:
                has_def = True
        elif isinstance(node, (ast.ImportFrom, ast.Import)):
            for alias in node.names:
                if alias.name == name or alias.asname == name:
                    has_reexport = True
    return has_reexport and not has_def


def _classify(name: str, locations: List[Location]) -> str:
    paths = [loc[0] for loc in locations]
    hashes = [loc[3] for loc in locations]

    # 0. AST idêntico sempre vence — mesmo que nome esteja na base conhecida
    if len(hashes) >= 2 and len(set(hashes)) == 1:
        return f"❌ CONFIRMADA (AST hash: {hashes[0]})"

    # 1. Base de conhecimento explícita
    if name in _KNOWN_DISTINCT:
        return f"✅ DOMÍNIOS DISTINTOS\n   {_KNOWN_DISTINCT[name]}"
    if name in _PROTOCOL_IMPLEMENTATIONS:
        return f"🟩 IMPLEMENTAÇÃO DE PROTOCOLO\n   {_PROTOCOL_IMPLEMENTATIONS[name]}"
    if name in _COLLISION_VOCABULARY:
        return f"⚠️ COLISÃO DE VOCABULÁRIO\n   {_COLLISION_VOCABULARY[name]}"

    # 2. Limite de ocorrências
    max_ok = _ALLOWED_DUPLICATES.get(name)
    if max_ok is not None and len(paths) > max_ok:
        return f"⚠️ EXCEDEU LIMITE ({max_ok}× permitido, {len(paths)}× encontrado)"

    # 3. Re-export em __init__.py (verificar antes do hash divergente)
    for loc in locations:
        if loc[0].endswith("__init__.py"):
            try:
                tree = ast.parse((PROJECT_DIR / loc[0]).read_text(encoding="utf-8"))
                if _is_re_export_in_init(tree, name):
                    return "⚠️ REVISAR (re-export em __init__.py confirmado)"
            except Exception:
                pass

    # 4. Hash estrutural divergente
    if len(hashes) >= 2 and len(set(hashes)) == len(hashes):
        return "⚠️ REVISAR (AST divergente — sem duplicação estrutural comprovada)"

    # 6. Domínio compartilhado
    dirs = set(_domain(p) for p in paths)
    if len(dirs) <= 1 and len(paths) >= 2:
        return "❌ DUPLICAÇÃO FUNCIONAL (mesmo diretório)"

    if name in _GENERIC_NAMES:
        return "⚠️ REVISAR (nome genérico)"

    return "⚠️ REVISAR"


def generate_reports(symbols: Dict[str, List[Location]]) -> List[Dict]:
    reports = []
    for name, locations in sorted(symbols.items()):
        if len(locations) < 2:
            continue
        classification = _classify(name, locations)
        report: Dict[str, Any] = {
            "name": name,
            "occurrences": len(locations),
            "locations": [(p, l) for p, l, _sig, _hash in sorted(locations)],
            "classification": classification,
        }
        hashes = set(loc[3] for loc in locations)
        if len(hashes) == 1 and len(locations) >= 2:
            report["ast_hash"] = list(hashes)[0]
        reports.append(report)
    return reports


def _print_ascii(reports: List[Dict]) -> None:
    print(f"\n=== COLISÕES NOMINAIS ({len(reports)} encontradas) ===\n")
    for r in reports:
        print(f"  {r['name']} ({r['occurrences']}×)")
        for path, line in r["locations"]:
            print(f"    {path}:{line}")
        if r.get("ast_hash"):
            print(f"    AST hash: {r['ast_hash']}")
        print(f"  → {r['classification']}")
        print()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Auditoria Arquitetural — Colisões Nominais"
    )
    parser.add_argument("--json", action="store_true", help="Saída JSON")
    parser.add_argument(
        "--include-functions",
        action="store_true",
        help="Incluir detecção de funções duplicadas (≥14 chars)",
    )
    args = parser.parse_args()

    reports: List[Dict] = []
    classes = collect_classes(PROJECT_DIR)
    reports.extend(generate_reports(classes))

    if args.include_functions:
        funcs = collect_functions(PROJECT_DIR)
        reports.extend(generate_reports(funcs))

    if args.json:
        print(json.dumps(reports, indent=2, ensure_ascii=False))
    else:
        _print_ascii(reports)

    return 1 if any("DUPLICAÇÃO" in r["classification"] for r in reports) else 0


if __name__ == "__main__":
    sys.exit(main())
