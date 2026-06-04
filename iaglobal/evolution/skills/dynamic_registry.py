"""DynamicSkillRegistry — Registry persistente com suporte a skills dinâmicas.

Estende SkillRegistry com:
- Persistência SQLite de skills geradas dinamicamente
- Carregamento automático na inicialização
- Suporte a run_fn via template (LLM ou determinístico)
"""

import json
import sqlite3
from pathlib import Path
from typing import Dict, Optional, List, Any, Callable, Union
from dataclasses import dataclass, field

from iaglobal._paths import CORE_DB, get_db_connection as _norm_path
from iaglobal.evolution.skills.skill import Skill, ExecutionPolicy
from iaglobal.evolution.skills.skill_registry import SkillRegistry, skill_registry as _global_registry
from iaglobal.utils.logger import logger


class DynamicSkillRegistry(SkillRegistry):
    """SkillRegistry com persistência SQLite para skills dinâmicas."""

    def __init__(self, db_path: Union[str, Path] = CORE_DB):
        super().__init__()
        p = Path(db_path) if isinstance(db_path, str) else db_path
        self.db_path = _norm_path(p)
        self._init_tables()
        self._load_dynamic_skills()

    def _init_tables(self):
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS dynamic_skills (
                    name TEXT PRIMARY KEY,
                    description TEXT,
                    inputs TEXT DEFAULT '[]',
                    outputs TEXT DEFAULT '[]',
                    constraints TEXT DEFAULT '[]',
                    execution_policy TEXT DEFAULT 'single-run',
                    version TEXT DEFAULT 'v1',
                    author TEXT DEFAULT 'dynamic',
                    tags TEXT DEFAULT '[]',
                    template_type TEXT DEFAULT 'llm',
                    template_prompt TEXT DEFAULT '',
                    active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    usage_count INTEGER DEFAULT 0
                )
            """)
            conn.commit()
        finally:
            conn.close()

    def register_dynamic(self, skill: Skill, template_type: str = "llm",
                         template_prompt: str = "") -> bool:
        """Registra skill dinâmica + persiste no SQLite."""
        import time
        start = time.time()
        exists = self.get(skill.name) is not None
        result = self.register_or_update(skill)
        if result:
            self._save_to_db(skill, template_type, template_prompt)
            elapsed = time.time() - start
            action = "atualizada" if exists else "registrada"
            logger.info(f"[DYNAMIC-SKILL] Skill {action}: {skill.name} v{skill.version} "
                        f"template={template_type} elapsed={elapsed:.2f}s")
        else:
            logger.warning(f"[DYNAMIC-SKILL] Falha ao registrar: {skill.name} (já existe)")
        return result

    def register_dynamic_from_dict(self, data: Dict) -> Optional[Skill]:
        """Cria e registra skill dinâmica a partir de dicionário."""
        import time
        start = time.time()
        try:
            policy_map = {
                "single-run": ExecutionPolicy.SINGLE_RUN,
                "repeatable": ExecutionPolicy.REPEATABLE,
                "on-demand": ExecutionPolicy.ON_DEMAND,
                "always": ExecutionPolicy.ALWAYS,
            }
            skill = Skill(
                name=data["name"],
                description=data.get("description", ""),
                inputs=data.get("inputs", []),
                outputs=data.get("outputs", []),
                constraints=data.get("constraints", []),
                execution_policy=policy_map.get(
                    data.get("execution_policy", "single-run"),
                    ExecutionPolicy.SINGLE_RUN
                ),
                version=data.get("version", "v1"),
                author=data.get("author", "dynamic"),
                tags=data.get("tags", []),
            )
            self.register_dynamic(
                skill,
                template_type=data.get("template_type", "llm"),
                template_prompt=data.get("template_prompt", ""),
            )
            elapsed = time.time() - start
            logger.info(f"[DYNAMIC-SKILL] Skill criada de dict: {skill.name} "
                        f"inputs={skill.inputs} outputs={skill.outputs} elapsed={elapsed:.2f}s")
            return skill
        except Exception as e:
            elapsed = time.time() - start
            logger.error(f"[DYNAMIC-SKILL] Erro ao registrar skill de dict: {e} "
                         f"elapsed={elapsed:.2f}s")
            return None

    def list_dynamic_skills(self) -> List[Dict]:
        """Lista skills dinâmicas persistidas."""
        conn = sqlite3.connect(self.db_path)
        try:
            rows = conn.execute(
                "SELECT name, description, version, template_type, active, usage_count FROM dynamic_skills ORDER BY created_at DESC"
            ).fetchall()
            result = [
                {"name": r[0], "description": r[1][:80], "version": r[2],
                 "template_type": r[3], "active": bool(r[4]), "usage": r[5]}
                for r in rows
            ]
            if result:
                logger.debug(f"[DYNAMIC-SKILL] Listadas {len(result)} skills dinâmicas")
            return result
        finally:
            conn.close()

    def get_dynamic_templates(self) -> Dict[str, Dict]:
        """Retorna templates de todas as skills dinâmicas."""
        conn = sqlite3.connect(self.db_path)
        try:
            rows = conn.execute(
                "SELECT name, template_type, template_prompt FROM dynamic_skills WHERE active = 1"
            ).fetchall()
            result = {r[0]: {"type": r[1], "prompt": r[2]} for r in rows}
            logger.debug(f"[DYNAMIC-SKILL] {len(result)} templates carregados")
            return result
        finally:
            conn.close()

    def _save_to_db(self, skill: Skill, template_type: str, template_prompt: str):
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("""
                INSERT OR REPLACE INTO dynamic_skills
                (name, description, inputs, outputs, constraints, execution_policy,
                 version, author, tags, template_type, template_prompt, active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            """, (
                skill.name, skill.description,
                json.dumps(skill.inputs), json.dumps(skill.outputs),
                json.dumps(skill.constraints), skill.execution_policy.value,
                skill.version, skill.author, json.dumps(skill.tags),
                template_type, template_prompt,
            ))
            conn.commit()
        finally:
            conn.close()

    def _load_dynamic_skills(self):
        """Carrega skills dinâmicas do SQLite no registry."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute("SELECT * FROM dynamic_skills WHERE active = 1")
            rows = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            for row in rows:
                data = dict(zip(columns, row))
                skill = Skill(
                    name=data["name"],
                    description=data["description"],
                    inputs=json.loads(data["inputs"]),
                    outputs=json.loads(data["outputs"]),
                    constraints=json.loads(data["constraints"]),
                    execution_policy=ExecutionPolicy(data["execution_policy"]),
                    version=data["version"],
                    author=data["author"],
                    tags=json.loads(data["tags"]),
                )
                self.register(skill)
                entry = self._skills.get(skill.name)
                if entry:
                    entry.usage_count = data["usage_count"] or 0
            if rows:
                logger.info(f"[DYNAMIC-SKILL] Carregadas {len(rows)} skills dinâmicas")
        finally:
            conn.close()

    def increment_usage(self, name: str):
        super().increment_usage(name)
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                "UPDATE dynamic_skills SET usage_count = usage_count + 1 WHERE name = ?",
                (name,)
            )
            conn.commit()
        finally:
            conn.close()


# Instância global
dynamic_registry = DynamicSkillRegistry()
