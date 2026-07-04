# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
iaglobal/agents/prompt_improver.py

PromptImprover v2 — Pipeline de melhoria de prompts em 5 estágios:

  1. DetectorEngine     → análise semântica multi-domínio com scoring (n-gramas)
  2. ConstraintRegistry → constraints por domínio com severidade e condições
  3. PersonaComposer    → persona composta para tarefas multi-domínio
  4. DecompositionEngine→ decomposição adaptativa baseada em complexidade real
  5. ReflectionEngine   → auto-crítica dinâmica baseada em domínio + histórico MTA

Integrado com:
  - AcetylcholineBus   → publica eventos de melhoria
  - MTARecycler        → injeta exemplos negativos de falhas anteriores
  - SkillStore         → aproveita skills de produção como exemplos positivos
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from iaglobal.utils.logger import logger

# Importações opcionais — o PromptImprover funciona sem elas,
# mas se estiverem disponíveis, ativa integração biológica.
try:
    from iaglobal.core.acetylcholine_bus import bus, Signal
    _BUS_AVAILABLE = True
except ImportError:
    _BUS_AVAILABLE = False

try:
    from iaglobal.evolution.mta_recycler import MTARecycler
    _MTA_AVAILABLE = True
except ImportError:
    _MTA_AVAILABLE = False

try:
    from iaglobal.evolution.skills.skill_registry import skill_registry
    _SKILL_REGISTRY_AVAILABLE = True
except ImportError:
    _SKILL_REGISTRY_AVAILABLE = False


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class PromptMode(str, Enum):
    FULL     = "full"      # máxima qualidade, sem limite de tokens
    COMPACT  = "compact"   # modelos pequenos/locais, tokens limitados
    CHAIN    = "chain"     # para encadeamento de prompts (sem persona)
    DEBUG    = "debug"     # inclui rastreamento interno da melhoria


class ConstraintSeverity(str, Enum):
    CRITICAL  = "critical"   # sempre incluída
    HIGH      = "high"       # incluída se domínio detectado com score > 0.5
    MEDIUM    = "medium"     # incluída em modo FULL
    LOW       = "low"        # incluída apenas se houver espaço


class ComplexityLevel(str, Enum):
    TRIVIAL  = "trivial"    # score 0–1
    SIMPLE   = "simple"     # score 2–3
    MODERATE = "moderate"   # score 4–6
    COMPLEX  = "complex"    # score 7–10
    CRITICAL = "critical"   # score 11+


# ---------------------------------------------------------------------------
# DataClasses
# ---------------------------------------------------------------------------

@dataclass
class Constraint:
    text: str
    severity: ConstraintSeverity
    condition: Optional[str] = None   # ex: "error_context contains 'sql'"
    applies_to_modes: List[PromptMode] = field(
        default_factory=lambda: [PromptMode.FULL, PromptMode.COMPACT, PromptMode.CHAIN]
    )


@dataclass
class DomainProfile:
    name: str
    keywords: Dict[str, float]          # token → peso
    anti_keywords: List[str]
    constraints: List[Constraint]
    persona_full: str
    persona_compact: str
    reflection_checks: List[str]        # perguntas específicas de auto-crítica

    def score(self, tokens: Set[str]) -> float:
        total = sum(w for kw, w in self.keywords.items() if kw in tokens)
        penalty = sum(0.3 for ak in self.anti_keywords if ak in tokens)
        return max(0.0, total - penalty)

    def get_constraints(
        self,
        mode: PromptMode,
        error_context: str = "",
        min_severity: ConstraintSeverity = ConstraintSeverity.MEDIUM,
    ) -> List[Constraint]:
        severity_order = [
            ConstraintSeverity.CRITICAL,
            ConstraintSeverity.HIGH,
            ConstraintSeverity.MEDIUM,
            ConstraintSeverity.LOW,
        ]
        min_idx = severity_order.index(min_severity)
        result = []
        for c in self.constraints:
            if mode not in c.applies_to_modes:
                continue
            sev_idx = severity_order.index(c.severity)
            if sev_idx > min_idx:
                continue
            if c.condition:
                if not self._eval_condition(c.condition, error_context):
                    continue
            result.append(c)
        return result

    @staticmethod
    def _eval_condition(condition: str, error_context: str) -> bool:
        """Avalia condições simples: 'error_context contains X'."""
        if condition.startswith("error_context contains"):
            term = condition.split("contains")[-1].strip().strip("'\"")
            return term.lower() in error_context.lower()
        return True


@dataclass
class ImprovementReport:
    original_length: int
    final_length: int
    mode: PromptMode
    detected_domains: List[Tuple[str, float]]
    complexity: ComplexityLevel
    complexity_score: int
    constraints_applied: int
    negative_examples_injected: int
    positive_examples_injected: int
    decomposed: bool
    reflection_checks: int
    mta_examples_used: bool
    skill_examples_used: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "original_length": self.original_length,
            "final_length": self.final_length,
            "mode": self.mode.value,
            "detected_domains": [(d, round(s, 3)) for d, s in self.detected_domains],
            "complexity": self.complexity.value,
            "complexity_score": self.complexity_score,
            "constraints_applied": self.constraints_applied,
            "negative_examples_injected": self.negative_examples_injected,
            "positive_examples_injected": self.positive_examples_injected,
            "decomposed": self.decomposed,
            "reflection_checks": self.reflection_checks,
        }


