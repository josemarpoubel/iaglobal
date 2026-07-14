# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
LineageGate — Portal de Segurança Genômica para Nós do Grafo

Cada nó do pipeline (run_planner, run_coder, run_critic, etc) passa por
este gate ANTES de executar qualquer lógica.

Protocolo:
  token_esperado = SHA3_512(GENESIS_HASH_OFFICIAL + node_name)
  token_recebido = ctx.get("_lineage_token", "")

  Se token_recebido != token_esperado → bloqueio imediato (patógeno)

Isso garante que:
  1. Apenas nós autenticados (que possuem o genesis hash) executam
  2. Nós injetados externamente na rede são rejeitados antes de tocar
     qualquer código, banco de dados ou LLM
  3. O token é derivado, não armazenado — não há segredo em disco
"""

import json
import time
from pathlib import Path
from typing import Any, Dict, Optional, Set

from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.genesis.lineage_gate")

# Cache de tokens por node_name (memória only, efêmero)
_token_cache: Dict[str, str] = {}

# Flag: se True, aceita qualquer token (apenas para boot/testes)
_OPEN_MODE = False

# CRL (Certificate Revocation List) — persistida em disco
# Caminho padrão: obsidian/revocation_list.json
# Formato: {"revoked": {"node_name": expira_em_timestamp}, ...}
# expira_em_timestamp = 0 significa permanente
_REVOCATION_FILE: Optional[Path] = None
_REVOKED_CACHE: Dict[str, float] = {}  # node_name -> expiration_timestamp
_REVOCATION_MTIME: float = 0.0


def set_revocation_file(path: Optional[str | Path]) -> None:
    """Configura o caminho da lista de revogação."""
    global _REVOCATION_FILE
    _REVOCATION_FILE = Path(path) if path else None


def _load_revocation_list() -> Dict[str, float]:
    """Carrega (com cache) a lista de revogação do disco, expurgando entradas vencidas."""
    global _REVOKED_CACHE, _REVOCATION_MTIME
    if _REVOCATION_FILE is None:
        return _REVOKED_CACHE
    try:
        if _REVOCATION_FILE.exists():
            mtime = _REVOCATION_FILE.stat().st_mtime
            if mtime != _REVOCATION_MTIME:
                _REVOCATION_MTIME = mtime
                data = json.loads(_REVOCATION_FILE.read_text(encoding="utf-8"))
                revoked_raw = data.get("revoked", {}) if isinstance(data, dict) else {}

                # Suporta formato legado (lista de strings)
                if isinstance(revoked_raw, list):
                    revoked_raw = {str(e): 0 for e in revoked_raw if e}

                now = time.time()
                active: Dict[str, float] = {}
                expired: list[str] = []
                for name, exp in revoked_raw.items():
                    exp_f = float(exp)
                    if exp_f == 0 or exp_f > now:
                        active[str(name)] = exp_f
                    else:
                        expired.append(str(name))

                # Expurga entradas vencidas do disco
                if expired:
                    history = data.get("revocation_history", [])
                    for name in expired:
                        history.append({
                            "node": name,
                            "reason": "expiracao_automatica",
                            "timestamp": now,
                            "action": "unrevoke",
                        })
                    data["revoked"] = {k: v for k, v in active.items()}
                    data["revocation_history"] = history
                    data["last_updated"] = now
                    _REVOCATION_FILE.write_text(
                        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
                    )

                _REVOKED_CACHE = active
        return _REVOKED_CACHE
    except Exception as e:
        logger.warning("[LINEAGE_GATE] Falha ao carregar CRL: %s", e)
        return _REVOKED_CACHE


def revoke_node(
    node_name: str, reason: str = "", duration_hours: Optional[int] = None
) -> bool:
    """
    Revoga um nó da lista de certificados válidos.

    Args:
        node_name: Nome do nó a revogar (ex: "coder", "planner", "critic")
        reason: Motivo da revogação (auditoria)
        duration_hours: Duração em horas (None = permanente)

    Returns:
        True se revogação aplicada com sucesso
    """
    if _REVOCATION_FILE is None:
        logger.warning(
            "[LINEAGE_GATE] CRL não configurada — defina set_revocation_file() primeiro"
        )
        return False

    try:
        # Carrega estado atual
        if _REVOCATION_FILE.exists():
            data = json.loads(_REVOCATION_FILE.read_text(encoding="utf-8"))
        else:
            data = {"revoked": {}, "revocation_history": []}

        if not isinstance(data, dict):
            data = {"revoked": {}, "revocation_history": []}

        # Converte formato legado se necessário
        revoked_raw = data.get("revoked", {})
        if isinstance(revoked_raw, list):
            revoked_raw = {str(e): 0 for e in revoked_raw if e}

        # Calcula timestamp de expiração
        if duration_hours is not None and duration_hours > 0:
            expires_at = time.time() + (duration_hours * 3600)
        else:
            expires_at = 0  # permanente

        revoked_raw[node_name] = expires_at

        # Atualiza cache em memória
        _REVOKED_CACHE = {k: float(v) for k, v in revoked_raw.items()}

        # Registra no histórico (auditoria)
        history = data.get("revocation_history", [])
        history.append(
            {
                "node": node_name,
                "reason": reason,
                "timestamp": time.time(),
                "duration_hours": duration_hours,
                "expires_at": expires_at,
                "action": "revoke",
            }
        )
        data["revoked"] = {k: float(v) for k, v in revoked_raw.items()}
        data["revocation_history"] = history
        data["last_updated"] = time.time()

        # Persiste
        _REVOCATION_FILE.parent.mkdir(parents=True, exist_ok=True)
        _REVOCATION_FILE.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        duration_str = "permanentemente" if expires_at == 0 else f"por {duration_hours}h"
        logger.warning(
            "[LINEAGE_GATE] 🔒 Nó revogado %s: %s | %s", duration_str, node_name, reason
        )
        return True

    except Exception as e:
        logger.error("[LINEAGE_GATE] Falha ao revogar %s: %s", node_name, e)
        return False


def unrevoke_node(node_name: str, reason: str = "") -> bool:
    """Remove um nó da lista de revogação (readmissão após reabilitação)."""
    if _REVOCATION_FILE is None:
        return False

    try:
        if not _REVOCATION_FILE.exists():
            return False

        data = json.loads(_REVOCATION_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return False

        revoked_raw = data.get("revoked", {})
        if isinstance(revoked_raw, list):
            revoked_raw = {str(e): 0 for e in revoked_raw if e}

        revoked_raw.pop(node_name, None)
        _REVOKED_CACHE = {k: float(v) for k, v in revoked_raw.items()}

        history = data.get("revocation_history", [])
        history.append(
            {
                "node": node_name,
                "reason": reason,
                "timestamp": time.time(),
                "action": "unrevoke",
            }
        )
        data["revoked"] = {k: float(v) for k, v in revoked_raw.items()}
        data["revocation_history"] = history
        data["last_updated"] = time.time()

        _REVOCATION_FILE.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        logger.info(
            "[LINEAGE_GATE] 🔓 Nó readmitido: %s | motivo: %s", node_name, reason
        )
        return True

    except Exception as e:
        logger.error("[LINEAGE_GATE] Falha ao readmitir %s: %s", node_name, e)
        return False


def get_revoked_nodes() -> Set[str]:
    """Retorna conjunto de nós atualmente revogados (expurga vencidos automaticamente)."""
    return set(_load_revocation_list().keys())


def set_open_mode(enabled: bool = True) -> None:
    """Altera modo do gate. APENAS para testes locais."""
    global _OPEN_MODE
    _OPEN_MODE = enabled
    if enabled:
        logger.warning("[LINEAGE_GATE] ⚠️  MODO ABERTO — segurança desativada!")


def get_expected_token(node_name: str) -> str:
    """Deriva token esperado para um nó (cacheado em RAM)."""
    if node_name not in _token_cache:
        _token_cache[node_name] = derive_node_lineage(node_name)
    return _token_cache[node_name]


def verify_lineage_token(
    node_name: str,
    received_token: Optional[str] = None,
    ctx: Optional[Dict[str, Any]] = None,
) -> bool:
    """
    Verifica se o token de lineage recebido corresponde ao esperado.

    Args:
        node_name: Nome do nó sendo acessado (ex: "run_planner")
        received_token: Token explícito (opcional)
        ctx: Contexto do pipeline — extrai _lineage_token se presente

    Returns:
        True se token válido ou modo aberto; False se bloqueado
    """
    if _OPEN_MODE:
        logger.debug(
            "[LINEAGE_GATE] Open mode — %s autorizado sem verificação", node_name
        )
        return True

    # Verifica lista de revogação (CRL)
    revoked = _load_revocation_list()
    if node_name in revoked:
        logger.critical(
            "[LINEAGE_GATE] 🚨 BLOQUEIO CRL | %s | certificado revogado — acesso negado permanentemente",
            node_name,
        )
        return False

    expected = get_expected_token(node_name)

    # Extrair token do contexto se não fornecido explicitamente
    token = received_token
    if token is None and ctx is not None:
        token = ctx.get("_lineage_token")

    if not token:
        logger.critical(
            "[LINEAGE_GATE] 🚨 BLOQUEIO | %s | motivo=token_ausente | "
            "agente_sem_credencial tentou acessar nó sem assinatura genesis",
            node_name,
        )
        return False

    if token != expected:
        logger.critical(
            "[LINEAGE_GATE] 🚨 BLOQUEIO | %s | motivo=token_invalido | "
            "esperado=%s... recebido=%s...",
            node_name,
            expected[:16],
            token[:16] if token else "None",
        )
        return False

    logger.debug("[LINEAGE_GATE] ✅ %s autenticado", node_name)
    return True


class LineageGateError(Exception):
    """Levantada quando um nó é bloqueado por falha de verificação de lineage."""

    def __init__(self, node_name: str, reason: str):
        self.node_name = node_name
        self.reason = reason
        super().__init__(f"[LINEAGE_GATE] Acesso negado a '{node_name}': {reason}")


def gate_node(node_name: str, ctx: Dict[str, Any]) -> None:
    """
    Verifica e bloqueia se o nó não tiver lineage válido.

    Chamada no início de cada run_* antes de qualquer lógica.

    Raises:
        LineageGateError: Se o token for inválido, ausente ou cert revogado
    """
    if not verify_lineage_token(node_name, ctx=ctx):
        raise LineageGateError(
            node_name=node_name,
            reason="token de lineage inválido/ausente ou certificado revogado — acesso negado pelo Tribunal Genesis",
        )
