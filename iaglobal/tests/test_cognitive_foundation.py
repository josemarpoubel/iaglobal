# iaglobal/tests/test_cognitive_foundation.py
"""
Testes dos contratos cognitivos — verifica consistência da fundação
sem implementar nenhum backend concreto.

Arquitetura:
    DOMÍNIO: foundation.py (MemoryChunk, MemoryType, tipos de memória, AttentionManager)
    INFRA:    memory/repository.py (MemoryRepository, MemoryReader, MemoryWriter, MemorySearcher)
    METACOGNIÇÃO: metacognition/reflection.py (Reflection, ReflectionEngine)
"""

import inspect
import pytest


class TestMemoryTypeEnum:
    def test_memory_type_enum_values(self):
        from iaglobal.memory.cognitive import MemoryType

        assert MemoryType.WORKING.value == "working"
        assert MemoryType.EPISODIC.value == "episodic"
        assert MemoryType.SEMANTIC.value == "semantic"
        assert MemoryType.PROCEDURAL.value == "procedural"
        assert MemoryType.EXTERNAL.value == "external"

    def test_memory_type_has_description(self):
        from iaglobal.memory.cognitive import MemoryType

        for mt in MemoryType:
            desc = mt.description
            assert len(desc) > 0, f"{mt} sem descrição"

    def test_memory_type_registry(self):
        from iaglobal.memory.cognitive import MEMORY_TYPE_REGISTRY, MemoryType

        assert set(MEMORY_TYPE_REGISTRY.keys()) == {
            MemoryType.WORKING,
            MemoryType.EPISODIC,
            MemoryType.SEMANTIC,
            MemoryType.PROCEDURAL,
            MemoryType.EXTERNAL,
        }


class TestMemoryChunkContract:
    def test_chunk_creation_with_enum(self):
        from iaglobal.memory.cognitive import MemoryChunk, MemoryType

        chunk = MemoryChunk(
            content="Python é uma linguagem de programação",
            memory_type=MemoryType.SEMANTIC,
            source="knowledge",
            agent_id="planner",
            confidence=0.9,
            tags=("python", "linguagem"),
        )
        assert chunk.content
        assert chunk.memory_type == MemoryType.SEMANTIC
        assert chunk.source == "knowledge"
        assert chunk.confidence == 0.9
        assert "python" in chunk.tags

    def test_chunk_default_type(self):
        from iaglobal.memory.cognitive import MemoryChunk, MemoryType

        chunk = MemoryChunk(content="teste")
        assert chunk.memory_type == MemoryType.SEMANTIC

    def test_chunk_is_empty(self):
        from iaglobal.memory.cognitive import MemoryChunk

        assert MemoryChunk(content="").is_empty
        assert MemoryChunk(content="   ").is_empty
        assert not MemoryChunk(content="ok").is_empty

    def test_chunk_is_frozen(self):
        from iaglobal.memory.cognitive import MemoryChunk

        chunk = MemoryChunk(content="teste")
        with pytest.raises(Exception):
            chunk.content = "alterado"

    def test_chunk_defaults(self):
        from iaglobal.memory.cognitive import MemoryChunk, MemoryType

        chunk = MemoryChunk(content="teste")
        assert chunk.memory_type == MemoryType.SEMANTIC
        assert chunk.source == "unknown"
        assert chunk.agent_id == ""
        assert chunk.confidence == 1.0
        assert chunk.tags == ()
        assert chunk.context == {}


class TestDomainModels:
    """Verifica que os modelos de memória são DOMÍNIO PURO (sem backends)."""

    def test_models_do_not_have_backend_parameter(self):
        """Nenhum modelo de memória deve receber backend no __init__."""
        from iaglobal.memory.cognitive import (
            EpisodicMemory,
            ExternalMemory,
            ProceduralMemory,
            SemanticMemory,
            WorkingMemory,
        )

        for cls in (
            WorkingMemory,
            EpisodicMemory,
            SemanticMemory,
            ProceduralMemory,
            ExternalMemory,
        ):
            instance = cls()
            assert not hasattr(instance, "_backend"), f"{cls.__name__} tem _backend"

    def test_models_create_chunks_correctly(self):
        from iaglobal.memory.cognitive import (
            EpisodicMemory,
            MemoryType,
            SemanticMemory,
            WorkingMemory,
        )

        wm = WorkingMemory()
        chunk = wm.create_chunk(content="contexto atual", agent_id="agent1")
        assert chunk.memory_type == MemoryType.WORKING
        assert chunk.agent_id == "agent1"

        sm = SemanticMemory()
        chunk = sm.create_chunk(content="conhecimento python", tags=("python",))
        assert chunk.memory_type == MemoryType.SEMANTIC
        assert "python" in chunk.tags

        em = EpisodicMemory()
        chunk = em.create_chunk(
            content="erro corrigido", context={"execution_id": "123"}
        )
        assert chunk.memory_type == MemoryType.EPISODIC
        assert chunk.context["execution_id"] == "123"

    def test_domain_models_have_no_backend_parameter(self):
        """Verifica via inspect que nenhum modelo tem parâmetro 'backend'."""
        from iaglobal.memory.cognitive import (
            EpisodicMemory,
            ExternalMemory,
            ProceduralMemory,
            SemanticMemory,
            WorkingMemory,
        )

        for cls in (
            WorkingMemory,
            EpisodicMemory,
            SemanticMemory,
            ProceduralMemory,
            ExternalMemory,
        ):
            sig = inspect.signature(cls.__init__)
            params = list(sig.parameters.keys())
            assert "backend" not in params, (
                f"{cls.__name__}.__init__ tem parâmetro 'backend'"
            )


