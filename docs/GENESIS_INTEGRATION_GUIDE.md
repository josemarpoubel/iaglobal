# docs/GENESIS_INTEGRATION_GUIDE.md

# Guia de Integração: Genesis Global Protector

## Passo 1: Estrutura do Genesis Congelado
```
iaglobal/
├── genesis/
│   ├── data/
│   │   ├── webhidden_genesis_blueprint.cbor  # Hash soberano + manifesto
│   │   ├── webhidden_genesis_evolutive.cbor  # DNA bruto
│   │   └── integrity_tree.cbor               # Árvore de integridade (raiz)
│   ├── verifygenesis.py                     # Tribunal de DNA
│   └── __init__.py                          # Exports
```

## Passo 2: Integração do Entropy Sentinel

### 2.1 Importação no security/__init__.py
```python
from iaglobal.security.entropy_sentinel import EntropySentinel, entropy_sentinel
```

### 2.2 Uso em Agentes/Nós
```python
# Cada agente deve validar sua linhagem no __init__
from iaglobal.security.entropy_sentinel import entropy_sentinel

def __init__(self):
    self.node_id = entropy_sentinel.get_sober_agent_id(self.__class__.__name__)
    if not self.node_id.startswith("expected_prefix"):
        raise SecurityError("Agent não derivado do genesis válido")
```

### 2.3 Hook no Pipeline
```python
# No nó entropy_sentinel (executa antes de immune_check)
result = entropy_sentinel.scan_critical_files()
if not result["healthy"]:
    # Bloquear execução
    quarantine.record_failure("system", "Genesis violation detected", impact=5)
```

## Passo 3: Proteção de Arquivos Críticos

### 3.1 Validação de Hashes
```python
# integrity_tree.cbor contém hashes de todos os arquivos .py
for root, files in integrity_tree.items():
    for file_path, expected_hash in files.items():
        actual = calculate_sha3_512(file_path)
        if actual != expected_hash:
            # Manipulação detectada!
            mhc_detector.quarantine_if_parasite(file_path, {
                "unauthorized_path": file_path,
                "unexpected_output": True
            })
```

### 3.2 Proteção de Topologia
```python
# No topology.py, adicionar:
EXPECTED_TOPOLOGY_HASH = hashlib.sha3_512(
    str(NODE_DEPENDENCIES).encode()
).hexdigest()[:32]

# Compare com genesis para detectar injeção de nós maliciosos
```

## Passo 4: ID Soberano para Agentes

### 4.1 Geração Automática
```python
# Em cada agente/node:
from iaglobal.security.pysecurity1024 import gerar_node_id_soberano

self.sober_id = gerar_node_id_soberano(
    f"{genesis_hash}:{agent_class}:{code_fingerprint}".encode()
)
```

### 4.2 Verificação de Linhagem
```python
# Lista branca de IDs válidos (derivados do genesis)
WHITELISTED_ID_PREFIXES = [
    "ge-",  # webhidden prefix
    "bi-",
    "de-",
]

def is_legitimate_agent(agent_id: str) -> bool:
    return any(agent_id.startswith(p) for p in WHITELISTED_ID_PREFIXES)
```

## Passo 5: Sessões de Boot Seguro

### 5.1 Verificação Inicial
```python
# Em main.py ou entry point:
from iaglobal.genesis.verifygenesis import VerifyGenesis

tribunal = VerifyGenesis()
if not tribunal.verify_frozen_authority():
    print("BOOT ABORTADO: Genesis violado")
    sys.exit(1)
```

### 5.2 Snapshot de Genesis
```python
# Salvar snapshot do genesis no Obsidian (Long Term Memory)
await subconscious.escrever_longo_prazo(
    "genesis_snapshot",
    f"# Checksum: {genesis_hash}",
    tipo="Blueprint",
    fitness=1.0
)
```

## Caminhos de Integração

### Arquivos já modificados:
- `security/entropy_sentinel.py` ✓
- `security/__init__.py` ✓
- `graphs/nodes/no_entropy_sentinel.py` ✓
- `genesis/verifygenesis.py` ✓

### Próximas integrações:
- `graphs/builder.py` → Adicionar verificação de genesis antes de build
- `core/orchestrator.py` → Validar IDs soberanos antes de dispatch
- `evolution/skill_executor.py` → Verificar linhagem antes de execução
- `pipeline/engine.py` → Hook de segurança pre-execução