# ---------------------------------------------------------------------------
# Registry de Domínios
# ---------------------------------------------------------------------------

DOMAIN_REGISTRY: List[DomainProfile] = [

    DomainProfile(
        name="php",
        keywords={"php": 1.0, "laravel": 0.9, "symfony": 0.9, "wordpress": 0.8,
                  "composer": 0.7, "pdo": 0.9, "mysqli": 0.8},
        anti_keywords=[],
        persona_full=(
            "Você é um Desenvolvedor PHP Sênior com 15 anos de experiência "
            "em aplicações de alta disponibilidade, focado em segurança, "
            "código limpo e padrões PSR."
        ),
        persona_compact="Dev PHP Sênior (seguro, PSR).",
        constraints=[
            Constraint("Use prepared statements (PDO/MySQLi) — NUNCA interpole variáveis em SQL.", ConstraintSeverity.CRITICAL),
            Constraint("Sanitize entradas com filter_input() e FILTER_SANITIZE_*.", ConstraintSeverity.CRITICAL),
            Constraint("Valide CSRF com tokens de sessão em todos os formulários POST.", ConstraintSeverity.CRITICAL),
            Constraint("Configure header('Content-Type: application/json; charset=utf-8') em respostas JSON.", ConstraintSeverity.HIGH),
            Constraint("Nunca exponha paths do servidor, versões ou stack traces ao cliente.", ConstraintSeverity.HIGH),
            Constraint("Use password_hash()/password_verify() para senhas.", ConstraintSeverity.HIGH),
            Constraint("Implemente rate limiting em endpoints públicos.", ConstraintSeverity.MEDIUM),
            Constraint("Aplique princípio do menor privilégio em conexões de banco.", ConstraintSeverity.MEDIUM),
        ],
        reflection_checks=[
            "Todas as queries usam prepared statements?",
            "Há validação de CSRF nos formulários?",
            "Entradas estão sanitizadas antes de qualquer uso?",
            "Erros internos estão sendo logados mas não expostos ao cliente?",
        ],
    ),

    DomainProfile(
        name="web",
        keywords={"html": 0.7, "css": 0.6, "javascript": 0.7, "js": 0.6,
                  "frontend": 0.8, "web": 0.6, "site": 0.6, "pagina": 0.5,
                  "formulario": 0.5, "react": 0.8, "vue": 0.8, "angular": 0.8,
                  "dom": 0.7, "responsive": 0.7, "spa": 0.8, "email": 0.5,
                  "captar": 0.4, "landing": 0.5, "lead": 0.5, "newsletter": 0.5,
                  "dark": 0.4, "escuro": 0.4, "tema": 0.3},
        anti_keywords=["api", "backend", "servidor"],
        persona_full=(
            "Você é um Desenvolvedor Front-End Sênior especializado em "
            "interfaces modernas, acessíveis (WCAG 2.1) e seguras, com "
            "domínio em HTML5, CSS3 e JavaScript ES2024."
        ),
        persona_compact="Dev Front-End Sênior (acessível, seguro).",
        constraints=[
            Constraint("Escape toda saída HTML — use textContent, não innerHTML com dados externos.", ConstraintSeverity.CRITICAL),
            Constraint("Aplique Content-Security-Policy via meta ou header.", ConstraintSeverity.HIGH),
            Constraint("Nunca exponha tokens, chaves ou paths em código client-side.", ConstraintSeverity.CRITICAL),
            Constraint("Implemente atributos de acessibilidade (aria-*, role, alt) em elementos interativos.", ConstraintSeverity.HIGH),
            Constraint("Use HTTPS para todas as requisições externas.", ConstraintSeverity.HIGH),
            Constraint("Valide formulários tanto no cliente quanto declare validação server-side.", ConstraintSeverity.MEDIUM),
            Constraint("Evite dependências externas desnecessárias — minimize surface de ataque.", ConstraintSeverity.MEDIUM),
            Constraint("Mobile-first: meta viewport + CSS media queries (max-width: 768px) para responsividade.", ConstraintSeverity.CRITICAL),
        ],
        reflection_checks=[
            "Há risco de XSS via innerHTML ou dangerouslySetInnerHTML?",
            "Tokens ou chaves estão expostos no client-side?",
            "A interface é acessível via teclado?",
            "CSP está configurado?",
            "Meta viewport está presente para mobile?",
            "Media queries cobrem breakpoints mobile (768px) e tablet?",
        ],
    ),

    DomainProfile(
        name="api",
        keywords={"api": 0.9, "rest": 0.9, "graphql": 0.9, "endpoint": 0.9,
                  "http": 0.7, "json": 0.6, "webhook": 0.8, "rota": 0.7,
                  "route": 0.7, "servidor": 0.6, "backend": 0.7, "fastapi": 0.9,
                  "flask": 0.7, "django": 0.7, "express": 0.8},
        anti_keywords=["frontend", "html", "css"],
        persona_full=(
            "Você é um Engenheiro de API Sênior especializado em REST e "
            "GraphQL com foco em segurança, contratos claros, versionamento "
            "e observabilidade (OpenTelemetry)."
        ),
        persona_compact="Engenheiro API Sênior (REST, seguro, observável).",
        constraints=[
            Constraint("Retorne códigos HTTP semânticos (200, 201, 400, 401, 403, 404, 422, 500).", ConstraintSeverity.CRITICAL),
            Constraint("Valide toda entrada com schema (Pydantic, Joi ou equivalente).", ConstraintSeverity.CRITICAL),
            Constraint("Nunca retorne stack traces ou mensagens internas em produção.", ConstraintSeverity.CRITICAL),
            Constraint("Implemente autenticação (JWT/OAuth2) e autorização por recurso.", ConstraintSeverity.HIGH),
            Constraint("Inclua headers CORS com origens explícitas — nunca '*' em produção.", ConstraintSeverity.HIGH),
            Constraint("Versione a API via URL (/v1/) ou header Accept.", ConstraintSeverity.MEDIUM),
            Constraint("Adicione rate limiting e circuit breaker em chamadas externas.", ConstraintSeverity.MEDIUM),
            Constraint("Documente contratos com OpenAPI/Swagger inline.", ConstraintSeverity.LOW),
        ],
        reflection_checks=[
            "Todos os endpoints validam entrada antes de processar?",
            "Erros retornam mensagens genéricas ao cliente?",
            "Autenticação e autorização estão separadas?",
            "Rate limiting está implementado?",
        ],
    ),

    DomainProfile(
        name="dados",
        keywords={"dados": 0.8, "data": 0.8, "dataframe": 1.0, "csv": 0.7,
                  "pandas": 0.9, "polars": 0.9, "numpy": 0.7, "analise": 0.7,
                  "estatistica": 0.8, "visualizacao": 0.7, "grafico": 0.6,
                  "etl": 0.9, "pipeline": 0.6, "excel": 0.6, "sql": 0.5},
        anti_keywords=["api", "web", "frontend"],
        persona_full=(
            "Você é um Engenheiro de Dados Sênior especializado em pipelines "
            "ETL robustos, análise exploratória e visualização, com foco em "
            "qualidade de dados e reprodutibilidade."
        ),
        persona_compact="Engenheiro de Dados Sênior (ETL, qualidade).",
        constraints=[
            Constraint("Trate valores nulos/NaN explicitamente — nunca assuma dados limpos.", ConstraintSeverity.CRITICAL),
            Constraint("Valide tipos e ranges antes de operações numéricas/estatísticas.", ConstraintSeverity.CRITICAL),
            Constraint("Documente schema, colunas e tipos esperados no código.", ConstraintSeverity.HIGH),
            Constraint("Use tipos explícitos ao carregar CSVs (dtype=).", ConstraintSeverity.HIGH),
            Constraint("Evite loops sobre DataFrames — use operações vetorizadas.", ConstraintSeverity.HIGH),
            Constraint("Trate encoding de arquivos explicitamente (utf-8, latin-1).", ConstraintSeverity.MEDIUM),
            Constraint("Adicione logging de volume (linhas lidas/descartadas) em cada etapa do pipeline.", ConstraintSeverity.MEDIUM),
            Constraint("Use chunking para arquivos grandes (> 100MB).", ConstraintSeverity.LOW),
        ],
        reflection_checks=[
            "Há tratamento explícito de NaN/nulos em todas as colunas críticas?",
            "Tipos de dados foram validados antes de operações?",
            "O pipeline é reprodutível com os mesmos dados?",
            "Performance foi considerada (vetorização vs loops)?",
        ],
    ),

    DomainProfile(
        name="financeiro",
        keywords={"financeiro": 1.0, "mercado": 0.9, "acao": 0.9, "bolsa": 1.0,
                  "investimento": 0.9, "portfolio": 0.9, "trading": 1.0,
                  "yfinance": 1.0, "dividendo": 0.9, "retorno": 0.7,
                  "volatilidade": 0.9, "ibovespa": 1.0, "b3": 1.0,
                  "crypto": 0.8, "bitcoin": 0.8, "forex": 1.0, "dolar": 0.8,
                  "backtesting": 1.0, "risco": 0.7},
        anti_keywords=[],
        persona_full=(
            "Você é um Analista Quantitativo Sênior com experiência em "
            "modelagem financeira, análise de risco e desenvolvimento de "
            "sistemas de trading algorítmico."
        ),
        persona_compact="Analista Quant Sênior (risco, precisão).",
        constraints=[
            Constraint("Use Decimal ou bibliotecas financeiras para valores monetários — NUNCA float puro.", ConstraintSeverity.CRITICAL),
            Constraint("Nunca logue chaves de API, tokens ou credenciais de corretoras.", ConstraintSeverity.CRITICAL),
            Constraint("Trate datas com timezone awareness (pytz ou zoneinfo).", ConstraintSeverity.HIGH),
            Constraint("Valide dados históricos: cheque gaps, splits e dividendos.", ConstraintSeverity.HIGH),
            Constraint("Inclua tratamento de erros para APIs de dados (rate limit, timeout).", ConstraintSeverity.HIGH),
            Constraint("Documente premissas de modelagem e limitações explicitamente.", ConstraintSeverity.MEDIUM),
            Constraint("Backtesting deve incluir custo de transação e slippage.", ConstraintSeverity.MEDIUM),
        ],
        reflection_checks=[
            "Valores monetários usam Decimal ou aritmética financeira?",
            "Credenciais estão fora do código?",
            "Timezone está tratado em todas as datas?",
            "Limitações do modelo estão documentadas?",
        ],
    ),

    DomainProfile(
        name="machine_learning",
        keywords={"modelo": 0.6, "treinar": 0.8, "train": 0.8, "ml": 0.8,
                  "classificacao": 0.9, "regressao": 0.9, "neural": 0.9,
                  "deep learning": 1.0, "llm": 1.0, "embedding": 0.9,
                  "rag": 1.0, "fine-tuning": 1.0, "inferencia": 0.8,
                  "sklearn": 0.9, "torch": 0.9, "tensorflow": 0.9,
                  "transformers": 0.9, "bert": 0.9, "gpt": 0.8},
        anti_keywords=[],
        persona_full=(
            "Você é um Engenheiro de Machine Learning Sênior especializado "
            "em modelos de produção, com foco em reprodutibilidade, "
            "avaliação robusta e prevenção de leakage."
        ),
        persona_compact="Engenheiro ML Sênior (produção, reprodutível).",
        constraints=[
            Constraint("Nunca use dados de teste para decisões de treino (leakage).", ConstraintSeverity.CRITICAL),
            Constraint("Fixe random seeds para reprodutibilidade.", ConstraintSeverity.CRITICAL),
            Constraint("Avalie com métricas adequadas ao problema (não só accuracy).", ConstraintSeverity.HIGH),
            Constraint("Normalize/padronize features antes de modelos sensíveis à escala.", ConstraintSeverity.HIGH),
            Constraint("Use cross-validation em vez de split simples para datasets pequenos.", ConstraintSeverity.HIGH),
            Constraint("Documente hiperparâmetros e versão de bibliotecas.", ConstraintSeverity.MEDIUM),
            Constraint("Implemente early stopping para evitar overfitting.", ConstraintSeverity.MEDIUM),
            Constraint("Monitore distribuição de dados de produção vs treino (data drift).", ConstraintSeverity.LOW),
        ],
        reflection_checks=[
            "Há risco de data leakage no pipeline?",
            "Random seeds foram fixados?",
            "As métricas escolhidas são adequadas ao problema?",
            "O modelo foi avaliado em dados não vistos?",
        ],
    ),

    DomainProfile(
        name="seguranca",
        keywords={"seguranca": 0.9, "security": 0.9, "autenticacao": 0.9,
                  "criptografia": 1.0, "encrypt": 0.9, "hash": 0.7,
                  "vulnerabilidade": 1.0, "injection": 1.0, "xss": 1.0,
                  "csrf": 1.0, "jwt": 0.9, "oauth": 0.9, "rbac": 1.0,
                  "pentest": 1.0, "hardening": 0.9, "ssl": 0.8, "tls": 0.8},
        anti_keywords=[],
        persona_full=(
            "Você é um Engenheiro de Segurança Sênior especializado em "
            "secure-by-design, modelagem de ameaças (STRIDE) e hardening "
            "de sistemas distribuídos."
        ),
        persona_compact="Engenheiro Segurança Sênior (STRIDE, hardening).",
        constraints=[
            Constraint("NUNCA implemente criptografia própria — use bibliotecas auditadas (cryptography, libsodium).", ConstraintSeverity.CRITICAL),
            Constraint("Use bcrypt ou Argon2 para senhas — SHA-1/MD5 são proibidos.", ConstraintSeverity.CRITICAL),
            Constraint("Valide tamanho, tipo e formato de TODAS as entradas externas.", ConstraintSeverity.CRITICAL),
            Constraint("Implemente defesa em profundidade — múltiplas camadas de validação.", ConstraintSeverity.HIGH),
            Constraint("Nunca exponha detalhes de implementação em mensagens de erro.", ConstraintSeverity.HIGH),
            Constraint("Use timing-safe comparison para segredos (hmac.compare_digest).", ConstraintSeverity.HIGH),
            Constraint("Implemente logging de eventos de segurança (falhas de auth, rate limit).", ConstraintSeverity.MEDIUM),
        ],
        reflection_checks=[
            "Alguma criptografia foi implementada manualmente?",
            "Todas as entradas estão validadas antes de qualquer processamento?",
            "Mensagens de erro expõem detalhes internos?",
            "Timing attacks foram considerados em comparações de segredos?",
        ],
    ),

    DomainProfile(
        name="blockchain",
        keywords={"blockchain": 1.0, "web3": 1.0, "ethereum": 1.0, "solidity": 1.0,
                  "smart contract": 1.0, "nft": 0.9, "defi": 1.0,
                  "wallet": 0.8, "carteira": 0.7, "token": 0.6,
                  "descentralizado": 0.9, "metamask": 0.9, "abi": 0.9},
        anti_keywords=[],
        persona_full=(
            "Você é um Engenheiro Blockchain Sênior especializado em "
            "contratos inteligentes seguros (OpenZeppelin), análise de "
            "vulnerabilidades (reentrancy, overflow) e integração Web3."
        ),
        persona_compact="Engenheiro Blockchain Sênior (OpenZeppelin, seguro).",
        constraints=[
            Constraint("Use bibliotecas auditadas (OpenZeppelin) — nunca implemente primitivos próprios.", ConstraintSeverity.CRITICAL),
            Constraint("Proteja contra reentrancy com checks-effects-interactions pattern.", ConstraintSeverity.CRITICAL),
            Constraint("Valide endereços antes de qualquer operação on-chain.", ConstraintSeverity.CRITICAL),
            Constraint("Mantenha chaves privadas FORA do código-fonte — use variáveis de ambiente.", ConstraintSeverity.CRITICAL),
            Constraint("Trate inteiros com SafeMath ou Solidity >= 0.8 (overflow nativo).", ConstraintSeverity.HIGH),
            Constraint("Implemente circuit breaker (pause) em contratos críticos.", ConstraintSeverity.HIGH),
            Constraint("Teste em testnet antes de mainnet — documente gas costs.", ConstraintSeverity.MEDIUM),
        ],
        reflection_checks=[
            "Há risco de reentrancy no contrato?",
            "Chaves privadas estão no código?",
            "Endereços foram validados antes de operações?",
            "Overflow/underflow está protegido?",
        ],
    ),

    DomainProfile(
        name="devops",
        keywords={"docker": 0.9, "kubernetes": 1.0, "k8s": 1.0, "deploy": 0.8,
                  "ci": 0.7, "cd": 0.7, "terraform": 1.0, "ansible": 0.9,
                  "container": 0.8, "helm": 0.9, "pipeline": 0.6,
                  "infraestrutura": 0.8, "monitoramento": 0.7, "log": 0.5},
        anti_keywords=[],
        persona_full=(
            "Você é um Engenheiro DevOps/SRE Sênior especializado em "
            "infraestrutura como código, observabilidade e práticas de "
            "GitOps e zero-downtime deployment."
        ),
        persona_compact="Engenheiro DevOps/SRE Sênior (IaC, GitOps).",
        constraints=[
            Constraint("Nunca hardcode credenciais — use secrets manager ou variáveis de ambiente.", ConstraintSeverity.CRITICAL),
            Constraint("Containers devem rodar como non-root user.", ConstraintSeverity.CRITICAL),
            Constraint("Implemente health checks e readiness probes em todos os serviços.", ConstraintSeverity.HIGH),
            Constraint("Use imagens base mínimas (alpine/distroless) para reduzir surface de ataque.", ConstraintSeverity.HIGH),
            Constraint("Infraestrutura deve ser idempotente — aplicar múltiplas vezes sem efeito colateral.", ConstraintSeverity.HIGH),
            Constraint("Implemente rollback automático em caso de falha no deploy.", ConstraintSeverity.MEDIUM),
            Constraint("Documente resource limits (CPU/memory) de todos os containers.", ConstraintSeverity.MEDIUM),
        ],
        reflection_checks=[
            "Credenciais estão fora do código e dos logs?",
            "O container roda como non-root?",
            "Health checks estão configurados?",
            "O deploy é reversível?",
        ],
    ),
]


