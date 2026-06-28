"""Parse the text-format architectural audit report and check private orphans."""
import re
from pathlib import Path

project = Path("/home/kitohamachi/projeto-iaglobal")
relatorio = project / "iaglobal/memory/data/auditoria/relatorio_funcoes.txt"

# Autocontained: gera o relatório se não existir
if not relatorio.exists():
    from iaglobal.auditoria_arquitetural import gerar_relatorio
    relatorio.parent.mkdir(parents=True, exist_ok=True)
    gerar_relatorio(str(project), saida=str(relatorio), formato="txt")


def _parse_orphans(text: str) -> list[dict]:
    orphans: list[dict] = []
    in_section = False
    for line in text.splitlines():
        if line.startswith("=== POSSÍVEIS ÓRFÃS ==="):
            in_section = True
            continue
        if not in_section or not line.strip():
            continue
        if line.startswith("=== "):
            break
        match = re.match(r"^(.+\.py)::(.+)$", line.strip())
        if match:
            orphans.append({"funcao": match.group(1), "nome": match.group(2)})
    return orphans


def test_orphans_report_exists():
    assert relatorio.exists(), f"Relatório não encontrado: {relatorio}"
    text = relatorio.read_text(encoding="utf-8")
    assert "POSSÍVEIS ÓRFÃS" in text


def test_private_orphans_have_internal_usage():
    text = relatorio.read_text(encoding="utf-8")
    orphans = _parse_orphans(text)
    private_orphans = [o for o in orphans if o["nome"].startswith("_")]
    dead: list[str] = []
    for o in sorted(private_orphans, key=lambda x: x["funcao"]):
        filepath = project / o["funcao"]
        name = o["nome"]
        if not filepath.exists():
            dead.append(f"{o['funcao']}::{name} -- ARQUIVO NAO ENCONTRADO")
            continue
        content = filepath.read_text(encoding="utf-8")
        pattern = rf"(?<!def\s)(?<!class\s)\b{re.escape(name)}\b"
        matches = re.findall(pattern, content)
        def_pattern = rf"^\s*(?:async\s+)?def\s+{re.escape(name)}\s*\("
        def_count = len(re.findall(def_pattern, content, re.MULTILINE))
        class_def_pattern = rf"^\s+(?:async\s+)?def\s+{re.escape(name)}\s*\("
        class_def_count = len(re.findall(class_def_pattern, content, re.MULTILINE))
        internal_refs = len(matches) - def_count - class_def_count
        if internal_refs == 0:
            dead.append(f"{o['funcao']}::{name} -- DEAD CODE ({internal_refs} refs internas)")
    if dead:
        print("\n".join(dead))
    assert not dead, f"{len(dead)} private orphan(s) appear to be dead code"
