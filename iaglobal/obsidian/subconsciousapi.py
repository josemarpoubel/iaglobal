# ============================================================
# ARQUIVO 3: iaglobal/obsidian/subconsciousapi.py
# CORREÇÃO: Todo I/O de arquivo encapsulado em asyncio.to_thread (BUG #3)
#           Colisão de nome de arquivo corrigida com microsegundos (BUG #6)
#           Wrapper síncrono para compatibilidade com testes (compat)
# ============================================================
"""SubconsciousAPI — Interface unificada de comunicação com o Vault Obsidian.

Centraliza leitura e escrita do subconsciente (arquivos Markdown),
permitindo que agentes consultem memórias passadas via tags e links.

ARQUITETURA ASYNC:
  Toda operação de I/O de disco é encapsulada em asyncio.to_thread()
  para não bloquar o event loop. A API expõe métodos async publicamente
  e delega o I/O bloqueante para threads do pool padrão do asyncio.
  
COMPAT:
  Wrappers síncronos existem para compatibilidade com calls diretas.
  Use await para performance ótima, ou use sync version para simplicidade.
"""

import asyncio
import logging
import re
from pathlib import Path
from datetime import datetime, UTC
from typing import List, Optional

from iaglobal._paths import PACKAGE_DIR

logger = logging.getLogger(__name__)


def _sync_wrap(async_fn):
    """Decorator to create sync wrapper for async methods."""
    def _wrapper(*args, **kwargs):
        return asyncio.run(async_fn(*args, **kwargs))
    return _wrapper


