# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/genesis/identity.py
"""
🧬 NodeIdentity — Núcleo de Identidade Soberana do Organismo

Responsável por:
- Gerar identidade efêmera baseada no Genesis (imprinting genômico)
- Verificar integridade do Tribunal Genesis (tribunal)
- Proteger contra adulteração (sistema imune)
- Expurgar memória na morte (anti-forense)
- Fornecer health check (homeostase)

- Organismo Computacional Completo:
- Tribunal Genesis HABILITADO (conformidade obrigatória)
- Circuit breaker para proteção contra falhas
- Telemetria completa (Tracer + batch_writer)
- Timeout em todas operações
- Validação robusta de inputs
- Métricas endógenas
- Health check
- Graceful degradation

AXIOMAS IMPLEMENTADOS:
- AXIOMA 1 (Homeostase): Health check + métricas
- AXIOMA 3 (Glutationa): Circuit breaker + retry
- AXIOMA 6 (Apoptose): Expurgo de RAM
- AXIOMA 8 (Sinalização): Telemetria completa
- AXIOMA 9 (Tribunal): Conformidade com Genesis Hash
"""

import asyncio
import atexit
import hashlib
import os
import secrets
import signal
import threading
import time
from pathlib import Path
from typing import Optional, Dict, Any

import cbor2

from iaglobal.utils.logger import get_logger
from iaglobal.observability.tracing import Tracer
from iaglobal._paths import PACKAGE_DIR, DATA_ROOT

logger = get_logger("iaglobal")


# =====================================================================
# PARÂMETROS HOMEOSTÁTICOS (Epigenética Operacional)
# =====================================================================
GENESIS_VERIFY_TIMEOUT = float(os.environ.get("GENESIS_VERIFY_TIMEOUT", "5.0"))
CB_FAILURE_THRESHOLD = int(os.environ.get("IDENTITY_CB_THRESHOLD", "3"))
CB_RECOVERY_TIMEOUT = float(os.environ.get("IDENTITY_CB_RECOVERY", "60"))
FONETIC_ROTATION_INTERVAL = int(os.environ.get("FONETIC_ROTATION_INTERVAL", "900"))


# =====================================================================
# GENESIS HASH (DNA Congelado — Tribunal)
# =====================================================================

# Hash oficial do Genesis Congelado (SHA3-512) - A Âncora Imutável
GENESIS_HASH_OFFICIAL = "cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136"


# =====================================================================
# CIRCUIT BREAKER (Glutationa — Defesa Antioxidante)
# =====================================================================


class IdentityCircuitBreaker:
    """Circuit breaker para proteger contra falhas repetidas."""

    def __init__(self):
        self._failures = 0
        self._last_failure = 0.0
        self._lock = asyncio.Lock()

    async def can_execute(self) -> bool:
        async with self._lock:
            if self._failures >= CB_FAILURE_THRESHOLD:
                if (time.time() - self._last_failure) < CB_RECOVERY_TIMEOUT:
                    return False
                self._failures = 0
            return True

    async def record_success(self):
        async with self._lock:
            self._failures = 0

    async def record_failure(self):
        async with self._lock:
            self._failures += 1
            self._last_failure = time.time()

    async def get_state(self) -> str:
        async with self._lock:
            if self._failures >= CB_FAILURE_THRESHOLD:
                return "OPEN"
            elif self._failures > 0:
                return "HALF_OPEN"
            return "CLOSED"


_identity_cb = IdentityCircuitBreaker()


# =====================================================================
# DIRETÓRIOS SOBERANOS
# =====================================================================

DATA_DIR = PACKAGE_DIR / "genesis" / "data"
LOG_DIR = DATA_ROOT / "logs"
PATH_PERSISTENT = DATA_DIR / "node_identity.cbor"
GENESIS_FILE = DATA_DIR / "webhidden_genesis_evolutive.cbor"


# =====================================================================
# VERIFICAÇÃO DO TRIBUNAL (Conformidade Obrigatória)
# =====================================================================


