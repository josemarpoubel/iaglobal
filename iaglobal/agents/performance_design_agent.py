"""
iaglobal/agents/performance_design_agent.py

PerformanceDesignAgent v2 — Análise de performance full-stack com:

  Backend:
  - Detecção semântica por n-gramas (sem falsos positivos de substring)
  - Perfis de carga (startup → enterprise → hyperscale)
  - Análise de banco de dados, cache, async, batch, conexões, sharding
  - Análise de resiliência: circuit breaker, retry, bulkhead, timeout

  Frontend:
  - Core Web Vitals (LCP, CLS, FID/INP, TTFB)
  - Rendering strategy (SSR, SSG, ISR, CSR, Streaming)
  - Bundle analysis: code splitting, tree shaking, lazy loading
  - CSS performance: critical path, containment, layer, will-change
  - Asset pipeline: imagens, fontes, preload, prefetch
  - Runtime: React re-renders, memory leaks, web workers, virtual scroll

  Organismo Biológico:
  - AcetylcholineBus: publica eventos de análise
  - MTARecycler: aproveita histórico de falhas de performance
  - SAMeEngine: registra custo de evoluções de performance

  Output:
  - PerformanceReport tipado com score 0–100, severidade, impacto e plano
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from iaglobal.utils.logger import get_logger
logger = get_logger(__name__)

# Integrações biológicas opcionais
try:
    from iaglobal.communication import AcetylcholineBus, AgentMessage
    bus = AcetylcholineBus()
    _BUS_AVAILABLE = True
except ImportError:
    _BUS_AVAILABLE = False

try:
    from iaglobal.recycling.prompt_recycler import PromptRecycler
    _MTA_AVAILABLE = True
except ImportError:
    _MTA_AVAILABLE = False

try:
    from iaglobal.evolution.same_engine import SAMePool, MethylationInhibitor
    _SAME_AVAILABLE = True
except ImportError:
    _SAME_AVAILABLE = False


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class Severity(str, Enum):
    CRITICAL = "critical"   # bloqueia produção ou degrada UX gravemente
    HIGH     = "high"       # impacto significativo em performance/custo
    MEDIUM   = "medium"     # melhoria importante mas não urgente
    LOW      = "low"        # otimização fina, nice-to-have


class ImpactArea(str, Enum):
    LATENCY      = "latency"
    THROUGHPUT   = "throughput"
    AVAILABILITY = "availability"
    COST         = "cost"
    UX           = "ux"
    SEO          = "seo"
    SECURITY     = "security"
    SCALABILITY  = "scalability"
    MEMORY       = "memory"
    BUNDLE_SIZE  = "bundle_size"
    RENDER_PERF  = "render_performance"
    ACCESSIBILITY= "accessibility"


class LoadProfile(str, Enum):
    """Perfil de carga estimado — determina rigor das recomendações."""
    STARTUP      = "startup"       # < 1k usuários/dia
    GROWTH       = "growth"        # 1k–100k usuários/dia
    ENTERPRISE   = "enterprise"    # 100k–10M usuários/dia
    HYPERSCALE   = "hyperscale"    # > 10M usuários/dia


class RenderingStrategy(str, Enum):
    CSR      = "csr"       # Client-Side Rendering
    SSR      = "ssr"       # Server-Side Rendering
    SSG      = "ssg"       # Static Site Generation
    ISR      = "isr"       # Incremental Static Regeneration
    STREAMING = "streaming" # React 18 Streaming SSR
    HYBRID   = "hybrid"    # mix de estratégias


# ---------------------------------------------------------------------------
# DataClasses
# ---------------------------------------------------------------------------

@dataclass
class PerformanceIssue:
    id: str
    title: str
    description: str
    severity: Severity
    impact_areas: List[ImpactArea]
    layer: str                              # "backend" | "frontend" | "infra" | "database"
    detected_by: str                        # nome da regra que detectou
    estimated_impact: str                   # ex: "200–500ms de latência adicional"
    recurrence: bool = False                # detectado em error_context também
    load_profiles: List[LoadProfile] = field(
        default_factory=lambda: list(LoadProfile)
    )


@dataclass
class PerformanceRecommendation:
    issue_id: str
    title: str
    action: str
    rationale: str
    effort: str                             # "low" | "medium" | "high"
    priority: int                           # 1 = mais urgente
    code_hint: Optional[str] = None        # snippet ilustrativo
    references: List[str] = field(default_factory=list)
    applicable_load_profiles: List[LoadProfile] = field(
        default_factory=lambda: list(LoadProfile)
    )


@dataclass
class CoreWebVitalsAnalysis:
    lcp_risk: Optional[str] = None     # Largest Contentful Paint
    cls_risk: Optional[str] = None     # Cumulative Layout Shift
    inp_risk: Optional[str] = None     # Interaction to Next Paint
    ttfb_risk: Optional[str] = None    # Time to First Byte
    fcp_risk: Optional[str] = None     # First Contentful Paint
    score: int = 100                   # 0–100, começa perfeito e desconta


@dataclass
class PerformanceScore:
    backend:  int = 100
    frontend: int = 100
    database: int = 100
    infra:    int = 100

    @property
    def overall(self) -> int:
        return int((self.backend + self.frontend + self.database + self.infra) / 4)

    def deduct(self, layer: str, amount: int):
        current = getattr(self, layer, 100)
        setattr(self, layer, max(0, current - amount))


@dataclass
class PerformanceReport:
    load_profile: LoadProfile
    rendering_strategy: RenderingStrategy
    score: PerformanceScore
    issues: List[PerformanceIssue]
    recommendations: List[PerformanceRecommendation]
    cwv: CoreWebVitalsAnalysis
    summary: Dict[str, Any]
    quick_wins: List[str]
    architectural_risks: List[str]

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["score_overall"] = self.score.overall
        return d

    @property
    def critical_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == Severity.CRITICAL)

    @property
    def high_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == Severity.HIGH)


# ---------------------------------------------------------------------------
# Tokenizador Semântico (mesmo padrão do organismo)
# ---------------------------------------------------------------------------

def _tokenize(text: str) -> Set[str]:
    """N-gramas 1–3 palavras. Elimina falsos positivos de substring."""
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    words = text.split()
    tokens: Set[str] = set(words)
    for i in range(len(words) - 1):
        tokens.add(f"{words[i]} {words[i+1]}")
    for i in range(len(words) - 2):
        tokens.add(f"{words[i]} {words[i+1]} {words[i+2]}")
    return tokens


def _has(tokens: Set[str], *keywords: str) -> bool:
    """True se ALGUMA keyword estiver nos tokens."""
    return any(k in tokens for k in keywords)


def _has_all(tokens: Set[str], *keywords: str) -> bool:
    """True se TODAS as keywords estiverem nos tokens."""
    return all(k in tokens for k in keywords)


def _missing(tokens: Set[str], *keywords: str) -> bool:
    """True se NENHUMA keyword estiver nos tokens."""
    return not any(k in tokens for k in keywords)


# ---------------------------------------------------------------------------
# Detectores de Perfil de Carga e Rendering
# ---------------------------------------------------------------------------

def _detect_load_profile(tokens: Set[str]) -> LoadProfile:
    if _has(tokens, "hyperscale", "bilhao", "billion", "global scale", "cdn global"):
        return LoadProfile.HYPERSCALE
    if _has(tokens, "enterprise", "milhao", "million", "alta disponibilidade",
            "high availability", "multi region", "multi-region"):
        return LoadProfile.ENTERPRISE
    if _has(tokens, "crescimento", "growth", "escalar", "scale", "mil usuarios",
            "thousand users", "producao", "production"):
        return LoadProfile.GROWTH
    return LoadProfile.STARTUP


def _detect_rendering(tokens: Set[str]) -> RenderingStrategy:
    if _has(tokens, "streaming ssr", "react 18 streaming", "suspense streaming"):
        return RenderingStrategy.STREAMING
    if _has(tokens, "isr", "incremental static"):
        return RenderingStrategy.ISR
    if _has(tokens, "ssg", "static site", "static generation", "next export", "gatsby"):
        return RenderingStrategy.SSG
    if _has(tokens, "ssr", "server side render", "server-side render", "next ssr", "nuxt ssr"):
        return RenderingStrategy.SSR
    if _has(tokens, "spa", "single page", "client side render", "csr", "react csr", "vue csr"):
        return RenderingStrategy.CSR
    if _has(tokens, "next", "nuxt", "remix", "astro"):
        return RenderingStrategy.HYBRID
    return RenderingStrategy.CSR


# ---------------------------------------------------------------------------
# Regras de Performance — Backend
# ---------------------------------------------------------------------------

class BackendRules:
    """
    Conjunto de regras de performance para camada backend.
    Cada método retorna (PerformanceIssue, PerformanceRecommendation) ou None.
    """

    @staticmethod
    def check_n_plus_one(
        tokens: Set[str], error_tokens: Set[str], profile: LoadProfile
    ) -> Optional[Tuple[PerformanceIssue, PerformanceRecommendation]]:
        has_orm = _has(tokens, "orm", "sqlalchemy", "django", "sequelize", "prisma", "hibernate")
        has_loop_query = _has(tokens, "for loop", "foreach", "loop query", "n+1", "n plus 1")
        recurrence = _has(error_tokens, "n+1", "query", "slow query", "n plus 1")

        if not (has_orm or has_loop_query or recurrence):
            return None

        severity = Severity.CRITICAL if recurrence else Severity.HIGH
        issue = PerformanceIssue(
            id="BE-001",
            title="Risco de N+1 Queries",
            description=(
                "ORMs sem eager loading geram uma query por item em loops, "
                "causando degradação exponencial com volume de dados."
            ),
            severity=severity,
            impact_areas=[ImpactArea.LATENCY, ImpactArea.THROUGHPUT, ImpactArea.COST],
            layer="backend",
            detected_by="BackendRules.check_n_plus_one",
            estimated_impact="100ms–10s de latência adicional dependendo do volume",
            recurrence=recurrence,
        )
        rec = PerformanceRecommendation(
            issue_id="BE-001",
            title="Implementar Eager Loading",
            action=(
                "Use select_related/prefetch_related (Django), joinedload/subqueryload "
                "(SQLAlchemy) ou include (Prisma) para carregar relações em batch."
            ),
            rationale="Reduz N queries para 1–2, independente do volume de dados.",
            effort="low",
            priority=1,
            code_hint=(
                "# Django\n"
                "orders = Order.objects.select_related('customer')"
                ".prefetch_related('items').filter(status='pending')\n\n"
                "# SQLAlchemy\n"
                "stmt = select(Order).options(joinedload(Order.customer),"
                " subqueryload(Order.items))"
            ),
            references=["https://docs.djangoproject.com/en/stable/ref/models/querysets/#select-related"],
        )
        return issue, rec

    @staticmethod
    def check_cache_strategy(
        tokens: Set[str], error_tokens: Set[str], profile: LoadProfile
    ) -> Optional[Tuple[PerformanceIssue, PerformanceRecommendation]]:
        has_cache = _has(tokens, "cache", "redis", "memcached", "varnish",
                         "cdn", "cloudfront", "fastly", "etag", "cache-control")
        has_reads = _has(tokens, "consulta", "query", "busca", "search",
                         "listagem", "leitura", "read", "get")
        recurrence = _has(error_tokens, "cache", "lento", "timeout", "slow")

        if has_cache or (not has_reads and not recurrence):
            return None

        severity = Severity.CRITICAL if profile in (LoadProfile.ENTERPRISE, LoadProfile.HYPERSCALE) else Severity.HIGH
        issue = PerformanceIssue(
            id="BE-002",
            title="Ausência de Estratégia de Cache",
            description="Leituras repetidas sem cache geram load desnecessário no banco.",
            severity=severity,
            impact_areas=[ImpactArea.LATENCY, ImpactArea.THROUGHPUT, ImpactArea.COST],
            layer="backend",
            detected_by="BackendRules.check_cache_strategy",
            estimated_impact="50–500ms por request + custo de DB desnecessário",
            recurrence=recurrence,
            load_profiles=[LoadProfile.GROWTH, LoadProfile.ENTERPRISE, LoadProfile.HYPERSCALE],
        )
        rec = PerformanceRecommendation(
            issue_id="BE-002",
            title="Implementar Cache em Camadas",
            action=(
                "Camada 1: Cache in-process (TTLCache/lru_cache) para dados quentes. "
                "Camada 2: Redis com TTL por tipo de dado. "
                "Camada 3: CDN para recursos estáticos e respostas de API pública."
            ),
            rationale="Cache em camadas reduz latência em 80–99% para reads frequentes.",
            effort="medium",
            priority=2,
            code_hint=(
                "import redis\nfrom functools import lru_cache\n\n"
                "r = redis.Redis(host='localhost', decode_responses=True)\n\n"
                "def get_product(product_id: str) -> dict:\n"
                "    key = f'product:{product_id}'\n"
                "    cached = r.get(key)\n"
                "    if cached:\n"
                "        return json.loads(cached)\n"
                "    product = db.query(Product).get(product_id)\n"
                "    r.setex(key, 300, json.dumps(product.to_dict()))  # TTL 5min\n"
                "    return product.to_dict()"
            ),
            references=["https://redis.io/docs/manual/patterns/"],
        )
        return issue, rec

    @staticmethod
    def check_async_io(
        tokens: Set[str], error_tokens: Set[str], profile: LoadProfile
    ) -> Optional[Tuple[PerformanceIssue, PerformanceRecommendation]]:
        has_async = _has(tokens, "async", "asyncio", "await", "aiohttp",
                         "httpx", "fastapi async", "async def")
        has_io = _has(tokens, "api externa", "external api", "http request",
                      "requests", "urllib", "io bound", "file read", "s3")
        has_sync_io = _has(tokens, "requests.get", "requests.post", "urllib.request")

        if has_async or (not has_io and not has_sync_io):
            return None

        issue = PerformanceIssue(
            id="BE-003",
            title="I/O Síncrono Bloqueante em Operações de Rede",
            description=(
                "Chamadas HTTP síncronas bloqueiam a thread durante toda a "
                "operação, desperdiçando recursos e limitando throughput."
            ),
            severity=Severity.HIGH,
            impact_areas=[ImpactArea.THROUGHPUT, ImpactArea.LATENCY],
            layer="backend",
            detected_by="BackendRules.check_async_io",
            estimated_impact="Throughput limitado ao número de threads; P99 cresce linearmente com carga",
        )
        rec = PerformanceRecommendation(
            issue_id="BE-003",
            title="Migrar para I/O Assíncrono",
            action=(
                "Substitua `requests` por `httpx` (async) ou `aiohttp`. "
                "Use `asyncio.gather()` para paralelizar chamadas independentes."
            ),
            rationale="Async I/O permite milhares de conexões simultâneas com uma única thread.",
            effort="medium",
            priority=2,
            code_hint=(
                "import asyncio\nimport httpx\n\n"
                "async def fetch_all(urls: list[str]) -> list[dict]:\n"
                "    async with httpx.AsyncClient(timeout=10.0) as client:\n"
                "        tasks = [client.get(url) for url in urls]\n"
                "        responses = await asyncio.gather(*tasks, return_exceptions=True)\n"
                "        return [r.json() for r in responses if not isinstance(r, Exception)]"
            ),
            references=["https://www.python-httpx.org/async/"],
        )
        return issue, rec

    @staticmethod
    def check_pagination(
        tokens: Set[str], error_tokens: Set[str], profile: LoadProfile
    ) -> Optional[Tuple[PerformanceIssue, PerformanceRecommendation]]:
        has_list = _has(tokens, "listar", "listing", "listagem", "buscar todos",
                        "get all", "fetch all", "todos os registros")
        has_pagination = _has(tokens, "paginacao", "pagination", "paginate",
                              "limit", "offset", "cursor", "page")

        if not has_list or has_pagination:
            return None

        issue = PerformanceIssue(
            id="BE-004",
            title="Listagem sem Paginação",
            description="Queries sem LIMIT retornam volumes ilimitados, causando OOM e timeouts.",
            severity=Severity.CRITICAL,
            impact_areas=[ImpactArea.LATENCY, ImpactArea.MEMORY, ImpactArea.AVAILABILITY],
            layer="backend",
            detected_by="BackendRules.check_pagination",
            estimated_impact="OOM crash com >100k registros; timeout em produção",
        )
        rec = PerformanceRecommendation(
            issue_id="BE-004",
            title="Implementar Cursor-Based Pagination",
            action=(
                "Prefira cursor-based pagination para grandes volumes "
                "(evita O(n) do OFFSET). "
                "Implemente limite máximo de page_size no servidor."
            ),
            rationale="Cursor pagination mantém O(1) independente da página.",
            effort="low",
            priority=1,
            code_hint=(
                "# Cursor-based (recomendado)\n"
                "def list_orders(cursor: str | None, limit: int = 20) -> dict:\n"
                "    limit = min(limit, 100)  # cap máximo\n"
                "    q = db.query(Order).order_by(Order.id)\n"
                "    if cursor:\n"
                "        q = q.filter(Order.id > cursor)\n"
                "    items = q.limit(limit + 1).all()\n"
                "    has_next = len(items) > limit\n"
                "    return {\n"
                "        'items': items[:limit],\n"
                "        'next_cursor': items[limit - 1].id if has_next else None\n"
                "    }"
            ),
        )
        return issue, rec

    @staticmethod
    def check_db_indexes(
        tokens: Set[str], error_tokens: Set[str], profile: LoadProfile
    ) -> Optional[Tuple[PerformanceIssue, PerformanceRecommendation]]:
        has_db = _has(tokens, "banco", "database", "db", "sql", "postgres",
                      "mysql", "sqlite", "mongodb")
        has_indexes = _has(tokens, "index", "indice", "b-tree", "compound index",
                           "partial index", "gin", "gist")
        has_filter = _has(tokens, "where", "filtro", "filter", "busca", "search",
                          "order by", "join", "foreign key")

        if not has_db or has_indexes or not has_filter:
            return None

        issue = PerformanceIssue(
            id="DB-001",
            title="Ausência de Estratégia de Índices",
            description=(
                "Queries sem índices em colunas de filtro/join resultam em "
                "full table scans — degradação severa com crescimento de dados."
            ),
            severity=Severity.HIGH,
            impact_areas=[ImpactArea.LATENCY, ImpactArea.THROUGHPUT],
            layer="database",
            detected_by="BackendRules.check_db_indexes",
            estimated_impact="Full scan: 10ms → 10s+ com 10M registros",
        )
        rec = PerformanceRecommendation(
            issue_id="DB-001",
            title="Definir Índices por Padrão de Query",
            action=(
                "Crie índices para colunas em WHERE, JOIN, ORDER BY e foreign keys. "
                "Use índices compostos na ordem de seletividade decrescente. "
                "Considere partial indexes para subconjuntos frequentes."
            ),
            rationale="Índice correto reduz full scan (O(n)) para B-tree search (O(log n)).",
            effort="low",
            priority=1,
            code_hint=(
                "-- PostgreSQL\n"
                "-- Índice simples\n"
                "CREATE INDEX CONCURRENTLY idx_orders_status ON orders(status);\n\n"
                "-- Índice composto (ordem importa: seletividade decrescente)\n"
                "CREATE INDEX CONCURRENTLY idx_orders_status_created\n"
                "    ON orders(status, created_at DESC);\n\n"
                "-- Partial index (subset frequente)\n"
                "CREATE INDEX CONCURRENTLY idx_orders_pending\n"
                "    ON orders(created_at) WHERE status = 'pending';\n\n"
                "-- SQLAlchemy\n"
                "class Order(Base):\n"
                "    __table_args__ = (\n"
                "        Index('idx_status_created', 'status', 'created_at'),\n"
                "    )"
            ),
        )
        return issue, rec

    @staticmethod
    def check_connection_pool(
        tokens: Set[str], error_tokens: Set[str], profile: LoadProfile
    ) -> Optional[Tuple[PerformanceIssue, PerformanceRecommendation]]:
        has_db = _has(tokens, "banco", "database", "postgres", "mysql", "mongodb")
        has_pool = _has(tokens, "pool", "connection pool", "pgbouncer",
                        "pool size", "max connections")
        recurrence = _has(error_tokens, "too many connections", "connection refused",
                          "pool exhausted", "timeout")

        if not has_db or has_pool:
            return None

        severity = Severity.CRITICAL if recurrence else Severity.MEDIUM
        if profile == LoadProfile.HYPERSCALE:
            severity = Severity.CRITICAL

        issue = PerformanceIssue(
            id="DB-002",
            title="Connection Pool não Configurado",
            description=(
                "Sem pool de conexões, cada request abre/fecha uma conexão de banco — "
                "overhead severo e risco de esgotamento de conexões."
            ),
            severity=severity,
            impact_areas=[ImpactArea.LATENCY, ImpactArea.AVAILABILITY, ImpactArea.SCALABILITY],
            layer="database",
            detected_by="BackendRules.check_connection_pool",
            estimated_impact="20–100ms overhead por request + crash por connection limit",
            recurrence=recurrence,
        )
        rec = PerformanceRecommendation(
            issue_id="DB-002",
            title="Configurar Connection Pool com PgBouncer ou SQLAlchemy Pool",
            action=(
                "Configure pool_size, max_overflow e pool_timeout no SQLAlchemy. "
                "Para hyperscale, adicione PgBouncer em modo transaction pooling."
            ),
            rationale="Pool reutiliza conexões — elimina overhead de handshake TCP+TLS+auth.",
            effort="low",
            priority=2,
            code_hint=(
                "# SQLAlchemy\n"
                "engine = create_engine(\n"
                "    DATABASE_URL,\n"
                "    pool_size=20,           # conexões persistentes\n"
                "    max_overflow=10,        # burst temporário\n"
                "    pool_timeout=30,        # espera máxima por conexão\n"
                "    pool_recycle=1800,      # recicla a cada 30min\n"
                "    pool_pre_ping=True,     # verifica conexão antes de usar\n"
                ")"
            ),
        )
        return issue, rec

    @staticmethod
    def check_circuit_breaker(
        tokens: Set[str], error_tokens: Set[str], profile: LoadProfile
    ) -> Optional[Tuple[PerformanceIssue, PerformanceRecommendation]]:
        has_external = _has(tokens, "api externa", "external service", "terceiro",
                            "third party", "microservico", "http client")
        has_cb = _has(tokens, "circuit breaker", "fallback", "hystrix",
                      "resilience", "retry", "tenacity")

        if not has_external or has_cb:
            return None

        if profile == LoadProfile.STARTUP:
            return None  # não obrigatório para startup

        issue = PerformanceIssue(
            id="BE-005",
            title="Sem Circuit Breaker em Serviços Externos",
            description=(
                "Falhas em serviços externos sem circuit breaker causam "
                "cascade failure — um serviço derruba toda a aplicação."
            ),
            severity=Severity.HIGH,
            impact_areas=[ImpactArea.AVAILABILITY, ImpactArea.LATENCY],
            layer="backend",
            detected_by="BackendRules.check_circuit_breaker",
            estimated_impact="Cascade failure pode derrubar 100% da aplicação",
            load_profiles=[LoadProfile.GROWTH, LoadProfile.ENTERPRISE, LoadProfile.HYPERSCALE],
        )
        rec = PerformanceRecommendation(
            issue_id="BE-005",
            title="Implementar Circuit Breaker + Retry com Backoff",
            action=(
                "Use tenacity para retry com backoff exponencial. "
                "Implemente circuit breaker manual ou via pybreaker. "
                "Defina timeouts agressivos em todas as chamadas externas."
            ),
            rationale="Circuit breaker falha rápido quando serviço externo está degradado.",
            effort="medium",
            priority=2,
            code_hint=(
                "from tenacity import retry, stop_after_attempt, wait_exponential\n"
                "import pybreaker\n\n"
                "breaker = pybreaker.CircuitBreaker(fail_max=5, reset_timeout=60)\n\n"
                "@breaker\n"
                "@retry(stop=stop_after_attempt(3),\n"
                "       wait=wait_exponential(multiplier=1, min=1, max=10))\n"
                "async def call_external_api(url: str) -> dict:\n"
                "    async with httpx.AsyncClient(timeout=5.0) as client:\n"
                "        response = await client.get(url)\n"
                "        response.raise_for_status()\n"
                "        return response.json()"
            ),
        )
        return issue, rec

    @staticmethod
    def check_batch_processing(
        tokens: Set[str], error_tokens: Set[str], profile: LoadProfile
    ) -> Optional[Tuple[PerformanceIssue, PerformanceRecommendation]]:
        has_volume = _has(tokens, "muitos registros", "large volume", "bulk",
                          "milhares", "thousands", "importacao", "import",
                          "exportacao", "export", "processamento em massa")
        has_batch = _has(tokens, "batch", "chunk", "chunking", "bulk insert",
                         "bulk_create", "copyfrom", "streaming")

        if not has_volume or has_batch:
            return None

        issue = PerformanceIssue(
            id="BE-006",
            title="Processamento de Volume sem Estratégia Batch",
            description=(
                "Processamento de grandes volumes registro a registro "
                "causa OOM, timeouts e degrada todo o sistema."
            ),
            severity=Severity.HIGH,
            impact_areas=[ImpactArea.MEMORY, ImpactArea.THROUGHPUT, ImpactArea.AVAILABILITY],
            layer="backend",
            detected_by="BackendRules.check_batch_processing",
            estimated_impact="OOM com >50k registros em memória; timeout > 30s",
        )
        rec = PerformanceRecommendation(
            issue_id="BE-006",
            title="Implementar Processamento em Chunks com Backpressure",
            action=(
                "Processe em chunks de 500–5000 registros. "
                "Use generators para streaming de dados. "
                "Implemente backpressure com filas (Celery/RQ) para processos longos."
            ),
            rationale="Chunks mantêm memória constante O(chunk_size) em vez de O(n).",
            effort="medium",
            priority=2,
            code_hint=(
                "def process_in_chunks(queryset, chunk_size: int = 1000):\n"
                "    offset = 0\n"
                "    while True:\n"
                "        chunk = queryset[offset:offset + chunk_size]\n"
                "        if not chunk:\n"
                "            break\n"
                "        yield from chunk\n"
                "        offset += chunk_size\n\n"
                "# PostgreSQL COPY (bulk insert mais rápido)\n"
                "from psycopg2.extras import execute_values\n"
                "execute_values(cursor,\n"
                "    'INSERT INTO products (name, price) VALUES %s',\n"
                "    [(p.name, p.price) for p in products],\n"
                "    page_size=1000\n"
                ")"
            ),
        )
        return issue, rec


# ---------------------------------------------------------------------------
# Regras de Performance — Frontend
# ---------------------------------------------------------------------------

class FrontendRules:
    """
    Regras de performance para camada frontend com foco em Core Web Vitals.
    """

    @staticmethod
    def check_lcp(
        tokens: Set[str], rendering: RenderingStrategy
    ) -> Optional[Tuple[PerformanceIssue, PerformanceRecommendation]]:
        has_images = _has(tokens, "imagem", "image", "img", "hero", "banner", "foto")
        has_preload = _has(tokens, "preload", "lcp preload", "fetchpriority")
        has_lazy_hero = _has(tokens, "lazy hero", "loading lazy hero")

        if not has_images or has_preload:
            return None

        issue = PerformanceIssue(
            id="FE-001",
            title="LCP em Risco — Imagens Hero sem Preload",
            description=(
                "Imagens acima do fold sem preload atrasam o LCP (Largest Contentful Paint). "
                "LCP > 2.5s é penalizado pelo Google e degrada UX."
            ),
            severity=Severity.CRITICAL,
            impact_areas=[ImpactArea.UX, ImpactArea.SEO, ImpactArea.RENDER_PERF],
            layer="frontend",
            detected_by="FrontendRules.check_lcp",
            estimated_impact="LCP > 2.5s → penalidade SEO + 30% abandono de página",
        )
        rec = PerformanceRecommendation(
            issue_id="FE-001",
            title="Implementar Preload + fetchpriority para Imagens Hero",
            action=(
                "Adicione <link rel='preload'> para a imagem hero no <head>. "
                "Use fetchpriority='high' na tag <img>. "
                "Use next/image com priority={true} no Next.js. "
                "Nunca use loading='lazy' em imagens above-the-fold."
            ),
            rationale="Preload da imagem hero pode reduzir LCP em 0.5–1.5s.",
            effort="low",
            priority=1,
            code_hint=(
                "<!-- HTML -->\n"
                "<link rel='preload' as='image' href='/hero.webp' "
                "fetchpriority='high'>\n"
                "<img src='/hero.webp' fetchpriority='high' "
                "alt='Hero' width='1200' height='600'>\n\n"
                "// Next.js\n"
                "<Image src='/hero.webp' priority alt='Hero' "
                "width={1200} height={600} />"
            ),
            references=["https://web.dev/lcp/", "https://web.dev/priority-hints/"],
        )
        return issue, rec

    @staticmethod
    def check_cls(
        tokens: Set[str], rendering: RenderingStrategy
    ) -> Optional[Tuple[PerformanceIssue, PerformanceRecommendation]]:
        has_dynamic = _has(tokens, "anuncio", "ad", "banner dinamico", "dynamic content",
                           "skeleton", "loading state", "placeholder")
        has_dimensions = _has(tokens, "width height", "aspect-ratio", "min-height",
                              "skeleton loader", "cls fix")
        has_fonts = _has(tokens, "google fonts", "custom font", "webfont",
                         "@font-face", "font-display")

        if (not has_dynamic and not has_fonts) or has_dimensions:
            return None

        issue = PerformanceIssue(
            id="FE-002",
            title="CLS em Risco — Conteúdo sem Dimensões Reservadas",
            description=(
                "Conteúdo dinâmico ou fontes carregando sem dimensões reservadas "
                "causa layout shift — CLS > 0.1 penaliza SEO e UX."
            ),
            severity=Severity.HIGH,
            impact_areas=[ImpactArea.UX, ImpactArea.SEO, ImpactArea.RENDER_PERF],
            layer="frontend",
            detected_by="FrontendRules.check_cls",
            estimated_impact="CLS > 0.25 → penalidade grave no Core Web Vitals",
        )
        rec = PerformanceRecommendation(
            issue_id="FE-002",
            title="Reservar Dimensões e Otimizar Font Loading",
            action=(
                "Defina width/height explícitos ou aspect-ratio em todos os elementos dinâmicos. "
                "Use font-display: swap ou optional em @font-face. "
                "Implemente skeleton loaders com dimensões fixas para conteúdo assíncrono."
            ),
            rationale="Dimensões reservadas eliminam layout shifts — CLS → 0.",
            effort="low",
            priority=2,
            code_hint=(
                "/* CSS — Reservar espaço para imagens */\n"
                "img { aspect-ratio: 16/9; width: 100%; object-fit: cover; }\n\n"
                "/* Font loading otimizado */\n"
                "@font-face {\n"
                "  font-family: 'MyFont';\n"
                "  font-display: swap; /* opcional: 'optional' para zero CLS */\n"
                "}\n\n"
                "/* Skeleton loader */\n"
                ".skeleton {\n"
                "  height: 200px; /* dimensão explícita */\n"
                "  background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);\n"
                "  background-size: 200% 100%;\n"
                "  animation: shimmer 1.5s infinite;\n"
                "}"
            ),
            references=["https://web.dev/cls/"],
        )
        return issue, rec

    @staticmethod
    def check_bundle_size(
        tokens: Set[str], rendering: RenderingStrategy
    ) -> Optional[Tuple[PerformanceIssue, PerformanceRecommendation]]:
        has_framework = _has(tokens, "react", "vue", "angular", "next", "nuxt",
                             "remix", "svelte", "webpack", "vite", "rollup")
        has_splitting = _has(tokens, "code splitting", "lazy import", "dynamic import",
                             "import(", "React.lazy", "defineAsyncComponent",
                             "tree shaking", "bundle analysis")

        if not has_framework or has_splitting:
            return None

        issue = PerformanceIssue(
            id="FE-003",
            title="Bundle sem Code Splitting",
            description=(
                "Bundle monolítico carrega todo o código no primeiro load, "
                "mesmo código de rotas nunca visitadas. "
                "FCP e TTI degradam proporcionalmente ao bundle size."
            ),
            severity=Severity.HIGH,
            impact_areas=[ImpactArea.RENDER_PERF, ImpactArea.UX, ImpactArea.BUNDLE_SIZE],
            layer="frontend",
            detected_by="FrontendRules.check_bundle_size",
            estimated_impact="Bundle > 500KB → FCP > 3s em redes 4G",
        )
        rec = PerformanceRecommendation(
            issue_id="FE-003",
            title="Implementar Code Splitting por Rota",
            action=(
                "Use React.lazy + Suspense para code splitting por rota. "
                "Use dynamic import() para componentes pesados (charts, editors, maps). "
                "Analise o bundle com webpack-bundle-analyzer ou vite-plugin-visualizer."
            ),
            rationale="Code splitting reduz bundle inicial em 40–70% em SPAs típicas.",
            effort="medium",
            priority=2,
            code_hint=(
                "// React — lazy loading por rota\n"
                "const Dashboard = React.lazy(() => import('./pages/Dashboard'));\n"
                "const Analytics = React.lazy(() => import('./pages/Analytics'));\n\n"
                "<Suspense fallback={<PageSkeleton />}>\n"
                "  <Routes>\n"
                "    <Route path='/dashboard' element={<Dashboard />} />\n"
                "    <Route path='/analytics' element={<Analytics />} />\n"
                "  </Routes>\n"
                "</Suspense>\n\n"
                "// Componente pesado — lazy no uso\n"
                "const Chart = React.lazy(() => import('recharts').then(\n"
                "  m => ({ default: m.LineChart })\n"
                "));"
            ),
            references=["https://react.dev/reference/react/lazy"],
        )
        return issue, rec

    @staticmethod
    def check_rendering_strategy(
        tokens: Set[str], rendering: RenderingStrategy, profile: LoadProfile
    ) -> Optional[Tuple[PerformanceIssue, PerformanceRecommendation]]:
        has_seo = _has(tokens, "seo", "search engine", "google", "indexacao",
                       "crawl", "meta tags", "open graph")
        has_dynamic_data = _has(tokens, "dados em tempo real", "real time",
                                "dados do usuario", "user specific", "personalizado")

        if rendering != RenderingStrategy.CSR:
            return None
        if not has_seo:
            return None

        issue = PerformanceIssue(
            id="FE-004",
            title="CSR com Requisito de SEO — Estratégia Inadequada",
            description=(
                "Client-Side Rendering produz HTML vazio no primeiro carregamento. "
                "Crawlers têm dificuldade em indexar SPAs puras."
            ),
            severity=Severity.HIGH,
            impact_areas=[ImpactArea.SEO, ImpactArea.UX, ImpactArea.RENDER_PERF],
            layer="frontend",
            detected_by="FrontendRules.check_rendering_strategy",
            estimated_impact="Perda de indexação orgânica — tráfego SEO próximo de zero",
        )

        strategy = "SSG" if not has_dynamic_data else "SSR/ISR"
        rec = PerformanceRecommendation(
            issue_id="FE-004",
            title=f"Migrar para {strategy}",
            action=(
                f"Dados estáticos → SSG (Next.js getStaticProps). "
                f"Dados por usuário → SSR (getServerSideProps) ou ISR. "
                f"Use Next.js, Nuxt ou Astro para suporte nativo."
            ),
            rationale=f"{strategy} entrega HTML pré-renderizado — indexação perfeita + TTFB < 200ms.",
            effort="high",
            priority=1,
            code_hint=(
                "// Next.js — SSG para conteúdo estático\n"
                "export async function getStaticProps() {\n"
                "  const data = await fetchProducts();\n"
                "  return { props: { data }, revalidate: 3600 }; // ISR\n"
                "}\n\n"
                "// SSR para conteúdo dinâmico por request\n"
                "export async function getServerSideProps({ req }) {\n"
                "  const user = await getUser(req);\n"
                "  return { props: { user } };\n"
                "}"
            ),
        )
        return issue, rec

    @staticmethod
    def check_react_rerenders(
        tokens: Set[str], rendering: RenderingStrategy
    ) -> Optional[Tuple[PerformanceIssue, PerformanceRecommendation]]:
        has_react = _has(tokens, "react", "jsx", "tsx", "componente react")
        has_memo = _has(tokens, "memo", "usememo", "usecallback", "react.memo",
                        "shouldcomponentupdate", "pure component")
        has_state = _has(tokens, "usestate", "state", "context", "redux",
                         "zustand", "lista grande", "large list")

        if not has_react or has_memo or not has_state:
            return None

        issue = PerformanceIssue(
            id="FE-005",
            title="Risco de Re-renders Desnecessários",
            description=(
                "State ou context sem memoização causam re-renders em toda "
                "a árvore de componentes, bloqueando o thread principal."
            ),
            severity=Severity.MEDIUM,
            impact_areas=[ImpactArea.RENDER_PERF, ImpactArea.UX],
            layer="frontend",
            detected_by="FrontendRules.check_react_rerenders",
            estimated_impact="Jank > 16ms por frame → animações travando em listas grandes",
        )
        rec = PerformanceRecommendation(
            issue_id="FE-005",
            title="Implementar Memoização Estratégica",
            action=(
                "Use React.memo para componentes puros em listas. "
                "Use useMemo para computações caras. "
                "Use useCallback para handlers passados como props. "
                "Para listas grandes (> 100 itens), use virtualização (react-window)."
            ),
            rationale="Memoização evita re-renders — mantém 60fps em listas grandes.",
            effort="medium",
            priority=3,
            code_hint=(
                "import { memo, useMemo, useCallback } from 'react';\n"
                "import { FixedSizeList } from 'react-window';\n\n"
                "// Componente memoizado\n"
                "const ProductCard = memo(({ product, onSelect }) => (\n"
                "  <div onClick={() => onSelect(product.id)}>{product.name}</div>\n"
                "));\n\n"
                "// Lista virtualizada para > 100 itens\n"
                "const ProductList = ({ products }) => (\n"
                "  <FixedSizeList height={600} itemCount={products.length}\n"
                "    itemSize={80} width='100%'>\n"
                "    {({ index, style }) => (\n"
                "      <div style={style}>\n"
                "        <ProductCard product={products[index]} />\n"
                "      </div>\n"
                "    )}\n"
                "  </FixedSizeList>\n"
                ");"
            ),
            references=["https://react.dev/reference/react/memo", "https://react-window.now.sh/"],
        )
        return issue, rec

    @staticmethod
    def check_css_performance(
        tokens: Set[str], rendering: RenderingStrategy
    ) -> Optional[Tuple[PerformanceIssue, PerformanceRecommendation]]:
        has_css = _has(tokens, "css", "estilo", "animacao", "animation",
                       "transition", "transform")
        has_perf_css = _has(tokens, "will-change", "contain", "content-visibility",
                            "css containment", "compositor layer")
        has_animations = _has(tokens, "animacao", "animation", "scroll animation",
                              "parallax", "hover effect")

        if not has_css or has_perf_css or not has_animations:
            return None

        issue = PerformanceIssue(
            id="FE-006",
            title="Animações CSS sem Otimização de Compositor",
            description=(
                "Animações em propriedades que causam layout/paint (width, height, "
                "top, left, margin) bloqueiam o thread principal."
            ),
            severity=Severity.MEDIUM,
            impact_areas=[ImpactArea.RENDER_PERF, ImpactArea.UX],
            layer="frontend",
            detected_by="FrontendRules.check_css_performance",
            estimated_impact="Layout thrashing → jank visível em animações e scroll",
        )
        rec = PerformanceRecommendation(
            issue_id="FE-006",
            title="Animar Apenas Propriedades do Compositor",
            action=(
                "Anime APENAS transform e opacity — executam no compositor sem "
                "bloquear o main thread. "
                "Use will-change: transform em elementos com animação frequente. "
                "Use content-visibility: auto para seções abaixo do fold."
            ),
            rationale="transform/opacity no compositor = 60fps garantido sem repaints.",
            effort="low",
            priority=3,
            code_hint=(
                "/* ✓ Correto — compositor thread */\n"
                ".card {\n"
                "  transition: transform 200ms ease, opacity 200ms ease;\n"
                "}\n"
                ".card:hover {\n"
                "  transform: translateY(-4px) scale(1.02);\n"
                "  opacity: 0.95;\n"
                "}\n\n"
                "/* ✗ Evitar — causa layout + paint */\n"
                "/* .card:hover { width: 110%; top: -4px; } */\n\n"
                "/* content-visibility para seções abaixo do fold */\n"
                ".below-fold-section {\n"
                "  content-visibility: auto;\n"
                "  contain-intrinsic-size: 0 500px;\n"
                "}"
            ),
            references=["https://web.dev/animations-guide/"],
        )
        return issue, rec

    @staticmethod
    def check_font_performance(
        tokens: Set[str], rendering: RenderingStrategy
    ) -> Optional[Tuple[PerformanceIssue, PerformanceRecommendation]]:
        has_fonts = _has(tokens, "fonte", "font", "tipografia", "typography",
                         "google fonts", "custom font", "@font-face")
        has_font_opt = _has(tokens, "font-display", "preload font", "woff2",
                            "subset", "font subset", "variable font")

        if not has_fonts or has_font_opt:
            return None

        issue = PerformanceIssue(
            id="FE-007",
            title="Fontes Web sem Otimização de Carregamento",
            description=(
                "Fontes sem preload ou font-display causam FOUT/FOIT "
                "(flash de texto invisível/sem estilo), aumentando CLS e FCP."
            ),
            severity=Severity.MEDIUM,
            impact_areas=[ImpactArea.UX, ImpactArea.RENDER_PERF],
            layer="frontend",
            detected_by="FrontendRules.check_font_performance",
            estimated_impact="FOUT por 200–2000ms + CLS de fontes afetando LCP",
        )
        rec = PerformanceRecommendation(
            issue_id="FE-007",
            title="Otimizar Carregamento de Fontes Web",
            action=(
                "Prefira fontes variáveis (1 arquivo, múltiplos pesos). "
                "Use apenas woff2 (melhor compressão). "
                "Faça subsetting para remover caracteres não usados. "
                "Preload a fonte principal. Use font-display: swap."
            ),
            rationale="Subsetting + woff2 reduz tamanho de fonte em 60–80%.",
            effort="low",
            priority=3,
            code_hint=(
                "<!-- Preload da fonte principal -->\n"
                "<link rel='preload' href='/fonts/inter-var.woff2'\n"
                "      as='font' type='font/woff2' crossorigin>\n\n"
                "@font-face {\n"
                "  font-family: 'Inter';\n"
                "  src: url('/fonts/inter-var.woff2') format('woff2');\n"
                "  font-weight: 100 900; /* fonte variável */\n"
                "  font-display: swap;\n"
                "  unicode-range: U+0000-00FF; /* subset latin */\n"
                "}"
            ),
            references=["https://web.dev/font-best-practices/"],
        )
        return issue, rec

    @staticmethod
    def check_image_optimization(
        tokens: Set[str], rendering: RenderingStrategy
    ) -> Optional[Tuple[PerformanceIssue, PerformanceRecommendation]]:
        has_images = _has(tokens, "imagem", "image", "img", "foto", "photo",
                          "galeria", "gallery", "thumbnail")
        has_img_opt = _has(tokens, "webp", "avif", "next/image", "responsive image",
                           "srcset", "picture", "lazy load", "blur placeholder")

        if not has_images or has_img_opt:
            return None

        issue = PerformanceIssue(
            id="FE-008",
            title="Imagens sem Pipeline de Otimização",
            description=(
                "Imagens sem formato moderno (WebP/AVIF), sem lazy loading "
                "e sem responsive srcset degradam LCP e consomem bandwidth desnecessário."
            ),
            severity=Severity.HIGH,
            impact_areas=[ImpactArea.RENDER_PERF, ImpactArea.UX, ImpactArea.COST],
            layer="frontend",
            detected_by="FrontendRules.check_image_optimization",
            estimated_impact="Imagens PNG/JPG sem otimização = 2–5x tamanho maior que WebP/AVIF",
        )
        rec = PerformanceRecommendation(
            issue_id="FE-008",
            title="Implementar Pipeline de Imagens Moderno",
            action=(
                "Use AVIF (melhor) ou WebP como formato principal. "
                "Implemente responsive images com srcset. "
                "Use lazy loading (loading='lazy') para imagens below-the-fold. "
                "No Next.js, use <Image> com blur placeholder automático."
            ),
            rationale="AVIF vs JPEG: mesma qualidade com 50% menos bytes.",
            effort="medium",
            priority=2,
            code_hint=(
                "<!-- HTML responsivo com formatos modernos -->\n"
                "<picture>\n"
                "  <source srcset='/img/hero.avif' type='image/avif'>\n"
                "  <source srcset='/img/hero.webp' type='image/webp'>\n"
                "  <img src='/img/hero.jpg' alt='Hero'\n"
                "       srcset='/img/hero-400.jpg 400w, /img/hero-800.jpg 800w'\n"
                "       sizes='(max-width: 768px) 100vw, 50vw'\n"
                "       width='800' height='450'\n"
                "       loading='lazy'>\n"
                "</picture>\n\n"
                "// Next.js\n"
                "<Image src='/img/hero.jpg' alt='Hero'\n"
                "       width={800} height={450}\n"
                "       placeholder='blur' quality={85} />"
            ),
            references=["https://web.dev/uses-optimized-images/"],
        )
        return issue, rec


# ---------------------------------------------------------------------------
# PerformanceDesignAgent v2
# ---------------------------------------------------------------------------

class PerformanceDesignAgent:
    """
    Agente de análise de performance full-stack.

    Analisa contexto de design e retorna PerformanceReport com:
    - Score 0–100 por camada (backend, frontend, database, infra)
    - Issues priorizados por severidade e impacto
    - Recomendações com code hints e referências
    - Core Web Vitals analysis
    - Quick wins e riscos arquiteturais
    - Integração com organismo biológico (bus, MTA, SAMe)
    """

    def __init__(
        self,
        mta_recycler: Optional[Any] = None,
        same_engine: Optional[Any] = None,
    ):
        self._mta  = mta_recycler
        self._same = same_engine

        self._backend_rules = [
            BackendRules.check_n_plus_one,
            BackendRules.check_cache_strategy,
            BackendRules.check_async_io,
            BackendRules.check_pagination,
            BackendRules.check_db_indexes,
            BackendRules.check_connection_pool,
            BackendRules.check_circuit_breaker,
            BackendRules.check_batch_processing,
        ]

        self._frontend_rules = [
            FrontendRules.check_lcp,
            FrontendRules.check_cls,
            FrontendRules.check_bundle_size,
            FrontendRules.check_rendering_strategy,
            FrontendRules.check_react_rerenders,
            FrontendRules.check_css_performance,
            FrontendRules.check_font_performance,
            FrontendRules.check_image_optimization,
        ]

    def analyze(
        self,
        design_context: Dict[str, Any],
        knowledge_context: str = "",
        error_context: str = "",
        **kwargs,
    ) -> Dict[str, Any]:

        logger.info("⚡ [PERF-DESIGN] Iniciando análise full-stack de performance...")

        # ── Contexto unificado em tokens ─────────────────────────────────────
        architecture  = design_context.get("architecture", {})
        requirements  = design_context.get("requirements", {})
        combined_text = " ".join([
            str(architecture), str(requirements),
            knowledge_context, str(design_context)
        ])
        tokens        = _tokenize(combined_text)
        error_tokens  = _tokenize(error_context)

        if knowledge_context:
            logger.info("⚡ [PERF-DESIGN] knowledge_context=%d chars", len(knowledge_context))
        if error_context:
            logger.info("⚡ [PERF-DESIGN] error_context=%d chars", len(error_context))

        # ── Perfis ───────────────────────────────────────────────────────────
        profile   = _detect_load_profile(tokens)
        rendering = _detect_rendering(tokens)
        logger.info("⚡ [PERF-DESIGN] load_profile=%s | rendering=%s", profile, rendering)

        # ── Executa regras ───────────────────────────────────────────────────
        issues:  List[PerformanceIssue]          = []
        recs:    List[PerformanceRecommendation] = []
        score    = PerformanceScore()

        for rule in self._backend_rules:
            try:
                result = rule(tokens, error_tokens, profile)
                if result:
                    issue, rec = result
                    # Filtra por load profile se restrito
                    if issue.load_profiles and profile not in issue.load_profiles:
                        continue
                    issues.append(issue)
                    recs.append(rec)
                    self._apply_score_deduction(score, issue)
            except Exception as exc:
                logger.warning("⚡ [PERF-DESIGN] Regra backend falhou: %s", exc)

        for rule in self._frontend_rules:
            try:
                if rule == FrontendRules.check_rendering_strategy:
                    result = rule(tokens, rendering, profile)
                else:
                    result = rule(tokens, rendering)
                if result:
                    issue, rec = result
                    issues.append(issue)
                    recs.append(rec)
                    self._apply_score_deduction(score, issue)
            except Exception as exc:
                logger.warning("⚡ [PERF-DESIGN] Regra frontend falhou: %s", exc)

        # ── Core Web Vitals ──────────────────────────────────────────────────
        cwv = self._analyze_cwv(issues)

        # ── Quick wins e riscos ──────────────────────────────────────────────
        quick_wins = [
            rec.title for rec in recs
            if rec.effort == "low"
        ]
        arch_risks = [
            issue.title for issue in issues
            if issue.severity == Severity.CRITICAL
        ]

        # ── Sort por prioridade ──────────────────────────────────────────────
        recs.sort(key=lambda r: r.priority)
        issues.sort(key=lambda i: (
            ["critical","high","medium","low"].index(i.severity.value)
        ))

        # ── Recycle no PromptRecycler se houver problemas críticos ──────────
        if self._mta and _MTA_AVAILABLE and arch_risks:
            try:
                self._mta.recycle(arch_risks[:3])
            except Exception:
                pass

        # ── Relatório ────────────────────────────────────────────────────────
        report = PerformanceReport(
            load_profile=profile,
            rendering_strategy=rendering,
            score=score,
            issues=issues,
            recommendations=recs,
            cwv=cwv,
            summary={
                "total_issues": len(issues),
                "critical": sum(1 for i in issues if i.severity == Severity.CRITICAL),
                "high":     sum(1 for i in issues if i.severity == Severity.HIGH),
                "medium":   sum(1 for i in issues if i.severity == Severity.MEDIUM),
                "low":      sum(1 for i in issues if i.severity == Severity.LOW),
                "score_overall": score.overall,
                "score_backend": score.backend,
                "score_frontend": score.frontend,
                "score_database": score.database,
                "quick_wins": len(quick_wins),
            },
            quick_wins=quick_wins,
            architectural_risks=arch_risks,
        )

        logger.info(
            "⚡ [PERF-DESIGN] Score: overall=%d | backend=%d | frontend=%d | "
            "db=%d | issues=%d (critical=%d high=%d) | rendering=%s | profile=%s",
            score.overall, score.backend, score.frontend, score.database,
            len(issues), report.critical_count, report.high_count,
            rendering.value, profile.value,
        )

        # ── Publica no AcetylcholineBus ──────────────────────────────────────
        if _BUS_AVAILABLE:
            try:
                bus.publish(AgentMessage(
                    topic="performance.analyzed",
                    sender="performance_design_agent",
                    data=report.summary,
                ))
            except Exception:
                pass

        return {
            "performance_design_report": report.to_dict(),
            "performance_requirements": [r.action for r in recs],
            "quick_wins": quick_wins,
            "architectural_risks": arch_risks,
            "score": score.overall,
            "cwv": asdict(cwv),
        }

    def _apply_score_deduction(self, score: PerformanceScore, issue: PerformanceIssue):
        deductions = {
            Severity.CRITICAL: 20,
            Severity.HIGH:     12,
            Severity.MEDIUM:    6,
            Severity.LOW:       2,
        }
        amount = deductions[issue.severity]
        score.deduct(issue.layer if issue.layer in ("backend","frontend","database","infra") else "backend", amount)

    def _analyze_cwv(self, issues: List[PerformanceIssue]) -> CoreWebVitalsAnalysis:
        cwv = CoreWebVitalsAnalysis()
        for issue in issues:
            if issue.id == "FE-001":
                cwv.lcp_risk = issue.description
                cwv.score -= 25
            if issue.id == "FE-002":
                cwv.cls_risk = issue.description
                cwv.score -= 20
            if issue.id == "FE-006":
                cwv.inp_risk = issue.description
                cwv.score -= 15
            if issue.id == "FE-004":
                cwv.ttfb_risk = issue.description
                cwv.score -= 20
            if issue.id == "FE-003":
                cwv.fcp_risk = issue.description
                cwv.score -= 20
        cwv.score = max(0, cwv.score)
        return cwv
