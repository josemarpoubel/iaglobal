# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
MetaLearner — Meta-aprendizado do Autonomous Research Loop.

Funcionalidades:
1. Auto-curadoria — Papers com baixo fitness são marcados como "baixa qualidade"
2. Recomendação ativa — Sugere novos papers baseado em tópicos de alto fitness
3. Citação cruzada — Links entre papers consolidados via [[paper_id]]
4. Meta-análise — Gera review automático após N papers
5. Replicação automática — Hipóteses não validadas disparam nova rodada

Integra com:
- ResearchConsolidator (entrada: ConsolidatedPaper)
- obsidian/subconsciousapi.py (saída: citações, reviews)
- memory/data/json/meta_analysis.json
"""

import asyncio
import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from collections import Counter

from iaglobal._paths import JSON_DIR
from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.agents.ingestion.meta_learner")


@dataclass
class PaperRecommendation:
    """Recomendação de paper para leitura."""
    paper_id: str
    title: str
    topics: List[str]
    predicted_fitness: float
    reason: str
    similar_to: List[str]  # paper_ids similares

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class MetaAnalysis:
    """Meta-análise de N papers consolidados."""
    total_papers: int
    total_hypotheses: int
    validated_hypotheses: int
    overall_fitness: float
    top_topics: List[Tuple[str, int]]
    low_fitness_papers: List[str]
    high_fitness_papers: List[str]
    replication_candidates: List[str]
    generated_at: str = ""

    def __post_init__(self):
        if not self.generated_at:
            self.generated_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class MetaLearner:
    """Meta-aprendizado do Autonomous Research Loop."""

    def __init__(self):
        self.consolidated_dir = JSON_DIR / "papers"
        self.meta_analysis_file = JSON_DIR / "meta_analysis.json"
        self.recommendations_file = JSON_DIR / "paper_recommendations.json"

    async def load_consolidated_papers(self) -> List[Dict[str, Any]]:
        """Carrega todos os papers consolidados (async I/O)."""
        papers = []
        
        if not self.consolidated_dir.exists():
            logger.warning("[META] Diretório de papers não existe: %s", self.consolidated_dir)
            return papers
        
        def _load_files() -> List[Dict[str, Any]]:
            loaded = []
            for consolidated_file in self.consolidated_dir.glob("*_consolidated.json"):
                try:
                    data = json.loads(consolidated_file.read_text(encoding="utf-8"))
                    loaded.append(data)
                except Exception as e:
                    logger.debug("[META] Erro ao ler %s: %s", consolidated_file.name, e)
            return loaded
        
        papers = await asyncio.to_thread(_load_files)
        logger.info("[META] %d papers consolidados carregados", len(papers))
        return papers

    async def generate_meta_analysis(self, min_papers: int = 5) -> Optional[MetaAnalysis]:
        """
        Gera meta-análise após N papers.

        Args:
            min_papers: Mínimo de papers para gerar análise

        Returns:
            MetaAnalysis ou None se < min_papers
        """
        papers = await self.load_consolidated_papers()
        
        if len(papers) < min_papers:
            logger.info("[META] Apenas %d papers (mínimo: %d) — skip meta-análise", len(papers), min_papers)
            return None
        
        # Calcular métricas agregadas
        total_papers = len(papers)
        total_hypotheses = sum(p["summary"]["total_hypotheses"] for p in papers)
        validated_hypotheses = sum(p["summary"]["validated"] for p in papers)
        overall_fitness = validated_hypotheses / total_hypotheses if total_hypotheses > 0 else 0.0
        
        # Tópicos mais freqüentes
        all_topics = []
        for p in papers:
            all_topics.extend(p["paper"].get("topics", []))
        topic_counts = Counter(all_topics)
        top_topics = topic_counts.most_common(10)
        
        # Papers por fitness
        low_fitness = []
        high_fitness = []
        replication_candidates = []
        
        for p in papers:
            paper_id = p["paper"]["paper_id"]
            fitness = p["summary"]["fitness_score"]
            
            if fitness < 0.5:
                low_fitness.append(paper_id)
            elif fitness >= 0.8:
                high_fitness.append(paper_id)
            
            # Candidatos a replicação: fitness entre 0.33 e 0.67 (resultados mistos)
            if 0.33 <= fitness <= 0.67:
                replication_candidates.append(paper_id)
        
        analysis = MetaAnalysis(
            total_papers=total_papers,
            total_hypotheses=total_hypotheses,
            validated_hypotheses=validated_hypotheses,
            overall_fitness=overall_fitness,
            top_topics=top_topics,
            low_fitness_papers=low_fitness,
            high_fitness_papers=high_fitness,
            replication_candidates=replication_candidates,
        )
        
        # Salvar
        await self._save_meta_analysis(analysis)
        
        logger.info(
            "[META] Meta-análise: %d papers, %d hipóteses, fitness=%.0f%%",
            total_papers, total_hypotheses, overall_fitness * 100,
        )
        
        return analysis

    async def _save_meta_analysis(self, analysis: MetaAnalysis):
        """Salva meta-análise em JSON (async I/O)."""
        def _save():
            self.meta_analysis_file.parent.mkdir(parents=True, exist_ok=True)
            self.meta_analysis_file.write_text(
                json.dumps(analysis.to_dict(), indent=2, ensure_ascii=False),
                encoding="utf-8"
            )
        
        await asyncio.to_thread(_save)
        logger.info("[META] Meta-análise salva em: %s", self.meta_analysis_file)

    async def curate_low_fitness_papers(self, threshold: float = 0.5) -> List[str]:
        """
        Marca papers com baixo fitness como "baixa qualidade".

        Args:
            threshold: Fitness máximo para ser considerado "baixo"

        Returns:
            Lista de paper_ids de baixa qualidade
        """
        papers = await self.load_consolidated_papers()
        low_quality = []
        
        for p in papers:
            if p["summary"]["fitness_score"] < threshold:
                paper_id = p["paper"]["paper_id"]
                low_quality.append(paper_id)
                
                # Adicionar tag de baixa qualidade no JSON consolidado
                p["paper"]["quality_flag"] = "low"
                p["paper"]["quality_reason"] = f"fitness < {threshold:.0%}"
                
                # Salvar atualização - converter paper_id para formato do arquivo (2401.000 -> 2401_000)
                file_safe_id = paper_id.replace(".", "_").replace(":", "_")
                consolidated_file = self.consolidated_dir / f"{file_safe_id}_consolidated.json"
                
                def _save_update():
                    consolidated_file.write_text(
                        json.dumps(p, indent=2, ensure_ascii=False),
                        encoding="utf-8"
                    )
                
                logger.debug("[META] Salvando atualização em: %s", consolidated_file)
                try:
                    await asyncio.to_thread(_save_update)
                    logger.debug("[META] Arquivo atualizado com sucesso")
                except Exception as e:
                    logger.error("[META] Erro ao salvar %s: %s", consolidated_file, e)
        
        logger.info("[META] %d papers marcados como baixa qualidade", len(low_quality))
        return low_quality

    async def generate_recommendations(
        self,
        user_topics: Optional[List[str]] = None,
        limit: int = 10,
    ) -> List[PaperRecommendation]:
        """
        Gera recomendações de papers baseado em tópicos de alto fitness.

        Args:
            user_topics: Tópicos de interesse do usuário (opcional)
            limit: Máximo de recomendações

        Returns:
            Lista de PaperRecommendation
        """
        papers = await self.load_consolidated_papers()
        
        # Filtrar papers de alto fitness
        high_fitness_papers = [
            p for p in papers
            if p["summary"]["fitness_score"] >= 0.8
        ]
        
        if not high_fitness_papers:
            logger.warning("[META] Nenhum paper de alto fitness para recomendações")
            return []
        
        # Calcular tópicos "quentes" (alto fitness + freqüente)
        topic_fitness = {}
        for p in high_fitness_papers:
            fitness = p["summary"]["fitness_score"]
            for topic in p["paper"].get("topics", []):
                if topic not in topic_fitness:
                    topic_fitness[topic] = []
                topic_fitness[topic].append(fitness)
        
        # Média de fitness por tópico
        topic_avg_fitness = {
            topic: sum(fitnesses) / len(fitnesses)
            for topic, fitnesses in topic_fitness.items()
        }
        
        # Ordenar por fitness médio
        sorted_topics = sorted(topic_avg_fitness.items(), key=lambda x: x[1], reverse=True)
        
        # Gerar recomendações
        recommendations = []
        for paper in high_fitness_papers[:limit]:
            paper_topics = paper["paper"].get("topics", [])
            
            # Calcular predicted fitness baseado em tópicos
            predicted_fitness = sum(
                topic_avg_fitness.get(t, 0.5) for t in paper_topics
            ) / max(len(paper_topics), 1)
            
            # Motivo da recomendação
            if user_topics:
                matching_topics = set(paper_topics) & set(user_topics)
                reason = f"Match com seus tópicos: {', '.join(matching_topics)}"
            else:
                reason = f"Alto fitness ({paper['summary']['fitness_score']:.0%}) em {paper_topics[0] if paper_topics else 'geral'}"
            
            rec = PaperRecommendation(
                paper_id=paper["paper"]["paper_id"],
                title=paper["paper"]["title"],
                topics=paper_topics,
                predicted_fitness=predicted_fitness,
                reason=reason,
                similar_to=[],  # TODO: implementar similaridade
            )
            recommendations.append(rec)
        
        # Ordenar por predicted fitness
        recommendations.sort(key=lambda r: r.predicted_fitness, reverse=True)
        
        # Salvar
        await self._save_recommendations(recommendations)
        
        logger.info("[META] %d recomendações geradas", len(recommendations))
        return recommendations

    async def _save_recommendations(self, recommendations: List[PaperRecommendation]):
        """Salva recomendações em JSON (async I/O)."""
        def _save():
            self.recommendations_file.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "recommendations": [r.to_dict() for r in recommendations],
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }
            self.recommendations_file.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8"
            )
        
        await asyncio.to_thread(_save)

    async def trigger_replication(self, paper_id: str) -> bool:
        """
        Dispara replicação automática de paper com resultados mistos.

        Args:
            paper_id: ID do paper para replicar

        Returns:
            True se replicação disparada com sucesso
        """
        # Converter paper_id para formato do arquivo (2401.000 -> 2401_000)
        file_safe_id = paper_id.replace(".", "_").replace(":", "_")
        consolidated_file = self.consolidated_dir / f"{file_safe_id}_consolidated.json"
        
        if not consolidated_file.exists():
            logger.warning("[META] Paper não encontrado: %s", paper_id)
            return False
        
        def _load_data():
            return json.loads(consolidated_file.read_text(encoding="utf-8"))
        
        data = await asyncio.to_thread(_load_data)
        
        # Verificar se é candidato (fitness entre 0.33 e 0.67)
        fitness = data["summary"]["fitness_score"]
        if not (0.33 <= fitness <= 0.67):
            logger.info("[META] %s não é candidato a replicação (fitness=%.0f%%)", paper_id, fitness * 100)
            return False
        
        # TODO: Disparar nova rodada de experimentos com parâmetros ajustados
        # Por enquanto, apenas log
        logger.info(
            "[META] Replicação disparada para %s (fitness=%.0f%%, hipóteses mistas)",
            paper_id,
            fitness * 100,
        )
        
        # Marcar como "em replicação"
        data["replication"] = {
            "status": "pending",
            "triggered_at": datetime.now(timezone.utc).isoformat(),
            "reason": f"fitness={fitness:.0%} (resultados mistos)",
        }
        
        def _save_data():
            consolidated_file.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8"
            )
        
        await asyncio.to_thread(_save_data)
        
        return True

    async def generate_cross_citations(self) -> Dict[str, List[str]]:
        """
        Gera citações cruzadas entre papers consolidados.

        Returns:
            Dict {paper_id: [paper_ids_citados]}
        """
        papers = await self.load_consolidated_papers()
        citations = {}
        
        # Agrupar por tópicos
        topic_to_papers = {}
        for p in papers:
            for topic in p["paper"].get("topics", []):
                if topic not in topic_to_papers:
                    topic_to_papers[topic] = []
                topic_to_papers[topic].append(p["paper"]["paper_id"])
        
        # Gerar citações (papers com tópicos em comum)
        for p in papers:
            paper_id = p["paper"]["paper_id"]
            paper_topics = p["paper"].get("topics", [])
            
            # Papers relacionados (mesmos tópicos, exceto ele mesmo)
            related = set()
            for topic in paper_topics:
                related.update(topic_to_papers.get(topic, []))
            
            related.discard(paper_id)  # Remover ele mesmo
            citations[paper_id] = list(related)[:5]  # Top 5 relacionados
        
        # Atualizar JSONs consolidados com citações
        async def _update_citation(pid, cited_ids):
            file_safe_id = pid.replace(".", "_").replace(":", "_")
            consolidated_file = self.consolidated_dir / f"{file_safe_id}_consolidated.json"
            
            if consolidated_file.exists():
                def _update():
                    data = json.loads(consolidated_file.read_text(encoding="utf-8"))
                    data["citations"] = cited_ids
                    consolidated_file.write_text(
                        json.dumps(data, indent=2, ensure_ascii=False),
                        encoding="utf-8"
                    )
                await asyncio.to_thread(_update)
        
        # Atualizar em paralelo
        await asyncio.gather(*[_update_citation(pid, cited) for pid, cited in citations.items()])
        
        logger.info("[META] Citações cruzadas geradas para %d papers", len(citations))
        return citations

    async def get_summary(self) -> Dict[str, Any]:
        """Retorna resumo do meta-aprendizado."""
        papers = await self.load_consolidated_papers()
        
        if not papers:
            return {"status": "no_data"}
        
        total = len(papers)
        high_fitness = sum(1 for p in papers if p["summary"]["fitness_score"] >= 0.8)
        low_fitness = sum(1 for p in papers if p["summary"]["fitness_score"] < 0.5)
        
        return {
            "status": "active",
            "total_papers": total,
            "high_fitness": high_fitness,
            "low_fitness": low_fitness,
            "quality_rate": high_fitness / total if total > 0 else 0.0,
            "last_meta_analysis": self.meta_analysis_file.exists(),
            "last_recommendations": self.recommendations_file.exists(),
        }


# Funções utilitárias
async def run_meta_learning(min_papers: int = 5) -> Dict[str, Any]:
    """
    Executa meta-aprendizado completo.

    Args:
        min_papers: Mínimo de papers para meta-análise

    Returns:
        Dict com resumo das operações
    """
    learner = MetaLearner()
    
    results = {
        "meta_analysis": None,
        "low_quality_papers": [],
        "recommendations": [],
        "citations": {},
    }
    
    # 1. Meta-análise
    analysis = await learner.generate_meta_analysis(min_papers)
    if analysis:
        results["meta_analysis"] = analysis.to_dict()
    
    # 2. Curadoria
    results["low_quality_papers"] = await learner.curate_low_fitness_papers()
    
    # 3. Recomendações
    recommendations = await learner.generate_recommendations(limit=5)
    results["recommendations"] = [r.to_dict() for r in recommendations]
    
    # 4. Citações cruzadas
    results["citations"] = await learner.generate_cross_citations()
    
    # 5. Resumo
    results["summary"] = await learner.get_summary()
    
    logger.info(
        "[META] Meta-aprendizado completo: %d papers, %d baixa qualidade, %d recomendações",
        results["summary"].get("total_papers", 0),
        len(results["low_quality_papers"]),
        len(results["recommendations"]),
    )
    
    return results