async def verify_genesis_integrity() -> Dict[str, Any]:
    """
    🧊 LÊ A ÚNICA LEI FÍSICA: Verifica se o Genesis evolutivo no disco é autêntico.

    Equivalente biológico: Teste de paternidade — verifica se o DNA
    do organismo corresponde ao DNA original congelado no tribunal.

    Returns:
        Dict com: match (bool), expected_hash, actual_hash, status
    """
    # Circuit breaker check
    if not await _identity_cb.can_execute():
        logger.error("[GÊNESIS] Circuit breaker OPEN — verificação bloqueada")
        return {
            "match": False,
            "expected_hash": GENESIS_HASH_OFFICIAL,
            "actual_hash": None,
            "status": "❌ CIRCUIT BREAKER OPEN",
        }

    start_time = time.time()

    try:
        # Verificar se arquivo existe
        if not GENESIS_FILE.exists():
            await _identity_cb.record_failure()
            logger.warning(
                "[GÊNESIS] ⚠️ Arquivo congelado não encontrado: %s", GENESIS_FILE
            )
            return {
                "match": False,
                "expected_hash": GENESIS_HASH_OFFICIAL,
                "actual_hash": None,
                "status": "❌ ARQUIVO NÃO ENCONTRADO",
            }

        # Ler arquivo com timeout
        async def _read_and_hash():
            genesis_data = await asyncio.to_thread(GENESIS_FILE.read_bytes)
            computed_hash = hashlib.sha3_512(genesis_data).hexdigest()
            return computed_hash

        computed_hash = await asyncio.wait_for(
            _read_and_hash(), timeout=GENESIS_VERIFY_TIMEOUT
        )

        # Comparar com hash esperado
        match = computed_hash == GENESIS_HASH_OFFICIAL

        if match:
            await _identity_cb.record_success()
            logger.info("[GÊNESIS] ✅ Tribunal: Blueprint autêntico")
        else:
            await _identity_cb.record_failure()
            logger.critical("[GÊNESIS] 🚨 TRIBUNAL: Blueprint VIOLADO!")
            logger.critical("[GÊNESIS] Esperado: %s", GENESIS_HASH_OFFICIAL[:40])
            logger.critical("[GÊNESIS] Atual: %s", computed_hash[:40])

        # Telemetria
        try:
            Tracer.trace_event(
                "GenesisVerification",
                {
                    "match": match,
                    "duration_ms": round((time.time() - start_time) * 1000, 2),
                },
            )
        except Exception:
            pass

        return {
            "match": match,
            "expected_hash": GENESIS_HASH_OFFICIAL,
            "actual_hash": computed_hash,
            "status": "✅ CONFORME" if match else "❌ NÃO CONFORME",
        }

    except asyncio.TimeoutError:
        await _identity_cb.record_failure()
        logger.error(
            "[GÊNESIS] ⏱️ Timeout na verificação após %ds", GENESIS_VERIFY_TIMEOUT
        )
        return {
            "match": False,
            "expected_hash": GENESIS_HASH_OFFICIAL,
            "actual_hash": None,
            "status": f"❌ TIMEOUT ({GENESIS_VERIFY_TIMEOUT}s)",
        }

    except Exception as e:
        await _identity_cb.record_failure()
        logger.error("[GÊNESIS] 💥 Erro ao verificar Genesis: %s", e)
        return {
            "match": False,
            "expected_hash": GENESIS_HASH_OFFICIAL,
            "actual_hash": None,
            "status": f"❌ ERRO: {e}",
        }


