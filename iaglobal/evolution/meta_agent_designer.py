# iaglobal/evolution/meta_agent_designer.py

import logging
import threading
from typing import Dict, List, Optional, Set, Any

from iaglobal.graphs.execution_graph import ExecutionGraph
from iaglobal.evolution.task_analyzer import TaskAnalyzer

logger = logging.getLogger(__name__)

# Mapa unificado: especialidade → instruções explícitas indexadas pelo identificador real da Skill
SPECIALIZATION_PROMPTS = {
    "security": {
        "critic": (
            "[ESPECIALIDADE: SEGURANÇA]\n"
            "Revisão focada em:\n"
            "- SQL Injection: parâmetros sanitizados? Usa ORM?\n"
            "- XSS: escape de HTML? Content-Security-Policy?\n"
            "- CSRF: tokens CSRF em formulários?\n"
            "- Autenticação: senhas hasheadas? JWT seguro? Session management?\n"
            "- Autorização: verificação de permissões em cada rota?\n"
            "- Vazamento de dados: informações sensíveis expostas?\n"
        ),
        "coder": (
            "[ESPECIALIDADE: SEGURANÇA]\n"
            "⚠️ Priorize segurança no código gerado:\n"
            "- Use bibliotecas seguras (bcrypt, jwt, OAuth)\n"
            "- Sanitize todas as entradas de usuário\n"
            "- Adicione tokens CSRF em formulários\n"
            "- Nunca exponha senhas ou chaves no código\n"
            "- Use HTTPS e headers de segurança (CSP, HSTS)\n"
        ),
    },
    "ux": {
        "critic": (
            "[ESPECIALIDADE: UX / ACESSIBILIDADE]\n"
            "Revisão focada em:\n"
            "- Clareza do fluxo: o usuário entende o que fazer?\n"
            "- Acessibilidade: aria-labels, contraste, foco visível?\n"
            "- Mobile: responsivo? Touch targets adequados?\n"
            "- Feedback: mensagens de erro/sucesso claras?\n"
            "- Carregamento: loading states, feedback visual?\n"
        ),
        "coder": (
            "[ESPECIALIDADE: UX / ACESSIBILIDADE]\n"
            "🎯 Priorize experiência do usuário:\n"
            "- Design responsivo (mobile-first)\n"
            "- Contraste mínimo WCAG AA (4.5:1)\n"
            "- ARIA labels em elementos interativos\n"
            "- Feedback visual para ações do usuário\n"
            "- Mensagens de erro claras e amigáveis\n"
            "- Loading states para operações assíncronas\n"
        ),
    },
    "architecture": {
        "critic": (
            "[ESPECIALIDADE: ARQUITETURA]\n"
            "Revisão focada em:\n"
            "- Acoplamento: módulos são independentes?\n"
            "- SRP: cada classe/função tem uma responsabilidade?\n"
            "- Escalabilidade: o design suporta crescimento?\n"
            "- Padrões de projeto: uso apropriado?\n"
            "- Testabilidade: código é testável?\n"
        ),
        "coder": (
            "[ESPECIALIDADE: ARQUITETURA]\n"
            "🏛️ Priorize boa arquitetura:\n"
            "- Separe responsabilidades (controllers, services, repositories)\n"
            "- Injeção de dependência para baixo acoplamento\n"
            "- Interfaces/contratos claros entre módulos\n"
            "- Código testável (inversão de dependências)\n"
            "- Tratamento de erros consistente\n"
        ),
    },
    "performance": {
        "critic": (
            "[ESPECIALIDADE: PERFORMANCE]\n"
            "Revisão focada em:\n"
            "- Consultas N+1? Lazy loading adequado?\n"
            "- Cache implementado onde faz sentido?\n"
            "- Recursos estáticos otimizados?\n"
            "- Bundle size? Code splitting?\n"
        ),
        "coder": (
            "[ESPECIALIDADE: PERFORMANCE]\n"
            "⚡ Priorize performance:\n"
            "- Cache de consultas frequentes\n"
            "- Lazy loading de recursos pesados\n"
            "- Otimização de queries (índices, select only needed)\n"
            "- Minificação de assets\n"
            "- Conexões de banco poolizadas\n"
        ),
    },
    "theming": {
        "coder": (
            "[ESPECIALIDADE: TEMA ESCURO]\n"
            "🎨 Aplique tema escuro rigorosamente:\n"
            "- Background principal: #121212 ou #1a1a2e\n"
            "- Texto: #e0e0e0 ou #ffffff\n"
            "- Inputs/textarea: background #2a2a3e, borda #444\n"
            "- Botões primários: #e94560 ou similar contrastante\n"
            "- Cards/sections: #1e1e2e com borda sutil #333\n"
            "- Links: #64b5f6 ou similar visível no escuro\n"
            "- NUNCA use fundo branco (#fff, #f4f4f4, #f9f9f9)\n"
        ),
    },
    "form_handling": {
        "coder": (
            "[ESPECIALIDADE: FORMULÁRIOS]\n"
            "📋 Priorize formulários completos:\n"
            "- Validação client-side (HTML5 + JS)\n"
            "- Validação server-side (CSRF, sanitize)\n"
            "- Feedback visual de erro/sucesso\n"
            "- Máscaras de input (telefone, CPF, CEP)\n"
            "- Prevenção de double-submit\n"
            "- Acessibilidade: labels, aria-describedby\n"
        ),
    },
    "web_development": {
        "coder": (
            "[ESPECIALIDADE: WEB]\n"
            "🌐 Gere código web completo e funcional:\n"
            "- HTML semântico e acessível\n"
            "- CSS responsivo com variáveis de tema\n"
            "- JS com validação e interatividade\n"
            "- Backend (Flask/Django) com rotas e views\n"
            "- Separe HTML, CSS e JS em arquivos (# FILE:)\n"
        ),
    },
    "database": {
        "coder": (
            "[ESPECIALIDADE: BANCO DE DADOS]\n"
            "🗄️ Priorize modelagem de dados:\n"
            "- Modelos com campos e constraints adequados\n"
            "- Migrações ou CREATE TABLE statements\n"
            "- Consultas ORM eficientes\n"
            "- Índices para campos de busca\n"
            "- Relacionamentos (FK, M2M, 1to1) corretos\n"
        ),
    },
    "api_design": {
        "coder": (
            "[ESPECIALIDADE: API]\n"
            "🔌 Projete API RESTful:\n"
            "- Endpoints REST (GET, POST, PUT, DELETE)\n"
            "- Validação de request body\n"
            "- Tratamento de erros (status codes adequados)\n"
            "- Documentação ou schemas claros\n"
            "- Rate limiting se aplicável\n"
        ),
    },
    "documentation": {
        "coder": (
            "[ESPECIALIDADE: DOCUMENTO]\n"
            "📄 Gere um documento formatado, não um software:\n"
            "- Ignore arquitetura, banco de dados, API e microserviços\n"
            "- Use a biblioteca fpdf2 se for gerar PDF\n"
            "- Formate o conteúdo de forma limpa e legivel\n"
            "- Nao gere codigo de software — gere o documento final\n"
        ),
    },
}


