# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136

# iaglobal/reflection/claim_detection.py
"""
Claim Detection — Fonte única para detecção de claims arquiteturais suspeitos.

Módulo centralizado para evitar drift entre cópias da mesma lógica em:
  - no_artifact_writer.py
  - consolidation.py (REMSleep)
  - Outros nodes que precisem validar claims

Patterns de risco:
  - Afirmações de ausência ("não possui", "não tem")
  - Caracterização arquitetural ("sistema é offline")
  - Claims sobre capabilities do iaglobal

Uso:
  from iaglobal.reflection.claim_detection import (
      detect_architectural_claims,
      verify_architectural_claims,
  )
  
  claims = detect_architectural_claims(text)
  verified, unverified = verify_architectural_claims(claims)
"""
import re
from pathlib import Path
from typing import Dict, List, Tuple
from datetime import datetime, UTC

from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.reflection.claim_detection")


# Patterns de risco — FONTE ÚNICA DE VERDADE
ARCHITECTURAL_CLAIM_PATTERNS = [
    # Afirmações de ausência (false negative capability)
    (r"não\s+(possui|tem|existe|mecanismo|sistema|implementa|suporta)", "false_negative_capability"),
    (r"ausência\s+de\s+\w+", "false_negative_capability"),
    (r"inexistente\s+\w+", "false_negative_capability"),
    
    # Caracterização arquitetural (architectural hallucination)
    (r"sistema\s+é\s+(auto-contido|offline|isolado|fechado|restrito)", "architectural_hallucination"),
    (r"iaglobal\s+não\s+(possui|tem|suporta|implementa|permite)", "architectural_hallucination"),
    (r"ecossistema\s+não\s+(possui|tem|suporta)", "architectural_hallucination"),
    
    # Claims sobre nodes/agents
    (r"não\s+existe\s+(node|agente|módulo|skill)", "false_negative_capability"),
    (r"não\s+há\s+(node|agente|módulo|skill|mecanismo)", "false_negative_capability"),
]


def detect_architectural_claims(text: str) -> List[Dict[str, str]]:
    """
    Detecta claims arquiteturais suspeitos em texto.
    
    Args:
        text: Texto para analisar
        
    Returns:
        Lista de claims detectados com:
          - type: Tipo de claim (false_negative_capability, architectural_hallucination)
          - text: Contexto do claim (frase completa)
          - severity: HIGH para architectural, MEDIUM para capability
    """
    claims = []
    text_lower = text.lower()
    
    for pattern, claim_type in ARCHITECTURAL_CLAIM_PATTERNS:
        matches = re.finditer(pattern, text_lower, re.IGNORECASE)
        for match in matches:
            # Pega contexto (frase completa)
            start = max(0, match.start() - 50)
            end = min(len(text), match.end() + 100)
            context = text[start:end].strip()
            
            # Remove quebras de linha múltiplas
            context = " ".join(context.split())
            
            claims.append({
                "type": claim_type,
                "text": context,
                "severity": "HIGH" if "architectural" in claim_type else "MEDIUM",
                "pattern_matched": pattern,
            })
    
    return claims


def verify_architectural_claims(
    claims: List[Dict[str, str]],
    nodes_dir: Path = None,
) -> Tuple[bool, List[str]]:
    """
    Verifica claims arquiteturais contra código-fonte real.
    
    Args:
        claims: Lista de claims detectados
        nodes_dir: Diretório dos nodes (default: iaglobal/graphs/nodes)
    
    Returns:
        (verified, unverified_claims)
          - verified: True se todos os claims foram verificados como verdadeiros
          - unverified_claims: Lista de claims falsos ou não-verificáveis
    """
    if nodes_dir is None:
        from iaglobal._paths import PACKAGE_DIR
        nodes_dir = PACKAGE_DIR / "graphs" / "nodes"
    
    # Coleta nodes existentes
    existing_nodes = set()
    existing_functions = set()
    
    if nodes_dir.exists():
        for f in nodes_dir.glob("no_*.py"):
            node_name = f.stem.replace("no_", "")
            existing_nodes.add(node_name)
            
            # Extrai funções run_* do arquivo
            try:
                content = f.read_text(encoding="utf-8")
                for match in re.finditer(r"async\s+def\s+(run_\w+)", content):
                    existing_functions.add(match.group(1))
            except Exception:
                pass
    
    verified = True
    unverified = []
    
    for claim in claims:
        claim_text = claim["text"].lower()
        is_false = False
        
        # Verifica claims de ausência contra nodes existentes
        # Ex: "não tem search" vs no_search.py existe
        for node in existing_nodes:
            if node in claim_text and ("não" in claim_text or "ausência" in claim_text):
                is_false = True
                break
        
        # Verifica claims de ausência contra funções existentes
        for func in existing_functions:
            if func.replace("run_", "") in claim_text and "não" in claim_text:
                is_false = True
                break
        
        # Verifica claims específicos conhecidos
        false_claims_known = [
            ("offline", "system_is_online"),
            ("auto-contido", "system_has_integrations"),
            ("isolado", "system_has_integrations"),
        ]
        
        for keyword, _ in false_claims_known:
            if keyword in claim_text and "não" in claim_text:
                is_false = True
                break
        
        if is_false:
            verified = False
            unverified.append(claim["text"])
    
    return verified, unverified


