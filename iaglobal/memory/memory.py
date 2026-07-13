from iaglobal import _paths
# iaglobal/memory/memory.py

import os
import datetime
import re


def carregar() -> str:
    """Load memory from evolution file."""
    if not os.path.exists(_paths.EVOLUTION_DOC):
        return "memória vazia"

    with open(_paths.EVOLUTION_DOC, "r", encoding="utf-8") as f:
        return f.read()[-20000:]


def salvar(texto: str) -> None:
    """Save text to evolution file with clean hierarchical structure."""
    os.makedirs(_paths.DATA_DIR, exist_ok=True)

    agora = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    texto_limpo = texto.strip()

    # 🔍 1. FILTRO DE INTEGRIDADE: Evita salvar strings residuais ou vazias
    if not texto_limpo or len(texto_limpo) < 5:
        return

    # 🏷️ 2. CLASSIFICAÇÃO SEMÂNTICA AUTOMÁTICA
    texto_lower = texto_limpo.lower()
    if any(
        w in texto_lower
        for w in ["explique", "conceito", "solid", "polimorfismo", "o que é"]
    ):
        tag = "#CONCEITO"
    elif any(
        w in texto_lower
        for w in ["crie", "função", "valide", "def ", "class ", "código"]
    ):
        tag = "#CODIGO"
    else:
        tag = "#EXECUCAO"

    # 🛑 3. BLOQUEIO DE CONTAMINAÇÃO (Anti-Loop SistemaVazio)
    # Se for uma busca ou explicação conceitual legítima, impede a injeção do mock de erro
    if tag == "#CONCEITO" and "sistemavazio" in texto_lower:
        return

    # 📝 4. MONTAGEM DO TEMPLATE ESTRUTURADO (Markdown Rígido)
    # Se o texto já vier no formato bruto antigo "USER: ... \nAI: ...", nós o organizamos
    if "user:" in texto_lower and "ai:" in texto_lower:
        partes = re.split(r"(?i)ai:", texto_limpo, maxsplit=1)
        prompt_user = partes[0].replace("USER:", "").replace("user:", "").strip()
        resposta_ai = partes[1].strip() if len(partes) > 1 else ""

        bloco_estruturado = (
            f"# 🚀 REGISTRO DE EVOLUÇÃO | {tag}\n"
            f"- **Data/Hora:** {agora}\n\n"
            f"### 📥 Entrada do Usuário (Prompt)\n"
            f"> {prompt_user}\n\n"
            f"### 📤 Resposta Consolidada (AI)\n"
            f"{resposta_ai}\n\n"
            f"---\n\n"
        )
    else:
        # Se for um dump direto de texto dos agentes, salva de forma limpa e cronológica
        bloco_estruturado = (
            f"# 🚀 REGISTRO DE EVOLUÇÃO | {tag}\n"
            f"- **Data/Hora:** {agora}\n\n"
            f"### 📄 Conteúdo Indexado\n"
            f"{texto_limpo}\n\n"
            f"---\n\n"
        )

    with open(_paths.EVOLUTION_DOC, "a", encoding="utf-8") as f:
        f.write(bloco_estruturado)


class Memory:
    """Main memory class for managing system memory."""

    def __init__(self):
        self.content = ""
        self.history = []
        self.metadata = {}

    def load(self) -> str:
        """Load memory from storage."""
        self.content = carregar()
        return self.content

    def save(self, texto: str) -> None:
        """Save memory to storage."""
        salvar(texto)
        self.history.append(texto)
        self.content += texto

    def append(self, texto: str) -> None:
        """Append text to memory."""
        self.content += "\n" + texto
        self.save(texto)

    def clear(self) -> None:
        """Clear memory."""
        self.content = ""