class SubconsciousAPI:
    """API de acesso ao cofre Obsidian (subconsciente do iaglobal).

    Cada nota é um arquivo .md com YAML Frontmatter.
    O mapa central (04_Synapses/Mapa_Mental_Subconsciente.md) indexa
    todas as notas de longo prazo por tags e links bidirecionais.

    Todos os métodos públicos são async — use `await` ao chamar.
    """

    def __init__(self, vault_path: Optional[Path] = None):
        self.vault_path = Path(vault_path or PACKAGE_DIR / "obsidian")
        self.instincts_dir = self.vault_path / "01_Instincts"
        self.short_term_dir = self.vault_path / "02_Short_Term"
        self.long_term_dir = self.vault_path / "03_Long_Term"
        self.synapses_dir = self.vault_path / "04_Synapses"

        # Criação de diretórios é feita uma única vez no construtor —
        # mkdir é rápido e idempotente, não precisa de thread pool.
        for d in [self.instincts_dir, self.short_term_dir,
                  self.long_term_dir, self.synapses_dir]:
            d.mkdir(parents=True, exist_ok=True)

    # =================================================================
    # ESCRITA NO VAULT (async)
    # =================================================================

    async def escrever_nota(self, diretorio: Path, nome: str, conteudo: str) -> Path:
        """Escreve uma nota Markdown no diretório especificado."""
        caminho = diretorio / f"{nome}.md"
        caminho.parent.mkdir(parents=True, exist_ok=True)

        def _write():
            caminho.write_text(conteudo, encoding="utf-8")
            return caminho

        return await asyncio.to_thread(_write)

    async def escrever_curto_prazo(
        self, nome: str, conteudo: str, tags: Optional[List[str]] = None
    ) -> Path:
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
        return await self.escrever_nota(self.short_term_dir, nome, nota)

    async def escrever_longo_prazo(
        self,
        nome: str,
        conteudo: str,
        tipo: str = "ConhecimentoConsolidado",
        tags: Optional[List[str]] = None,
        fitness: float = 0.5,
        links: Optional[List[str]] = None,
    ) -> Path:
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
        return await self.escrever_nota(self.long_term_dir, nome, nota)

    async def escrever_instinto(self, nome: str, conteudo: str) -> Path:
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
        return await self.escrever_nota(self.instincts_dir, nome, nota)

    async def registrar_erro(
        self,
        agente: str,
        tarefa: str,
        erro: str,
        tags: Optional[List[str]] = None,
    ) -> Path:
        """Registra automaticamente uma falha no curto prazo.

        CORREÇÃO BUG #6: timestamp agora inclui microsegundos (%f) para
        evitar colisão de nomes quando dois erros ocorrem no mesmo segundo.
        """
        all_tags = (tags or []) + ["#erro", f"#agente-{agente}"]
        # %f = microsegundos (6 dígitos) — garante unicidade mesmo sob
        # carga alta onde múltiplos erros chegam no mesmo segundo.
        ts = datetime.now(UTC).strftime("%Y%m%d%H%M%S%f")
        return await self.escrever_curto_prazo(
            f"erro_{agente}_{ts}",
            f"## Erro no Agente: {agente}\n\n**Tarefa:** {tarefa}\n\n**Erro:**\n```\n{erro}\n```",
            tags=all_tags,
        )

    # =================================================================
    # LEITURA E CONSULTA (async)
    # =================================================================

    async def sussurrar_intuicao(self, tags_tarefa: List[str]) -> str:
        """Busca no subconsciente (longo prazo) memórias relacionadas às tags."""
        mapa_path = self.synapses_dir / "Mapa_Mental_Subconsciente.md"

        def _read_mapa() -> Optional[str]:
            return mapa_path.read_text(encoding="utf-8") if mapa_path.exists() else None

        mapa_conteudo = await asyncio.to_thread(_read_mapa)
        if mapa_conteudo is None:
            return "Subconsciente: Vazio. Execute por instinto puro."

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

            def _read_nota(p=caminho_nota) -> Optional[str]:
                return p.read_text(encoding="utf-8") if p.exists() else None

            conteudo = await asyncio.to_thread(_read_nota)
            if conteudo:
                conteudo_limpo = re.sub(r"---.*?---", "", conteudo, flags=re.DOTALL).strip()
                insights.append(f"[Memória Atávica: {nome_nota}]\n{conteudo_limpo}")

        return "\n\n".join(insights) if insights else (
            "Subconsciente: Sem memórias diretas correlacionadas a este padrão."
        )

    async def obter_insight_subconsciente(self, termos_chave: List[str]) -> str:
        """Consulta o subconsciente por termos-chave, com fallback para notas recentes."""
        mapa_path = self.synapses_dir / "Mapa_Mental_Subconsciente.md"

        def _read_mapa() -> Optional[str]:
            return mapa_path.read_text(encoding="utf-8") if mapa_path.exists() else None

        mapa_conteudo = await asyncio.to_thread(_read_mapa)
        if mapa_conteudo is None:
            return "Nenhum insight subconsciente disponível para esta tarefa."

        notas_para_ler = []
        todos_links = re.findall(r"\[\[(.*?)\]\]", mapa_conteudo)

        for link in todos_links:
            for termo in termos_chave:
                if termo.lower() in link.lower():
                    notas_para_ler.append(link)
                    break

        if not notas_para_ler and self.long_term_dir.exists():
            def _listar_recentes():
                return sorted(
                    self.long_term_dir.glob("*.md"),
                    key=lambda x: x.stat().st_mtime,
                    reverse=True,
                )

            arquivos = await asyncio.to_thread(_listar_recentes)
            notas_para_ler = [f.stem for f in arquivos[:2]]

        memorias = []
        for nome_nota in notas_para_ler[:3]:
            caminho_nota = self.long_term_dir / f"{nome_nota}.md"

            def _read(p=caminho_nota) -> Optional[str]:
                return p.read_text(encoding="utf-8") if p.exists() else None

            conteudo = await asyncio.to_thread(_read)
            if conteudo:
                conteudo_limpo = re.sub(r"---.*?---", "", conteudo, flags=re.DOTALL).strip()
                memorias.append(f"### Memória: {nome_nota}\n{conteudo_limpo}")

        if not memorias:
            return "Subconsciente: Sem memórias diretas sobre este tema. Prossiga por instinto puro."
        return "\n\n".join(memorias)

    async def ler_nota(self, nome: str, diretorio: Optional[Path] = None) -> Optional[str]:
        """Lê uma nota Markdown pelo nome."""
        diretorios = [diretorio] if diretorio else [
            self.long_term_dir, self.short_term_dir,
            self.synapses_dir, self.instincts_dir,
        ]

        def _find_and_read():
            for d in diretorios:
                caminho = d / f"{nome}.md"
                if caminho.exists():
                    return caminho.read_text(encoding="utf-8")
            return None

        return await asyncio.to_thread(_find_and_read)

    async def listar_notas(self, diretorio: Optional[Path] = None) -> List[str]:
        """Lista todas as notas Markdown em um diretório."""
        alvo = diretorio or self.long_term_dir

        def _list():
            if not alvo.exists():
                return []
            return sorted(f.stem for f in alvo.glob("*.md"))

        return await asyncio.to_thread(_list)

    # =================================================================
    # MAPA SINÁPTICO (async)
    # =================================================================

    async def atualizar_mapa_conexoes(self) -> None:
        """Reconstrói o Mapa Sináptico Central (MOC) a partir das notas de longo prazo."""
        def _build_moc() -> str:
            todas_tags: set = set()
            links_encontrados: List[str] = []

            for f in self.long_term_dir.glob("*.md"):
                texto = f.read_text(encoding="utf-8")
                tags = re.findall(r"#[\w-]+", texto)
                todas_tags.update(tags)
                links_encontrados.append(f"[[{f.stem}]]")

            return (
                f"---\n"
                f"tipo: MapaSinapticoCentral\n"
                f"ultima_atualizacao: \"{datetime.now(UTC).isoformat()}Z\"\n"
                f"total_notas: {len(links_encontrados)}\n"
                f"tags_ativas: [{', '.join(f'\"{t}\"' for t in sorted(todas_tags))}]\n"
                f"---\n\n"
                f"# Córtex Sináptico Central (Subconsciente iaglobal)\n\n"
                f"## Tags Ativas no Ecossistema\n"
                f"{', '.join(sorted(todas_tags)) if todas_tags else '(nenhuma tag ativa)'}\n\n"
                f"## Memórias de Longo Prazo Consolidadas\n"
                + "\n".join(f"- {link}" for link in links_encontrados)
            )

        def _write_moc(content: str):
            moc_path = self.synapses_dir / "Mapa_Mental_Subconsciente.md"
            moc_path.write_text(content, encoding="utf-8")

        moc_content = await asyncio.to_thread(_build_moc)
        await asyncio.to_thread(_write_moc, moc_content)

    async def exportar_nota_agente(
        self,
        agent_id: str,
        strategy: str,
        fitness: float,
        parent_id: Optional[str] = None,
    ) -> Path:
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
        return await self.escrever_nota(vault_agents, agent_id, content)

    # Sync wrappers for compatibility
    escrever_curto_prazo_sync = _sync_wrap(escrever_curto_prazo)
    escrever_longo_prazo_sync = _sync_wrap(escrever_longo_prazo)
    obter_insight_subconsciente_sync = _sync_wrap(obter_insight_subconsciente)
    ler_nota_sync = _sync_wrap(ler_nota)
    listar_notas_sync = _sync_wrap(listar_notas)