def create_quarantine_report(
    arquivo: str,
    conteudo: str,
    claims: List[Dict[str, str]],
    vault_path: Path,
) -> Path:
    """
    Cria relatório de quarentena para memória contaminada.
    
    Args:
        arquivo: Nome do arquivo original
        conteudo: Conteúdo bruto da memória
        claims: Claims detectados
        vault_path: Caminho do vault Obsidian
    
    Returns:
        Caminho do arquivo em quarentena
    """
    quarentena_dir = vault_path / "00_Quarentena"
    quarentena_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now(UTC).isoformat()
    
    # Escreve arquivo em quarentena com metadata
    quarentena_path = quarentena_dir / f"CONTAMINATED_{arquivo}"
    
    lines = [
        "---",
        f"arquivo_original: \"{arquivo}\"",
        f"data_quarentena: \"{timestamp}\"",
        f"claims_detectados: {len(claims)}",
        "status: AGUARDANDO_REVISAO_HUMANA",
        "---",
        "",
        "# 🚨 MEMÓRIA EM QUARENTENA",
        "",
        "**Este arquivo contém claims arquiteturais não-verificados e foi bloqueado.**",
        "",
        "## Claims Detectados",
        "",
    ]
    
    for i, claim in enumerate(claims, 1):
        lines.extend([
            f"### Claim {i}",
            f"- **Tipo**: {claim['type']}",
            f"- **Severidade**: {claim['severity']}",
            f"- **Texto**: {claim['text']}",
            "",
        ])
    
    lines.extend([
        "## Conteúdo Original",
        "",
        conteudo,
        "",
        "---",
        "*Este arquivo requer revisão humana antes de ser consolidado no longo prazo.*",
    ])
    
    quarentena_path.write_text("\n".join(lines), encoding="utf-8")
    
    logger.warning(
        "🚨 [QUARANTINE] Memória em quarentena | arquivo=%s | claims=%d | path=%s",
        arquivo, len(claims), quarentena_path,
    )
    
    return quarentena_path


REFUSAL_PATTERNS = [
    r"(desculpe|sorry|não posso|cannot|unable to)\s+(ajudar|assist|help|respond|answer)",
    r"I'?m?\s+(sorry|afraid|unable)\s+(,?\s*but\s+)?(I|cannot|can'?t)",
    r"(não\s+é\s+possível|not\s+possible)\s+(gerar|fornecer|produzir|generate|provide)",
    r"as\s+(an\s+)?AI\s+(assistant|language\s+model|model),\s+(I|cannot|can'?t)",
    r"(I|cannot|can'?t)\s+(complete|fulfill|satisfy)\s+(this\s+)?(request|task)",
]


def is_refusal_or_hallucination(text: str) -> bool:
    """Retorna True se o texto parece uma recusa de IA ou alucinação arquitetural conhecida.

    Combina dois detectores:
    - Recusas genéricas (padrões de language model refusal)
    - Claims arquiteturais falsos (false negatives sobre capabilities do iaglobal)
    """
    if not text:
        return False
    text_lower = text.lower().strip()
    for pattern in REFUSAL_PATTERNS:
        if re.search(pattern, text_lower, re.IGNORECASE):
            return True
    claims = detect_architectural_claims(text)
    if claims:
        return True
    return False


def should_elevate_model(task_type: str, context: str = "") -> bool:
    """
    Decide se tarefa exige elevação de modelo (NVIDIA/Groq) em vez de modelo local fraco.
    
    Critérios:
      - Auto-análise arquitetural
      - Claims sobre o próprio sistema
      - Tarefas de raciocínio crítico
    
    Args:
        task_type: Tipo da tarefa (ex: "system_analysis", "code_generation")
        context: Contexto adicional da tarefa
    
    Returns:
        True se deve elevar modelo
    """
    elevation_keywords = [
        "análise", "analisar", "diagnóstico", "avaliação",
        "arquitetura", "sistema", "capabilidade", "mecanismo",
        "raciocínio", "crítico", "verificação", "validação",
    ]
    
    task_lower = task_type.lower()
    context_lower = context.lower()
    
    # Tarefas de auto-análise sempre exigem elevação
    if "analysis" in task_lower or "analise" in task_lower:
        return True
    
    # Contexto com keywords de elevação
    for keyword in elevation_keywords:
        if keyword in context_lower:
            return True
    
    return False
