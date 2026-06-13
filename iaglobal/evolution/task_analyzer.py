# iaglobal/evolution/skills/task_analyzer.py

import re
from typing import Dict, List, Set, Any
from iaglobal.utils.logger import logger

class TaskAnalyzer:
    """
    Analisa o prompt da tarefa de forma atómica (Thread-Safe e Otimizada),
    derivando estratégias e gerando agentes especialistas sincronizados com o catálogo de Skills.
    """

    # 🗺️ Mapeamento expandido e internacionalizado para resiliência de parsing
    KEYWORD_STRATEGIES: Dict[str, List[str]] = {
        # Desenvolvimento Web e APIs
        "django": ["web_development"],
        "flask": ["web_development"],
        "fastapi": ["web_development", "api_design"],
        "html": ["web_development"],
        "css": ["web_development"],
        "javascript": ["web_development"],
        "typescript": ["web_development"],
        "pagina web": ["web_development"],
        "webpage": ["web_development"],
        "site": ["web_development"],
        "frontend": ["web_development"],
        "backend": ["web_development"],
        "api rest": ["api_design"],
        "rest api": ["api_design"],
        "endpoint": ["api_design"],
        "graphql": ["api_design"],
        
        # Arquitetura e Dados
        "banco de dados": ["database"],
        "database": ["database"],
        "sql": ["database"],
        "nosql": ["database"],
        "postgres": ["database"],
        "arquitetura": ["architecture"],
        "architecture": ["architecture"],
        "solid": ["architecture"],
        "clean code": ["architecture"],
        
        # Documentação e Requisitos
        "receita": ["documentation"],
        "recipe": ["documentation"],
        "pdf": ["documentation"],
        "relatorio": ["documentation"],
        "report": ["documentation"],
        "documento": ["documentation"],
        "doc": ["documentation"],
        "markdown": ["documentation"],
        
        # Segurança e Cibersegurança
        "autenticacao": ["authentication", "security"],
        "authentication": ["authentication", "security"],
        "login": ["authentication"],
        "token": ["authentication"],
        "jwt": ["authentication"],
        "oauth": ["authentication"],
        "criptografia": ["security"],
        "cryptography": ["security"],
        "seguranca": ["security"],
        "security": ["security"],
        "hack": ["security"],
        "vulnerabilidade": ["security"],
        "vulnerability": ["security"],
        
        # Performance e Auditoria
        "performance": ["performance"],
        "otimizacao": ["performance"],
        "optimization": ["performance"],
        "lento": ["performance"],
        "slow": ["performance"],
        "cache": ["performance"],
        "memory leak": ["performance"],
    }

    # 🔥 RESOLUÇÃO DO BUG 2 (Otimização ReDoS): Pré-compilação do dicionário de busca em Regex
    # Constrói um único padrão compilado em memória para busca ultra-rápida
    _REGEX_PATTERNS = {
        kw: re.compile(rf"\b{re.escape(kw)}\b", re.IGNORECASE) for kw in KEYWORD_STRATEGIES
    }

    @classmethod
    def analyze(cls, prompt: str) -> Dict[str, Any]:
        """
        Executa a varredura do prompt e extrai estratégias e tecnologias.
        """
        if not prompt:
            return {"strategies": set(), "technologies": set()}

        strategies: Set[str] = set()
        technologies: Set[str] = set()

        # Executa matches rápidos usando os patterns pré-compilados
        for kw, regex in cls._REGEX_PATTERNS.items():
            if regex.search(prompt):
                # Associa as estratégias mapeadas
                for strategy in cls.KEYWORD_STRATEGIES[kw]:
                    strategies.add(strategy)
                
                # Coleta a palavra-chave como indicador tecnológico corporativo
                technologies.add(kw.lower())

        logger.debug(f"[TASK-ANALYZER] Análise concluída. Estratégias identificadas: {list(strategies)}")
        return {
            "strategies": strategies,
            "technologies": technologies
        }

    @classmethod
    def derive_agents(cls, strategies: Set[str]) -> List[Dict[str, Any]]:
        """
        Gera a equipe de agentes sob medida.
        As chaves são resolvidas dinamicamente de skill.py usando Lazy Import
        para impedir colisões e importações circulares em tempo de execução.
        """
        # 🔄 LAZY IMPORT: O Python só lê este arquivo quando a função for de fato executada,
        # após todo o ecossistema e registries já estarem carregados na memória RAM.
        from iaglobal.evolution.skills.skill import (
            SKILL_CODER,
            SKILL_CRITIC,
            SKILL_SECURITY,
            SKILL_PERFORMANCE,
            SKILL_ARCHITECT,
            SKILL_DOCUMENTATION,
            SKILL_API_DESIGN
        )

        agentes: List[Dict[str, Any]] = []

        if "web_development" in strategies or "api_design" in strategies:
            agentes.append({
                "nome": "web_developer",
                "descricao": "Especialista em construir aplicações web, endpoints, APIs e integrações",
                "skill_base": SKILL_CODER.name,  # Segurança total de tipo, sem strings soltas!
                "estrategias": ["web_development", "api_design"],
            })

        if "database" in strategies:
            agentes.append({
                "nome": "database_architect",
                "descricao": "Especialista em modelagem de dados, otimização de queries e queries SQL",
                "skill_base": SKILL_ARCHITECT.name,
                "estrategias": ["database"],
            })

        if "documentation" in strategies:
            agentes.append({
                "nome": "technical_writer",
                "descricao": "Especialista em gerar documentação limpa, relatórios estruturados e manuais",
                "skill_base": SKILL_DOCUMENTATION.name,
                "estrategias": ["documentation"],
            })

        if "architecture" in strategies:
            agentes.append({
                "nome": "architecture_reviewer",
                "descricao": "Avalia acoplamento, princípios SOLID, escalabilidade e design patterns",
                "skill_base": SKILL_CRITIC.name,
                "estrategias": ["architecture"],
            })

        if "performance" in strategies:
            agentes.append({
                "nome": "performance_auditor",
                "descricao": "Audita gargalos de processamento, vazamentos de memória e políticas de cache",
                "skill_base": SKILL_PERFORMANCE.name,
                "estrategias": ["performance"],
            })

        if "security" in strategies or "authentication" in strategies:
            agentes.append({
                "nome": "security_reviewer",
                "descricao": "Revisa vetores de ataque, autenticação de tokens JWT, OAuth e proteção de rotas",
                "skill_base": SKILL_SECURITY.name,
                "estrategias": ["authentication", "security"],
            })

        # 🛡️ FALLBACK CONTROLADO
        if not agentes:
            agentes.append({
                "nome": "generalist",
                "descricao": "Agente genérico atribuído para resolver problemas sem classificação estrita",
                "skill_base": SKILL_CODER.name,
                "estrategias": ["general"],
            })

        return agentes

    @classmethod
    def extract_technologies_summary(cls, technologies: Set[str]) -> str:
        if not technologies:
            return "tecnologia indefinida"
        return ", ".join(sorted(technologies))
