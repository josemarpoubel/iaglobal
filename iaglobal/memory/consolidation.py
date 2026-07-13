"""ConsolidationEngine — Agrupa, sumariza e consolida conhecimento.

Implementa o ciclo de "aprendizado sem treinar modelo":
1. Agrupa knowledge em clusters por similaridade
2. Sumariza cada cluster em um insight compacto
3. Armazena no LongTermMemory com fonte "consolidated"
"""

import re
from typing import List, Dict, Optional
from collections import defaultdict


class ConsolidationEngine:
    """Engine de consolidação inteligente de conhecimento."""

    def __init__(self, long_term_memory=None, min_cluster_size: int = 2):
        self.ltm = long_term_memory
        self.min_cluster_size = min_cluster_size

    def consolidate(self, items: List[Dict]) -> List[Dict]:
        """Processa uma lista de itens (web + local) e retorna consolidados."""
        clusters = self._cluster(items)
        summaries = []
        for cluster in clusters:
            if len(cluster) >= self.min_cluster_size:
                summary = self._summarize(cluster)
                if summary:
                    summaries.append(summary)
                    if self.ltm:
                        self.ltm.consolidate(
                            summary["content"],
                            {**summary.get("metadata", {}), "source": "consolidated"},
                        )
        return summaries

    def consolidate_web_knowledge(
        self, web_results: List[Dict], local_memories: List[Dict]
    ) -> List[Dict]:
        """Consolida conhecimento web + local em insights."""
        all_items = self._normalize(web_results, "web") + self._normalize(
            local_memories, "local"
        )
        return self.consolidate(all_items)

    def _cluster(self, items: List[Dict]) -> List[List[Dict]]:
        """Agrupa itens por palavras-chave compartilhadas."""
        clusters = defaultdict(list)
        for item in items:
            text = item.get("content", "") or item.get("text", "") or ""
            words = set(re.findall(r"\b[a-z]{4,}\b", text.lower()))
            # Find best cluster match
            best_cluster = None
            best_overlap = 0
            for key in clusters:
                overlap = len(words & key)
                if overlap > best_overlap:
                    best_overlap = overlap
                    best_cluster = key
            if best_cluster and best_overlap >= 2:
                clusters[best_cluster].append(item)
            else:
                clusters[frozenset(words)].append(item)
        return [c for c in clusters.values()]

    def _summarize(self, cluster: List[Dict]) -> Optional[Dict]:
        """Sumariza um cluster em um insight consolidado."""
        if not cluster:
            return None
        sources = list(set(item.get("source", "unknown") for item in cluster))
        titles = [
            item.get("title", "") or item.get("type", "")
            for item in cluster
            if item.get("title") or item.get("type")
        ]
        contents = [item.get("content", "") or item.get("text", "") for item in cluster]

        # Combine content and extract key info
        combined = " ".join(c for c in contents if c)
        key_topics = list(
            set(re.findall(r"\b[A-Z][a-z]+(?:\s[A-Z][a-z]+)*\b", combined))
        )
        key_topics = [t for t in key_topics if len(t) > 3][:5]

        summary_content = combined[:500] if len(combined) > 500 else combined

        return {
            "content": f"Insight consolidado ({', '.join(sources)}): {summary_content}",
            "metadata": {
                "source": "+".join(sources),
                "clusters": len(cluster),
                "topics": key_topics,
                "titles": titles[:3],
            },
        }

    def _normalize(self, items: List[Dict], default_source: str) -> List[Dict]:
        """Normaliza itens para formato padrao."""
        normalized = []
        for item in items:
            if isinstance(item, dict):
                normalized.append(
                    {
                        "content": item.get("content")
                        or item.get("text")
                        or item.get("body", ""),
                        "title": item.get("title", ""),
                        "source": item.get("source", default_source),
                        "type": item.get("type", default_source),
                    }
                )
            elif isinstance(item, str):
                normalized.append(
                    {
                        "content": item,
                        "title": "",
                        "source": default_source,
                        "type": default_source,
                    }
                )
        return normalized
