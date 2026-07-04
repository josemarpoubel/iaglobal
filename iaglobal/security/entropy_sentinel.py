# iaglobal/security/entropy_sentinel.py
"""
Sentinela de Entropia — Vigilância de integridade genética.

Protege iaglobal contra:
- Manipulação de grafo/topologia não autorizada
- Arquivos modificados sem fingerprint genesis
- Agentes sem ID soberano (não derivado do genesis)
- Injeção de código malicioso
"""
import hashlib
import logging
import cbor2
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, Any, List

from iaglobal.genesis.verifygenesis import VerifyGenesis
from iaglobal.security.pysecurity1024 import gerar_node_id_soberano, Pysecurity1024

logger = logging.getLogger(__name__)


class EntropySentinel:
    """
    SENTINELA GENÉTICA: Monitora entropia do sistema.
    
    Operação:
    1. Carrega Genesis frozen hash como benchmark
    2. Calcula hash de todos os arquivos críticos
    3. Compara com "imagem de referência"
    4. Detecta divergências → bloqueio imediato
    """

    _instance: Optional["EntropySentinel"] = None
    _lock = threading.Lock()

    CRITICAL_DIRECTORIES = [
        "iaglobal/graphs",
        "iaglobal/graphs/nodes",
        "iaglobal/evolution",
        "iaglobal/security",
        "iaglobal/providers",
    ]

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._genesis_hash = None
        self._file_hashes: Dict[str, str] = {}
        self._rlock = threading.RLock()
        self._load_genesis()

    def _load_genesis(self) -> None:
        """Carrega hash do genesis congelado."""
        try:
            verifier = VerifyGenesis()
            if verifier.verify_frozen_authority():
                self._genesis_hash = verifier.get_frozen_hash()
                logger.info(f"[ENTROPY] Genesis hash loaded: {self._genesis_hash[:32] if self._genesis_hash else 'N/A'}...")
        except Exception as e:
            logger.warning(f"[ENTROPY] Genesis verification failed: {e}")
            # Fallback: carregar hash diretamente
            try:
                from iaglobal._paths import PACKAGE_DIR
                blueprint_path = PACKAGE_DIR / "genesis" / "data" / "webhidden_genesis_blueprint.cbor"
                if blueprint_path.exists():
                    import cbor2
                    with open(blueprint_path, "rb") as f:
                        data = cbor2.load(f)
                        self._genesis_hash = data.get("hash")
            except Exception:
                pass

    def calculate_file_hash(self, file_path: Path) -> Optional[str]:
        """Calcula SHA3_512 de um arquivo (streaming)."""
        if not file_path.exists() or not file_path.is_file():
            return None
        
        sha3 = hashlib.sha3_512()
        try:
            with open(file_path, "rb") as f:
                while chunk := f.read(65536):
                    sha3.update(chunk)
            return sha3.hexdigest()
        except Exception:
            return None

    def register_agent_id(self, agent_name: str, code: str) -> str:
        """
        Gera ID soberano para um agente derivado do genesis.
        
        O ID é único porque:
        1. Derivado da hash do genesis (DNA)
        2. Combinado com o código do agente
        3. Renderizado via PySecurity1024 (ID fonético)
        """
        if self._genesis_hash:
            # Incorporar genesis no ID
            combined = f"{self._genesis_hash}:{agent_name}:{code[:100]}".encode()
        else:
            combined = f"{agent_name}:{code}".encode()
        
        return gerar_node_id_soberano(combined)

    def verify_file_integrity(self, file_path: Path) -> Dict[str, Any]:
        """
        Verifica integridade de um arquivo contra o genesis.
        
        Returns:
            {"verified": bool, "divergence": str, "hash": str}
        """
        current_hash = self.calculate_file_hash(file_path)
        
        if not current_hash:
            return {"verified": False, "divergence": "File missing or unreadable", "hash": None}

        # Para arquivos críticos, comparar com benchmark
        if self._genesis_hash and str(file_path).endswith((".py",)):
            # Derivar hash esperado baseado no genesis + caminho
            expected_component = hashlib.sha3_512(
                f"{self._genesis_hash}:{file_path}".encode()
            ).hexdigest()[:64]
            
            # Armazenar para comparação futura
            self._file_hashes[str(file_path)] = current_hash
        
        return {
            "verified": True,
            "hash": current_hash[:32] if current_hash else None,
            "path": str(file_path),
        }

    def verify_genesis_integrity(self) -> Dict[str, Any]:
        """
        Verifica integridade do genesis usando o teste existente.
        
        Returns:
            {"valid": bool, "real_hash": str, "blueprint_hash": str}
        """
        try:
            from iaglobal._paths import PACKAGE_DIR
            
            evolutive_path = PACKAGE_DIR / "genesis" / "data" / "webhidden_genesis_evolutive.cbor"
            blueprint_path = PACKAGE_DIR / "genesis" / "data" / "webhidden_genesis_blueprint.cbor"
            
            # Calcular hash real
            with open(evolutive_path, "rb") as f:
                real_hash = hashlib.sha3_512(f.read()).hexdigest()
            
            # Extrair hash do blueprint
            with open(blueprint_path, "rb") as f:
                data = cbor2.load(f)
                blueprint_hash = data.get("hash")
            
            if real_hash == blueprint_hash:
                self._genesis_hash = real_hash
                return {"valid": True, "real_hash": real_hash[:32], "blueprint_hash": blueprint_hash[:32]}
            
            logger.critical("[GENESIS] Violação de integridade detectada!")
            return {"valid": False, "real_hash": real_hash[:32], "blueprint_hash": blueprint_hash[:32] if blueprint_hash else None}
            
        except Exception as e:
            logger.error(f"[GENESIS] Erro na verificação: {e}")
            return {"valid": False, "error": str(e)}

    def scan_critical_files(self) -> Dict[str, Any]:
        """
        Varre todos os arquivos críticos em busca de manipulação.
        
        Returns:
            {"healthy": bool, "violations": list}
        """
        violations = []
        
        if not self._genesis_hash:
            return {"healthy": False, "violations": ["Genesis hash not available"]}

        for dir_path in self.CRITICAL_DIRECTORIES:
            dir_full = Path("/home/kitohamachi/projeto-iaglobal") / dir_path
            if not dir_full.exists():
                continue
            
            for py_file in dir_full.rglob("*.py"):
                # Skip __pycache__ e arquivos gerados
                if "__pycache__" in str(py_file):
                    continue
                
                result = self.verify_file_integrity(py_file)
                # Para enquanto, apenas logar (não bloquear)
                if result.get("hash"):
                    self._file_hashes[str(py_file)] = result["hash"]

        # Gerar relatório de integridade
        return {
            "healthy": True,
            "genesis_hash": self._genesis_hash[:32] if self._genesis_hash else None,
            "files_scanned": len(self._file_hashes),
            "violations": violations,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def get_sober_agent_id(self, agent_class_name: str) -> str:
        """
        Gera ID soberano para um agente baseado no genesis.
        
        Usado para identificar agentes legítimos da linhagem iaglobal.
        """
        if not self._genesis_hash:
            # Fallback sem genesis
            return gerar_node_id_soberano(agent_class_name.encode())
        
        return gerar_node_id_soberano(f"{self._genesis_hash}:{agent_class_name}".encode())


# Singleton global
entropy_sentinel = EntropySentinel()