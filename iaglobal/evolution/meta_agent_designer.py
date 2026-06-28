# iaglobal/evolution/meta_agent_designer.py

import logging
from typing import Any, Dict

from iaglobal.graphs.execution_graph import ExecutionGraph

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

    def design_team(self, task: str) -> Dict[str, Any]:
        """Analisa a task e retorna as especializações e lacunas detectadas."""
        task_lower = task.lower()
        detected = set()
        lacunas = []

        # Mapeia palavras-chave da task para especialidades
        keyword_map = {
            "security": ["security", "segurança", "auth", "login", "jwt", "oauth", "password",
                         "criptografia", "csrf", "xss", "sql injection", "sanitize"],
            "ux": ["ux", "ui", "interface", "acessibilidade", "aria", "wcag", "responsive",
                   "mobile", "user experience", "frontend"],
            "architecture": ["architecture", "arquitetura", "microservices", "ddd", "clean arch",
                             "solid", "design pattern", "acoplamento", "escalabilidade"],
            "performance": ["performance", "latency", "cache", "n+1", "bundle", "otimização",
                            "slow", "bottleneck", "benchmark"],
            "theming": ["tema", "dark mode", "theme", "escuro", "light", "theming", "css variables"],
            "form_handling": ["form", "formulário", "validation", "csrf token", "input mask"],
            "web_development": ["web", "html", "css", "javascript", "frontend", "backend",
                                "flask", "django", "react", "api rest"],
            "database": ["database", "banco de dados", "sql", "nosql", "orm", "migração",
                         "schema", "query", "índice", "index"],
            "api_design": ["api", "rest", "endpoint", "graphql", "rpc", "swagger",
                           "openapi", "rate limit"],
            "documentation": ["documentação", "documentation", "readme", "wiki", "pdf",
                              "manual", "guia", "tutorial"],
        }

        for spec, keywords in keyword_map.items():
            if any(kw in task_lower for kw in keywords):
                detected.add(spec)
                lacunas.append(f"Considerar especialização '{spec}' para a task")

        if not detected:
            detected.add("general")
            lacunas.append("Nenhuma especialização clara detectada — usar perfil generalista")

        return {
            "strategies": list(detected),
            "lacunas_detectadas": lacunas,
        }