# ---------------------------------------------------------------------------
# Motor de Detecção Semântica
# ---------------------------------------------------------------------------

class DetectorEngine:
    """
    Detecta domínios usando tokenização n-grama.
    Elimina falsos positivos de substring simples.
    """

    @staticmethod
    def tokenize(text: str) -> Set[str]:
        text = text.lower()
        text = re.sub(r"[^\w\s]", " ", text)
        words = text.split()
        tokens: Set[str] = set(words)
        for i in range(len(words) - 1):
            tokens.add(f"{words[i]} {words[i+1]}")
        for i in range(len(words) - 2):
            tokens.add(f"{words[i]} {words[i+1]} {words[i+2]}")
        return tokens

    @staticmethod
    def detect(
        text: str,
        min_score: float = 0.3,
    ) -> List[Tuple[DomainProfile, float]]:
        tokens = DetectorEngine.tokenize(text)
        scored = [(d, d.score(tokens)) for d in DOMAIN_REGISTRY]
        return sorted(
            [(d, s) for d, s in scored if s >= min_score],
            key=lambda x: x[1],
            reverse=True,
        )


# ---------------------------------------------------------------------------
# Motor de Complexidade
# ---------------------------------------------------------------------------

_COMPLEXITY_SIGNALS: Dict[str, Dict[str, float]] = {
    "multi_tech": {
        "php": 1.0, "html": 0.8, "css": 0.8, "javascript": 1.0,
        "react": 1.2, "vue": 1.2, "python": 0.8, "docker": 1.0,
    },
    "integration": {
        "integrar": 1.5, "conectar": 1.5, "api": 1.0,
        "webhook": 1.5, "comunicar": 1.2, "sincronizar": 1.5,
    },
    "multi_feature": {
        "autenticacao": 1.5, "login": 1.0, "crud": 1.5, "admin": 1.2,
        "relatorio": 1.0, "dashboard": 1.5, "notificacao": 1.2,
    },
    "data_pipeline": {
        "banco": 1.0, "sql": 1.0, "query": 0.8, "pipeline": 1.5,
        "etl": 2.0, "streaming": 2.0, "cache": 1.0,
    },
    "distributed": {
        "microservico": 2.0, "fila": 1.5, "kafka": 2.0,
        "kubernetes": 2.0, "escalabilidade": 1.5, "distribuido": 2.0,
    },
    "security": {
        "autorizacao": 1.5, "rbac": 2.0, "criptografia": 2.0,
        "auditoria": 1.5, "compliance": 2.0,
    },
}


