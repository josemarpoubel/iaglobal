# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# ⚖️ O TRIBUNAL DE GÊNESIS — Validação de DNA Sistêmico (V1.5 "Guardião Rigoroso")

import logging
import hashlib
import cbor2
import sys
import os
from pathlib import Path

from iaglobal._paths import PACKAGE_DIR
from iaglobal.utils.logger import get_logger

logger = logging.getLogger("iaglobal")

# Cache de validação — o blueprint/evolutive não muda durante o runtime.
_frozen_authority_validated: bool = False
_frozen_authority_hash: str | None = None
_validation_error: str | None = None


class VerifyGenesis:
    """
    ⚖️ O TRIBUNAL (GUARDIÃO RIGOROSO):
    Define a soberania do nó no nascimento. Se a fórmula SHA3_512 divergir,
    o nó é considerado um "corpo estranho" e o boot é abortado.
    """
    def __init__(self):
        # Conversão para Path para garantir métodos .exists() consistentes
        self.blueprint_path = PACKAGE_DIR / "genesis" / "data" / "webhidden_genesis_blueprint.cbor"
        self.evolutive_path = PACKAGE_DIR / "genesis" / "data" / "webhidden_genesis_evolutive.cbor"
        self.validated_hash = None

    def _calculate_sha3_512(self, file_path):
        """
        ⚡ STREAMING HASH (64KB Chunks): 
        Cálculo de alta precisão e baixo consumo de RAM (Raspberry Pi Friendly).
        """
        sha3 = hashlib.sha3_512()
        try:
            if not file_path.exists():
                return None
                
            with open(file_path, 'rb') as f:
                # Processamento em blocos para eficiência de I/O
                while chunk := f.read(65536):
                    sha3.update(chunk)
            
            return sha3.hexdigest()
        except Exception as e:
            logger.error(f"❌ [TRIBUNAL] Falha no streaming de hash: {e}")
            return None

    def verify_frozen_authority(self) -> bool:
        """
        ⚖️ SENTENÇA DE SOBERANIA:
        Valida se a alma (Evolutive) e o certificado (Blueprint) são um só.
        Resultado é cacheado em módulo: o blueprint/evolutive não muda em runtime.
        """
        global _frozen_authority_validated, _frozen_authority_hash, _validation_error

        if _frozen_authority_validated:
            return True

        if _validation_error is not None:
            return False

        logger.info("⚖️ Invocando o Tribunal: Validando nascimento do nó...")

        if not self.blueprint_path.exists() or not self.evolutive_path.exists():
            _validation_error = "DNA ausente — blueprint ou evolutive não localizado."
            logger.critical("🚨 [DNA AUSENTE] Gênese não localizada. O nó não pode nascer.")
            return False

        try:
            # 1. Extração do Hash Soberano (Blueprint)
            with open(self.blueprint_path, 'rb') as f:
                blueprint_data = cbor2.load(f)

            # O Tribunal exige a presença da chave 'hash'
            expected_hash = blueprint_data.get("hash")
            if not expected_hash:
                _validation_error = "Blueprint inválido — chave 'hash' ausente."
                logger.error("🚨 [BLUEPRINT INVÁLIDO] Chave 'hash' ausente no certificado.")
                return False

            # 2. Cálculo da Matéria Real (Evolutive)
            actual_hash = self._calculate_sha3_512(self.evolutive_path)

            # 3. O Veredito de Realidade
            if actual_hash != expected_hash:
                _validation_error = (
                    f"VIOLAÇÃO DE REALIDADE — esperado {expected_hash[:32]}..., "
                    f"obtido {actual_hash[:32]}..."
                )
                logger.critical(
                    f"❌ [VIOLAÇÃO DE REALIDADE] O nó não pertence a este universo!\n"
                    f"   Esperado: {expected_hash[:32]}...\n"
                    f"   Obtido:   {actual_hash[:32]}..."
                )
                return False

            # 4. Validação de Estrutura do Manifesto (Mínima)
            # Se houver um manifesto, ele deve ser íntegro.
            manifesto = blueprint_data.get("manifesto", {})
            if manifesto and not isinstance(manifesto, dict):
                _validation_error = "Blueprint inválido — manifesto corrompido."
                logger.error("🚨 [BLUEPRINT INVÁLIDO] Estrutura de manifesto corrompida.")
                return False

            self.validated_hash = actual_hash
            _frozen_authority_hash = actual_hash
            _frozen_authority_validated = True
            logger.info("✅ [SOBERANIA CONFIRMADA] DNA validado. Nó autorizado a ingressar na malha.")
            return True

        except Exception as e:
            _validation_error = f"Falha crítica na análise de DNA: {e}"
            logger.error(f"💥 [COLAPSO] Falha crítica na análise de DNA: {e}")
            return False

    def get_frozen_hash(self) -> str:
        """Retorna a prova de integridade validada pelo Tribunal."""
        return self.validated_hash

    def check_and_ignite(self):
        """
        O GRANDE INTERRUPTOR:
        Executa a sentença. Se houver divergência, o nó se desliga para
        proteger o Multiverso de injeção de dados falsos.
        """
        if not self.verify_frozen_authority():
            logger.critical("\n🛑 [TRIBUNAL] ACESSO NEGADO. Integridade do Genesis violada.")
            logger.critical("🛑 O Multiverso rejeitou a assinatura deste nó.\n")
            sys.exit(1)
        return True