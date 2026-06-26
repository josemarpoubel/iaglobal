# 🧬 GATEKEEPER DE GÊNESIS — O Guardião da Linhagem Universal
# 
# Este módulo é o "portão de nascimento" obrigatório para TODOS os agentes e skills.
# Sem a certificação de DNA SHA3-512, nenhum componente pode nascer ou evoluir.
# 
# Inspirado na biologia celular: assim como uma célula só se divide se seu DNA estiver íntegro,
# nenhum agente/skill pode ser instanciado sem passar pelo Gatekeeper.

import logging
import hashlib
import cbor2
from pathlib import Path
from typing import Optional, Dict, Any, Type
from datetime import datetime
import threading

from iaglobal._paths import PACKAGE_DIR
from iaglobal.genesis.verifygenesis import VerifyGenesis
from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal")


class GenesisCertificationError(Exception):
    """Exceção lançada quando um componente falha na certificação de gênese."""
    pass


class GenesisGatekeeper:
    """
    🛡️ O GUARDIÃO DA LINHAGEM UNIVERSAL
    
    Responsabilidades:
    1. Validar DNA SHA3-512 de cada agente/skill antes do nascimento
    2. Registrar linhagem no Integrity Tree (CBOR)
    3. Impedir nascimento de componentes "órfãos" (sem certificação)
    4. Manter histórico evolutivo de cada componente
    5. Bloquear componentes com violações de integridade
    
    Analogia Biológica:
    - Funciona como o "checkpoint G1/S" do ciclo celular
    - A célula (agente/skill) só entra em mitose se o DNA estiver íntegro
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """Singleton thread-safe para garantir um único guardião."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Inicializa o Gatekeeper apenas uma vez."""
        if hasattr(self, '_initialized') and self._initialized:
            return
            
        self._initialized = True
        self.integrity_tree_path = PACKAGE_DIR / "genesis" / "data" / "integrity_tree.cbor"
        self.blueprint_path = PACKAGE_DIR / "genesis" / "data" / "webhidden_genesis_blueprint.cbor"
        self.evolutive_path = PACKAGE_DIR / "genesis" / "data" / "webhidden_genesis_evolutive.cbor"
        
        # Cache de componentes certificados (em memória)
        self._certified_components: Dict[str, Dict[str, Any]] = {}
        
        # Carrega ou inicializa a árvore de integridade
        self._load_integrity_tree()
        
        # Verifica a gênese uma única vez na inicialização
        self._genesis_verified = False
        
        logger.info("🛡️ [GATEKEEPER] Guardião da Linhagem inicializado")
    
    def _load_integrity_tree(self):
        """Carrega a árvore de integridade do CBOR ou cria uma nova."""
        try:
            if self.integrity_tree_path.exists():
                with open(self.integrity_tree_path, 'rb') as f:
                    self.integrity_tree = cbor2.load(f)
                logger.debug(f"📊 [GATEKEEPER] Árvore de integridade carregada: {len(self.integrity_tree.get('components', []))} componentes")
            else:
                self.integrity_tree = {
                    "genesis_hash": None,
                    "components": [],
                    "created_at": datetime.utcnow().isoformat(),
                    "last_updated": datetime.utcnow().isoformat()
                }
                self._save_integrity_tree()
                logger.info("🌳 [GATEKEEPER] Nova árvore de integridade criada")
        except Exception as e:
            logger.error(f"💥 [GATEKEEPER] Erro ao carregar árvore de integridade: {e}")
            self.integrity_tree = {
                "genesis_hash": None,
                "components": [],
                "created_at": datetime.utcnow().isoformat(),
                "last_updated": datetime.utcnow().isoformat()
            }
    
    def _save_integrity_tree(self):
        """Persiste a árvore de integridade no disco."""
        try:
            self.integrity_tree["last_updated"] = datetime.utcnow().isoformat()
            with open(self.integrity_tree_path, 'wb') as f:
                cbor2.dump(self.integrity_tree, f)
            logger.debug("💾 [GATEKEEPER] Árvore de integridade persistida")
        except Exception as e:
            logger.error(f"💥 [GATEKEEPER] Erro ao salvar árvore de integridade: {e}")
    
    def verify_genesis_once(self) -> bool:
        """
        ⚖️ VERIFICAÇÃO PRIMORDIAL: Valida a gênese do sistema uma única vez.
        
        Returns:
            bool: True se a gênese for válida, False caso contrário.
        """
        if self._genesis_verified:
            return True
            
        verifier = VerifyGenesis()
        if verifier.check_and_ignite():
            self._genesis_verified = True
            self.integrity_tree["genesis_hash"] = verifier.get_frozen_hash()
            self._save_integrity_tree()
            logger.info("✅ [GATEKEEPER] Gênese primordial validada")
            return True
        else:
            logger.critical("🚨 [GATEKEEPER] GÊNESE VIOLADA! Sistema não pode prosseguir.")
            return False
    
    def calculate_component_dna(self, source_code: str, component_name: str, 
                                 component_type: str, version: str = "1.0.0") -> str:
        """
        🧬 CALCULA O DNA SHA3-512 DE UM COMPONENTE
        
        Fórmula do DNA:
        SHA3-512(source_code + component_name + component_type + version + genesis_hash)
        
        Args:
            source_code: Código-fonte do componente (como string)
            component_name: Nome do agente/skill (ex: "coder_agent")
            component_type: Tipo ("agent", "skill", "engine", etc.)
            version: Versão semântica do componente
            
        Returns:
            str: Hash hexadecimal SHA3-512 (DNA do componente)
        """
        if not self._genesis_verified:
            if not self.verify_genesis_once():
                raise GenesisCertificationError("Gênese não verificada. Abortando cálculo de DNA.")
        
        genesis_hash = self.integrity_tree.get("genesis_hash", "")
        
        # Concatenação canônica para o hash
        canonical_string = (
            f"{source_code}|{component_name}|{component_type}|{version}|{genesis_hash}"
        )
        
        dna_hash = hashlib.sha3_512(canonical_string.encode('utf-8')).hexdigest()
        
        logger.debug(f"🧬 [GATEKEEPER] DNA calculado para {component_name}: {dna_hash[:16]}...")
        return dna_hash
    
    def certify_component(self, component_class: Type, 
                          source_code: Optional[str] = None,
                          version: str = "1.0.0",
                          metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        🎓 CERTIFICAÇÃO DE NASCIMENTO: Registra e valida um novo componente.
        
        Args:
            component_class: Classe do componente (agente, skill, etc.)
            source_code: Código-fonte (se None, tenta ler do arquivo da classe)
            version: Versão semântica
            metadata: Metadados adicionais (autor, descrição, tags, etc.)
            
        Returns:
            Dict: Certificado de linhagem com DNA, timestamp e status
            
        Raises:
            GenesisCertificationError: Se a certificação falhar
        """
        component_name = component_class.__name__
        component_type = self._infer_component_type(component_class)
        
        # Tenta obter o source code se não fornecido
        if source_code is None:
            try:
                import inspect
                source_code = inspect.getsource(component_class)
            except Exception as e:
                logger.warning(f"⚠️ [GATEKEEPER] Não foi possível obter source de {component_name}: {e}")
                source_code = str(component_class)
        
        # Calcula o DNA
        dna = self.calculate_component_dna(
            source_code=source_code,
            component_name=component_name,
            component_type=component_type,
            version=version
        )
        
        # Verifica se já existe na árvore de integridade
        existing = self._find_component_in_tree(component_name, component_type)
        
        certificate = {
            "component_name": component_name,
            "component_type": component_type,
            "dna": dna,
            "version": version,
            "certified_at": datetime.utcnow().isoformat(),
            "genesis_hash": self.integrity_tree.get("genesis_hash"),
            "metadata": metadata or {},
            "status": "active",
            "lineage_verified": True
        }
        
        if existing:
            # Atualiza componente existente
            if existing.get("dna") != dna:
                logger.warning(f"⚠️ [GATEKEEPER] DNA divergente para {component_name}. Registrando nova versão.")
                certificate["previous_dna"] = existing.get("dna")
                certificate["evolution_count"] = existing.get("evolution_count", 0) + 1
            else:
                logger.debug(f"✅ [GATEKEEPER] {component_name} já certificado com DNA íntegro")
        else:
            # Novo componente
            logger.info(f"🎓 [GATEKEEPER] Novo componente certificado: {component_name} ({component_type})")
            certificate["evolution_count"] = 0
        
        # Registra no cache em memória
        cache_key = f"{component_type}:{component_name}"
        self._certified_components[cache_key] = certificate
        
        # Adiciona/atualiza na árvore de integridade
        self._upsert_component_in_tree(certificate)
        
        return certificate
    
    def validate_component(self, component_class: Type, 
                           expected_dna: Optional[str] = None) -> bool:
        """
        ✅ VALIDAÇÃO DE INTEGRIDADE: Verifica se o DNA atual corresponde ao esperado.
        
        Args:
            component_class: Classe do componente a validar
            expected_dna: DNA esperado (se None, busca na árvore de integridade)
            
        Returns:
            bool: True se o DNA for válido, False caso contrário
        """
        component_name = component_class.__name__
        component_type = self._infer_component_type(component_class)
        
        try:
            import inspect
            source_code = inspect.getsource(component_class)
        except Exception:
            source_code = str(component_class)
        
        current_dna = self.calculate_component_dna(
            source_code=source_code,
            component_name=component_name,
            component_type=component_type,
            version="current"
        )
        
        if expected_dna is None:
            # Busca na árvore de integridade
            existing = self._find_component_in_tree(component_name, component_type)
            if existing:
                expected_dna = existing.get("dna")
            else:
                logger.warning(f"⚠️ [GATEKEEPER] Componente {component_name} não encontrado na árvore")
                return False
        
        is_valid = current_dna == expected_dna
        
        if is_valid:
            logger.debug(f"✅ [GATEKEEPER] Validação positiva: {component_name}")
        else:
            logger.error(f"🚨 [GATEKEEPER] VIOLAÇÃO DE DNA detectada em {component_name}!")
            logger.error(f"   Esperado: {expected_dna[:32]}...")
            logger.error(f"   Obtido:   {current_dna[:32]}...")
        
        return is_valid
    
    def get_lineage_history(self, component_name: str, 
                            component_type: Optional[str] = None) -> list:
        """
        📜 HISTÓRICO DE LINHAGEM: Retorna todo o histórico evolutivo de um componente.
        
        Args:
            component_name: Nome do componente
            component_type: Tipo do componente (opcional)
            
        Returns:
            list: Lista de certificados históricos (do mais antigo ao mais recente)
        """
        history = []
        for cert in self.integrity_tree.get("components", []):
            if cert["component_name"] == component_name:
                if component_type is None or cert["component_type"] == component_type:
                    history.append(cert)
        
        # Ordena por data de certificação
        history.sort(key=lambda x: x.get("certified_at", ""))
        return history
    
    def revoke_component(self, component_name: str, 
                         component_type: Optional[str] = None,
                         reason: str = "Unspecified") -> bool:
        """
        🔴 REVOGAÇÃO DE CERTIDÃO: Marca um componente como revogado (não deleta).
        
        Args:
            component_name: Nome do componente
            component_type: Tipo do componente
            reason: Motivo da revogação
            
        Returns:
            bool: True se revogado com sucesso
        """
        cache_key = f"{component_type or 'unknown'}:{component_name}"
        
        if cache_key in self._certified_components:
            self._certified_components[cache_key]["status"] = "revoked"
            self._certified_components[cache_key]["revoked_at"] = datetime.utcnow().isoformat()
            self._certified_components[cache_key]["revocation_reason"] = reason
            
            # Atualiza na árvore
            self._upsert_component_in_tree(self._certified_components[cache_key])
            
            logger.warning(f"🔴 [GATEKEEPER] Componente revogado: {component_name} - {reason}")
            return True
        
        logger.warning(f"⚠️ [GATEKEEPER] Componente não encontrado para revogação: {component_name}")
        return False
    
    def _infer_component_type(self, component_class: Type) -> str:
        """Inferência automática do tipo de componente baseado no nome da classe."""
        class_name = component_class.__name__.lower()
        
        if "agent" in class_name:
            return "agent"
        elif "skill" in class_name or "node" in class_name:
            return "skill"
        elif "engine" in class_name:
            return "engine"
        elif "orchestrator" in class_name:
            return "orchestrator"
        elif "detector" in class_name:
            return "detector"
        elif "guardian" in class_name:
            return "guardian"
        else:
            return "component"
    
    def _find_component_in_tree(self, component_name: str, 
                                 component_type: str) -> Optional[Dict[str, Any]]:
        """Busca um componente na árvore de integridade."""
        for cert in self.integrity_tree.get("components", []):
            if (cert["component_name"] == component_name and 
                cert["component_type"] == component_type):
                return cert
        return None
    
    def _upsert_component_in_tree(self, certificate: Dict[str, Any]):
        """Insere ou atualiza um certificado na árvore de integridade."""
        existing = self._find_component_in_tree(
            certificate["component_name"], 
            certificate["component_type"]
        )
        
        if existing:
            # Atualiza existente
            index = self.integrity_tree["components"].index(existing)
            self.integrity_tree["components"][index] = certificate
        else:
            # Novo registro
            self.integrity_tree["components"].append(certificate)
        
        self._save_integrity_tree()
    
    def get_certified_components_summary(self) -> Dict[str, Any]:
        """Retorna um resumo de todos os componentes certificados."""
        total = len(self.integrity_tree.get("components", []))
        by_type = {}
        by_status = {"active": 0, "revoked": 0}
        
        for cert in self.integrity_tree.get("components", []):
            ctype = cert.get("component_type", "unknown")
            status = cert.get("status", "unknown")
            
            by_type[ctype] = by_type.get(ctype, 0) + 1
            by_status[status] = by_status.get(status, 0) + 1
        
        return {
            "total_components": total,
            "by_type": by_type,
            "by_status": by_status,
            "genesis_hash": self.integrity_tree.get("genesis_hash", "")[:16] + "...",
            "last_updated": self.integrity_tree.get("last_updated")
        }


# Singleton global
gatekeeper = GenesisGatekeeper()


def certify_birth(component_class: Type, version: str = "1.0.0", 
                  metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    🎓 FUNÇÃO CONVENIENTE PARA CERTIFICAÇÃO DE NASCIMENTO
    
    Uso recomendado no __init__ de cada agente/skill:
    
    class CoderAgent:
        def __init__(self):
            self.certification = certify_birth(CoderAgent, version="2.1.0")
            # ... resto da inicialização
    """
    return gatekeeper.certify_component(component_class, version=version, metadata=metadata)


def validate_dna(component_class: Type, expected_dna: Optional[str] = None) -> bool:
    """
    ✅ FUNÇÃO CONVENIENTE PARA VALIDAÇÃO DE DNA
    
    Uso recomendado antes de executar ações críticas:
    
    if not validate_dna(CoderAgent):
        raise Exception("DNA violado! Agente comprometido.")
    """
    return gatekeeper.validate_component(component_class, expected_dna=expected_dna)