class MetaAgentDesigner:
    """
    🏗️ MetaAgentDesigner (Thread-Safe & Isolado).
    Projeta as especializações comportamentais da equipe e injeta via contexto do pipeline,
    mantendo a topologia do Grafo fixa e veloz.
    """

    def __init__(self, graph: ExecutionGraph):
        self.graph = graph
        self.last_design: Optional[Dict] = None
        # Protege mutações internas no histórico de designs da instância
        self._lock = threading.Lock()

    def design_team(self, task: str) -> Dict:
        """
        Projeta a composição ideal da equipe para a tarefa de forma thread-safe.
        Gera as instruções de contexto sem duplicar ou corromper nós no DAG.
        """
        logger.info("=" * 60)
        logger.info("🏗️ [MetaAgentDesigner] Projetando especialização isolada...")
        logger.info("=" * 60)

        # 1. Análise estática/heurística do prompt
        analysis = TaskAnalyzer.analyze(task)
        task_type = analysis.get("task_type", "general")
        strategies = analysis.get("strategies", set())
        technologies = analysis.get("technologies", set())

        logger.info(
            "[MetaAgentDesigner] Análise: type=%s strategies=%s techs=%s",
            task_type, strategies, technologies
        )

        # 2. 🔥 RESOLUÇÃO DO BUG 1: Lazy Import do GapAnalyzer para aniquilar importação circular
        try:
            from iaglobal.evolution.agents.gap_analyzer import GapAnalyzer
            lacunas = GapAnalyzer.detect_gaps(task, self.graph)
        except (ImportError, ModuleNotFoundError) as e:
            logger.warning("[MetaAgentDesigner] GapAnalyzer indisponível no barramento atual: %s", e)
            lacunas = []
            
        lacunas_detectadas = [g.get("nome", g) if isinstance(g, dict) else str(g) for g in lacunas]

        # Dicionário local isolado por ciclo de CPU (Evita poluição de memória concorrente)
        local_instructions: Dict[str, str] = {}

        # 3. Agrega as instruções baseadas nas estratégias detectadas
        for strategy in strategies:
            if strategy in SPECIALIZATION_PROMPTS:
                for skill, instruction in SPECIALIZATION_PROMPTS[strategy].items():
                    existing = local_instructions.get(skill, "")
                    if instruction not in existing:
                        local_instructions[skill] = (
                            existing + "\n" + instruction if existing else instruction
                        )

        # 4. Agrega instruções para lacunas metacognitivas detectadas
        for gap_name in lacunas_detectadas:
            gap_key = gap_name.replace("_reviewer", "").replace("_specialist", "").replace("_auditor", "")
            if gap_key in SPECIALIZATION_PROMPTS:
                for skill, instruction in SPECIALIZATION_PROMPTS[gap_key].items():
                    existing = local_instructions.get(skill, "")
                    if instruction not in existing:
                        local_instructions[skill] = (
                            existing + "\n" + instruction if existing else instruction
                        )

        # 5. Define task_type como fallback explícito para a skill de desenvolvimento (coder)
        if "coder" not in local_instructions:
            type_instructions = SPECIALIZATION_PROMPTS.get(task_type, {}).get("coder", "")
            if type_instructions:
                local_instructions["coder"] = type_instructions

        # 6. Monta o payload estruturado de resposta
        composicao = {
            "task_type": task_type,
            "strategies": list(strategies),
            "technologies": list(technologies),
            "total_agentes": len(self.graph.nodes) if hasattr(self.graph, "nodes") else 0,
            "agentes_por_tipo": self._count_by_type(),
            "lacunas_detectadas": lacunas_detectadas,
            "specialization_instructions": local_instructions,
            "note": (
                "Abordagem híbrida: as especializações são injetadas via contexto "
                "nos nós existentes (coder, critic, tester). Nenhum nó duplicado foi criado."
            ),
        }

        # Sincroniza de forma atômica a persistência do histórico do objeto
        with self._lock:
            self.last_design = composicao

        logger.info("-" * 60)
        if local_instructions:
            logger.info("[MetaAgentDesigner] ✅ %d especializações ativas prontas.", len(local_instructions))
            for skill, instr in local_instructions.items():
                logger.info("  🎯 '%s': %s...", skill, instr[:50].replace("\n", " "))
        return composicao

    def get_specialization_for(self, skill: str) -> str:
        """Busca atômica de instruções para uma skill específica sob lock."""
        with self._lock:
            if not self.last_design:
                return ""
            instructions_map = self.last_design.get("specialization_instructions", {})
            return instructions_map.get(skill, "")

    def get_evolution_strategies(self) -> List[str]:
        with self._lock:
            if not self.last_design:
                return ["general", "fast"]
            return list(set(self.last_design.get("strategies", []) + ["general", "fast"]))

    def _count_by_type(self) -> Dict[str, int]:
        counts = {}
        try:
            nodes_map = getattr(self.graph, "nodes", {})
            for node in nodes_map.values():
                t = getattr(node, "node_type", "general") or "general"
                counts[t] = counts.get(t, 0) + 1
        except Exception:
            pass
        return counts

    def get_composition_report(self) -> str:
        with self._lock:
            if not self.last_design:
                return "Nenhum design foi realizado ainda no ecossistema."

            lines = [
                "=" * 60,
                "🏗️  RELATÓRIO DE ESPECIALIZAÇÃO COGNITIVA DA EQUIPE",
                "=" * 60,
                f"Tipo de tarefa: {self.last_design['task_type']}",
                f"Estratégias: {', '.join(self.last_design['strategies'])}",
                f"Tecnologias: {', '.join(self.last_design['technologies']) or 'Nenhuma detectada'}",
                f"Total de agentes ativos no DAG: {self.last_design['total_agentes']}",
                "",
                "Especializações injetadas ativas por barramento de skill:",
            ]
            for skill, instr in self.last_design.get("specialization_instructions", {}).items():
                lines.append(f"  🎯 {skill}: {instr[:60].strip().replace('\n', ' ')}...")
            lines.append("")
            lines.append(self.last_design.get("note", ""))
            lines.append("=" * 60)
            return "\n".join(lines)

