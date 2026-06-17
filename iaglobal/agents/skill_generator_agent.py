# iaglobal/agents/skill_generator_agent.py

import re
import json
import sqlite3
import logging  # <--- ADICIONE ESTA LINHA

from pathlib import Path

from typing import List, Dict, Optional, Union

from datetime import datetime, timezone

from collections import Counter

from iaglobal._paths import CORE_DB, get_db_connection as _norm_path

from iaglobal.evolution.skills.skill import Skill

from iaglobal.evolution.skills.skill import ExecutionPolicy

from iaglobal.evolution.skills.run_fn_factory import make_dynamic_run_fn

from iaglobal.evolution.skills.dynamic_registry import dynamic_registry

from iaglobal.memory.fusion_engine import KnowledgeGraph

from iaglobal.utils.logger import logger

logger = logging.getLogger("ia-global")

class SkillGeneratorAgent:
    """Gera skills automaticamente da base de conhecimento."""

    def __init__(self, db_path: Union[str, Path] = CORE_DB):
        p = Path(db_path) if isinstance(db_path, str) else db_path
        self.db_path = _norm_path(p)
        self.kg = KnowledgeGraph(self.db_path)
        self._generated_count = 0

    def analyze_and_generate(self) -> List[Dict]:
        """Analisa KB e KG e gera novas skills. Retorna lista de skills geradas."""
        import time
        start = time.time()
        generated = []

        kb_count = len(dynamic_registry.list_dynamic_skills())
        logger.info(f"[SKILL-GEN] Iniciando análise: {kb_count} skills dinâmicas existentes")

        kb_skills = self._generate_from_kb_entries()
        generated.extend(kb_skills)
        if kb_skills:
            logger.info(f"[SKILL-GEN] {len(kb_skills)} skills de KB entries")

        concept_skills = self._generate_from_concepts()
        generated.extend(concept_skills)
        if concept_skills:
            logger.info(f"[SKILL-GEN] {len(concept_skills)} skills de conceitos")

        faq_skills = self._generate_from_faqs()
        generated.extend(faq_skills)
        if faq_skills:
            logger.info(f"[SKILL-GEN] {len(faq_skills)} skills de FAQs")

        elapsed = time.time() - start
        logger.info(f"[SKILL-GEN] Análise concluída: {len(generated)} novas skills "
                    f"geradas em {elapsed:.2f}s (KB={len(kb_skills)} "
                    f"conceitos={len(concept_skills)} FAQs={len(faq_skills)})")
        return generated

    def generate_skill_from_pattern(self, name: str, description: str,
                                     inputs: List[str], outputs: List[str],
                                     template_key: str = "summary",
                                     tags: Optional[List[str]] = None) -> Optional[Dict]:
        """Gera skill a partir de um padrão explícito."""
        import time
        start = time.time()

        fn_factory = dynamic_registry.get(template_key)
        run_fn = fn_factory() if fn_factory else make_dynamic_run_fn(name, "llm", description)

        skill = Skill(
            name=name,
            description=description,
            inputs=inputs,
            outputs=outputs,
            constraints=["llm"],
            execution_policy=ExecutionPolicy.SINGLE_RUN,
            version="v1",
            author="skill_generator",
            tags=tags or ["dynamic", "generated"],
            run_fn=run_fn,
        )

        registered = dynamic_registry.register_dynamic(
            skill, template_type="llm",
            template_prompt=description
        )

        if registered:
            self._generated_count += 1
            result = {
                "name": name,
                "description": description[:60],
                "inputs": inputs,
                "outputs": outputs,
                "template": template_key,
            }
            elapsed = time.time() - start
            logger.info(f"[SKILL-GEN] Nova skill: {name} "
                        f"template={template_key} inputs={inputs} outputs={outputs} "
                        f"elapsed={elapsed:.2f}s")
            return result

        logger.warning(f"[SKILL-GEN] Falha ao registrar skill: {name} (já existe?)")
        return None

    def get_generated_count(self) -> int:
        return self._generated_count

    def get_stats(self) -> Dict:
        skills = dynamic_registry.list_dynamic_skills()
        return {
            "total_generated": self._generated_count,
            "persisted": len(skills),
            "skills": skills,
        }

    # =========================================================================
    # GERADORES ESPECÍFICOS
    # =========================================================================

    def _generate_from_kb_entries(self) -> List[Dict]:
        """Gera skills a partir de entries da KB."""
        generated = []
        conn = sqlite3.connect(self.db_path)
        try:
            entries = conn.execute(
                "SELECT entry_type, title, content, tags FROM kb_entries ORDER BY id"
            ).fetchall()
        except sqlite3.OperationalError:
            logger.debug("[SKILL-GEN] Tabela kb_entries não existe ainda")
            return []
        finally:
            conn.close()

        type_counts = Counter(r[0] for r in entries)
        logger.debug(f"[SKILL-GEN] KB entry types: {dict(type_counts)}")
        for entry_type, count in type_counts.items():
            if count < 2:
                logger.debug(f"[SKILL-GEN] {entry_type}: apenas {count} entry(s), mínimo 2")
                continue
            skill_name = f"kb_{entry_type}_analyzer"
            if dynamic_registry.get(skill_name):
                logger.debug(f"[SKILL-GEN] Skill já existe: {skill_name}")
                continue

            logger.info(f"[SKILL-GEN] Gerando skill para {entry_type} ({count} entries)")
            skill = self.generate_skill_from_pattern(
                name=skill_name,
                description=f"Analisa e processa entries do tipo {entry_type} na base de conhecimento",
                inputs=["task"],
                outputs=[f"{entry_type}_analysis"],
                template_key="analysis",
                tags=["dynamic", "kb", entry_type],
            )
            if skill:
                generated.append(skill)
        return generated

    def _generate_from_concepts(self) -> List[Dict]:
        """Gera skills a partir de conceitos frequentes no KG."""
        top = self.kg.get_top_concepts(limit=20)
        generated = []

        high_freq = [c for c in top if c["frequency"] >= 3]
        logger.debug(f"[SKILL-GEN] Conceitos frequentes (>=3): {len(high_freq)} de {len(top)}")
        for concept in high_freq[:5]:
            name = concept["name"].lower().replace(" ", "_")
            skill_name = f"concept_{name}_expert"
            if dynamic_registry.get(skill_name):
                continue

            logger.info(f"[SKILL-GEN] Gerando skill para conceito: {concept['name']} "
                        f"(freq={concept['frequency']})")
            skill = self.generate_skill_from_pattern(
                name=skill_name,
                description=f"Especialista no conceito {concept['name']}: explica, aplica e relaciona",
                inputs=["task"],
                outputs=[f"{name}_insight"],
                template_key="summary",
                tags=["dynamic", "concept", name],
            )
            if skill:
                generated.append(skill)
        return generated

    def _generate_from_faqs(self) -> List[Dict]:
        """Gera skills a partir de FAQs frequentes."""
        generated = []
        conn = sqlite3.connect(self.db_path)
        try:
            faqs = conn.execute(
                "SELECT question, answer, frequency FROM kb_faq ORDER BY frequency DESC LIMIT 10"
            ).fetchall()
        except sqlite3.OperationalError:
            logger.debug("[SKILL-GEN] Tabela kb_faq não existe ainda")
            return []
        finally:
            conn.close()

        logger.debug(f"[SKILL-GEN] FAQs disponíveis: {len(faqs)}")
        for q, a, freq in faqs:
            if freq < 2:
                continue
            topic = re.sub(r"[^a-zA-Z0-9]", "_", q[:30].lower()).strip("_")
            skill_name = f"faq_{topic}_helper"
            if dynamic_registry.get(skill_name):
                continue

            logger.info(f"[SKILL-GEN] Gerando skill para FAQ: {q[:40]}... (freq={freq})")
            skill = self.generate_skill_from_pattern(
                name=skill_name,
                description=f"Responde perguntas frequentes sobre: {q[:60]}",
                inputs=["task"],
                outputs=["faq_answer"],
                template_key="summary",
                tags=["dynamic", "faq", topic],
            )
            if skill:
                generated.append(skill)
        return generated
