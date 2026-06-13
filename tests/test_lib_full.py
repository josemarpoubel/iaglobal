# test_lib_full.py

import ast
import os
import pkgutil
import importlib
from typing import Set

from iaglobal.evolution.skills.run_fn_factory import _make_deterministic_run_fn

class LibIntegrityTester:
    def __init__(self, base_package="iaglobal"):
        self.base_package = base_package
        self.errors = []
        # Lista de padrões que indicam que o sistema está em modo genérico/degradado
        self.fallback_patterns = ["node.run()", "Redirecionando para barramento genérico", "fallback para node.run"]

    def analyze_file(self, filepath: str):
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
            try:
                tree = ast.parse(content)
            except SyntaxError:
                self.errors.append(f"❌ Erro de Sintaxe em: {filepath}")
                return

        # 1. Detector de Fallbacks (Procura referências a node.run() no código)
        if "node.run" in content:
             self.errors.append(f"🚨 Fallback Detectado: '{filepath}' ainda referencia 'node.run()'")

        # 2. Analisador de Classes (Skill)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                methods = {m.name for m in node.body if isinstance(m, ast.FunctionDef)}
                # Se herda de Skill e não tem run_fn explícita
                if "Skill" in [getattr(base, 'id', '') for base in node.bases]:
                    if "run_fn" not in methods:
                        self.errors.append(f"⚠️ Skill sem run_fn injetada: {node.name} em {filepath}")

    def run_full_suite(self):
        print(f"🔍 Executando Exorcismo de Fallbacks em: {self.base_package}...")
        package = importlib.import_module(self.base_package)
        for _, name, is_pkg in pkgutil.walk_packages(package.__path__, package.__name__ + "."):
            if not is_pkg:
                path = name.replace(".", "/") + ".py"
                if os.path.exists(path):
                    self.analyze_file(path)
        return self.errors

if __name__ == "__main__":
    tester = LibIntegrityTester()
    results = tester.run_full_suite()
    if not results:
        print("✅ Sistema limpo! Nenhuma referência a node.run() encontrada.")
    else:
        for error in results:
            print(error)
