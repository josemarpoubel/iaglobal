"""SubconsciousAPI — Interface unificada de comunicação com o Vault Obsidian.

Centraliza leitura e escrita do subconsciente (arquivos Markdown),
permitindo que agentes consultem memórias passadas via tags e links.
"""

import os
import re
from pathlib import Path

from datetime import datetime, UTC

from typing import List, Optional, Dict, Any

from iaglobal._paths import PACKAGE_DIR


class SubconsciousAPI:
    """API de acesso ao cofre Obsidian (subconsciente do iaglobal).

    Cada nota é um arquivo .md com YAML Frontmatter.
    O mapa central (04_Synapses/Mapa_Mental_Subconsciente.md) indexa
    todas as notas de longo prazo por tags e links bidirecionais.
    """

    def __init__(self, vault_path: Optional[Path] = None):
        self.vault_path = Path(vault_path or PACKAGE_DIR / "obsidian")
        self.instincts_dir = self.vault_path / "01_Instincts"
        self.short_term_dir = self.vault_path / "02_Short_Term"
        self.long_term_dir = self.vault_path / "03_Long_Term"
        self.synapses_dir = self.vault_path / "04_Synapses"

        for d in [self.instincts_dir, self.short_term_dir,
                  self.long_term_dir, self.synapses_dir]:
            d.mkdir(parents=True, exist_ok=True)

    # =================================================================
    # ESCRITA NO VAULT
    # =================================================================

    def escrever_nota(self, diretorio: Path, nome: str, conteudo: str) -> Path:
        """Escreve uma nota Markdown no diretório especificado."""
        caminho = diretorio / f"{nome}.md"
        caminho.parent.mkdir(parents=True, exist_ok=True)
        with open(caminho, "w", encoding="utf-8") as f:
            f.write(conteudo)
        return caminho

    def escrever_curto_prazo(self, nome: str, conteudo: str, tags: Optional[List[str]] = None) -> Path:
        """Registra uma memória bruta no curto prazo (02_Short_Term)."""
        tag_str = ", ".join(f'"{t}"' for t in (tags or []))
        nota = f"""---
id: "{nome}"
tipo: "MemoriaBruta"
timestamp: "{datetime.now(UTC).isoformat()}Z"
tags: [{tag_str}]
---

# {nome}

{conteudo}
"""
        return self.escrever_nota(self.short_term_dir, nome, nota)

    def escrever_longo_prazo(self, nome: str, conteudo: str, tipo: str = "ConhecimentoConsolidado",
                             tags: Optional[List[str]] = None,
                             fitness: float = 0.5,
                             links: Optional[List[str]] = None) -> Path:
        """Registra conhecimento consolidado no longo prazo (03_Long_Term)."""
        tag_str = ", ".join(f'"{t}"' for t in (tags or []))
        links_str = ", ".join(f'"[[{l}]]"' for l in (links or [])) if links else ""
        nota = f"""---
id: "{nome}"
tipo: "{tipo}"
timestamp: "{datetime.now(UTC).isoformat()}Z"
tags: [{tag_str}]
fitness_score: {fitness}
links_associados: [{links_str}]
---

# {nome}

{conteudo}
"""
        return self.escrever_nota(self.long_term_dir, nome, nota)

    def escrever_instinto(self, nome: str, conteudo: str) -> Path:
        """Registra uma diretriz imutável em 01_Instincts."""
        nota = f"""---
id: "{nome}"
tipo: "Instinto"
timestamp: "{datetime.now(UTC).isoformat()}Z"
imutavel: true
---

# {nome}

{conteudo}
"""
        return self.escrever_nota(self.instincts_dir, nome, nota)

    def registrar_erro(self, agente: str, tarefa: str, erro: str, tags: Optional[List[str]] = None) -> Path:
        """Registra automaticamente uma falha no curto prazo."""
        all_tags = (tags or []) + ["#erro", f"#agente-{agente}"]
        return self.escrever_curto_prazo(
            f"erro_{agente}_{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}",
            f"## Erro no Agente: {agente}\n\n**Tarefa:** {tarefa}\n\n**Erro:**\n```\n{erro}\n```",
            tags=all_tags,
        )

    # =================================================================
    # LEITURA E CONSULTA
    # =================================================================

    def sussurrar_intuicao(self, tags_tarefa: List[str]) -> str:
        """Busca no subconsciente (longo prazo) memórias relacionadas às tags.

        Primeiro consulta o mapa sináptico, depois abre as notas
        correlacionadas. Retorna fragmentos prontos para injeção em prompt.
        """
        mapa_path = self.synapses_dir / "Mapa_Mental_Subconsciente.md"
        if not mapa_path.exists():
            return "Subconsciente: Vazio. Execute por instinto puro."

        with open(mapa_path, "r", encoding="utf-8") as f:
            mapa_conteudo = f.read()

        todos_links = re.findall(r"\[\[(.*?)\]\]", mapa_conteudo)
        notas_correlacionadas = []

        for link in todos_links:
            for tag in tags_tarefa:
                tag_limpa = tag.replace("#", "").lower()
                if tag_limpa in link.lower():
                    notas_correlacionadas.append(link)
                    break

        if not notas_correlacionadas:
            return "Subconsciente: Sem memórias diretas correlacionadas a este padrão."

        insights = []
        for nome_nota in notas_correlacionadas[:2]:
            caminho_nota = self.long_term_dir / f"{nome_nota}.md"
            if caminho_nota.exists():
                with open(caminho_nota, "r", encoding="utf-8") as f:
                    conteudo = re.sub(r"---.*?---", "", f.read(), flags=re.DOTALL).strip()
                    insights.append(f"[Memória Atávica: {nome_nota}]\n{conteudo}")

        return "\n\n".join(insights) if insights else (
            "Subconsciente: Sem memórias diretas correlacionadas a este padrão."
        )

    def obter_insight_subconsciente(self, termos_chave: List[str]) -> str:
        """Consulta o subconsciente por termos-chave, com fallback para notas recentes."""
        mapa_path = self.synapses_dir / "Mapa_Mental_Subconsciente.md"
        if not mapa_path.exists():
            return "Nenhum insight subconsciente disponível para esta tarefa."

        with open(mapa_path, "r", encoding="utf-8") as f:
            mapa_conteudo = f.read()

        notas_para_ler = []
        todos_links = re.findall(r"\[\[(.*?)\]\]", mapa_conteudo)

        for link in todos_links:
            for termo in termos_chave:
                if termo.lower() in link.lower():
                    notas_para_ler.append(link)
                    break

        if not notas_para_ler and self.long_term_dir.exists():
            arquivos = sorted(
                self.long_term_dir.glob("*.md"),
                key=lambda x: x.stat().st_mtime,
                reverse=True,
            )
            notas_para_ler = [f.stem for f in arquivos[:2]]

        memorias = []
        for nome_nota in notas_para_ler[:3]:
            caminho_nota = self.long_term_dir / f"{nome_nota}.md"
            if caminho_nota.exists():
                with open(caminho_nota, "r", encoding="utf-8") as f:
                    conteudo_limpo = re.sub(r"---.*?---", "", f.read(), flags=re.DOTALL).strip()
                    memorias.append(f"### Memória: {nome_nota}\n{conteudo_limpo}")

        if not memorias:
            return "Subconsciente: Sem memórias diretas sobre este tema. Prossiga por instinto puro."
        return "\n\n".join(memorias)

    def ler_nota(self, nome: str, diretorio: Optional[Path] = None) -> Optional[str]:
        """Lê uma nota Markdown pelo nome."""
        if diretorio is None:
            for d in [self.long_term_dir, self.short_term_dir,
                      self.synapses_dir, self.instincts_dir]:
                caminho = d / f"{nome}.md"
                if caminho.exists():
                    return caminho.read_text(encoding="utf-8")
            return None
        caminho = diretorio / f"{nome}.md"
        return caminho.read_text(encoding="utf-8") if caminho.exists() else None

    def listar_notas(self, diretorio: Optional[Path] = None) -> List[str]:
        """Lista todas as notas Markdown em um diretório."""
        alvo = diretorio or self.long_term_dir
        if not alvo.exists():
            return []
        return sorted(f.stem for f in alvo.glob("*.md"))

    # =================================================================
    # MAPA SINÁPTICO
    # =================================================================

    def atualizar_mapa_conexoes(self) -> None:
        """Reconstrói o Mapa Sináptico Central (MOC) a partir das notas de longo prazo."""
        todas_tags: set = set()
        links_encontrados: List[str] = []

        for f in self.long_term_dir.glob("*.md"):
            texto = f.read_text(encoding="utf-8")
            tags = re.findall(r"#[\w-]+", texto)
            todas_tags.update(tags)
            links_encontrados.append(f"[[{f.stem}]]")

        moc_content = f"""---
tipo: MapaSinapticoCentral
ultima_atualizacao: "{datetime.now(UTC).isoformat()}Z"
total_notas: {len(links_encontrados)}
tags_ativas: [{', '.join(f'"{t}"' for t in sorted(todas_tags))}]
---

# Córtex Sináptico Central (Subconsciente iaglobal)

## Tags Ativas no Ecossistema
{', '.join(sorted(todas_tags)) if todas_tags else '(nenhuma tag ativa)'}

## Memórias de Longo Prazo Consolidadas
""" + "\n".join(f"- {link}" for link in links_encontrados)

        moc_path = self.synapses_dir / "Mapa_Mental_Subconsciente.md"
        moc_path.write_text(moc_content, encoding="utf-8")

    def exportar_nota_agente(self, agent_id: str, strategy: str,
                             fitness: float, parent_id: Optional[str] = None) -> Path:
        """Exporta uma nota de linhagem de agente para o grafo do Obsidian."""
        parent_link = f"[[{parent_id}]]" if parent_id else "N/A"
        content = f"""---
id: "{agent_id}"
strategy: "{strategy}"
fitness: {fitness}
status: active
timestamp: "{datetime.now(UTC).isoformat()}Z"
---

# Agente {agent_id[:8]}

## Linhagem
Pai: {parent_link}

## Logs de Evolução
O agente executou a estratégia {strategy} com sucesso metabólico.
"""
        vault_agents = self.long_term_dir / "agentes"
        vault_agents.mkdir(parents=True, exist_ok=True)
        return self.escrever_nota(vault_agents, agent_id, content)
