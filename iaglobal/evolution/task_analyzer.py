"""TaskAnalyzer — extrai estratégias específicas do prompt para criar agentes especializados."""

import re
from typing import Dict, List, Set


class TaskAnalyzer:
    """
    Analisa o prompt da tarefa e deriva estratégias, palavras-chave,
    tecnologias e skills necessárias para respondê-la.

    Permite que o EvolutionEngine crie agentes com habilidades
    específicas para a tarefa vigente.
    """

    # Mapa de palavras-chave → estratégias
    KEYWORD_STRATEGIES: Dict[str, str] = {
        # Web / Frontend
        "django": "web_development",
        "flask": "web_development",
        "fastapi": "web_development",
        "html": "web_development",
        "css": "web_development",
        "javascript": "web_development",
        "pagina web": "web_development",
        "pagina": "web_development",
        "site": "web_development",
        "frontend": "web_development",
        "web": "web_development",
        "api rest": "api_design",
        "rest api": "api_design",
        "endpoint": "api_design",
        # Formulários / Contato
        "form": "form_handling",
        "formulario": "form_handling",
        "contato": "form_handling",
        "contact": "form_handling",
        "email": "form_handling",
        "enviar": "form_handling",
        "submit": "form_handling",
        # Tema / Design
        "tema": "theming",
        "theme": "theming",
        "dark": "theming",
        "escuro": "theming",
        "tema escuro": "theming",
        "dark mode": "theming",
        "bootstrap": "theming",
        "tailwind": "theming",
        # Banco de Dados
        "banco": "database",
        "sqlite": "database",
        "postgres": "database",
        "postgresql": "database",
        "mysql": "database",
        "mongodb": "database",
        "sqlalchemy": "database",
        "orm": "database",
        "modelo": "database",
        # Blockchain
        "blockchain": "blockchain",
        "bloco genesis": "blockchain",
        "genesis": "blockchain",
        "sha3": "blockchain",
        "sha256": "blockchain",
        "hash": "blockchain",
        "crypto": "blockchain",
        # Testes
        "test": "testing",
        "teste": "testing",
        "testar": "testing",
        "pytest": "testing",
        "unittest": "testing",
        "tdd": "testing",
        # CLI / Scripts
        "cli": "cli_tool",
        "linha de comando": "cli_tool",
        "command line": "cli_tool",
        "script": "cli_tool",
        # Autenticação
        "login": "authentication",
        "auth": "authentication",
        "autenticacao": "authentication",
        "senha": "authentication",
        "password": "authentication",
        "jwt": "authentication",
        "oauth": "authentication",
        # Segurança
        "sql injection": "security",
        "xss": "security",
        "csrf": "security",
        "seguranca": "security",
        "segurança": "security",
        "security": "security",
        "vazamento": "security",
        "criptografia": "security",
        "encrypt": "security",
        # UX / Acessibilidade
        "ux": "ux",
        "user experience": "ux",
        "acessibilidade": "ux",
        "accessibility": "ux",
        "usabilidade": "ux",
        "fluxo do usuario": "ux",
        "flow": "ux",
        # Arquitetura
        "arquitetura": "architecture",
        "architecture": "architecture",
        "escalabilidade": "architecture",
        "scalability": "architecture",
        "acoplamento": "architecture",
        "design pattern": "architecture",
        "solid": "architecture",
        "clean architecture": "architecture",
        # Performance
        "performance": "performance",
        "otimizacao": "performance",
        "cache": "performance",
        "slow": "performance",
        "lazy loading": "performance",
        # Docker / DevOps
        "docker": "devops",
        "container": "devops",
        "deploy": "devops",
        "devops": "devops",
        "nginx": "devops",
        "docker-compose": "devops",
    }

    # Tecnologias detectáveis
    TECHNOLOGY_PATTERNS: Dict[str, str] = {
        r'django': 'Django',
        r'flask|flask ': 'Flask',
        r'fastapi': 'FastAPI',
        r'react|reactjs|react\.js': 'React',
        r'vue|vuejs|vue\.js': 'Vue.js',
        r'node|nodejs|node\.js': 'Node.js',
        r'typescript': 'TypeScript',
        r'bootstrap': 'Bootstrap',
        r'tailwind': 'Tailwind CSS',
        r'postgres|postgresql': 'PostgreSQL',
        r'mysql': 'MySQL',
        r'mongodb|mongo': 'MongoDB',
        r'sqlite': 'SQLite',
        r'docker': 'Docker',
        r'kubernetes|k8s': 'Kubernetes',
        r'python': 'Python',
        r'sqlalchemy': 'SQLAlchemy',
    }

    # Skills que devem ser priorizadas por tecnologia
    TECHNOLOGY_SKILLS: Dict[str, List[str]] = {
        'Django': ['web_development', 'form_handling', 'theming', 'database'],
        'Flask': ['web_development', 'form_handling', 'database'],
        'FastAPI': ['api_design', 'database'],
        'React': ['web_development', 'theming'],
        'Bootstrap': ['theming', 'web_development'],
        'Tailwind CSS': ['theming', 'web_development'],
        'SQLite': ['database'],
        'PostgreSQL': ['database'],
        'Docker': ['devops'],
    }

    @classmethod
    def analyze(cls, task: str) -> Dict:
        """
        Analisa o prompt e retorna um dicionário com:
        - strategies: conjunto de estratégias relevantes
        - technologies: tecnologias detectadas
        - keywords: palavras-chave encontradas
        - task_type: tipo principal da tarefa
        - agentes_recomendados: agentes especializados sugeridos
        """
        task_lower = task.lower()
        strategies: Set[str] = set()
        technologies: Set[str] = set()
        keywords: Set[str] = set()

        for keyword, strategy in cls.KEYWORD_STRATEGIES.items():
            if keyword in task_lower:
                strategies.add(strategy)
                keywords.add(keyword)

        for pattern, tech in cls.TECHNOLOGY_PATTERNS.items():
            if re.search(pattern, task_lower):
                technologies.add(tech)
                tech_strategies = cls.TECHNOLOGY_SKILLS.get(tech, [])
                strategies.update(tech_strategies)

        task_type = cls._classify_task_type(strategies, keywords)

        agentes_recomendados = cls._recomendar_agentes(task_type, strategies, technologies)

        return {
            "strategies": strategies,
            "technologies": technologies,
            "keywords": keywords,
            "task_type": task_type,
            "agentes_recomendados": agentes_recomendados,
        }

    @classmethod
    def _classify_task_type(cls, strategies: Set[str], keywords: Set[str]) -> str:
        if any(k in keywords for k in ["bloco genesis", "blockchain", "genesis"]):
            return "blockchain"
        if any(s in strategies for s in ["web_development", "form_handling", "theming"]):
            return "web"
        if "api_design" in strategies:
            return "api"
        if "cli_tool" in strategies:
            return "cli"
        if "testing" in strategies:
            return "testing"
        if "database" in strategies:
            return "database"
        if "authentication" in strategies:
            return "auth"
        if "devops" in strategies:
            return "devops"
        if "blockchain" in strategies:
            return "blockchain"
        return "general"

    @classmethod
    def _recomendar_agentes(cls, task_type: str, strategies: Set[str],
                            technologies: Set[str]) -> List[Dict]:
        agentes = []

        if "web_development" in strategies:
            agentes.append({
                "nome": "web_specialist",
                "descricao": f"Gera código web ({', '.join(technologies) if technologies else 'HTML/CSS/JS'})",
                "skill_base": "coder",
                "estrategias": ["web_development", "theming"],
            })
        if "form_handling" in strategies:
            agentes.append({
                "nome": "form_handler",
                "descricao": "Implementa formulários com validação, CSRF e envio de email",
                "skill_base": "coder",
                "estrategias": ["form_handling"],
            })
        if "theming" in strategies:
            agentes.append({
                "nome": "theming_specialist",
                "descricao": "Aplica tema escuro e design responsivo com CSS/Bootstrap/Tailwind",
                "skill_base": "coder",
                "estrategias": ["theming"],
            })
        if "database" in strategies:
            agentes.append({
                "nome": "database_modeler",
                "descricao": "Cria modelos, migrações e consultas ORM",
                "skill_base": "coder",
                "estrategias": ["database"],
            })
        if "api_design" in strategies:
            agentes.append({
                "nome": "api_designer",
                "descricao": "Projeta endpoints REST com validação e documentação",
                "skill_base": "coder",
                "estrategias": ["api_design"],
            })
        if "blockchain" in strategies:
            agentes.append({
                "nome": "blockchain_developer",
                "descricao": "Gera blocos genesis, hashes SHA3 e estruturas blockchain",
                "skill_base": "coder",
                "estrategias": ["blockchain"],
            })
        if task_type == "web" or "web_development" in strategies:
            agentes.append({
                "nome": "critic_web",
                "descricao": "Valida código web: boas práticas, acessibilidade, responsividade",
                "skill_base": "critic",
                "estrategias": ["web_development"],
            })
            agentes.append({
                "nome": "tester_web",
                "descricao": "Gera testes para views, formulários e templates",
                "skill_base": "tester",
                "estrategias": ["web_development"],
            })
        if "security" in strategies:
            agentes.append({
                "nome": "security_reviewer",
                "descricao": "Revisa SQL Injection, XSS, CSRF, autenticação e vazamento de dados",
                "skill_base": "critic",
                "estrategias": ["security"],
            })
        if "ux" in strategies:
            agentes.append({
                "nome": "ux_reviewer",
                "descricao": "Analisa fluxo do usuário, acessibilidade e experiência mobile",
                "skill_base": "critic",
                "estrategias": ["ux"],
            })
        if "architecture" in strategies:
            agentes.append({
                "nome": "architecture_reviewer",
                "descricao": "Avalia acoplamento, SOLID, escalabilidade e padrões de projeto",
                "skill_base": "critic",
                "estrategias": ["architecture"],
            })
        if "performance" in strategies:
            agentes.append({
                "nome": "performance_auditor",
                "descricao": "Audita performance, otimização e cache",
                "skill_base": "critic",
                "estrategias": ["performance"],
            })
        if "authentication" in strategies:
            agentes.append({
                "nome": "security_reviewer",
                "descricao": "Revisa autenticação, tokens JWT, OAuth e proteção de rotas",
                "skill_base": "critic",
                "estrategias": ["authentication", "security"],
            })

        if not agentes:
            agentes.append({
                "nome": "generalist",
                "descricao": "Agente genérico para tarefas sem classificação específica",
                "skill_base": "coder",
                "estrategias": ["general"],
            })

        return agentes

    @classmethod
    def extract_technologies_summary(cls, technologies: Set[str]) -> str:
        if not technologies:
            return "tecnologia indefinida"
        return ", ".join(sorted(technologies))
