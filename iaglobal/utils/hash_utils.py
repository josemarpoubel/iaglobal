"""Hashing utilities for data integrity, verification, and lineage ID generation."""

import hashlib
import time
from typing import Tuple, Optional

def hash_string(data: str, algorithm: str = 'sha256') -> str:
    """Hash a string using the specified algorithm."""
    return hashlib.new(algorithm, data.encode()).hexdigest()

def verify_hash(data: str, hash_value: str, algorithm: str = 'sha256') -> bool:
    """Verify if data matches the given hash."""
    return hash_string(data, algorithm) == hash_value

def hash_file(filepath: str, algorithm: str = 'sha256') -> str:
    """Hash file contents."""
    hasher = hashlib.new(algorithm)
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b''):
            hasher.update(chunk)
    return hasher.hexdigest()


class LineageID:
    """
    SHA3-512 based lineage-aware ID generator.

    Cada entidade recebe:
      - lineage_id (128 chars): ID único SHA3-512 que codifica a ancestralidade.
      - lineage_marker (16 chars): Marcador hereditário — TODOS os descendentes
        de uma mesma raiz compartilham o mesmo marker, permitindo detecção
        rápida de parentesco.

    Para rastrear a linhagem completa, siga a cadeia de parent_lineage_id
    armazenada nos LineageEntry de cada entidade.
    """

    MARKER_LEN = 16

    @staticmethod
    def _root_marker(entity_type: str, root_name: str) -> str:
        """Gera o marcador hereditário da raiz."""
        return hashlib.sha3_256(
            f"lineage_marker::{entity_type}::{root_name}".encode()
        ).hexdigest()[:LineageID.MARKER_LEN]

    @staticmethod
    def compute(
        entity_type: str,
        name: str,
        parent_lineage_id: str = "",
        generation: int = 0,
        metadata: str = "",
        root_entity_type: str = "",
        root_name: str = "",
    ) -> tuple[str, str]:
        """
        Gera um par (lineage_id, lineage_marker) SHA3-512.

        Args:
            entity_type: Tipo da entidade (node, skill, execution, task)
            name: Nome único da entidade
            parent_lineage_id: ID de linhagem do progenitor (vazio se raiz)
            generation: Número da geração (0 = seed/genesis)
            metadata: String opcional (estratégia, versão, etc.)
            root_entity_type: Tipo da raiz (para calcular o marker hereditário)
            root_name: Nome da raiz (para calcular o marker hereditário)

        Returns:
            (lineage_id: str, lineage_marker: str)
        """
        raw = f"{entity_type}::{name}::{parent_lineage_id}::{generation}::{metadata}"
        lineage_id = hashlib.sha3_512(raw.encode()).hexdigest()

        # O marcador é herdado da raiz — todos os descendentes compartilham
        if root_entity_type and root_name:
            marker = LineageID._root_marker(root_entity_type, root_name)
        elif parent_lineage_id:
            marker = hashlib.sha3_256(
                f"inherit_marker::{parent_lineage_id}".encode()
            ).hexdigest()[:LineageID.MARKER_LEN]
        else:
            marker = LineageID._root_marker(entity_type, name)

        return lineage_id, marker

    @staticmethod
    def same_lineage(marker_a: str, marker_b: str) -> bool:
        """
        Verifica se dois marcadores pertencem à mesma linhagem.
        """
        return bool(marker_a and marker_b and marker_a == marker_b)

    @staticmethod
    def detect_collision(
        existing_ids: set,
        new_id: str,
        entity_name: str,
    ) -> Optional[str]:
        """
        Detecta colisão exata de ID.
        Retorna o ID colidido ou None se não houver colisão.
        Colisão de lineage_marker NÃO é erro — é esperado (mesma família).
        """
        if new_id in existing_ids:
            return new_id
        return None

    @staticmethod
    def compute_node_lineage(
        node_type: str,
        name: str,
        seed_id: str = "",
        mutation_id: str = "",
        version: str = "v1",
        generation: int = 0,
        parent_lineage_id: str = "",
    ) -> str:
        """
        Gera o SHA3-512 de linhagem para um Node.
        """
        raw = (
            f"node::{node_type}::{name}::{seed_id}::"
            f"{mutation_id}::{version}::{parent_lineage_id}::{generation}"
        )
        return hashlib.sha3_512(raw.encode()).hexdigest()

    @staticmethod
    def compute_skill_checksum(name: str, version: str, payload: str) -> str:
        """Gera checksum SHA3-512 para versionamento de skills."""
        raw = f"skill::{name}::{version}::{payload}"
        return hashlib.sha3_512(raw.encode()).hexdigest()