class ComplexityEngine:
    """Calcula complexidade real da tarefa com scores ponderados por categoria."""

    @staticmethod
    def analyze(text: str) -> Tuple[ComplexityLevel, int, Dict[str, float]]:
        tokens = DetectorEngine.tokenize(text)
        category_scores: Dict[str, float] = {}

        for category, signals in _COMPLEXITY_SIGNALS.items():
            cat_score = sum(weight for kw, weight in signals.items() if kw in tokens)
            if cat_score > 0:
                category_scores[category] = cat_score

        total = sum(category_scores.values())
        int_score = int(total)

        if int_score <= 1:
            level = ComplexityLevel.TRIVIAL
        elif int_score <= 3:
            level = ComplexityLevel.SIMPLE
        elif int_score <= 6:
            level = ComplexityLevel.MODERATE
        elif int_score <= 10:
            level = ComplexityLevel.COMPLEX
        else:
            level = ComplexityLevel.CRITICAL

        return level, int_score, category_scores


# ---------------------------------------------------------------------------
# Persona Composer
# ---------------------------------------------------------------------------

class PersonaComposer:
    """
    Compõe personas para tarefas multi-domínio.
    Domínio primário determina a base; secundários adicionam especialidades.
    """

    @staticmethod
    def compose(
        domains: List[Tuple[DomainProfile, float]],
        mode: PromptMode,
    ) -> str:
        if not domains:
            if mode == PromptMode.COMPACT:
                return "Engenheiro de Software Sênior."
            return (
                "Você é um Engenheiro de Software Sênior especializado em "
                "soluções robustas, seguras e escaláveis."
            )

        primary, primary_score = domains[0]

        if mode == PromptMode.COMPACT:
            if len(domains) == 1:
                return primary.persona_compact
            extras = " + ".join(d.name for d, _ in domains[1:3])
            return f"{primary.persona_compact} Com expertise em: {extras}."

        # Modo FULL — persona rica com especialidades secundárias
        base = primary.persona_full
        if len(domains) > 1:
            secondary_skills = [
                f"{d.name} (score={round(s,1)})"
                for d, s in domains[1:3]
            ]
            base += (
                f" Com conhecimento adicional em: {', '.join(secondary_skills)}."
            )
        return base


