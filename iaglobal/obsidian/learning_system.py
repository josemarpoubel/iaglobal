"""LearningSystem — Middleware Cognitivo para injeção de insights do subconsciente.

Funciona como um interceptor: antes de qualquer chamada de agente ao LLM,
o sistema consulta o Obsidian (subconsciente) e injeta memórias relevantes
no prompt, enriquecendo o contexto sem custo extra de tokens.
"""

from typing import List, Optional

from iaglobal.obsidian.subconsciousapi import SubconsciousAPI


class IAGlobalAgentWrapper:
    """Wrapper que dá a qualquer agente do iaglobal acesso ao subconsciente.

    Uso:
        agent = MetaAgentDesigner()
        wrapper = IAGlobalAgentWrapper(agent)
        prompt = await wrapper.preparar_prompt_com_intuicao(
            prompt_original_usuario="tarefa",
            tags_da_tarefa=["#tag1", "#tag2"],
        )
        resposta = agent.llm_call(prompt)
    """

    def __init__(self, agent_instance, vault_path=None):
        self.agent = agent_instance
        self.subconscious = SubconsciousAPI(vault_path)

    async def preparar_prompt_com_intuicao(
        self, prompt_original_usuario: str, tags_da_tarefa: List[str]
    ) -> str:
        """Injeta memória de longo prazo no prompt antes de enviar ao LLM."""
        sussurro = await self.subconscious.sussurrar_intuicao(tags_da_tarefa)

        prompt_enriquecido = f"""⚠️ [CAMADA SUBCONSCIENTE - MEMÓRIA DE LONGO PRAZO]

Abaixo estão as lições aprendidas em ciclos evolutivos anteriores sobre este tema:
{sussurro}

==================================================

🎯 [CAMADA CONSCIENTE - EXECUÇÃO ATUAL]
{prompt_original_usuario}"""

        return prompt_enriquecido


class LearningSystem:
    """Ponto de entrada unificado para chamadas de agentes com subconsciente ativo.

    Intercepta a requisição, busca intuição no Obsidian, monta o prompt
    enriquecido e retorna o contexto pronto para o LLM.
    """

    def __init__(self, vault_path=None, model_client=None):
        self.vault_path = vault_path
        self.model_client = model_client
        self._subconscious = SubconsciousAPI(vault_path)

    async def processar_requisicao_agente(
        self,
        agente_nome: str,
        tarefa_texto: str,
        tags_contexto: Optional[List[str]] = None,
    ) -> str:
        """Processa requisição de um agente com infusão de memória subconsciente."""
        tags = tags_contexto or []

        insights = await self._subconscious.obter_insight_subconsciente(tags)

        prompt_sistema = f"""Você é o agente [{agente_nome}] operando no ecossistema biológico-digital iaglobal.
Diretriz Primária: Use a sabedoria do seu subconsciente (experiências passadas)
para guiar suas decisões conscientes atuais. Evite erros históricos."""

        prompt_usuario = f"""::: SUBCONSCIENTE (MEMÓRIA DE LONGO PRAZO) :::
{insights}

::: CONSCIENTE (TAREFA ATUAL) :::
Tarefa: {tarefa_texto}
Tags Associadas: {", ".join(tags) if tags else "(nenhuma)"}

Forneça a resposta ou código técnico ideal baseado nas restrições acima."""

        return prompt_usuario
