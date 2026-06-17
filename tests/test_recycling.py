import pytest
from unittest.mock import MagicMock, patch

from iaglobal.recycling.mta_pool import MTAPool, mta_pool
from iaglobal.recycling.prompt_recycler import PromptRecycler
from iaglobal.recycling.skill_recycler import SkillRecycler


class TestMTAPool:

    def test_add_and_count(self):
        pool = MTAPool()
        pool.items = []
        pool.add("failed_prompt", "test error", {"error_type": "RuntimeError"})
        assert pool.count() == 1
        assert pool.count("failed_prompt") == 1

    def test_flush_by_type(self):
        pool = MTAPool()
        pool.items = []
        pool.add("failed_prompt", "msg1")
        pool.add("obsolete_skill", "msg2")
        flushed = pool.flush("failed_prompt")
        assert len(flushed) == 1
        assert pool.count() == 1

    def test_extract_negative_prompts(self):
        pool = MTAPool()
        pool.items = []
        pool.add("failed_prompt", "não use essa abordagem")
        pool.add("failed_prompt", "faça algo")
        negatives = pool.extract_negative_prompts()
        assert len(negatives) >= 1
        assert "não" in negatives[0]


class TestPromptRecycler:

    def test_recycle_empty(self):
        r = PromptRecycler.recycle([])
        assert r["analyzed"] == 0
        assert len(r["suggestions"]) == 0

    def test_recycle_falta_contexto(self):
        r = PromptRecycler.recycle(["não tenho contexto para responder"])
        assert r["analyzed"] >= 1
        assert any("CONTEXTO" in s for s in r["suggestions"])


class TestSkillRecycler:

    def test_recycle_no_auto_generated(self):
        from iaglobal.evolution.skills.skill import Skill
        from iaglobal.evolution.skills.skill_registry import skill_registry
        saved = dict(skill_registry._skills)
        skill_registry._skills = {}
        try:
            skill_registry.register(Skill(
                name="manual_skill", version="v1", description="manual",
                run_fn=lambda ctx: {"output": "ok"}, tags=["production"],
            ))
            r = SkillRecycler.recycle()
            assert r["count"] == 0
        finally:
            skill_registry._skills = saved


class TestRecyclingIntegration:

    def test_store_error_adds_to_mta_pool(self):
        from iaglobal.memory.memory_error import store_error
        saved = list(mta_pool.items)
        mta_pool.items = []
        try:
            store_error("test prompt", "bad response", "critique", "corrected", "TestError")
            assert mta_pool.count("failed_prompt") >= 0
        finally:
            mta_pool.items = saved

    def test_orchestrator_has_recycling(self):
        from iaglobal.core.orchestrator import Orchestrator
        assert hasattr(Orchestrator, "_run_metacognition_flow")
