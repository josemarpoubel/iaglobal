# iaglobal/graphs/skill_node.py
"""
SkillNode — Nó de execução de skills com validação das Leis Universais.

LEIS UNIVERSAIS (Holliwell):
Cada execução de skill é validada contra as 15 Leis Universais.
Violações críticas disparam apoptose imediata do nó.
"""

import hashlib
from typing import Any, Dict

from iaglobal.evolution.skills.dynamic_registry import dynamic_registry
from iaglobal.utils.logger import logger
from iaglobal.core.law_engine import law_compliance_engine
from iaglobal.immunity.apoptosis_engine import apoptosis_engine


def _compute_node_id(node_type: str, seed_id: str = "", mutation_id: str = "", version: str = "v1", name: str = "") -> str:
    raw = f"{node_type}::{seed_id}::{mutation_id}::{version}::{name}"
    return hashlib.sha3_256(raw.encode()).hexdigest()[:16]


class SkillNode:
    def __init__(self, name: str, skill_name: str = None, depends_on: list = None):
        self.name = name
        self.depends_on = depends_on or []
        self._skill_name = skill_name or name
        self.node_type = "general"
        self.seed_id = ""
        self.mutation_id = ""
        self.version = "v1"

    @property
    def node_id(self) -> str:
        effective_type = self.node_type if self.node_type != "general" else self.name
        effective_seed = self.seed_id if self.seed_id else self.name
        return _compute_node_id(
            node_type=effective_type,
            seed_id=effective_seed,
            mutation_id=self.mutation_id,
            version=self.version,
            name=self.name,
        )

    async def run(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        try:
            # --- PRÉ-EXECUÇÃO: Validação das Leis Universais ---
            law_check = law_compliance_engine.evaluate_action({
                "action": f"skill_{self._skill_name}",
                "context": ctx,
                "output": "",  # Ainda não há output
                "metrics": {"node_id": self.node_id, "version": self.version}
            })
            
            if not law_check.get("compliant", True):
                violations = law_check.get("violations", [])
                severity = law_check.get("severity", 0)
                
                logger.warning(f"[SKILL-NODE] Violação das Leis Universais detectada em {self._skill_name}: {violations}")
                
                # Violações críticas disparam apoptose imediata
                if severity >= 5:
                    logger.critical(f"[SKILL-NODE] Apoptose ativada para {self._skill_name} - violação crítica (severity={severity})")
                    apoptosis_engine.trigger_apoptosis(
                        cell_id=self.node_id,
                        reason=f"Violação das Leis Universais: {violations}",
                        severity=severity
                    )
                    return {
                        "output": None,
                        "success": False,
                        "error": f"Skill bloqueada por violação das Leis Universais: {violations}",
                        "law_violations": violations,
                        "apoptosis_triggered": True
                    }
                
                # Violações não-críticas apenas registram o evento
                ctx["law_warnings"] = ctx.get("law_warnings", []) + [violations]
            
            # --- EXECUÇÃO DA SKILL ---
            result = await dynamic_registry.execute(self._skill_name, ctx)
            
            # --- PÓS-EXECUÇÃO: Validação do Output ---
            if result and result.get("output"):
                output_check = law_compliance_engine.evaluate_action({
                    "action": f"skill_{self._skill_name}_output",
                    "context": ctx,
                    "output": str(result.get("output")),
                    "metrics": result.get("metrics", {})
                })
                
                if not output_check.get("compliant", True):
                    violations = output_check.get("violations", [])
                    logger.warning(f"[SKILL-NODE] Output de {self._skill_name} violou Leis Universais: {violations}")
                    result["law_violations"] = violations
                    result["law_compliance_score"] = output_check.get("compliance_score", 0)
                    
                    # Se violação crítica no output, também dispara apoptose
                    if output_check.get("severity", 0) >= 5:
                        logger.critical(f"[SKILL-NODE] Apoptose pós-execução para {self._skill_name}")
                        apoptosis_engine.trigger_apoptosis(
                            cell_id=self.node_id,
                            reason=f"Output violou Leis Universais: {violations}",
                            severity=output_check.get("severity", 0)
                        )
                        result["apoptosis_triggered"] = True
            
            if result:
                return result
            return {"output": None, "success": True, "law_compliant": True}
            
        except Exception as e:
            logger.warning(f"[SKILL-NODE] {self._skill_name} execute failed: {e}")
            return {"output": None, "success": False, "error": str(e)}
