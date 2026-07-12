# iaglobal/obsidian/epigenetic_registry.py
"""
EpigeneticRegistry — Registro de comportamento adaptativo de agentes via Obsidian Vault.

Tradução das Leis de Holliwell:
- Lei 4 (Colheita): O que você planta no registro epigenético, colhe em adaptação comportamental.
- Lei 6 (Amor): Reconheça e recompense padrões de sucesso; eles se multiplicarão.
- Lei 9 (Esforço): O esforço de registrar falhas gera aprendizado proporcional.

Funcionalidades:
- Registro de falhas/sucessos como marcas epigenéticas
- Recuperação de pesos adaptativos para ajuste de comportamento
- Integração com BanditPolicy para rewards baseados em IVM
- Ciclo completo: Falha → Peso → Adaptação → Reward → Epigenética
"""

import asyncio
import hashlib
import logging
import time
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field

logger = logging.getLogger("iaglobal")


@dataclass
class EpigeneticMarker:
    """Marca epigenética com metadados completos."""
    agent_id: str
    task_hash: str
    error_type: str
    timestamp: float
    context: Dict[str, Any]
    ivm_score: Optional[float] = None
    reward_value: Optional[float] = None
    adaptation_count: int = 0


class EpigeneticRegistry:
    """Registra e recupera configurações epigenéticas via Obsidian Vault."""

    def __init__(self, base_path: Path | None = None):
        from iaglobal._paths import PACKAGE_DIR
        self.base_path = base_path or (PACKAGE_DIR / "obsidian" / "epigenetic")
        self.base_path.mkdir(parents=True, exist_ok=True)
        self._memory_cache: Dict[str, EpigeneticMarker] = {}
        
    def _epigenetic_id(self, agent_id: str, task_hash: str, error_type: str, event_index: int = None) -> str:
        """Gera ID único para marca epigenética.
        
        Se event_index for fornecido, cria ID único para cada evento.
        Caso contrário, usa ID determinístico baseado em agent/task/error.
        """
        if event_index is not None:
            # ID único por evento (para múltiplos rewards/sucessos)
            return hashlib.sha3_512(
                f"{agent_id}:{task_hash}:{error_type}:{event_index}:{time.time()}".encode()
            ).hexdigest()[:16]
        else:
            # ID determinístico para lookup de pesos adaptativos
            return hashlib.sha3_512(
                f"{agent_id}:{task_hash}:{error_type}".encode()
            ).hexdigest()[:16]

    async def record_failure(
        self, agent_id: str, task_hash: str, error_type: str, context: Dict[str, Any],
        ivm_score: Optional[float] = None
    ) -> str:
        """Registra uma falha como 'marca epigenética' no Obsidian Vault."""
        # Usa timestamp para criar ID único para cada evento de falha
        event_index = int(time.time() * 1000) % 1000000
        epigenetic_id = self._epigenetic_id(agent_id, task_hash, error_type, event_index=event_index)
        
        metadata = {
            "agent_id": agent_id,
            "task_hash": task_hash,
            "error_type": error_type,
            "timestamp": time.time(),
            "context": context,
            "ivm_score": ivm_score,
        }
        file_path = self.base_path / f"{epigenetic_id}.cbor"

        # Atualiza cache em memória
        marker = EpigeneticMarker(
            agent_id=agent_id,
            task_hash=task_hash,
            error_type=error_type,
            timestamp=metadata["timestamp"],
            context=context,
            ivm_score=ivm_score,
            adaptation_count=0
        )
        self._memory_cache[epigenetic_id] = marker

        def _write():
            import cbor2
            with open(file_path, "wb") as f:
                cbor2.dump(metadata, f)

        await asyncio.to_thread(_write)
        logger.info("🧬 [EPIGENETIC] Falha registrada: %s | %s | IVM=%.2f", epigenetic_id, error_type, ivm_score or 0.0)
        return epigenetic_id

    async def record_success(
        self, agent_id: str, task_hash: str, 
        ivm_score: Optional[float] = None,
        reward_value: Optional[float] = None
    ) -> str:
        """Registra uma tentativa bem-sucedida como 'epigenética positiva'."""
        metadata = {
            "agent_id": agent_id,
            "task_hash": task_hash,
            "error_type": "success",
            "timestamp": time.time(),
            "context": {"status": "success"},
            "ivm_score": ivm_score,
            "reward_value": reward_value,
        }
        epigenetic_id = self._epigenetic_id(agent_id, task_hash, "success")
        file_path = self.base_path / f"{epigenetic_id}.cbor"

        # Atualiza cache em memória
        marker = EpigeneticMarker(
            agent_id=agent_id,
            task_hash=task_hash,
            error_type="success",
            timestamp=metadata["timestamp"],
            context={"status": "success"},
            ivm_score=ivm_score,
            reward_value=reward_value,
            adaptation_count=1
        )
        self._memory_cache[epigenetic_id] = marker

        def _write():
            import cbor2
            with open(file_path, "wb") as f:
                cbor2.dump(metadata, f)

        await asyncio.to_thread(_write)
        logger.info("✅ [EPIGENETIC] Sucesso registrado: %s | IVM=%.2f | Reward=%.2f", epigenetic_id, ivm_score or 0.0, reward_value or 0.0)
        return epigenetic_id

    async def get_adaptive_weights(
        self, agent_id: str, task_hash: str
    ) -> Dict[str, float]:
        """Recupera pesos epigenéticos para ajustar o comportamento do agente."""
        weights = {"retry_delay": 1.0, "model_priority": 1.0, "fallback_enabled": True}

        def _read_all() -> Dict[str, float]:
            import cbor2
            result = weights.copy()
            for file in self.base_path.glob("*.cbor"):
                try:
                    with open(file, "rb") as f:
                        data = cbor2.load(f)
                    if data.get("agent_id") == agent_id and data.get("task_hash") == task_hash:
                        error_type = data.get("error_type", "").lower()
                        # Normaliza tipos de erro: "TimeoutError" → "timeout", "InvalidOutput" → "invalid_output"
                        if "timeout" in error_type:
                            result["retry_delay"] *= 1.5
                            result["model_priority"] *= 0.8
                        elif "invalid" in error_type or error_type == "invalid_output":
                            result["fallback_enabled"] = False
                        elif "security" in error_type:
                            result["model_priority"] *= 0.5
                        elif error_type == "success":
                            result["retry_delay"] = min(result["retry_delay"] * 0.9, 1.0)
                except Exception as exc:
                    logger.warning("[EPIGENETIC] Falha ao ler %s: %s", file.name, exc)
            return result

        return await asyncio.to_thread(_read_all)

    async def apply_bandit_reward(
        self, agent_id: str, task_hash: str, 
        reward: float, ivm: float
    ) -> None:
        """Aplica reward do BanditPolicy e atualiza marca epigenética."""
        # Usa event_index para criar ID único para cada reward
        epigenetic_id = self._epigenetic_id(agent_id, task_hash, "success", event_index=int(time.time() * 1000) % 1000000)
        
        # Cria novo marcador de reward (sempre cria novo para acumular)
        marker = EpigeneticMarker(
            agent_id=agent_id,
            task_hash=task_hash,
            error_type="success",
            timestamp=time.time(),
            context={"bandit_reward": reward, "ivm": ivm},
            ivm_score=ivm,
            reward_value=reward,
            adaptation_count=1
        )
        self._memory_cache[epigenetic_id] = marker
        
        # Persiste em disco
        metadata = {
            "agent_id": agent_id,
            "task_hash": task_hash,
            "error_type": "success",
            "timestamp": marker.timestamp,
            "context": {"bandit_reward": reward, "ivm": ivm},
            "ivm_score": ivm,
            "reward_value": reward,
        }
        file_path = self.base_path / f"{epigenetic_id}.cbor"
        
        def _write():
            import cbor2
            with open(file_path, "wb") as f:
                cbor2.dump(metadata, f)
        
        await asyncio.to_thread(_write)
        logger.info(
            "🎯 [EPIGENETIC] Reward aplicado: %s | Reward=%.2f | IVM=%.2f | Adaptações=%d",
            epigenetic_id, reward, ivm, marker.adaptation_count
        )

    async def get_agent_epigenetic_profile(self, agent_id: str) -> Dict[str, Any]:
        """Retorna perfil epigenético completo de um agente."""
        profile = {
            "total_markers": 0,
            "successes": 0,
            "failures": 0,
            "avg_ivm": 0.0,
            "avg_reward": 0.0,
            "adaptation_events": [],
        }
        
        ivm_sum = 0.0
        reward_sum = 0.0
        ivm_count = 0
        reward_count = 0
        
        def _read_all():
            import cbor2
            markers = []
            for file in self.base_path.glob("*.cbor"):
                try:
                    with open(file, "rb") as f:
                        data = cbor2.load(f)
                    if data.get("agent_id") == agent_id:
                        markers.append(data)
                except Exception as exc:
                    logger.warning("[EPIGENETIC] Falha ao ler %s: %s", file.name, exc)
            return markers
        
        markers = await asyncio.to_thread(_read_all)
        
        profile["total_markers"] = len(markers)
        
        for marker in markers:
            error_type = marker.get("error_type")
            if error_type == "success":
                profile["successes"] += 1
                if marker.get("ivm_score") is not None:
                    ivm_sum += marker["ivm_score"]
                    ivm_count += 1
                if marker.get("reward_value") is not None:
                    reward_sum += marker["reward_value"]
                    reward_count += 1
            else:
                profile["failures"] += 1
            
            profile["adaptation_events"].append({
                "type": error_type,
                "timestamp": marker.get("timestamp"),
                "ivm": marker.get("ivm_score"),
            })
        
        if ivm_count > 0:
            profile["avg_ivm"] = ivm_sum / ivm_count
        if reward_count > 0:
            profile["avg_reward"] = reward_sum / reward_count
        
        return profile


# Singleton global
epigenetic_registry = EpigeneticRegistry()