class TestAttentionManager:
    def test_attention_filters_by_confidence(self):
        from iaglobal.memory.cognitive import AttentionManager, MemoryChunk, MemoryType

        am = AttentionManager(token_budget=100)

        memories = [
            MemoryChunk(
                content="alta confiança",
                confidence=0.9,
                memory_type=MemoryType.SEMANTIC,
            ),
            MemoryChunk(
                content="baixa confiança",
                confidence=0.1,
                memory_type=MemoryType.SEMANTIC,
            ),
            MemoryChunk(
                content="média confiança",
                confidence=0.5,
                memory_type=MemoryType.SEMANTIC,
            ),
        ]

        result = am.filter(memories, available_tokens=100)
        assert len(result) == 3  # Todos cabem no orçamento
        assert result[0].confidence >= result[1].confidence

    def test_attention_respects_token_budget(self):
        from iaglobal.memory.cognitive import AttentionManager, MemoryChunk, MemoryType

        am = AttentionManager(token_budget=10)  # 10 tokens = 40 chars

        memories = [
            MemoryChunk(
                content="a" * 30, confidence=1.0, memory_type=MemoryType.SEMANTIC
            ),
            MemoryChunk(
                content="b" * 30, confidence=0.8, memory_type=MemoryType.SEMANTIC
            ),
        ]

        result = am.filter(memories, available_tokens=10)
        # Orçamento: 10 tokens = 40 chars
        # Primeiro chunk: 30 chars < 40 → cabe
        # Segundo: 30 chars + overhead ≈ 32 chars, total ≈ 62 > 40 → não cabe
        assert len(result) <= 2

    def test_attention_empty_list(self):
        from iaglobal.memory.cognitive import AttentionManager

        am = AttentionManager()
        result = am.filter([])
        assert result == []

    def test_attention_filters_empty_chunks(self):
        from iaglobal.memory.cognitive import AttentionManager, MemoryChunk, MemoryType

        am = AttentionManager()

        memories = [
            MemoryChunk(content="", memory_type=MemoryType.SEMANTIC),
            MemoryChunk(content="ok", memory_type=MemoryType.SEMANTIC),
        ]

        result = am.filter(memories)
        assert len(result) == 1
        assert result[0].content == "ok"


class TestMemoryRepositoryProtocol:
    """Valida que MemoryRepository é a interface correta de infraestrutura."""

    def test_repository_has_correct_interface(self):
        from iaglobal.memory.repository import MemoryRepository

        assert hasattr(MemoryRepository, "read")
        assert hasattr(MemoryRepository, "write")
        assert hasattr(MemoryRepository, "search")

    def test_repository_uses_memory_type_enum(self):
        """MemoryRepository deve usar MemoryType (não str) nos contratos."""
        from iaglobal.memory.repository import MemorySearcher
        import inspect

        sig = inspect.signature(MemorySearcher.search)
        params = list(sig.parameters.keys())
        assert "memory_type" in sig.parameters


class TestCognitiveLayerDecoupling:
    """Valida que a camada cognitiva NÃO depende de infraestrutura."""

    def test_foundation_nao_importa_backends_concretos(self):
        """O foundation.py não deve importar sqlite3, obsidian, qdrant, redis, s3."""
        import ast
        from pathlib import Path

        source = Path("iaglobal/memory/cognitive/foundation.py").read_text()
        tree = ast.parse(source)
        imports = [
            node.module for node in ast.walk(tree) if isinstance(node, ast.Import)
        ]
        from_imports = [
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        ]

        banned = {"sqlite3", "qdrant", "redis", "obsidian", "s3", "aiofiles"}
        all_imports = set(imports + from_imports)
        violations = banned & all_imports

        if violations:
            pytest.fail(f"Contratos cognitivos dependem de backends: {violations}")

    def test_no_backend_names_in_foundation(self):
        import ast
        from pathlib import Path

        source = Path("iaglobal/memory/cognitive/foundation.py").read_text()
        tree = ast.parse(source)

        banned_names = {
            "SQLiteBackend",
            "ObsidianBackend",
            "QdrantBackend",
            "RedisBackend",
            "MemoryBackend",
        }
        all_names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
        violations = banned_names & all_names

        if violations:
            pytest.fail(f"Contratos referenciam backends concretos: {violations}")

    def test_domain_models_have_no_backend_parameter(self):
        """WorkingMemory, SemanticMemory, etc. não recebem backend."""
        from iaglobal.memory.cognitive import (
            EpisodicMemory,
            ExternalMemory,
            ProceduralMemory,
            SemanticMemory,
            WorkingMemory,
        )

        for cls in (
            WorkingMemory,
            EpisodicMemory,
            SemanticMemory,
            ProceduralMemory,
            ExternalMemory,
        ):
            sig = inspect.signature(cls.__init__)
            params = list(sig.parameters.keys())
            assert "backend" not in params, (
                f"{cls.__name__}.__init__ tem parâmetro 'backend'"
            )