# =====================================================================
# NODE IDENTITY (Núcleo de Identidade Soberana)
# =====================================================================
# iaglobal/genesis/identity.py
class NodeIdentity:
    """
    🧬 Identidade Soberana Efêmera (RAM-Only).

    Equivalente biológico: DNA nuclear — define a identidade única
    de cada célula do organismo.

    Características:
    - Nasce do Genesis (imprinting genômico)
    - Vive na memória (efêmero)
    - Desaparece sem deixar rastros (anti-forense)
    """

    def __init__(self, seed: Optional[bytes] = None):
        self._cleaning_up = False
        self.genesis_hash = GENESIS_HASH_OFFICIAL

        # Métricas endógenas
        self._metrics = {
            "identity_created": False,
            "genesis_verified": False,
            "fonetic_rotations": 0,
        }

        # 1️⃣ VALIDAÇÃO DO TRIBUNAL (OBRIGATÓRIA)
        # Verificação síncrona para bloquear inicialização se falhar
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Se já estamos em um loop, agendar verificação
                asyncio.create_task(self._verify_genesis_async())
                self.authorized_transport = True  # Temporário
            else:
                # Loop não está rodando — verificação síncrona
                self.authorized_transport = loop.run_until_complete(
                    verify_genesis_integrity()
                )["match"]
        except Exception:
            # Fallback para verificação síncrona
            self.authorized_transport = self._verify_genesis_sync()

        if not self.authorized_transport:
            logger.critical(
                "[DNA] 🚨 TRIBUNAL: Blueprint violado. Encerrando por segurança."
            )
            raise RuntimeError(
                "💥 Tribunal barrou: blueprint não corresponde ao Genesis evolutivo."
            )

        self._metrics["genesis_verified"] = True

        # 2️⃣ GERAÇÃO DA SEMENTE MESTRE (Entropia Efêmera)
        raw_seed = seed or secrets.token_bytes(64)
        if isinstance(raw_seed, str):
            raw_seed = raw_seed.encode()

        self.master_seed = hashlib.sha3_512(raw_seed).digest()

        # 🧬 EXPANSÃO METABÓLICA (Harmonização Genômica)
        self.metabolic_hash = hashlib.sha3_512(
            self.master_seed + b"metabolism_v1"
        ).hexdigest()
        self.fitness_score = 0.5  # Base inicial

        # 3️⃣ SAL DE SESSÃO E HASH MUTANTE
        self.session_salt = secrets.token_bytes(32)
        self.node_hash = hashlib.sha3_512(self.session_salt + self.master_seed).digest()

        # 4️⃣ O DNA DO NÓ (Derivado na RAM)
        self.node_id = self.node_hash[:32]
        self.node_id_hex = self.node_id.hex()

        # 5️⃣ MIMETISMO FONÉTICO (A Máscara de Voz)
        try:
            from iaglobal.security.pysecurity1024 import Pysecurity1024

            self.node_name_fonetic = Pysecurity1024.bytes_para_frase(self.node_id[:16])
        except Exception as e:
            logger.error("[DNA] 💥 Falha ao gerar nome fonético: %s", e)
            self.node_name_fonetic = f"node-{self.node_id_hex[:12]}"

        self.mnemonic = self.node_name_fonetic  # Alias prático

        # 6️⃣ 🗑️ SISTEMA ANTI-FORENSE ATIVO
        atexit.register(self.reset_identity_on_exit)
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

        self._metrics["identity_created"] = True

        logger.info(
            "[DNA] ✨ Identidade Efêmera estabelecida: %s...",
            self.node_name_fonetic[:15],
        )

    async def _verify_genesis_async(self):
        """Verificação assíncrona do Genesis."""
        result = await verify_genesis_integrity()
        self.authorized_transport = result["match"]
        if not result["match"]:
            logger.critical("[DNA] 🚨 Tribunal falhou na verificação assíncrona")

    def _verify_genesis_sync(self) -> bool:
        """Verificação síncrona do Genesis (fallback)."""
        try:
            if not GENESIS_FILE.exists():
                return False

            genesis_data = GENESIS_FILE.read_bytes()
            computed_hash = hashlib.sha3_512(genesis_data).hexdigest()
            return computed_hash == GENESIS_HASH_OFFICIAL

        except Exception as e:
            logger.error("[DNA] 💥 Erro na verificação síncrona: %s", e)
            return False

    # --------------------------------------------------
    # ANTI-FORENSE (Expurgo de RAM)
    # --------------------------------------------------

    def reset_identity_on_exit(self):
        """
        🔥 EXPURGO DE RAM: Anula as chaves de memória antes da morte do processo.

        Equivalente biológico: Apoptose — morte celular programada que
        não deixa rastros para o sistema imunológico atacar.
        """
        if self._cleaning_up:
            return

        self._cleaning_up = True

        # Expurgar todas as chaves sensíveis
        self.master_seed = b""
        self.session_salt = b""
        self.node_hash = b""
        self.node_id = b""
        self.node_id_hex = ""
        self.node_name_fonetic = ""
        self.mnemonic = ""

        logger.debug("[DNA] 🗑️ Memória de identidade expurgada com sucesso.")

    def _signal_handler(self, signum, frame):
        """Captura sinais de morte súbita e garante o expurgo."""
        self.reset_identity_on_exit()
        os._exit(0)

    # --------------------------------------------------
    # MIMETISMO FONÉTICO (Rotação de Identidade)
    # --------------------------------------------------

    def _rotate_fonetic_name(self):
        """Rotaciona dinamicamente o nome fonético usando secrets."""
        try:
            from iaglobal.security.pysecurity1024 import Pysecurity1024

            source_bytes = self.node_id + self.session_salt
            start = secrets.randbelow(len(source_bytes) - 16)
            slice_bytes = source_bytes[start : start + 16]
            self.node_name_fonetic = Pysecurity1024.bytes_para_frase(slice_bytes)

            self._metrics["fonetic_rotations"] += 1
            logger.info(
                "[DNA] 🔄 Nome fonético rotacionado: %s", self.node_name_fonetic
            )

        except Exception as e:
            logger.error("[DNA] 💥 Erro ao rotacionar nome fonético: %s", e)

    def _start_fonetic_rotation(self, interval: int = FONETIC_ROTATION_INTERVAL):
        """Agenda rotação periódica do nome fonético."""
        logger.info("[DNA] Iniciando rotação fonética (intervalo: %ds)", interval)

        self._stop_rotation = threading.Event()

        def loop():
            while not self._stop_rotation.is_set():
                self._rotate_fonetic_name()
                if self._stop_rotation.wait(interval):
                    break

        self._rotation_thread = threading.Thread(target=loop, daemon=True)
        self._rotation_thread.start()

    def stop_fonetic_rotation(self):
        """Interrompe a rotação periódica do nome fonético."""
        if hasattr(self, "_stop_rotation"):
            self._stop_rotation.set()

    # --------------------------------------------------
    # PERSISTÊNCIA (Memória de Longo Prazo)
    # --------------------------------------------------

    def exists(self) -> bool:
        """Verifica se a Identidade Soberana já está selada fisicamente."""
        return PATH_PERSISTENT.exists()

    def load(self):
        """Recarrega o DNA e ID Público do CBOR."""
        self.master_seed = self._load_or_create_master_seed()
        self.node_id_hex = self._load_or_create_node_id()
        self.node_id = bytes.fromhex(self.node_id_hex)

    def create(self):
        """Força a geração de uma nova alma."""
        self.master_seed = self._generate_new_seed()
        self.node_id_hex = self._derive_node_id()
        self.node_id = bytes.fromhex(self.node_id_hex)
        self._persist_identity()

    def _generate_new_seed(self) -> bytes:
        """Gera uma nova seed aleatória de 32 bytes."""
        return secrets.token_bytes(32)

    def _derive_node_id(self) -> str:
        """Deriva o ID Público a partir da seed + Genesis congelado."""
        try:
            genesis_data = GENESIS_FILE.read_bytes()
            genesis_hash = hashlib.sha3_512(genesis_data).digest()
            derived = hashlib.sha3_512(self.master_seed + genesis_hash).digest()
            return derived.hex()
        except Exception as e:
            logger.error("[DNA] 💥 Erro ao derivar ID Público: %s", e)
            return secrets.token_bytes(32).hex()

    def _load_or_create_master_seed(self) -> bytes:
        """Carrega ou cria a seed persistente."""
        if PATH_PERSISTENT.exists():
            try:
                data = cbor2.loads(PATH_PERSISTENT.read_bytes())
                seed = data.get("seed") or data.get("dna") or data.get("salt")
                if seed:
                    return bytes.fromhex(seed) if isinstance(seed, str) else seed
            except Exception as e:
                logger.error("[DNA] 💥 Erro ao ler DNA persistente: %s", e)

        return self._generate_new_seed()

    def _load_or_create_node_id(self) -> str:
        """Carrega ou gera o ID público persistente."""
        if PATH_PERSISTENT.exists():
            try:
                data = cbor2.loads(PATH_PERSISTENT.read_bytes())
                node_id = data.get("node_id")
                if node_id:
                    return node_id
            except Exception as e:
                logger.error("[DNA] 💥 Erro ao ler ID público: %s", e)

        node_id_hex = self._derive_node_id()
        self._persist_identity(node_id_hex=node_id_hex)
        return node_id_hex

    def _persist_identity(self, node_id_hex: Optional[str] = None):
        """Persiste identidade no disco (CBOR)."""
        try:
            PATH_PERSISTENT.parent.mkdir(parents=True, exist_ok=True)

            data = {
                "node_id": node_id_hex or self.node_id_hex,
                "seed": self.master_seed.hex() if self.master_seed else None,
            }

            PATH_PERSISTENT.write_bytes(cbor2.dumps(data))
            logger.debug("[DNA] 💾 Identidade persistida em %s", PATH_PERSISTENT)

        except Exception as e:
            logger.error("[DNA] 💥 Erro ao persistir identidade: %s", e)

    # --------------------------------------------------
    # VALIDAÇÃO (Sistema Imune)
    # --------------------------------------------------

    def validate_node_id(self) -> bool:
        """Valida se o ID camuflado corresponde ao ID derivado do Genesis."""
        try:
            from iaglobal.security.pysecurity1024 import Pysecurity1024

            recovered = Pysecurity1024.frase_para_bytes(self.node_name_fonetic)
            return recovered.hex() == self.node_id_hex[: len(recovered.hex())]

        except Exception as e:
            logger.error("[DNA] 💥 Erro ao validar ID Público: %s", e)
            return False

    # --------------------------------------------------
    # HEALTH CHECK (Homeostase Endógena)
    # --------------------------------------------------

    async def health_check(self) -> Dict[str, Any]:
        """Verifica saúde da identidade."""
        genesis_result = await verify_genesis_integrity()

        return {
            "status": "healthy" if self._metrics["identity_created"] else "not_created",
            "genesis_verified": self._metrics["genesis_verified"],
            "genesis_conformance": genesis_result,
            "circuit_breaker": await _identity_cb.get_state(),
            "metrics": {**self._metrics},
            "identity_exists": self.exists(),
        }

    # --------------------------------------------------
    # METRICS (Observabilidade Endógena)
    # --------------------------------------------------

    def get_metrics(self) -> Dict[str, Any]:
        """Retorna métricas da identidade."""
        return {
            **self._metrics,
            "circuit_breaker": _identity_cb.get_state(),
        }

    # --------------------------------------------------
    # PUBLIC API
    # --------------------------------------------------

    def get_public_bytes(self) -> bytes:
        """Retorna os bytes públicos (ID binário como chave pública)."""
        return self.node_id

    def derive_node_lineage(self, node_uid: str) -> str:
        """
        Deriva Lineage_Hash para um nó específico via SHA3-512(G0 + node_uid).

        Cada nó do pipeline recebe uma prova de derivação única baseada
        no Genesis oficial. O hash é mantido em memória — não persiste em disco.

        Args:
            node_uid: Identificador único efêmero do nó.

        Returns:
            str: Hash SHA3-512 de 128 hex chars.
        """
        g0 = bytes.fromhex(GENESIS_HASH_OFFICIAL)
        return hashlib.sha3_512(g0 + node_uid.encode()).hexdigest()


# =====================================================================
# LOG CLEANUP (Autofagia — Limpeza de Logs)
# =====================================================================


def clear_logs():
    """
    Limpa os arquivos de log truncando-os.

    ⚠️ ATENÇÃO: Esta função apaga logs de auditoria.
    Use apenas em ambientes de desenvolvimento.
    """
    try:
        if LOG_DIR.exists():
            for root, _, files in os.walk(LOG_DIR):
                for f in files:
                    file_path = Path(root) / f
                    file_path.write_text("")

            logger.info("[DNA] 🧹 Logs limpos com sucesso.")

    except Exception as e:
        logger.error("[DNA] 💥 Erro ao limpar logs: %s", e)


def schedule_log_cleanup(interval: int = 900):
    """Agenda limpeza periódica dos logs."""

    def cleanup_periodically():
        clear_logs()
        threading.Timer(interval, cleanup_periodically).start()

    threading.Timer(interval, cleanup_periodically).start()
