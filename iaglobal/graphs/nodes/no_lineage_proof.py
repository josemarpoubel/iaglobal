# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/graphs/nodes/no_lineage_proof.py

"""
Lineage Proof Node — Prova de derivação (Proof-of-Lineage) via SHA3-512.

Cada nó soberano carrega apenas seu node_uid efêmero.
A prova de soberania é uma derivação criptográfica a partir do GENESIS_HASH_OFFICIAL,
nunca uma cópia do Genesis em si.

Princípio:
    H_lineage = SHA3-512(G0 + Node_UID)

Onde:
    G0 = GENESIS_HASH_OFFICIAL (mantido apenas em genesis/identity.py)
    Node_UID = identificador efêmero do nó (RAM-Only)

O Tribunal valida por re-derivação local — não por cópia de hash.

Fluxo:
    nascimento -> generate_node_lineage(uid) -> H_lineage (RAM-Only)
    tribunal  -> validate_batch(manifest) -> [SOBERANIA CONFIRMADA] por batch_id
    pipeline  -> register_pipeline_nodes() -> integração automática no fluxo
"""
import hashlib
import logging
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _g0_bytes() -> bytes:
    """
    Retorna G0 como bytes para derivação SHA3-512.
    
    Importação lazy de genesis/identity.py para evitar ciclos.
    G0 NUNCA sai do módulo genesis — nós não carregam o Genesis.
    """
    from iaglobal.genesis.identity import GENESIS_HASH_OFFICIAL
    return bytes.fromhex(GENESIS_HASH_OFFICIAL)


def generate_node_lineage(node_uid: str) -> str:
    """
    Gera Lineage_Hash via SHA3-512(G0 + node_uid).
    
    Cada nó recebe uma assinatura de derivação única e irrevogável.
    O hash é mantido apenas em memória (RAM-Only) — nunca gravado em disco.
    
    Args:
        node_uid: Identificador único efêmero do nó (ex: uuid4 ou timestamp+random).
    
    Returns:
        str: Hash SHA3-512 de 128 hex chars representando a prova de derivação.
    
    Raises:
        ValueError: Se node_uid for vazio ou não for uma string.
    """
    if not node_uid or not isinstance(node_uid, str):
        raise ValueError("node_uid deve ser uma string não-vazia")
    
    g0 = _g0_bytes()
    return hashlib.sha3_512(g0 + node_uid.encode()).hexdigest()


