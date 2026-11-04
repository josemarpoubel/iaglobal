# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
Teste da passagem de memory por referência em _build_contract_ctx.

Garante que:
1. contract_ctx inclui o dict "memory" completo
2. Instâncias vivas dentro de memory (ex: _agent_bus, _mailbox_manager)
   sobrevivem como o MESMO objeto (referência, não deepcopy)
3. Bridge functions que usam context.get("memory", {}) recebem
   os dados reais, não um dict vazio
"""

from typing import Dict, Any


class TestBuildContractCtx:
    """Verifica que _build_contract_ctx passa memory por referência."""

    async def test_memory_present_in_contract_ctx(
        self,
    ):
        from iaglobal.evolution.skills.native.skill_executor import (
            SkillExecutor,
        )
        from iaglobal.evolution.skills.native.skill import SKILL_CODER

        executor = SkillExecutor()

        fake_ctx: Dict[str, Any] = {
            "input": {"task": "crie um app de vendas"},
            "task": "crie um app de vendas",
            "memory": {
                "prompt_builder": {
                    "output": "prompt elaborado para o coder",
                    "built_prompt": "prompt elaborado para o coder",
                },
            },
            "workdir": "/tmp",
        }

        contract_ctx = executor._build_contract_ctx(SKILL_CODER, fake_ctx)

        assert "memory" in contract_ctx, (
            "contract_ctx deve incluir 'memory' para que bridge functions "
            "consigam reconstruir o contexto completo do nó"
        )

    async def test_mailbox_instances_survive_by_reference(self):
        from iaglobal.evolution.skills.native.skill_executor import (
            SkillExecutor,
        )
        from iaglobal.evolution.skills.native.skill import SKILL_CODER
        from iaglobal.graphs.comms.acetylcholine_bus import (
            AcetylcholineBus,
        )

        executor = SkillExecutor()
        bus = AcetylcholineBus()
        mailbox_mgr: object = object()

        fake_ctx: Dict[str, Any] = {
            "input": {"task": "teste"},
            "task": "teste",
            "memory": {
                "agentmailbox": {
                    "_agent_bus": bus,
                    "_mailbox_manager": mailbox_mgr,
                    "output": "mailbox output",
                },
            },
            "workdir": "/tmp",
        }

        contract_ctx = executor._build_contract_ctx(SKILL_CODER, fake_ctx)

        assert "memory" in contract_ctx
        memory = contract_ctx["memory"]

        assert "_agent_bus" in memory.get("agentmailbox", {}), (
            "agentmailbox deve estar presente em contract_ctx['memory']"
        )
        assert memory["agentmailbox"]["_agent_bus"] is bus, (
            "_agent_bus deve ser a MESMA instância (referência, não deepcopy) — "
            "deepcopy quebraria objetos de concorrência (locks, filas, sockets)"
        )
        assert memory["agentmailbox"]["_mailbox_manager"] is mailbox_mgr, (
            "_mailbox_manager deve ser a MESMA instância por referência"
        )

    async def test_skill_input_validation_unaffected(self):
        """Adicionar memory ao contract_ctx não deve afetar a validação de inputs."""
        from iaglobal.evolution.skills.native.skill_executor import (
            SkillExecutor,
        )
        from iaglobal.evolution.skills.native.skill import SKILL_CODER

        executor = SkillExecutor()

        fake_ctx: Dict[str, Any] = {
            "input": {"task": "teste"},
            "task": "teste",
            "memory": {
                "prompt_builder": {
                    "output": "prompt de teste",
                    "built_prompt": "prompt de teste",
                },
            },
            "workdir": "/tmp",
        }

        contract_ctx = executor._build_contract_ctx(SKILL_CODER, fake_ctx)

        # SKILL_CODER inputs = ("task", "plan")
        # task deve estar presente (vem de input_data.task)
        assert "task" in contract_ctx, "task deve vir de input_data"
        # plan NÃO deve estar presente (ninguém produz "plan" no DAG atual)
        # Isso é esperado — o skill path falha e o fallback assume
        # Mas o importante é que memory NÃO mascare essa ausência
        assert "plan" not in contract_ctx, (
            "plan não deve ser magicamente adicionado — "
            "memory não deve poluir contract_ctx com chaves espúrias"
        )

    async def test_execution_result_still_works(self):
        """'execution_result' só deve ser adicionado se estiver em skill.inputs."""
        from iaglobal.evolution.skills.native.skill_executor import (
            SkillExecutor,
        )
        from iaglobal.evolution.skills.native.skill import SKILL_CODER

        executor = SkillExecutor()

        fake_ctx: Dict[str, Any] = {
            "input": {"task": "teste"},
            "task": "teste",
            "memory": {
                "prompt_builder": {"output": "prompt"},
            },
            "workdir": "/tmp",
        }

        contract_ctx = executor._build_contract_ctx(SKILL_CODER, fake_ctx)

        assert "execution_result" not in contract_ctx, (
            "execution_result só entra se skill.inputs contiver 'execution_result'"
        )