# ---------------------------------------------------------------------------
# Decomposition Engine
# ---------------------------------------------------------------------------

class DecompositionEngine:
    """
    Gera plano de decomposição adaptado ao nível de complexidade
    e aos domínios detectados.
    """

    _STEPS_BY_COMPLEXITY: Dict[ComplexityLevel, List[str]] = {
        ComplexityLevel.TRIVIAL: [
            "Implemente a solução diretamente.",
            "Verifique edge cases óbvios.",
        ],
        ComplexityLevel.SIMPLE: [
            "Passo 1 — Entenda o requisito e identifique inputs/outputs esperados.",
            "Passo 2 — Implemente a solução com tratamento de erros.",
            "Passo 3 — Verifique contra os requisitos antes de finalizar.",
        ],
        ComplexityLevel.MODERATE: [
            "Passo 1 — Analise requisitos e identifique componentes do sistema.",
            "Passo 2 — Defina a estrutura de dados e contratos de interface.",
            "Passo 3 — Implemente cada componente individualmente e de forma modular.",
            "Passo 4 — Integre os componentes com tratamento de erros entre eles.",
            "Passo 5 — Revise contra restrições técnicas e de segurança.",
        ],
        ComplexityLevel.COMPLEX: [
            "Passo 1 — Mapeie todos os requisitos funcionais e não-funcionais.",
            "Passo 2 — Defina a arquitetura: camadas, módulos e responsabilidades.",
            "Passo 3 — Projete contratos de dados (schemas, tipos, validações).",
            "Passo 4 — Implemente a camada de infraestrutura/persistência.",
            "Passo 5 — Implemente a lógica de negócio com separação de concerns.",
            "Passo 6 — Implemente a camada de apresentação/API.",
            "Passo 7 — Adicione observabilidade: logs, métricas, tratamento de erros.",
            "Passo 8 — Revise segurança em cada camada antes de finalizar.",
        ],
        ComplexityLevel.CRITICAL: [
            "Passo 1 — Decomponha o sistema em domínios independentes.",
            "Passo 2 — Defina bounded contexts e interfaces entre domínios.",
            "Passo 3 — Projete para falha: retry, circuit breaker, fallback.",
            "Passo 4 — Implemente domínio por domínio, começando pela infraestrutura.",
            "Passo 5 — Defina contratos de dados com versionamento.",
            "Passo 6 — Implemente lógica de negócio com testes embutidos.",
            "Passo 7 — Integre domínios via eventos ou contratos explícitos.",
            "Passo 8 — Adicione observabilidade full-stack (traces, métricas, logs).",
            "Passo 9 — Revise segurança, performance e escalabilidade.",
            "Passo 10 — Documente decisões de arquitetura inline.",
        ],
    }

    @staticmethod
    def decompose(
        complexity: ComplexityLevel,
        domains: List[Tuple[DomainProfile, float]],
        mode: PromptMode,
    ) -> str:
        if complexity == ComplexityLevel.TRIVIAL:
            return ""

        steps = DecompositionEngine._STEPS_BY_COMPLEXITY[complexity]

        if mode == PromptMode.COMPACT:
            return "Plano: " + " → ".join(
                s.split("—")[-1].strip() if "—" in s else s
                for s in steps[:4]
            )

        lines = [
            "",
            f"[PLANO DE EXECUÇÃO — complexidade: {complexity.value.upper()}]",
            "Siga rigorosamente esta sequência antes de gerar o código final:",
            "",
        ]
        lines.extend(steps)
        lines.append("")
        lines.append("IMPORTANTE: Complete cada passo antes de avançar ao próximo.")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Reflection Engine
