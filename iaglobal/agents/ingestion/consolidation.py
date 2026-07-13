# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
ResearchConsolidator — Consolida resultados de pesquisa em conhecimento de longo prazo.

Transforma:
- Paper + Hipóteses + Resultados de Experimentos
Em:
- Nota Obsidian em 03_Long_Term/ com tags, links e fitness score

Integra com:
- ExperimentRunner (entrada: List[ExperimentResult])
- PaperParser (entrada: PaperMetadata)
- obsidian/subconsciousapi.py (saída: 03_Long_Term/)
- memory/data/json/{paper_id}_consolidated.json
"""

import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime, timezone

from iaglobal._paths import JSON_DIR
from iaglobal.utils.logger import get_logger
from iaglobal.agents.ingestion.paper_parser import PaperMetadata
from iaglobal.agents.ingestion.experiment_runner import ExperimentResult

logger = get_logger("iaglobal.agents.ingestion.consolidation")


@dataclass
class ConsolidatedPaper:
    """Paper consolidado com resultados de validação."""

    paper_id: str
    title: str
    abstract: str
    authors: List[str]
    published_date: str
    repository: str
    topics: List[str]
    hypotheses_count: int
    validated_count: int
    failed_count: int
    fitness_score: float
    obsidian_path: Optional[str]
    consolidated_at: str = ""

    def __post_init__(self):
        if not self.consolidated_at:
            self.consolidated_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ResearchConsolidator:
    """Consolida resultados de pesquisa em conhecimento de longo prazo."""

    MARKDOWN_TEMPLATE = """---
id: "{paper_id}"
tipo: "PaperValidado"
topics: [{topics}]
fitness_score: {fitness_score:.2f}
tags: [{tags}]
---

# {title}

## Metadados

- **Paper ID**: {paper_id}
- **Autores**: {authors}
- **Data**: {published_date}
- **Repositório**: {repository}
- **Consolidado em**: {consolidated_at}

## Abstract

{abstract}

## Tópicos

{topics_list}

## Validação Experimental

**Resumo**: {validated_count}/{hypotheses_count} hipóteses validadas ({fitness_score:.0%})

### Hipóteses Validadas ✅

{validated_hypotheses}

### Hipóteses Não Validadas ❌

{failed_hypotheses}

## Métricas de Validação

{validation_metrics}

## Conclusão

{conclusion}

---

