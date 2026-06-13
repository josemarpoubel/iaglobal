import ast
from pathlib import Path
from collections import defaultdict

class Analyzer(ast.NodeVisitor):
    def __init__(self, arquivo):
        self.arquivo = arquivo
        self.funcao_atual = None
        self.funcoes = set()
        self.chamadas = defaultdict(set)

    def visit_FunctionDef(self, node):
        nome = f"{self.arquivo}::{node.name}"
        self.funcoes.add(nome)

        anterior = self.funcao_atual
        self.funcao_atual = nome

        self.generic_visit(node)

        self.funcao_atual = anterior

    def visit_AsyncFunctionDef(self, node):
        self.visit_FunctionDef(node)

    def visit_Call(self, node):
        if self.funcao_atual:
            if isinstance(node.func, ast.Name):
                self.chamadas[self.funcao_atual].add(node.func.id)

            elif isinstance(node.func, ast.Attribute):
                self.chamadas[self.funcao_atual].add(node.func.attr)

        self.generic_visit(node)


def analisar_projeto(pasta):
    todas_funcoes = set()
    todas_chamadas = defaultdict(set)

    for arquivo in Path(pasta).rglob("*.py"):
        try:
            codigo = arquivo.read_text(encoding="utf-8")
            arvore = ast.parse(codigo)

            analisador = Analyzer(str(arquivo))

            analisador.visit(arvore)

            todas_funcoes.update(analisador.funcoes)

            for origem, destinos in analisador.chamadas.items():
                todas_chamadas[origem].update(destinos)

        except Exception as e:
            print(f"Erro em {arquivo}: {e}")

    return todas_funcoes, todas_chamadas


funcoes, chamadas = analisar_projeto(".")

nomes_funcoes = {
    f.split("::")[-1]: f
    for f in funcoes
}

chamadas_recebidas = defaultdict(set)

for origem, destinos in chamadas.items():
    for destino in destinos:
        if destino in nomes_funcoes:
            chamadas_recebidas[destino].add(origem)

with open("relatorio_funcoes.txt", "w", encoding="utf-8") as f:

    f.write("=== MAPA DE FUNCOES ===\n\n")

    for func in sorted(funcoes):

        nome = func.split("::")[-1]

        f.write(f"FUNCAO: {func}\n")

        quem_chama = chamadas_recebidas.get(nome, set())

        if quem_chama:
            f.write("  CHAMADA POR:\n")
            for caller in sorted(quem_chama):
                f.write(f"    - {caller}\n")
        else:
            f.write("  CHAMADA POR: NINGUEM\n")

        f.write("\n")

    f.write("\n=== POSSIVEIS ORFAS ===\n\n")

    for func in sorted(funcoes):

        nome = func.split("::")[-1]

        if nome not in chamadas_recebidas:
            f.write(f"{func}\n")

print("Relatório salvo em relatorio_funcoes.txt")