# ---------------------------------------------------------------------------

class ReflectionEngine:
    """
    Gera checklist de auto-crítica dinâmica baseada em domínio,
    histórico de erros (error_context) e exemplos negativos do MTA.
    """

    _UNIVERSAL_CHECKS = [
        "Cada instrução do prompt foi atendida explicitamente?",
        "Existe tratamento de erros em todos os pontos de falha?",
        "Variáveis e funções têm nomes descritivos e semânticos?",
        "O código é testável de forma isolada?",
    ]

    @staticmethod
    def build(
        domains: List[Tuple[DomainProfile, float]],
        error_context: str,
        knowledge_context: str,
        negative_examples: List[str],
        positive_examples: List[str],
        mode: PromptMode,
    ) -> str:
        lines: List[str] = []

        # ── Checklist universal ──────────────────────────────────────────────
        if mode == PromptMode.COMPACT:
            lines.append(
                "Verifique: atendeu todos requisitos? tratamento de erros? seguro?"
            )
        else:
            lines.append("\n[AUTO-REVISÃO OBRIGATÓRIA]")
            lines.append("Antes de finalizar, confirme cada item:")
            for check in ReflectionEngine._UNIVERSAL_CHECKS:
                lines.append(f"☐ {check}")

        # ── Checks específicos por domínio ───────────────────────────────────
        domain_checks: List[str] = []
        for domain, score in domains[:2]:
            for check in domain.reflection_checks:
                if check not in domain_checks:
                    domain_checks.append(check)

        if domain_checks and mode != PromptMode.COMPACT:
            lines.append("")
            lines.append("Checks específicos do domínio:")
            for check in domain_checks:
                lines.append(f"☐ {check}")

        # ── Exemplos negativos do MTA ────────────────────────────────────────
        if negative_examples:
            lines.append("")
            if mode == PromptMode.COMPACT:
                lines.append(f"Evite: {negative_examples[0][:150]}")
            else:
                lines.append("[PADRÕES A EVITAR — aprendidos de falhas anteriores]")
                for ex in negative_examples[:3]:
                    lines.append(ex)

        # ── Exemplos positivos de skills em produção ─────────────────────────
        if positive_examples and mode != PromptMode.COMPACT:
            lines.append("")
            lines.append("[PADRÕES DE SUCESSO — skills validadas em produção]")
            for ex in positive_examples[:2]:
                lines.append(ex)

        # ── Lições do error_context ──────────────────────────────────────────
        if error_context:
            lines.append("")
            if mode == PromptMode.COMPACT:
                lines.append(f"Erros anteriores: {error_context.strip()[:200]}")
            else:
                lines.append("[LIÇÕES DE TENTATIVAS ANTERIORES]")
                for line in error_context.strip().split("\n")[:5]:
                    line = line.strip()
                    if line:
                        lines.append(f"✗ Evite: {line[:150]}")

        # ── Knowledge context ────────────────────────────────────────────────
        if knowledge_context and mode != PromptMode.COMPACT:
            lines.append("")
            lines.append("[CONTEXTO DE CONHECIMENTO]")
            lines.append(knowledge_context[:500])

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# PromptImprover v2
# ---------------------------------------------------------------------------

