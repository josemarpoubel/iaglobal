#!/usr/bin/env python3
# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136

"""
Auditoria de Migração — Provider Registry

Mede o progresso da migração dos aliases deprecated para os nomes canônicos.

Uso:
    python -m scripts.audit_registry_migration

Saída:
    - Contagem de usos de cada nome
    - Lista de arquivos que ainda usam aliases deprecated
    - Métrica de progresso (%)
"""

import re
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, List, Tuple


@dataclass
class MigrationMetric:
    canonical_name: str
    deprecated_names: List[str]
    canonical_count: int = 0
    deprecated_count: int = 0
    files_with_deprecated: List[str] = None

    def __post_init__(self):
        if self.files_with_deprecated is None:
            self.files_with_deprecated = []


def count_usages(
    root_dir: Path, patterns: List[str], exclude_patterns: List[str] = None
) -> Tuple[int, List[str]]:
    """Conta ocorrências de padrões em arquivos Python."""
    if exclude_patterns is None:
        exclude_patterns = ["__pycache__", ".pyc", "audit_registry_migration.py"]

    count = 0
    files_found = []

    for py_file in root_dir.rglob("*.py"):
        # Pula diretórios/exclusões
        if any(excl in str(py_file) for excl in exclude_patterns):
            continue

        try:
            content = py_file.read_text(encoding="utf-8")
        except Exception:
            continue

        file_count = 0
        for pattern in patterns:
            # Regex para encontrar o nome como identificador (não parte de outra palavra)
            regex = rf"\b{re.escape(pattern)}\b"
            matches = re.findall(regex, content)
            file_count += len(matches)

        if file_count > 0:
            count += file_count
            files_found.append(str(py_file.relative_to(root_dir)))

    return count, files_found


def audit_migration(root_dir: Path = None):
    """Executa auditoria completa da migração."""
    if root_dir is None:
        root_dir = Path(__file__).parent.parent

    metrics: List[MigrationMetric] = [
        MigrationMetric(
            canonical_name="LLMProviderRegistry",
            deprecated_names=["ProviderRegistry", "registry"],
        ),
        MigrationMetric(
            canonical_name="ContextProviderRegistry",
            deprecated_names=["ProviderRegistry", "provider_registry"],
        ),
    ]

    print("=" * 80)
    print("AUDITORIA DE MIGRAÇÃO — PROVIDER REGISTRY")
    print("=" * 80)
    print()

    total_canonical = 0
    total_deprecated = 0

    for metric in metrics:
        # Conta usos do nome canônico
        metric.canonical_count, _ = count_usages(
            root_dir, [metric.canonical_name]
        )

        # Conta usos dos nomes deprecated
        deprecated_count = 0
        all_deprecated_files = []

        for dep_name in metric.deprecated_names:
            count, files = count_usages(root_dir, [dep_name])
            deprecated_count += count
            all_deprecated_files.extend(files)

        metric.deprecated_count = deprecated_count
        metric.files_with_deprecated = list(set(all_deprecated_files))

        total_canonical += metric.canonical_count
        total_deprecated += deprecated_count

        # Imprime relatório por métrica
        print(f"📊 {metric.canonical_name}")
        print(f"   ✅ Canônico: {metric.canonical_count} ocorrências")
        print(f"   ⚠️  Deprecated: {metric.deprecated_count} ocorrências")

        if metric.files_with_deprecated:
            print(f"   📁 Arquivos com deprecated ({len(metric.files_with_deprecated)}):")
            for f in sorted(metric.files_with_deprecated)[:10]:
                print(f"      - {f}")
            if len(metric.files_with_deprecated) > 10:
                print(f"      ... e mais {len(metric.files_with_deprecated) - 10}")
        print()

    # Resumo geral
    print("=" * 80)
    print("RESUMO GERAL")
    print("=" * 80)
    print(f"✅ Total canônico:    {total_canonical}")
    print(f"⚠️  Total deprecated: {total_deprecated}")

    if total_canonical + total_deprecated > 0:
        progress = (total_canonical / (total_canonical + total_deprecated)) * 100
        print(f"📈 Progresso:        {progress:.1f}%")
    else:
        print("📈 Progresso:        N/A (nenhum uso encontrado)")

    print()

    if total_deprecated > 0:
        print("⚠️  AÇÃO RECOMENDADA:")
        print("   Migrar os arquivos listados acima para usar os nomes canônicos.")
        print("   Os aliases serão removidos quando não houver mais consumidores.")
    else:
        print("✅ PARABÉNS! Todos os usos estão migrados para nomes canônicos.")
        print("   Os aliases podem ser removidos com segurança na próxima versão major.")

    print()
    print("=" * 80)

    return {
        "total_canonical": total_canonical,
        "total_deprecated": total_deprecated,
        "metrics": metrics,
    }


if __name__ == "__main__":
    audit_migration()
