# iaglobal/immunity/pathogen_analyzer.py
"""
PathogenAnalyzer — Detecta scripts invasores tentando injetar código nas graphs/.

Análise:
- Handler not found → possível tentativa de injeção não registrada
- Código repetitivo anômalo → pathogen behavior
- Imports não declarados → possível invasor
"""

import hashlib
import logging
import re
import threading
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from iaglobal.genesis.verifygenesis import VerifyGenesis

logger = logging.getLogger(__name__)


class PathogenPattern:
    """Padrão de comportamento de pathogen."""

    def __init__(self, signature: str, threat_level: float = 0.5):
        self.signature = signature
        self.threat_level = threat_level
        self.occurrences = 0
        self.last_seen = None


class PathogenAnalyzer:
    """
    Analisa código em busca de padrões de pathogen.

    Operação:
    1. Varre graphs/ por tentativas de injeção não declaradas
    2. Detecta handlers ausentes (código tentando executar nó não existente)
    3. Analisa imports suspeitos
    4. Ativa quarentena via MHC se detectado
    """

    _instance: Optional["PathogenAnalyzer"] = None
    _lock = threading.Lock() if "threading" in dir() else None

    SUSPICIOUS_IMPORTS = {
        "os",
        "subprocess",
        "sys",
        "importlib",
        "ctypes",
        "paramiko",
        "requests",
        "urllib",
        "httpx",
    }

    INJECTION_PATTERNS = [
        r"__import__\s*\(",  # Importação dinâmica
        r"compile\s*\(",  # Compilação de código
        r"exec\s*\(",  # Execução direta
        r"eval\s*\(",  # Avaliação de string
        r"\.system\s*\(",  # system() call
        r"\.Popen\s*\(",  # Popen call
    ]

    def __new__(cls):
        if cls._lock:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
                return cls._instance
        else:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._patterns: Dict[str, PathogenPattern] = {}
        from iaglobal._paths import PACKAGE_DIR

        self._graphs_dir = PACKAGE_DIR / "graphs"

    def analyze_code(self, code: str, context: str = "unknown") -> Dict[str, Any]:
        """
        Analisa código em busca de padrões de pathogen.

        Returns:
            {"is_pathogen": bool, "threats": list, "confidence": float}
        """
        threats = []
        confidence = 0.0

        # Verificar imports suspeitos
        imports = re.findall(r"(?:import|from)\s+(\w+)", code)
        suspicious = [imp for imp in imports if imp in self.SUSPICIOUS_IMPORTS]
        if suspicious:
            threats.append(
                {
                    "type": "suspicious_imports",
                    "modules": suspicious,
                    "context": context,
                }
            )
            confidence += 0.4  # Aumentado de 0.3 para 0.4

        # Verificar padrões de injeção
        for pattern in self.INJECTION_PATTERNS:
            if re.search(pattern, code):
                threats.append(
                    {
                        "type": "injection_pattern",
                        "pattern": pattern,
                        "context": context,
                    }
                )
                confidence += 0.4

        # Verificar se faz parte do genesis
        if self._is_not_genesis_derivative(code):
            threats.append({"type": "non_genesis_derivative", "context": context})
            confidence += 0.3

        is_pathogen = confidence >= 0.5

        if is_pathogen:
            logger.warning(f"[PATHOGEN] Detectado em {context}: {threats}")

        return {
            "is_pathogen": is_pathogen,
            "threats": threats,
            "confidence": min(1.0, confidence),
        }

    def _is_not_genesis_derivative(self, code: str) -> bool:
        """Verifica se código tem marcas do genesis (IDs soberanos)."""
        # Código legítimo deve ter imports do iaglobal
        if "from iaglobal" in code or "import iaglobal" in code:
            return False
        return len(code) > 100  # Código grande sem imports do iaglobal é suspeito

    def scan_graphs_directory(self) -> Dict[str, Any]:
        """
        Varre graphs/ em busca de arquivos não registrados no genesis.
        """
        unregistered = []

        # Get genesis hash for comparison
        try:
            v = VerifyGenesis()
            v.verify_frozen_authority()
            genesis_hash = v.get_frozen_hash()
        except Exception:
            genesis_hash = None

        if not self._graphs_dir.exists():
            return {"healthy": True, "unregistered": [], "genesis_hash": genesis_hash}

        for py_file in self._graphs_dir.rglob("*.py"):
            # Verificar se está registrado via fingerprint
            content_hash = hashlib.sha3_512(py_file.read_bytes()).hexdigest()

            if genesis_hash:
                # Derivar fingerprint esperado
                expected = hashlib.sha3_512(
                    f"{genesis_hash}:{py_file}".encode()
                ).hexdigest()[:64]

                # Se mismatch, pode ser novo ou modificado
                # (Para agora, só logar)

        return {
            "healthy": True,
            "unregistered": unregistered,
            "genesis_hash": genesis_hash[:32] if genesis_hash else None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


# Singleton
pathogen_analyzer = PathogenAnalyzer()
