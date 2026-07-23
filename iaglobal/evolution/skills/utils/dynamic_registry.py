# iaglobal/evolution/skills/dynamic_registry.py

"""
🎯 DynamicSkillRegistry — Extensão de persistência SQLite thread-safe para o Registry Global.
"""

import json
import sqlite3
import threading

from pathlib import Path
from typing import Dict, Optional, List, Union

from iaglobal._paths import CORE_DB, get_db_connection as _norm_path
from iaglobal.evolution.skills.native.skill import Skill, ExecutionPolicy
from iaglobal.evolution.skills.native.skill_registry import (
    SkillRegistry,
    skill_registry as _global_registry,
)

from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.evolution.skills.utils.dynamic_registry")


class DynamicSkillRegistry:
    """
    Proxy seguro para o SkillRegistry global que gerencia persistência SQLite
    de habilidades evolutivas dinâmicas de forma atômica e não-bloqueante.
    """

    def __init__(
        self,
        registry: SkillRegistry = _global_registry,
        db_path: Union[str, Path] = CORE_DB,
    ):
        # 🔗 COMPARTILHAMENTO DE ESTADO REAL: Aponta para a mesma memória do registry global
        self._registry = registry

        p = Path(db_path) if isinstance(db_path, str) else db_path
        self.db_path = _norm_path(p)
        self._db_lock = (
            threading.Lock()
        )  # Protege as transações de escrita do SQLite contra concorrência externa
        self._init_tables()
        self._loaded = False

    def load_dynamic_skills(self):
        """Carrega skills dinâmicas do SQLite para dentro do registry global."""
        if self._loaded:
            return
        self._load_dynamic_skills()
        self._loaded = True

    def _init_tables(self):
        with self._db_lock:
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

    def register_dynamic(
        self, skill: Skill, template_type: str = "llm", template_prompt: str = ""
    ) -> bool:
        """Registra a skill na memória global controlada por Locks e replica no SQLite."""
        import time

        start = time.time()

        # Consome os métodos thread-safe do repositório real compartilhado
        exists = self._registry.get(skill.name) is not None
        result = self._registry.register_or_update(skill)

        if result:
            with self._db_lock:
                self._save_to_db(skill, template_type, template_prompt)

            elapsed = time.time() - start
            action = "atualizada" if exists else "registrada"
            logger.info(
                f"[DYNAMIC-SKILL] Skill {action}: {skill.name} v{skill.version} "
                f"template={template_type} elapsed={elapsed:.2f}s"
            )
        else:
            logger.warning(
                f"[DYNAMIC-SKILL] Falha ao registrar na memória: {skill.name}"
            )
        return result

    def list_dynamic_skills(self) -> List[Dict]:
        with self._db_lock:
            conn = sqlite3.connect(self.db_path)
            try:
                rows = conn.execute(
                    "SELECT name, description, version, template_type, active, usage_count FROM dynamic_skills ORDER BY created_at DESC"
                ).fetchall()
                return [
                    {
                        "name": r[0],
                        "description": r[1][:80],
                        "version": r[2],
                        "template_type": r[3],
                        "active": bool(r[4]),
                        "usage": r[5],
                    }
                    for r in rows
                ]
            finally:
                conn.close()

    def _save_to_db(self, skill: Skill, template_type: str, template_prompt: str):
        # NOTA: Presume-se chamado de dentro do escopo com self._db_lock
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO dynamic_skills
                (name, description, inputs, outputs, constraints, execution_policy,
                 version, author, tags, template_type, template_prompt, active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            """,
                (
                    skill.name,
                    skill.description,
                    json.dumps(skill.inputs),
                    json.dumps(skill.outputs),
                    json.dumps(skill.constraints),
                    skill.execution_policy.value,
                    skill.version,
                    skill.author,
                    json.dumps(skill.tags),
                    template_type,
                    template_prompt,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def _load_dynamic_skills(self):
        with self._db_lock:
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

                    # Registra com segurança na memória real unificada
                    self._registry.register(skill)

                    # Modifica a contagem utilizando o lock interno do próprio registry pai
                    with getattr(self._registry, "_lock", threading.Lock()):
                        entry = self._registry._skills.get(skill.name)
                        if entry:
                            entry.usage_count = data["usage_count"] or 0
                if rows:
                    logger.info(
                        f"[DYNAMIC-SKILL] Sincronizadas {len(rows)} skills dinâmicas do SQLite."
                    )
            finally:
                conn.close()

    def increment_usage(self, name: str):
        # Primeiro, incrementa de forma imediata na memória RAM global
        self._registry.increment_usage(name)

        # Executa a persistência do SQLite sob proteção de lock dedicada
        with self._db_lock:
            conn = sqlite3.connect(self.db_path)
            try:
                conn.execute(
                    "UPDATE dynamic_skills SET usage_count = usage_count + 1 WHERE name = ?",
                    (name,),
                )
                conn.commit()
            finally:
                conn.close()

    # 🎛️ MÉTODOS DE DELEGAÇÃO (PROXY): Garante compatibilidade total de interface de barramento
    def get(self, name: str) -> Optional[Skill]:
        return self._registry.get(name)

    def get_version(self, name: str, version: str) -> Optional[Skill]:
        return self._registry.get_version(name, version)

    def list_skills(self, active_only: bool = True) -> List[Skill]:
        return self._registry.list_skills(active_only)

    def find_alternatives(
        self, skill_name: str, available_inputs: set, visited: set = None
    ) -> List[Skill]:
        return self._registry.find_alternatives(skill_name, available_inputs, visited)


# 🔥 ÚNICA INSTÂNCIA DE OPERAÇÃO: Agora dynamic_registry consome e protege a memória de _global_registry
dynamic_registry = DynamicSkillRegistry()
