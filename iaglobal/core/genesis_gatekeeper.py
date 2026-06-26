"""
Genesis Gatekeeper - Guardião da Linhagem Genética Digital

Garante que TODOS os agentes e skills possuam um DNA válido (SHA3-512)
registrado no Genesis antes de serem instanciados ou executados.

Impede a deriva genética e garante rastreabilidade eterna.
"""

import hashlib
import json
import os
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class GenesisGatekeeper:
    """
    Porteiro central que valida a linhagem genética de todos os componentes.
    Nenhum agente ou skill existe sem passar por aqui.
    """
    
    def __init__(self, genesis_path: str = "iaglobal/obsidian/01_Genesis"):
        self.genesis_path = Path(genesis_path)
        self.dna_registry_file = self.genesis_path / "dna_registry.json"
        self.lineage_log = self.genesis_path / "lineage_log.jsonl"
        
        # Garante que o diretório Genesis exista
        self.genesis_path.mkdir(parents=True, exist_ok=True)
        
        # Carrega ou inicializa o registro
        self.dna_registry = self._load_registry()
        
        logger.info(f"Genesis Gatekeeper initialized at {self.genesis_path}")
        logger.info(f"Registered DNA sequences: {len(self.dna_registry)}")

    def _load_registry(self) -> Dict[str, Any]:
        """Carrega o registro de DNA existente."""
        if self.dna_registry_file.exists():
            try:
                with open(self.dna_registry_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Erro ao carregar registry: {e}. Criando novo.")
                return {"components": {}, "metadata": {"created": str(datetime.now())}}
        return {"components": {}, "metadata": {"created": str(datetime.now())}}

    def _save_registry(self):
        """Persiste o registro de DNA."""
        with open(self.dna_registry_file, 'w', encoding='utf-8') as f:
            json.dump(self.dna_registry, f, indent=2, ensure_ascii=False)

    def _log_lineage_event(self, event_type: str, component_id: str, details: Dict):
        """Registra evento imutável no log de linhagem."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "event": event_type,
            "component_id": component_id,
            "details": details
        }
        with open(self.lineage_log, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')

    def generate_dna(self, source_code: str, component_type: str, version: str = "1.0.0") -> str:
        """
        Gera um hash SHA3-512 único baseado no código fonte, tipo e versão.
        Este é o 'DNA' imutável do componente.
        """
        content = f"{component_type}:{version}:{source_code}"
        dna_hash = hashlib.sha3_512(content.encode('utf-8')).hexdigest()
        return dna_hash

    def register_component(self, component_id: str, source_code: str, 
                         component_type: str, version: str = "1.0.0", 
                         metadata: Optional[Dict] = None) -> str:
        """
        Registra um novo componente no Genesis e retorna seu DNA.
        Se já existir, valida se o código não mudou (mutação não autorizada).
        """
        new_dna = self.generate_dna(source_code, component_type, version)
        
        existing = self.dna_registry["components"].get(component_id)
        
        if existing:
            if existing["dna"] != new_dna:
                raise ValueError(
                    f"MUTATION DETECTED! Component {component_id} has changed without re-registration. "
                    f"Old DNA: {existing['dna'][:16]}... New DNA: {new_dna[:16]}..."
                )
            logger.debug(f"Component {component_id} verified. DNA matches.")
            return existing["dna"]
        
        # Novo registro
        record = {
            "dna": new_dna,
            "type": component_type,
            "version": version,
            "registered_at": datetime.now().isoformat(),
            "metadata": metadata or {}
        }
        
        self.dna_registry["components"][component_id] = record
        self._save_registry()
        
        self._log_lineage_event("REGISTRATION", component_id, {
            "dna": new_dna,
            "type": component_type,
            "version": version
        })
        
        logger.info(f"New component registered: {component_id} (DNA: {new_dna[:16]}...)")
        return new_dna

    def verify_dna(self, component_id: str, source_code: str, 
                   component_type: str, version: str = "1.0.0") -> bool:
        """
        Verifica se o componente atual corresponde ao DNA registrado.
        Lança exceção se houver divergência (corrupção ou mutação ilegal).
        """
        expected_dna = self.generate_dna(source_code, component_type, version)
        existing = self.dna_registry["components"].get(component_id)
        
        if not existing:
            raise ValueError(f"UNKNOWN LINEAGE: Component {component_id} is not registered in Genesis!")
        
        if existing["dna"] != expected_dna:
            self._log_lineage_event("VERIFICATION_FAILED", component_id, {
                "expected": existing["dna"][:16],
                "got": expected_dna[:16]
            })
            raise ValueError(
                f"DNA MISMATCH: Component {component_id} corrupted or mutated. "
                f"Expected: {existing['dna'][:16]}... Got: {expected_dna[:16]}..."
            )
            
        self._log_lineage_event("VERIFICATION_SUCCESS", component_id, {})
        return True

    def get_lineage(self, component_id: str) -> Optional[Dict]:
        """Retorna os dados de linhagem de um componente."""
        return self.dna_registry["components"].get(component_id)

# Instância global singleton
_gatekeeper_instance: Optional[GenesisGatekeeper] = None

def get_gatekeeper() -> GenesisGatekeeper:
    global _gatekeeper_instance
    if _gatekeeper_instance is None:
        _gatekeeper_instance = GenesisGatekeeper()
    return _gatekeeper_instance