def validate_batch(
    batch_manifest: List[Dict[str, str]],
    batch_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Valida atomicamente uma lista de manifestos de nós.
    
    Cada entrada do batch_manifest deve conter:
        {
            "uid": "<node_uid>",
            "lineage_hash": "<hash_recebido_do_no>"
        }
    
    A verificação é feita por re-derivação local: recalcula SHA3-512(G0 + uid)
    e compara com o hash apresentado. Qualquer divergência invalida o batch inteiro.
    
    Args:
        batch_manifest: Lista de manifestos {uid, lineage_hash}.
        batch_id: Identificador opcional do batch para logging.
    
    Returns:
        Dict com:
            - valid (bool): True se todos os nós passaram na prova de derivação.
            - sovereign_count (int): Nós válidos.
            - rejected (list): Lista de UIDs rejeitados com motivo.
            - batch_id (str): ID do batch processado.
    """
    if not batch_manifest:
        return {
            "valid": True,
            "sovereign_count": 0,
            "rejected": [],
            "batch_id": batch_id,
        }
    
    g0 = _g0_bytes()
    rejected = []
    
    for idx, entry in enumerate(batch_manifest):
        uid = entry.get("uid", "")
        presented_hash = entry.get("lineage_hash", "")
        
        if not uid or not presented_hash:
            rejected.append({
                "uid": uid or f"<missing:{idx}>",
                "reason": "uid ou lineage_hash ausente",
            })
            continue
        
        expected_hash = hashlib.sha3_512(g0 + uid.encode()).hexdigest()
        
        if presented_hash != expected_hash:
            logger.warning(
                "[LINEAGE_PROOF] Soberania violada — uid=%s batch=%s",
                uid,
                batch_id,
            )
            rejected.append({
                "uid": uid,
                "reason": "lineage_hash não corresponde à derivação de G0",
            })
    
    valid = len(rejected) == 0
    sovereign_count = len(batch_manifest) - len(rejected)
    
    if valid:
        logger.info(
            "[LINEAGE_PROOF] [SOBERANIA CONFIRMADA] batch=%s nodes=%d",
            batch_id,
            sovereign_count,
        )
    else:
        logger.error(
            "[LINEAGE_PROOF] Batch rejeitado — batch=%s rejected=%d/%d",
            batch_id,
            len(rejected),
            len(batch_manifest),
        )
    
    return {
        "valid": valid,
        "sovereign_count": sovereign_count,
        "rejected": rejected,
        "batch_id": batch_id,
    }


async def _register_pipeline_nodes() -> Dict[str, Any]:
    """
    Integração no nascimento dos nós do pipeline.
    
    Descobre todos os nós registrados em Nodes.list_nodes(),
    gera node_uid + lineage_hash para cada um e registra no
    NodeLineageRegistry. Retorna o resultado da validação.
    
    Returns:
        Dict com resultado da integração e execution_metrics.
    """
    from iaglobal.graphs.nodes import Nodes
    from iaglobal.graphs.node_lineage_registry import NodeLineageRegistry
    
    registry = NodeLineageRegistry()
    nodes = Nodes()
    node_names = nodes.list_nodes()
    
    batch_manifest = []
    for name in node_names:
        node_uid = f"{name}-{name.__hash__()}" if hasattr(name, '__hash__') else f"{name}-{id(name)}"
        lineage_hash = generate_node_lineage(node_uid)
        batch_manifest.append({
            "uid": node_uid,
            "lineage_hash": lineage_hash,
        })
    
    result = validate_batch(batch_manifest, batch_id="pipeline-integration")
    
    for entry in batch_manifest:
        await registry.register(
            entry["uid"].split("-")[0],
            entry["uid"],
            entry["lineage_hash"],
        )
    
    total = result.get("sovereign_count", 0) + len(result.get("rejected", []))
    return {
        **result,
        "total": total,
    }


async def run_lineage_proof(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Nó de pipeline que executa a prova de linhagem.
    
    Modos de operação:
    
    1. Integração no pipeline (padrão):
        Se nenhum parâmetro for fornecido, integra automaticamente
        todos os nós registrados em Nodes.list_nodes().
    
    2. Single (nascimento de nó):
        Espera receber:
            - node_uid (str): UID do nó a validar.
            - batch_id (str, opcional): ID do batch para rastreabilidade.
        Retorna Lineage_Hash gerado para esse node_uid.
    
    3. Batch (tribunal):
        Espera receber:
            - batch_manifest (list): Lista de manifestos {uid, lineage_hash}.
            - batch_id (str, opcional): ID do batch para logging.
        Retorna resultado da validação atômica do batch.
    
    Returns:
        Dict com output da validação e execution_metrics para JointOptimizationLoop.
    """
    start_time = time.time()
    
    batch_manifest = ctx.get("batch_manifest")
    single_uid = ctx.get("node_uid")
    batch_id = ctx.get("batch_id")
    
    # Modo padrão: integração no pipeline
    if batch_manifest is None and single_uid is None:
        try:
            result = await _register_pipeline_nodes()
            latency_ms = (time.time() - start_time) * 1000.0
            
            logger.info(
                "[LINEAGE_PROOF] Integração no pipeline concluída — "
                "sovereign=%d/%d",
                result.get("sovereign_count", 0),
                result.get("total", 0),
            )
            
            return {
                "output": result,
                "lineage_proof": {
                    "valid": result.get("valid", False),
                    "sovereign_count": result.get("sovereign_count", 0),
                    "rejected": result.get("rejected", []),
                    "batch_id": result.get("batch_id"),
                },
                "execution_metrics": {
                    "model": "local_sha3_512",
                    "success": result.get("valid", False),
                    "latency": latency_ms,
                    "cost": 0.0,
                },
            }
        except Exception as exc:
            latency_ms = (time.time() - start_time) * 1000.0
            logger.exception("[LINEAGE_PROOF] Falha na integração do pipeline: %s", exc)
            return {
                "output": {"error": str(exc)},
                "lineage_proof": {"valid": False, "error": str(exc)},
                "execution_metrics": {
                    "model": "local_sha3_512",
                    "success": False,
                    "latency": latency_ms,
                    "cost": 0.0,
                },
            }
    
    # Modo single: gera prova de derivação para um nó (nascimento)
    if single_uid is not None and not batch_manifest:
        if not single_uid or not isinstance(single_uid, str):
            latency_ms = (time.time() - start_time) * 1000.0
            logger.error(
                "[LINEAGE_PROOF] node_uid inválido — uid=%r",
                single_uid,
            )
            return {
                "output": {"error": "node_uid deve ser uma string não-vazia"},
                "lineage_proof": {"valid": False, "error": "node_uid inválido"},
                "execution_metrics": {
                    "model": "local_sha3_512",
                    "success": False,
                    "latency": latency_ms,
                    "cost": 0.0,
                },
            }
        
        try:
            lineage_hash = generate_node_lineage(single_uid)
            latency_ms = (time.time() - start_time) * 1000.0
            
            logger.info(
                "[LINEAGE_PROOF] Prova de derivação gerada — uid=%s batch=%s",
                single_uid,
                batch_id,
            )
            
            return {
                "output": {
                    "uid": single_uid,
                    "lineage_hash": lineage_hash,
                    "genesis_root": "<G0 withheld — RAM-Only derivation>",
                },
                "lineage_proof": {
                    "uid": single_uid,
                    "lineage_hash": lineage_hash,
                    "valid": True,
                },
                "execution_metrics": {
                    "model": "local_sha3_512",
                    "success": True,
                    "latency": latency_ms,
                    "cost": 0.0,
                },
            }
        except ValueError as exc:
            latency_ms = (time.time() - start_time) * 1000.0
            logger.error(
                "[LINEAGE_PROOF] Falha na geração de prova — uid=%s error=%s",
                single_uid,
                exc,
            )
            return {
                "output": {"error": str(exc)},
                "lineage_proof": {"valid": False, "error": str(exc)},
                "execution_metrics": {
                    "model": "local_sha3_512",
                    "success": False,
                    "latency": latency_ms,
                    "cost": 0.0,
                },
            }
    
    # Modo batch: valida lista de manifestos (tribunal)
    if batch_manifest is not None:
        result = validate_batch(batch_manifest, batch_id=batch_id)
        latency_ms = (time.time() - start_time) * 1000.0
        
        return {
            "output": result,
            "lineage_proof": {
                "valid": result["valid"],
                "sovereign_count": result["sovereign_count"],
                "rejected": result["rejected"],
                "batch_id": result["batch_id"],
            },
            "execution_metrics": {
                "model": "local_sha3_512",
                "success": result["valid"],
                "latency": latency_ms,
                "cost": 0.0,
            },
        }
    
    # Nenhum input válido
    latency_ms = (time.time() - start_time) * 1000.0
    logger.warning(
        "[LINEAGE_PROOF] Nenhum uid ou batch_manifest fornecido"
    )
    return {
        "output": {
            "error": "Forneça node_uid (single) ou batch_manifest (batch)",
        },
        "lineage_proof": {
            "valid": False,
            "error": "input ausente",
        },
        "execution_metrics": {
            "model": "local_sha3_512",
            "success": False,
            "latency": latency_ms,
            "cost": 0.0,
        },
    }
