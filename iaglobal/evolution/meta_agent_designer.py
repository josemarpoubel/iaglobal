"""MetaAgentDesigner — arquiteta a composição da equipe de agentes para cada tarefa.

Abordagem híbrida: em vez de criar N nós duplicados no DAG,
gera instruções de especialização que são injetadas via contexto
nos poucos nós de execução existentes (coder, critic, tester).

Fluxo:
    Prompt → TaskAnalyzer → MetaAgentDesigner → Gera specialization_instructions
                                              → (NÃO cria nós no DAG)
    Essas instruções são injetadas no ctx do pipeline e cada skill
    ajusta seu prompt de acordo com a especialidade detectada.
"""

import logging
from typing import Dict, List, Optional

from iaglobal.graphs.execution_graph import ExecutionGraph
from iaglobal.evolution.task_analyzer import TaskAnalyzer
from iaglobal.evolution.agents.gap_analyzer import GapAnalyzer

logger = logging.getLogger(__name__)

# Mapa: especialidade → instruções para cada skill
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
}


class MetaAgentDesigner:
    """
    🏗️ MetaAgentDesigner — Projeta a equipe ideal de agentes para a tarefa.

    Abordagem híbrida:
    - NÃO cria nós duplicados no DAG
    - Gera instruções de especialização para cada skill
    - As instruções são injetadas no contexto de execução do pipeline
    """

    def __init__(self, graph: ExecutionGraph):
        self.graph = graph
        self.last_design: Optional[Dict] = None
        self.specialization_instructions: Dict[str, str] = {}

    def design_team(self, task: str) -> Dict:
        """
        Projeta a composição ideal da equipe para a tarefa.

        Em vez de criar N nós, gera specialization_instructions
        que serão injetadas no contexto do pipeline.

        Returns:
            Dict com análise e instruções de especialização
        """
        logger.info("=" * 60)
        logger.info("🏗️ [MetaAgentDesigner] Projetando especialização para: %s...", task[:80])
        logger.info("=" * 60)

        # 1. Análise do prompt
        analysis = TaskAnalyzer.analyze(task)
        task_type = analysis["task_type"]
        strategies = analysis["strategies"]
        technologies = analysis["technologies"]

        logger.info(
            "[MetaAgentDesigner] Análise: type=%s strategies=%s techs=%s",
            task_type, strategies, technologies
        )

        # 2. Detecta lacunas via GapAnalyzer (apenas para log)
        lacunas = GapAnalyzer.detect_gaps(task, self.graph)
        lacunas_detectadas = [g["nome"] for g in lacunas]

        # 3. Gera instruções de especialização baseadas nas estratégias detectadas
        self.specialization_instructions = {}
        for strategy in strategies:
            base_key = strategy  # ex: "web_development", "security", "theming"
            if base_key in SPECIALIZATION_PROMPTS:
                for skill, instruction in SPECIALIZATION_PROMPTS[base_key].items():
                    existing = self.specialization_instructions.get(skill, "")
                    if instruction not in existing:
                        self.specialization_instructions[skill] = (
                            existing + "\n" + instruction if existing else instruction
                        )

        # 4. Gera instruções para lacunas detectadas (gap analyzer)
        for gap in lacunas:
            nome = gap["nome"]
            gap_key = nome.replace("_reviewer", "").replace("_specialist", "").replace("_auditor", "")
            if gap_key in SPECIALIZATION_PROMPTS:
                for skill, instruction in SPECIALIZATION_PROMPTS[gap_key].items():
                    existing = self.specialization_instructions.get(skill, "")
                    if instruction not in existing:
                        self.specialization_instructions[skill] = (
                            existing + "\n" + instruction if existing else instruction
                        )

        # 5. Define task_type como fallback para coder
        if "coder" not in self.specialization_instructions:
            type_instructions = SPECIALIZATION_PROMPTS.get(task_type, {}).get("coder", "")
            if type_instructions:
                self.specialization_instructions["coder"] = type_instructions

        # 6. Monta resultado
        composicao = {
            "task_type": task_type,
            "strategies": list(strategies),
            "technologies": list(technologies),
            "total_agentes": len(self.graph.nodes),
            "agentes_por_tipo": self._count_by_type(),
            "lacunas_detectadas": lacunas_detectadas,
            "specialization_instructions": dict(self.specialization_instructions),
            "note": (
                "Abordagem híbrida: as especializações são injetadas via contexto "
                "nos nós existentes (coder, critic, tester). Nenhum nó duplicado foi criado."
            ),
        }

        self.last_design = composicao

        logger.info("-" * 60)
        if self.specialization_instructions:
            logger.info(
                "[MetaAgentDesigner] ✅ %d instruções de especialização geradas:",
                len(self.specialization_instructions)
            )
            for skill, instr in self.specialization_instructions.items():
                logger.info("  🎯 '%s': %s...", skill, instr[:60].replace("\n", " "))
        else:
            logger.info("[MetaAgentDesigner] ℹ️  Nenhuma especialização necessária para esta task")
        if lacunas_detectadas:
            logger.info("  📋 Lacunas detectadas (apenas log): %s", lacunas_detectadas)
        logger.info("-" * 60)

        return composicao

    def get_specialization_for(self, skill: str) -> str:
        """Retorna as instruções de especialização para uma skill."""
        return self.specialization_instructions.get(skill, "")

    def get_evolution_strategies(self) -> List[str]:
        """Retorna as estratégias de evolução recomendadas com base no último design."""
        if not self.last_design:
            return ["general", "fast"]
        return list(set(
            self.last_design.get("strategies", []) + ["general", "fast"]
        ))

    def _count_by_type(self) -> Dict[str, int]:
        counts = {}
        for node in self.graph.nodes.values():
            t = node.node_type or "general"
            counts[t] = counts.get(t, 0) + 1
        return counts

    def get_composition_report(self) -> str:
        if not self.last_design:
            return "Nenhum design foi realizado ainda."

        lines = [
            "=" * 60,
            "🏗️  RELATÓRIO DE ESPECIALIZAÇÃO DA EQUIPE",
            "=" * 60,
            f"Tipo de tarefa: {self.last_design['task_type']}",
            f"Estratégias: {', '.join(self.last_design['strategies'])}",
            f"Tecnologias: {', '.join(self.last_design['technologies']) or 'Nenhuma'}",
            f"Total de agentes no DAG: {self.last_design['total_agentes']}",
            "",
            "Especializações ativas por skill:",
        ]
        for skill, instr in self.last_design.get("specialization_instructions", {}).items():
            lines.append(f"  🎯 {skill}: {instr[:80].strip()}...")
        if self.last_design.get("lacunas_detectadas"):
            lines.append("")
            lines.append(f"Lacunas detectadas: {', '.join(self.last_design['lacunas_detectadas'])}")
        lines.append("")
        lines.append(self.last_design.get("note", ""))
        lines.append("=" * 60)
        return "\n".join(lines)