*Consolidado automaticamente por ResearchConsolidator — Autonomous Research Loop*
"""

    def __init__(self):
        pass

    async def consolidate(
        self,
        paper: PaperMetadata,
        results: List[ExperimentResult],
        obsidian_enabled: bool = True,
    ) -> ConsolidatedPaper:
        """
        Consolida paper + resultados em conhecimento de longo prazo.

        Args:
            paper: PaperMetadata com metadados completos
            results: Lista de ExperimentResult das hipóteses
            obsidian_enabled: Se True, escreve no Obsidian Vault

        Returns:
            ConsolidatedPaper com caminho Obsidian e métricas
        """
        # Calcular métricas
        validated = [r for r in results if r.success]
        failed = [r for r in results if not r.success]
        fitness_score = len(validated) / len(results) if results else 0.0

        # Gerar conteúdo markdown
        markdown_content = self._generate_markdown(
            paper, results, validated, failed, fitness_score
        )

        # Escrever no Obsidian
        obsidian_path = None
        if obsidian_enabled:
            obsidian_path = await self._write_to_obsidian(
                markdown_content, paper, fitness_score
            )

        # Criar objeto consolidado
        consolidated = ConsolidatedPaper(
            paper_id=paper.paper_id,
            title=paper.title,
            abstract=paper.abstract,
            authors=paper.authors,
            published_date=paper.published_date,
            repository=paper.repository,
            topics=paper.topics,
            hypotheses_count=len(results),
            validated_count=len(validated),
            failed_count=len(failed),
            fitness_score=fitness_score,
            obsidian_path=obsidian_path,
        )

        # Salvar JSON
        self._save_consolidated_json(consolidated, results)

        logger.info(
            "[CONSOL] %s: %d/%d hipóteses validadas (fitness: %.2f) → %s",
            paper.paper_id,
            len(validated),
            len(results),
            fitness_score,
            obsidian_path or "JSON apenas",
        )

        return consolidated

    def _generate_markdown(
        self,
        paper: PaperMetadata,
        all_results: List[ExperimentResult],
        validated: List[ExperimentResult],
        failed: List[ExperimentResult],
        fitness_score: float,
    ) -> str:
        """Gera conteúdo markdown estruturado."""
        # Formatar tópicos
        topics_md = (
            ", ".join(f'"{t}"' for t in paper.topics)
            if paper.topics
            else '"sem-topicos"'
        )
        tags_md = (
            ", ".join(f'"{t}"' for t in paper.topics[:5])
            if paper.topics
            else '"research"'
        )

        # Formatar hipóteses validadas
        if validated:
            validated_md = "\n".join(
                f"### {r.hypothesis_id}\n\n"
                f"**Descrição**: {self._get_hypothesis_description(r)}\n\n"
                f"**Confiança**: {r.confidence:.0%}\n\n"
                f"**Métricas**: {self._format_metrics(r.metrics)}\n\n"
                f"**Detalhes**: {r.validation_details}\n"
                for r in validated
            )
        else:
            validated_md = "*Nenhuma hipótese validada*"

        # Formatar hipóteses falhadas
        if failed:
            failed_md = "\n".join(
                f"### {r.hypothesis_id}\n\n"
                f"**Descrição**: {self._get_hypothesis_description(r)}\n\n"
                f"**Erro**: {r.validation_details or r.stderr or 'Falha na execução'}\n"
                for r in failed
            )
        else:
            failed_md = "*Nenhuma hipótese falhou*"

        # Formatar métricas agregadas
        validation_metrics_md = self._format_aggregate_metrics(all_results)

        # Gerar conclusão
        conclusion = self._generate_conclusion(paper, fitness_score, validated, failed)

        # Formatar lista de tópicos
        topics_list = (
            "\n".join(f"- `{t}`" for t in paper.topics)
            if paper.topics
            else "- *sem tópicos*"
        )

        # Preencher template
        markdown = self.MARKDOWN_TEMPLATE.format(
            paper_id=paper.paper_id,
            title=paper.title,
            authors=", ".join(paper.authors),
            published_date=paper.published_date,
            repository=paper.repository,
            abstract=paper.abstract,
            topics=topics_md,
            tags=tags_md,
            topics_list=topics_list,
            fitness_score=fitness_score,
            hypotheses_count=len(all_results),
            validated_count=len(validated),
            failed_count=len(failed),
            validated_hypotheses=validated_md,
            failed_hypotheses=failed_md,
            validation_metrics=validation_metrics_md,
            conclusion=conclusion,
            consolidated_at=datetime.now(timezone.utc).strftime(
                "%Y-%m-%d %H:%M:%S UTC"
            ),
        )

        return markdown

    def _get_hypothesis_description(self, result: ExperimentResult) -> str:
        """Extrai descrição da hipótese do código ou validation_details."""
        # Tentar extrair do código (comentário inicial)
        if result.code:
            lines = result.code.split("\n")
            for line in lines[:5]:
                if line.strip().startswith("# Experimento:") or line.strip().startswith(
                    "#"
                ):
                    return line.replace("#", "").replace("# Experimento:", "").strip()

        # Fallback: usar validation_details
        return (
            result.validation_details[:100]
            if result.validation_details
            else "Hipótese não disponível"
        )

    def _format_metrics(self, metrics: Dict[str, Any]) -> str:
        """Formata métricas como lista markdown."""
        if not metrics:
            return "*Sem métricas*"

        return "\n".join(
            f"- **{k}**: {v:.4f}" if isinstance(v, float) else f"- **{k}**: {v}"
            for k, v in metrics.items()
        )

    def _format_aggregate_metrics(self, results: List[ExperimentResult]) -> str:
        """Formata métricas agregadas de todos os experimentos."""
        if not results:
            return "*Sem dados*"

        total_time = sum(r.execution_time_ms for r in results)
        avg_confidence = sum(r.confidence for r in results) / len(results)
        success_rate = sum(1 for r in results if r.success) / len(results)

        metrics = [
            f"- **Tempo total de execução**: {total_time:.0f}ms ({total_time / 1000:.1f}s)",
            f"- **Confiança média**: {avg_confidence:.0%}",
            f"- **Taxa de sucesso**: {success_rate:.0%}",
            f"- **Total de hipóteses**: {len(results)}",
        ]

        return "\n".join(metrics)

    def _generate_conclusion(
        self,
        paper: PaperMetadata,
        fitness_score: float,
        validated: List[ExperimentResult],
        failed: List[ExperimentResult],
    ) -> str:
        """Gera conclusão baseada nos resultados."""
        if fitness_score >= 0.8:
            return (
                f"**Alta validação**: {len(validated)}/{len(validated) + len(failed)} hipóteses confirmadas.\n\n"
                f"Os resultados experimentais suportam fortemente as claims do paper. "
                f"Recomenda-se: (1) replicação em datasets adicionais, (2) comparação com baselines alternativas."
            )
        elif fitness_score >= 0.5:
            return (
                f"**Validação moderada**: {len(validated)}/{len(validated) + len(failed)} hipóteses confirmadas.\n\n"
                f"Algumas claims do paper foram validadas, mas outras não. "
                f"Recomenda-se: (1) investigação das causas das falhas, (2) refinamento das hipóteses não validadas."
            )
        else:
            return (
                f"**Baixa validação**: {len(validated)}/{len(validated) + len(failed)} hipóteses confirmadas.\n\n"
                f"A maioria das claims não foram validadas experimentalmente. "
                f"Recomenda-se: (1) revisão crítica do paper, (2) verificação de erros metodológicos, (3) tentativa de replicação independente."
            )

    async def _write_to_obsidian(
        self, content: str, paper: PaperMetadata, fitness_score: float = 0.5
    ) -> str:
        """Escreve nota no Obsidian Vault 03_Long_Term/."""
        try:
            from iaglobal.obsidian.subconsciousapi import SubconsciousAPI

            sub = SubconsciousAPI()

            # Escrever em 03_Long_Term/
            note_name = f"paper_{paper.paper_id.replace(':', '_')}"

            note_path = await sub.escrever_longo_prazo(
                nome=note_name,
                conteudo=content,
                tipo="PaperValidado",
                tags=paper.topics[:5] if paper.topics else ["research"],
                fitness=fitness_score,
            )

            logger.info("[CONSOL] Obsidian: %s", note_path)
            return str(note_path)

        except ImportError:
            logger.warning("[CONSOL] SubconsciousAPI não disponível — skip Obsidian")
            return None
        except Exception as e:
            logger.error("[CONSOL] Erro ao escrever no Obsidian: %s", e)
            return None

    def _save_consolidated_json(
        self, consolidated: ConsolidatedPaper, results: List[ExperimentResult]
    ):
        """Salva consolidação em JSON."""
        output_path = (
            JSON_DIR / f"{consolidated.paper_id.replace(':', '_')}_consolidated.json"
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "paper": consolidated.to_dict(),
            "experiment_results": [r.to_dict() for r in results],
            "summary": {
                "total_hypotheses": consolidated.hypotheses_count,
                "validated": consolidated.validated_count,
                "failed": consolidated.failed_count,
                "fitness_score": consolidated.fitness_score,
            },
        }

        output_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        logger.debug("[CONSOL] JSON salvo em: %s", output_path)


# Funções utilitárias
async def consolidate_paper(
    paper: PaperMetadata,
    results: List[ExperimentResult],
    obsidian_enabled: bool = True,
) -> ConsolidatedPaper:
    """
    Consolida paper + resultados.

    Args:
        paper: PaperMetadata
        results: Lista de ExperimentResult
        obsidian_enabled: Se True, escreve no Obsidian

    Returns:
        ConsolidatedPaper
    """
    consolidator = ResearchConsolidator()
    return await consolidator.consolidate(paper, results, obsidian_enabled)


async def consolidate_full_pipeline(
    paper: PaperMetadata,
    hypotheses: List,
    results: List[ExperimentResult],
    obsidian_enabled: bool = True,
) -> ConsolidatedPaper:
    """
    Consolida pipeline completo: Paper → Hipóteses → Resultados → Obsidian.

    Args:
        paper: PaperMetadata
        hypotheses: Lista de Hypothesis (não usado diretamente, apenas para logging)
        results: Lista de ExperimentResult
        obsidian_enabled: Se True, escreve no Obsidian

    Returns:
        ConsolidatedPaper
    """
    logger.info(
        "[CONSOL] Consolidando %s: %d hipóteses, %d resultados",
        paper.paper_id,
        len(hypotheses),
        len(results),
    )

    return await consolidate_paper(paper, results, obsidian_enabled)