# ==============================================================================
# ORQUESTRADOR DO LOOP AUTO-EVOLUTIVO (CORRIGIDO)
# ==============================================================================
from iaglobal.evolution.reward_aggregator import reward_aggregator, RewardMetrics
from iaglobal.evolution.same_engine import same_pool, rewrite_prompt
from iaglobal.evolution.skills.dynamic_registry import dynamic_registry

def fechar_ciclo_auto_evolutivo(agent_name: str, skill_atual: Any, resultado_execucao: dict, task_type: str = "general"):
    """
    Consome os resultados operacionais da execução do Grafo e aciona
    o loop fechado de auto-regulação econômica e mutação genética.
    """
    # 1. Coleta e normaliza a telemetria da execução
    metrics = RewardMetrics(
        success=resultado_execucao.get("success", False),
        latency_ms=resultado_execucao.get("latency_ms", 1000.0),
        cost_usd=resultado_execucao.get("cost_usd", 0.0),
        error_type=resultado_execucao.get("error")
    )
    
    # 2. Calcula a nota métrica de feedback (Ciclo metabólico da Betaína)
    reward = reward_aggregator.calculate_reward(metrics)
    
    # 3. CORREÇÃO DO BUG 1: Sincroniza os argumentos com a assinatura real de meta_evolver.py
    # Passamos os scores brutos fictícios ou derivados para simular o delta de melhoria
    score_before = 50.0
    score_after = score_before + (reward * 10.0) # Converte a nota [-1.0, 2.0] num ganho proporcional
    improvement = score_after - score_before
    
    # Registra o teste atômico na telemetria hiper-heurística
    from iaglobal.evolution.meta_evolver import EvolutionParams
    meta_evolver.record_trial(params=EvolutionParams(), improvement=improvement, task_type=task_type)
    
    # 4. Avalia a necessidade de mutação por falha de contrato
    if not metrics.success:
        # CORREÇÃO DO BUG 2: Fallback defensivo para skills estáticas que não possuem .template_prompt
        prompt_base = getattr(skill_atual, "template_prompt", "")
        if not prompt_base and hasattr(skill_atual, "description"):
            prompt_base = skill_atual.description  # Fallback caso seja uma skill nativa estrutural
            
        # Gasta créditos SAMe para metilar/alterar o prompt através da LLM
        novo_prompt = rewrite_prompt(
            agent_name=agent_name, 
            current_prompt=prompt_base, 
            error_history=metrics.error_type or "Falha de consistência de contrato ou quebra de AST."
        )
        
        if novo_prompt:
            try:
                # Calcula a nova versão semântica de evolução (ex: v1 -> v1.1)
                versao_limpa = float(skill_atual.version.replace("v", "")) if hasattr(skill_atual, "version") else 1.0
                nova_versao = f"v{versao_limpa + 0.1:.1f}"
                
                # Se a skill aceitar derivação de cópias, gera a nova variante mutada
                if hasattr(skill_atual, "derivar_nova_versao"):
                    skill_mutada = skill_atual.derivar_nova_versao(
                        template_prompt=novo_prompt,
                        version=nova_versao
                    )
                else:
                    # Fallback polimórfico se for uma dataclass padrão congelada (frozen)
                    from iaglobal.evolution.skills.skill import Skill
                    skill_mutada = Skill(
                        name=skill_atual.name,
                        description=skill_atual.description,
                        inputs=list(skill_atual.inputs),
                        outputs=list(skill_atual.outputs),
                        constraints=list(skill_atual.constraints),
                        execution_policy=skill_atual.execution_policy,
                        version=nova_versao,
                        author="evolution_engine"
                    )
                    # Injeta dinamicamente a propriedade para o dynamic_registry salvar os metadados do prompt
                    object.__setattr__(skill_mutada, "template_prompt", novo_prompt)
                
                # 5. Salva a nova versão diretamente no barramento persistente do SQLite
                dynamic_registry.register_dynamic(skill_mutada, template_type="llm", template_prompt=novo_prompt)
                logger.info(f"✨ [EVOLUÇÃO] Loop fechado! Skill '{skill_atual.name}' sofreu mutação para {nova_versao} com sucesso.")
                
            except Exception as e:
                logger.error(f"[EVOLUÇÃO] Erro ao salvar variante genética da skill: {e}")
    else:
        # Se a execução foi impecável e obteve sucesso, recompensa o agente com créditos de SAMe
        # permitindo que ele acumule energia metabólica para mutações futuras mais complexas
        same_pool.recharge(agent_name, amount=15)
