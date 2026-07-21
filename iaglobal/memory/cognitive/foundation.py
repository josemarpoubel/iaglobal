# iaglobal/memory/cognitive/foundation.py
"""
Fundação Cognitiva — Domínio Puro (sem dependências de infraestrutura).

Este módulo define os MODELOS COGNITIVOS do sistema, completamente
independentes de backends de armazenamento.

Separação conceitual:
    DOMÍNIO (este arquivo):
        - MemoryChunk: unidade cognitiva (o que o sistema "pensa" ou "lembra")
        - Tipos de memória: Working, Episodic, Semantic, Procedural, External
        - Abstrações: AttentionManager, CognitiveSnapshot

    INFRAESTRUTURA (outros arquivos):
        - MemoryRepository: contrato de persistência
        - MemoryRecord: registro persistido (id, version, embedding, ttl)

    APLICAÇÃO:
        - MemoryResolver: orquestra tipos de memória via repositórios
        - ContextBuilder: adapta snapshots para agentes

Taxonomia oficial:
    Memory
    ├── WorkingMemory     — Estado temporário da execução atual
    ├── EpisodicMemory    — Experiências passadas (execuções, erros, correções)
    ├── SemanticMemory    — Conhecimento factual (domínios, padrões, regras)
    ├── ProceduralMemory  — Skills aprendidas (como fazer algo)
    └── ExternalMemory    — Memórias de agentes externos/observadores

    Metacognition (NÃO é memória):
    └── ReflectionMemory  — Reflexões e auto-avaliações (produz conhecimento sobre o sistema)

NOTA: ReflectionEngine está em iaglobal/evolution/metacognition/reflection.py
      porque é metacognição, não memória. Produz conhecimento SOBRE o sistema,
      não recupera conhecimento DO sistema.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


# ============================================================
# Tipos de memória (Enum — sem strings livres)
# ============================================================


class MemoryType(Enum):
    """
    Tipos cognitivos de memória.

    Usar Enum evita variações de string (semantic, SEMANTIC, semantica, etc.)
    e garante consistência em toda a arquitetura.
    """

    WORKING = "working"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"
    EXTERNAL = "external"

    @property
    def description(self) -> str:
        descriptions = {
            MemoryType.WORKING: "Estado temporário da execução atual",
            MemoryType.EPISODIC: "Experiências passadas e lições aprendidas",
            MemoryType.SEMANTIC: "Conhecimento factual e domínios",
            MemoryType.PROCEDURAL: "Skills e procedimentos (futuro)",
            MemoryType.EXTERNAL: "Observadores e agentes externos",
        }
        return descriptions[self]


# ============================================================
# Unidade cognitiva atômica (DOMÍNIO — sem campos de infraestrutura)
# ============================================================


@dataclass(frozen=True)
class MemoryChunk:
    """
    Unidade cognitiva atômica — representa uma memória no domínio.

    DIFERENTE de MemoryRecord (persistência), que vive na infraestrutura.

    Este objeto é PURAMENTE COGNITIVO. Não sabe onde está armazenado,
    não tem ID de banco, não tem timestamp de criação (isso é infra).

    Atributos:
        content: Conteúdo textual da memória
        memory_type: Tipo cognitivo (enum MemoryType)
        source: Origem da memória (execução, agente, observador)
        agent_id: ID do agente que gerou ou consumiu
        confidence: Confiança (0.0 a 1.0)
        tags: Tags para categorização
        context: Contexto de origem (opcional)
    """

    content: str
    memory_type: MemoryType = MemoryType.SEMANTIC
    source: str = "unknown"
    agent_id: str = ""
    confidence: float = 1.0
    tags: Tuple[str, ...] = ()
    context: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_empty(self) -> bool:
        return not self.content or not self.content.strip()


# ============================================================
# Abstrações de memória (DOMÍNIO — sem backends)
# ============================================================


class WorkingMemory:
    """
    Memória de trabalho — estado temporário da execução atual.

    PURE DOMAIN MODEL. Não sabe onde dados estão armazenados.
    A persistência é responsabilidade do MemoryResolver via repositórios.

    Contém:
        - Objetivo atual da tarefa
        - Plano corrente (passos, estágios)
        - Variáveis temporárias da execução
        - Janela de contexto (últimas interações)
        - Artefatos intermediários (parciais, em construção)

    Características:
        - Volátil (descartada após execução)
        - Baixa capacidade (limitada pela janela de contexto do LLM)
        - Alta velocidade de acesso
        - Não persistida permanentemente (por padrão)
    """

    def __init__(self):
        pass

    def create_chunk(
        self,
        content: str,
        source: str = "working",
        agent_id: str = "",
        confidence: float = 1.0,
        tags: Tuple[str, ...] = (),
    ) -> MemoryChunk:
        """Cria um MemoryChunk do tipo WORKING."""
        return MemoryChunk(
            content=content,
            memory_type=MemoryType.WORKING,
            source=source,
            agent_id=agent_id,
            confidence=confidence,
            tags=tags,
        )


class EpisodicMemory:
    """
    Memória episódica — experiências passadas do sistema.

    PURE DOMAIN MODEL. Não sabe onde dados estão armazenados.

    Contém:
        - Execuções anteriores (IDs, timestamps, resultados)
        - Erros encontrados e como foram corrigidos
        - Lições aprendidas com falhas
        - Padrões de sucesso em contextos similares
        - Histórico de decisões e seus resultados

    Características:
        - Persistida entre execuções (via repositório)
        - Indexada por contexto (domínio, tipo de tarefa, agente)
        - Usada para evitar erros repetidos
        - Fonte de aprendizado por experiência
    """

    def __init__(self):
        pass

    def create_chunk(
        self,
        content: str,
        source: str = "episodic",
        agent_id: str = "",
        confidence: float = 1.0,
        tags: Tuple[str, ...] = (),
        context: Dict[str, Any] = None,
    ) -> MemoryChunk:
        """Cria um MemoryChunk do tipo EPISODIC."""
        return MemoryChunk(
            content=content,
            memory_type=MemoryType.EPISODIC,
            source=source,
            agent_id=agent_id,
            confidence=confidence,
            tags=tags,
            context=context or {},
        )


class SemanticMemory:
    """
    Memória semântica — conhecimento factual do sistema.

    PURE DOMAIN MODEL. Não sabe onde dados estão armazenados.

    Contém:
        - Conhecimento de domínios (Python, LGPD, finanças)
        - Padrões arquiteturais (DDD, CQRS, Microservices)
        - Regras de negócio
        - Glossários e vocabulários
        - Fatos estáveis (não mudam com frequência)

    Características:
        - Persistida e consolidada (via repositório)
        - Buscada por similaridade semântica (embeddings)
        - Atualizada por processos de conhecimento
        - Compartilhada entre agentes
    """

    def __init__(self):
        pass

    def create_chunk(
        self,
        content: str,
        source: str = "semantic",
        agent_id: str = "",
        confidence: float = 1.0,
        tags: Tuple[str, ...] = (),
        context: Dict[str, Any] = None,
    ) -> MemoryChunk:
        """Cria um MemoryChunk do tipo SEMANTIC."""
        return MemoryChunk(
            content=content,
            memory_type=MemoryType.SEMANTIC,
            source=source,
            agent_id=agent_id,
            confidence=confidence,
            tags=tags,
            context=context or {},
        )


class ProceduralMemory:
    """
    Memória procedural — skills e procedimentos aprendidos.

    PURE DOMAIN MODEL (futuro).

    Contém:
        - Como escrever testes para um domínio
        - Como revisar código de um padrão específico
        - Como documentar APIs REST
        - Como otimizar consultas SQL
        - Como configurar CI/CD

    Características:
        - Ainda não implementada
        - Indexada por tipo de skill
        - Aprendida por demonstração e reforço
        - Reutilizada como templates/helpers
    """

    def __init__(self):
        pass

    def create_chunk(
        self,
        content: str,
        skill_name: str = "",
        agent_id: str = "",
        confidence: float = 1.0,
        tags: Tuple[str, ...] = (),
        context: Dict[str, Any] = None,
    ) -> MemoryChunk:
        """Cria um MemoryChunk do tipo PROCEDURAL."""
        tags_with_skill = (skill_name,) + tags if skill_name else tags
        return MemoryChunk(
            content=content,
            memory_type=MemoryType.PROCEDURAL,
            source=f"skill:{skill_name}" if skill_name else "procedural",
            agent_id=agent_id,
            confidence=confidence,
            tags=tags_with_skill,
            context=context or {},
        )


class ExternalMemory:
    """
    Memória externa — observadores e agentes externos.

    PURE DOMAIN MODEL.

    Contém:
        - Memórias de agentes externos conectados (MCP, API, outros sistemas)
        - Observações de eventos externos
        - Sinais de outros processos/ambientes
        - Memórias compartilhadas entre instâncias

    Características:
        - Interface com sistemas externos
        - Pode ser somente leitura ou leitura/escrita
        - Usada para coordenamento multi-agente
    """

    def __init__(self):
        pass

    def create_chunk(
        self,
        content: str,
        source: str = "external",
        agent_id: str = "",
        confidence: float = 1.0,
        tags: Tuple[str, ...] = (),
        context: Dict[str, Any] = None,
    ) -> MemoryChunk:
        """Cria um MemoryChunk do tipo EXTERNAL."""
        return MemoryChunk(
            content=content,
            memory_type=MemoryType.EXTERNAL,
            source=source,
            agent_id=agent_id,
            confidence=confidence,
            tags=tags,
            context=context or {},
        )


# ============================================================
# Attention Manager (componente cognitivo)
# ============================================================


class AttentionManager:
    """
    Gerencia o foco de atenção do sistema.

    Responsável por decidir QUAL memória entra na janela de contexto.
    Funciona como um filtro de saliência antes do MemoryResolver.

    Critérios de atenção:
        - Relevância para o objetivo atual
        - Recência (memórias mais recentes têm prioridade)
        - Importância (confiança, frequência de uso)
        - Recursos disponíveis (orçamento de tokens)

    Exemplo de fluxo:
        attention = AttentionManager(budget=4000)
        relevant = attention.filter(
            all_memories,
            current_goal="implementar autenticação",
            available_tokens=4000,
        )
        # Retorna apenas memórias relevantes dentro do orçamento
    """

    def __init__(self, token_budget: int = 4000):
        self.token_budget = token_budget

    def filter(
        self,
        memories: List[MemoryChunk],
        current_goal: str = "",
        available_tokens: Optional[int] = None,
    ) -> List[MemoryChunk]:
        """
        Filtra memórias por relevância e orçamento.

        Args:
            memories: Lista de memórias candidatas
            current_goal: Objetivo atual (para calcular relevância)
            available_tokens: Orçamento disponível (default: self.token_budget)

        Returns:
            Lista filtrada e ordenada por relevância
        """
        budget = available_tokens or self.token_budget

        # Filtra memórias vazias
        candidates = [m for m in memories if not m.is_empty]
        if not candidates:
            return []

        # Ordena por confiança (score de relevância)
        candidates.sort(key=lambda m: m.confidence, reverse=True)

        # Aplica orçamento (estimativa simples: 1 token ≈ 4 chars)
        result = []
        total_chars = 0
        max_chars = budget * 4

        for mem in candidates:
            mem_chars = len(mem.content)
            if total_chars + mem_chars > max_chars:
                break
            result.append(mem)
            total_chars += mem_chars + 2

        return result


# ============================================================
# Registry de tipos (referência)
# ============================================================

MEMORY_TYPE_REGISTRY: Dict[MemoryType, str] = {
    MemoryType.WORKING: "Estado temporário da execução atual",
    MemoryType.EPISODIC: "Experiências passadas e lições aprendidas",
    MemoryType.SEMANTIC: "Conhecimento factual e domínios",
    MemoryType.PROCEDURAL: "Skills e procedimentos (futuro)",
    MemoryType.EXTERNAL: "Observadores e agentes externos",
}
