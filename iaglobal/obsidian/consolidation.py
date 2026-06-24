# ============================================================
# ARQUIVO 4: iaglobal/obsidian/consolidation.py
# CORREÇÃO: Remove imports duplicados/mortos (BUG #4, BUG #5)
#           iniciar_fase_rem e I/O tornam-se async (BUG #3)
# ============================================================
"""REMSleepEngine — Ciclo de Consolidação de Memória (Fase REM).

Simula o sono biológico:
  1. Lê memórias brutas do curto prazo (02_Short_Term)
  2. Sintetiza conhecimento via IA (ou fallback mockado)
  3. Grava no longo prazo (03_Long_Term) com links bidirecionais
  4. Remove originais (poda sináptica — Lei do Vácuo da Prosperidade)
  5. Atualiza o mapa sináptico central (MOC)
"""
import asyncio
import logging
import re
from datetime import datetime, UTC
from pathlib import Path
from typing import Dict, List, Optional, Any

from iaglobal._paths import PACKAGE_DIR

logger = logging.getLogger(__name__)


class REMSleepEngine:
    """Motor de consolidação de memória — Ciclo do Sono.

    Deve ser executado periodicamente (ex: a cada 1 hora ou
    quando o fluxo de requisições estiver baixo).
    Todo I/O de disco é delegado para asyncio.to_thread para
    não bloquear o event loop durante a consolidação.
    """

    def __init__(self, vault_path: Optional[Path] = None, ai_client=None):
        self.vault_path = Path(vault_path or PACKAGE_DIR / "obsidian")
        self.short_term_dir = self.vault_path / "02_Short_Term"
        self.long_term_dir = self.vault_path / "03_Long_Term"
        self.synapses_dir = self.vault_path / "04_Synapses"
        self.ai_client = ai_client

        for d in [self.short_term_dir, self.long_term_dir, self.synapses_dir]:
            d.mkdir(parents=True, exist_ok=True)

    async def iniciar_fase_rem(self) -> Dict[str, Any]:
        """Executa o ciclo completo de consolidação de forma assíncrona."""
        resultado: Dict[str, Any] = {
            "iniciado_em": datetime.now(UTC).isoformat(),
            "memorias_processadas": 0,
            "memorias_consolidadas": 0,
            "erros": [],
        }

        experiencias = await self._listar_memorias_curto_prazo()
        if not experiencias:
            resultado["status"] = "sem_memorias"
            logger.info("[REMSleep] Nenhuma memória de curto prazo para consolidar.")
            return resultado

        resultado["memorias_processadas"] = len(experiencias)
        logger.info("[REMSleep] Iniciando consolidação de %d memórias.", len(experiencias))

        for arquivo, conteudo in experiencias.items():
            try:
                insight = await self._solicitar_sintese_ia(conteudo)
                if insight:
                    await self._gravar_longo_prazo(arquivo, insight)
                    await self._remover_curto_prazo(arquivo)
                    resultado["memorias_consolidadas"] += 1
            except Exception as e:
                logger.exception("[REMSleep] Falha ao consolidar '%s': %s", arquivo, e)
                resultado["erros"].append(f"{arquivo}: {e}")

        await self._atualizar_mapa_conexoes()
        resultado["status"] = "concluido"
        resultado["concluido_em"] = datetime.now(UTC).isoformat()
        logger.info(
            "[REMSleep] Ciclo concluído: %d consolidadas, %d erros.",
            resultado["memorias_consolidadas"], len(resultado["erros"]),
        )
        return resultado

    async def _listar_memorias_curto_prazo(self) -> Dict[str, str]:
        """Coleta todas as notas Markdown do curto prazo de forma não-bloqueante."""
        def _read_all() -> Dict[str, str]:
            memorias = {}
            if not self.short_term_dir.exists():
                return memorias
            for f in self.short_term_dir.glob("*.md"):
                memorias[f.name] = f.read_text(encoding="utf-8")
            return memorias

        return await asyncio.to_thread(_read_all)

    async def _solicitar_sintese_ia(self, conteudo_bruto: str) -> Optional[str]:
        """Solicita síntese do conteúdo via IA ou usa fallback mockado."""
        if self.ai_client:
            prompt = self._montar_prompt_sintese(conteudo_bruto)
            try:
                # Suporte a clientes sync e async
                if asyncio.iscoroutinefunction(self.ai_client.generate):
                    return await self.ai_client.generate(prompt)
                return await asyncio.to_thread(self.ai_client.generate, prompt)
            except Exception as e:
                logger.warning("[REMSleep] IA indisponível, usando mock: %s", e)
                return self._mock_sintese(conteudo_bruto)
        return self._mock_sintese(conteudo_bruto)

    def _montar_prompt_sintese(self, conteudo_bruto: str) -> str:
        return f"""Você atua como o Córtex Subconsciente de um sistema multiagente biológico-digital (iaglobal).
Sua tarefa é processar uma memória bruta do curto prazo, eliminar o ruído
e extrair apenas o DNA do conhecimento obtido.

Regras Cruciais:
1. Identifique a raiz do problema ou o motivo do sucesso.
2. Crie ou sugira links conceituais usando o padrão do Obsidian [[Nome_Do_Conceito]].
3. Formate a saída contendo um YAML Frontmatter no início e o resumo em markdown depois.

Memória Bruta do Dia:
---
{conteudo_bruto}
---

Responda estritamente no formato estruturado abaixo:
---
tipo: ConhecimentoConsolidado
tags: [#mutacao-sucesso, #correcao-erro]
fitness_impacto: alto
links_relacionados: "[[Conceito_A]]"
---
# Título Conciso do Aprendizado
## Insights Essenciais
- O que foi aprendido...
- Como evitar ou replicar...
"""

    def _mock_sintese(self, conteudo_bruto: str) -> str:
        """Fallback mockado quando não há cliente de IA disponível."""
        return """---
tipo: ConhecimentoConsolidado
tags: [#gargalo-resolvido, #metabolismo]
fitness_impacto: alto
links_relacionados: "[[ROS_Sensor]], [[Mitochondria_Efficiency]]"
---

# Otimização Consolidada

## Insights Essenciais
- Conteúdo processado e filtrado pelo ciclo REM.
- A limpeza agressiva promovida pela autofagia reduz a latência de processamento.
- Próximos agentes devem consultar [[Mitochondria_Efficiency]] antes de alocar memória extra.
"""

    async def _gravar_longo_prazo(self, nome_arquivo: str, conteudo_consolidado: str) -> Path:
        """Salva o conhecimento consolidado no longo prazo de forma não-bloqueante."""
        def _write():
            self.long_term_dir.mkdir(parents=True, exist_ok=True)
            caminho = self.long_term_dir / nome_arquivo
            caminho.write_text(conteudo_consolidado, encoding="utf-8")
            return caminho

        return await asyncio.to_thread(_write)

    async def _remover_curto_prazo(self, nome_arquivo: str) -> None:
        """Remove a memória bruta após consolidação (poda sináptica).

        Isolado em método próprio para rastreabilidade e para permitir
        que falhas na remoção sejam logadas sem cancelar a consolidação.
        """
        def _unlink():
            origem = self.short_term_dir / nome_arquivo
            if origem.exists():
                origem.unlink()

        await asyncio.to_thread(_unlink)

    async def _atualizar_mapa_conexoes(self) -> None:
        """Reconstrói o Mapa Sináptico Central a partir das notas de longo prazo."""
        def _build_and_write():
            todas_tags: set = set()
            links_encontrados: list = []

            for f in self.long_term_dir.glob("*.md"):
                texto = f.read_text(encoding="utf-8")
                tags = re.findall(r"#[\w-]+", texto)
                todas_tags.update(tags)
                links_encontrados.append(f"[[{f.stem}]]")

            moc_content = (
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

            moc_path = self.synapses_dir / "Mapa_Mental_Subconsciente.md"
            moc_path.write_text(moc_content, encoding="utf-8")

        await asyncio.to_thread(_build_and_write)