class PromptImprover:
    """
    Pipeline de melhoria de prompts em 5 estágios orquestrados.

    Estágios:
      1. Detecção semântica de domínios (n-gramas, sem falso positivo)
      2. Análise de complexidade ponderada
      3. Composição de persona (multi-domínio)
      4. Injeção de constraints por severidade e modo
      5. Decomposição adaptativa + auto-reflexão com memória biológica
    """

    def __init__(
        self,
        mta_recycler: Optional[Any] = None,
        self_registry: Optional[Any] = None,
    ):
        self._mta = mta_recycler
        self._skill_registry = skill_registry
        self._detector    = DetectorEngine()
        self._complexity  = ComplexityEngine()
        self._persona     = PersonaComposer()
        self._decomposer  = DecompositionEngine()
        self._reflection  = ReflectionEngine()

    def improve(
        self,
        raw_prompt: str,
        domain: str = "",           # hint externo — somado ao score detectado
        error_context: str = "",
        knowledge_context: str = "",
        suggested_libs: Optional[List[str]] = None,
        mode: PromptMode = PromptMode.FULL,
    ) -> str:
        result, _ = self.improve_with_report(
            raw_prompt, domain, error_context,
            knowledge_context, suggested_libs, mode,
        )
        return result

    def improve_with_report(
        self,
        raw_prompt: str,
        domain: str = "",
        error_context: str = "",
        knowledge_context: str = "",
        suggested_libs: Optional[List[str]] = None,
        mode: PromptMode = PromptMode.FULL,
    ) -> Tuple[str, ImprovementReport]:

        # ── 1. Detecção de domínios ──────────────────────────────────────────
        combined = " ".join(filter(None, [raw_prompt, domain, knowledge_context]))
        domains  = self._detector.detect(combined)

        # ── 2. Complexidade ──────────────────────────────────────────────────
        complexity, c_score, c_breakdown = self._complexity.analyze(raw_prompt)

        # ── 3. Memória biológica — MTA + SkillStore ──────────────────────────
        negative_examples: List[str] = []
        positive_examples: List[str] = []
        mta_used, skill_used = False, False

        if self._mta and _MTA_AVAILABLE:
            try:
                negative_examples = self._mta.recycle_as_negative_examples(limit=3)
                mta_used = bool(negative_examples)
            except Exception:
                pass

        if self._skill_registry and _SKILL_REGISTRY_AVAILABLE:
            try:
                skills = self._skill_registry.list_skills(active_only=True)[:2]
                for skill in skills:
                    usage = getattr(skill, 'usage_count', 0)
                    positive_examples.append(
                        f"[SKILL: {skill.name}]"
                        f" Descrição: {skill.description[:100]}"
                    )
                skill_used = bool(positive_examples)
            except Exception:
                pass

        # ── 4. Composição do prompt ──────────────────────────────────────────
        min_sev = (
            ConstraintSeverity.CRITICAL
            if mode == PromptMode.COMPACT
            else ConstraintSeverity.MEDIUM
        )

        sections: List[str] = []

        # Persona
        persona = self._persona.compose(domains, mode)
        sections.append(persona)

        # Prompt original
        sections.append("")
        sections.append(raw_prompt)

        # Libs disponíveis
        if suggested_libs:
            max_libs = 3 if mode == PromptMode.COMPACT else 8
            libs_str = ", ".join(suggested_libs[:max_libs])
            sections.append(f"\nBibliotecas disponíveis: {libs_str}")

        # Constraints por domínio
        all_constraints: List[Constraint] = []
        seen_texts: Set[str] = set()
        for d_profile, d_score in domains[:3]:
            for c in d_profile.get_constraints(mode, error_context, min_sev):
                if c.text not in seen_texts:
                    seen_texts.add(c.text)
                    all_constraints.append(c)

        if all_constraints:
            sections.append("")
            if mode == PromptMode.COMPACT:
                sections.append(
                    "Regras: " + " | ".join(c.text[:80] for c in all_constraints[:3])
                )
            else:
                sections.append("Restrições técnicas obrigatórias:")
                for c in all_constraints:
                    prefix = "⚠️ " if c.severity == ConstraintSeverity.CRITICAL else "- "
                    sections.append(f"{prefix}{c.text}")

        # Decomposição
        decomp = self._decomposer.decompose(complexity, domains, mode)
        if decomp:
            sections.append(decomp)

        # Reflexão
        reflection = self._reflection.build(
            domains, error_context, knowledge_context,
            negative_examples, positive_examples, mode,
        )
        sections.append(reflection)

        # Instrução final
        sections.append("")
        sections.append(
            "Responda APENAS com código funcional dentro do bloco markdown correto. "
            "Sem explicações fora do bloco."
        )

        final_prompt = "\n".join(sections)

        # ── 5. Relatório ─────────────────────────────────────────────────────
        report = ImprovementReport(
            original_length=len(raw_prompt),
            final_length=len(final_prompt),
            mode=mode,
            detected_domains=[(d.name, s) for d, s in domains],
            complexity=complexity,
            complexity_score=c_score,
            constraints_applied=len(all_constraints),
            negative_examples_injected=len(negative_examples),
            positive_examples_injected=len(positive_examples),
            decomposed=bool(decomp),
            reflection_checks=len(ReflectionEngine._UNIVERSAL_CHECKS) + sum(
                len(d.reflection_checks) for d, _ in domains[:2]
            ),
            mta_examples_used=mta_used,
            skill_examples_used=skill_used,
        )

        logger.info(
            "✨ [PROMPT_IMPROVER] %d→%d chars | mode=%s | domínios=%s | "
            "complexity=%s(score=%d) | constraints=%d | mta=%s | skills=%s",
            report.original_length, report.final_length, mode.value,
            [(d, round(s, 2)) for d, s in report.detected_domains],
            complexity.value, c_score,
            len(all_constraints),
            mta_used, skill_used,
        )

        # ── Publica no AcetylcholineBus ──────────────────────────────────────
        if _BUS_AVAILABLE:
            import asyncio
            try:
                asyncio.get_event_loop().run_until_complete(
                    bus.publish(Signal(
                        event="prompt.improved",
                        source="prompt_improver",
                        payload=report.to_dict(),
                    ))
                )
            except Exception:
                pass

        return final_prompt, report
