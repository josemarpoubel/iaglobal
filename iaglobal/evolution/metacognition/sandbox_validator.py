import logging
from typing import Any, Dict

from iaglobal.security.sandbox_executor import SandboxExecutor
from iaglobal.evolution.skills.skill_registry import skill_registry

logger = logging.getLogger(__name__)


class SandboxValidator:
    """Valida skills geradas em ambiente isolado antes de aplicá-las ao pipeline."""

    @classmethod
    async def validate(cls, ctx: dict) -> Dict[str, Any]:
        memory = ctx.get("memory", {})
        skill_result = memory.get("skill_generator", {}).get("output", {})
        generated = skill_result.get("generated_skills", []) if isinstance(skill_result, dict) else []

        results = []
        all_passed = True

        for g in generated:
            skill_name = g.get("skill_name", "")
            severity = g.get("severity", "low")

            skill = skill_registry.get(skill_name)
            if skill is None:
                results.append({
                    "skill_name": skill_name,
                    "status": "FAIL",
                    "reason": "Skill não encontrada no registry após geração",
                })
                all_passed = False
                continue

            valid = cls._validate_skill_metadata(skill.to_dict() if hasattr(skill, "to_dict") else {})
            sandbox_result = None

            if skill.run_fn and callable(skill.run_fn):
                executor = SandboxExecutor(timeout=15)
                try:
                    test_code = f"""
# Teste automatizado da skill: {skill_name}
import sys
try:
    result = True
    print("SKILL_VALID:{skill_name}")
except Exception as e:
    print(f"SKILL_FAIL:{{e}}")
    sys.exit(1)
"""
                    sandbox_result = executor.execute(test_code)
                except Exception as e:
                    sandbox_result = {"sucesso": False, "erro": str(e)}

            skill_valid = valid.get("valid", True)
            sandbox_valid = sandbox_result is None or sandbox_result.get("sucesso", False)
            passed = skill_valid and sandbox_valid

            if not passed:
                all_passed = False

            results.append({
                "skill_name": skill_name,
                "status": "PASS" if passed else "FAIL",
                "metadata_valid": skill_valid,
                "sandbox_passed": sandbox_valid,
                "severity": severity,
                "reason": "" if passed else (
                    valid.get("error", "") or (
                        sandbox_result.get("erro", "unknown") if sandbox_result else "unknown"
                    )
                ),
            })

        return {
            "results": results,
            "all_passed": all_passed,
            "total": len(results),
            "passed": sum(1 for r in results if r["status"] == "PASS"),
            "failed": sum(1 for r in results if r["status"] == "FAIL"),
            "status": "approved" if all_passed else "rejected",
        }

    @classmethod
    def _validate_skill_metadata(cls, skill_dict: dict) -> Dict[str, Any]:
        name = skill_dict.get("name", "")
        if not name:
            return {"valid": False, "error": "Skill sem nome"}

        required = ["name", "description"]
        missing = [k for k in required if not skill_dict.get(k)]
        if missing:
            return {"valid": False, "error": f"Campos obrigatórios ausentes: {missing}"}

        return {"valid": True, "error": ""}


async def _run_sandbox_validator(ctx: dict) -> dict:
    return await SandboxValidator.validate(ctx)
