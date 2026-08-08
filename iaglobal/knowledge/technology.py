# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
Technology Registry — mapeia capacidades para implementações concretas.

Cada TechnologyDescriptor representa uma biblioteca/ferramenta que implementa
uma ou mais capacidades. O Bandit escolhe *dentro* de uma capacidade entre
os candidatos disponíveis.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from iaglobal.knowledge.contracts import MaturityLevel, KnowledgeProvenance


@dataclass(frozen=True)
class TechnologyScore:
    static: float = 0.0
    benchmark: float | None = None
    experience: float | None = None
    ecosystem_health: float | None = None
    compatibility: float | None = None

    @property
    def composite(self) -> float:
        factors: list[float] = [self.static]
        weights: list[float] = [0.30]
        if self.benchmark is not None:
            factors.append(self.benchmark)
            weights.append(0.25)
        if self.experience is not None:
            factors.append(self.experience)
            weights.append(0.20)
        if self.ecosystem_health is not None:
            factors.append(self.ecosystem_health)
            weights.append(0.15)
        if self.compatibility is not None:
            factors.append(self.compatibility)
            weights.append(0.10)
        total_weight = sum(weights)
        return round(sum(f * w for f, w in zip(factors, weights)) / total_weight, 4)


@dataclass(frozen=True)
class TechnologyDescriptor:
    name: str
    supports: frozenset[str]
    maturity: MaturityLevel = MaturityLevel.EXPERIMENTAL
    difficulty: float = 0.5
    offline: bool = True
    license: str = ""
    python_only: bool = True
    pros: tuple[str, ...] = ()
    cons: tuple[str, ...] = ()
    provenance: KnowledgeProvenance | None = None
    aliases: frozenset[str] = frozenset()
    tags: frozenset[str] = frozenset()
    execution_runtime: frozenset[str] = frozenset({"python"})
    composite_score: TechnologyScore | None = None

    @property
    def score(self) -> float:
        return self.maturity.value * (1.0 - self.difficulty * 0.3)

    @property
    def effective_score(self) -> float:
        if self.composite_score is not None:
            return self.composite_score.composite
        return self.score


@dataclass
class TechnologyGraph:
    _techs: dict[str, TechnologyDescriptor] = field(default_factory=dict)

    def register(self, tech: TechnologyDescriptor) -> None:
        self._techs[tech.name] = tech

    def get(self, name: str) -> TechnologyDescriptor:
        if name not in self._techs:
            raise KeyError(f"Technology '{name}' not registered")
        return self._techs[name]

    def candidates_for(self, capability: str) -> list[TechnologyDescriptor]:
        return sorted(
            [t for t in self._techs.values() if capability in t.supports],
            key=lambda t: t.effective_score,
            reverse=True,
        )

    def all(self) -> list[TechnologyDescriptor]:
        return list(self._techs.values())


CATALOG: list[TechnologyDescriptor] = [
    # ── Document / PDF ──
    TechnologyDescriptor(
        name="reportlab",
        supports=frozenset({"pdf_generation", "document_creation"}),
        maturity=MaturityLevel.GOLD,
        difficulty=0.3,
        offline=True,
        license="BSD",
        pros=("estável", "alta performance", "controle total sobre layout"),
        cons=("API verbosa", "curva de aprendizado"),
    ),
    TechnologyDescriptor(
        name="weasyprint",
        supports=frozenset({"pdf_generation", "html_to_pdf"}),
        maturity=MaturityLevel.MATURE,
        difficulty=0.2,
        offline=True,
        license="BSD",
        pros=("HTML/CSS → PDF", "ótimo para relatórios"),
        cons=("lento em documentos grandes", "alto consumo de RAM"),
    ),
    TechnologyDescriptor(
        name="fpdf2",
        supports=frozenset({"pdf_generation"}),
        maturity=MaturityLevel.MATURE,
        difficulty=0.2,
        offline=True,
        license="LGPL",
        pros=("leve", "sem dependências", "API simples"),
        cons=("recursos limitados", "sem suporte nativo a CSS"),
    ),
    TechnologyDescriptor(
        name="borb",
        supports=frozenset({"pdf_generation", "pdf_reading", "pdf_ocr"}),
        maturity=MaturityLevel.IMMATURE,
        difficulty=0.4,
        offline=True,
        license="AGPL",
        pros=("leitura e escrita", "OCR integrado"),
        cons=("licença AGPL", "comunidade pequena"),
    ),
    TechnologyDescriptor(
        name="pypdf",
        supports=frozenset({"pdf_reading", "pdf_merging", "pdf_splitting"}),
        maturity=MaturityLevel.MATURE,
        difficulty=0.1,
        offline=True,
        license="BSD",
        pros=("leve", "estável", "excelente para manipulação"),
        cons=("não gera PDF do zero", "sem layout"),
    ),
    # ── Excel / Spreadsheets ──
    TechnologyDescriptor(
        name="openpyxl",
        supports=frozenset({"excel_reading", "excel_writing", "spreadsheet"}),
        maturity=MaturityLevel.STABLE,
        difficulty=0.2,
        offline=True,
        license="MIT",
        pros=("maduro", "suporta .xlsx", "fórmulas"),
        cons=("lento com arquivos grandes", "não suporta .xls"),
    ),
    TechnologyDescriptor(
        name="xlsxwriter",
        supports=frozenset({"excel_writing", "spreadsheet"}),
        maturity=MaturityLevel.STABLE,
        difficulty=0.1,
        offline=True,
        license="BSD",
        pros=("rápido", "otimizado para escrita"),
        cons=("não lê arquivos existentes",),
    ),
    TechnologyDescriptor(
        name="pandas",
        supports=frozenset(
            {
                "data_analysis",
                "excel_reading",
                "excel_writing",
                "csv_processing",
                "dataframe",
            }
        ),
        maturity=MaturityLevel.GOLD,
        difficulty=0.4,
        offline=True,
        license="BSD",
        pros=("onipresente", "rico em funcionalidades"),
        cons=("overhead para tarefas simples", "curva de aprendizado"),
    ),
    # ── Web / API ──
    TechnologyDescriptor(
        name="fastapi",
        supports=frozenset({"rest_api", "web_backend", "api_development"}),
        maturity=MaturityLevel.STABLE,
        difficulty=0.3,
        offline=False,
        license="MIT",
        pros=("performance", "docs automáticos", "type hints"),
        cons=("ecossistema mais novo que Django",),
    ),
    TechnologyDescriptor(
        name="flask",
        supports=frozenset({"rest_api", "web_backend", "web_application"}),
        maturity=MaturityLevel.GOLD,
        difficulty=0.2,
        offline=False,
        license="BSD",
        pros=("simples", "flexível", "enorme ecossistema"),
        cons=("mais boilerplate que FastAPI", "sem async nativo"),
    ),
    TechnologyDescriptor(
        name="django",
        supports=frozenset({"web_application", "web_backend", "admin_panel"}),
        maturity=MaturityLevel.GOLD,
        difficulty=0.5,
        offline=False,
        license="BSD",
        pros=("baterias incluídas", "admin", "ORM", "segurança"),
        cons=("pesado", "monolítico", "overhead para APIs simples"),
    ),
    # ── CLI ──
    TechnologyDescriptor(
        name="typer",
        supports=frozenset({"cli_application", "command_line"}),
        maturity=MaturityLevel.STABLE,
        difficulty=0.1,
        offline=True,
        license="MIT",
        pros=("simples", "type hints", "autocompletion"),
        cons=("menos flexível que argparse para casos complexos",),
    ),
    TechnologyDescriptor(
        name="rich",
        supports=frozenset({"cli_application", "terminal_ui", "logging"}),
        maturity=MaturityLevel.STABLE,
        difficulty=0.2,
        offline=True,
        license="MIT",
        pros=("saída colorida", "tables", "markdown", "progress"),
        cons=("apenas terminal", "sem TUI interativa"),
    ),
    # ── AI / Embeddings ──
    TechnologyDescriptor(
        name="sentence-transformers",
        supports=frozenset({"embeddings", "semantic_search", "text_similarity"}),
        maturity=MaturityLevel.STABLE,
        difficulty=0.4,
        offline=False,
        license="Apache 2.0",
        pros=("modelos state-of-art", "fácil uso"),
        cons=("pesado", "download de modelos grandes"),
    ),
    TechnologyDescriptor(
        name="chromadb",
        supports=frozenset({"vector_database", "semantic_search"}),
        maturity=MaturityLevel.MATURE,
        difficulty=0.3,
        offline=True,
        license="Apache 2.0",
        pros=("leve", "embedding nativo", "fácil setup"),
        cons=("escalabilidade limitada", "sem distribuição nativa"),
    ),
    # ── Image Processing ──
    TechnologyDescriptor(
        name="pillow",
        supports=frozenset({"image_processing", "image_manipulation", "thumbnail"}),
        maturity=MaturityLevel.GOLD,
        difficulty=0.2,
        offline=True,
        license="Historical",
        pros=("ubíquo", "estável", "leve"),
        cons=("sem suporte a formatos modernos RAW",),
    ),
    TechnologyDescriptor(
        name="opencv-python",
        supports=frozenset({"image_processing", "computer_vision", "video_processing"}),
        maturity=MaturityLevel.STABLE,
        difficulty=0.5,
        offline=True,
        license="Apache 2.0",
        pros=("onipresente em visão", "GPU加速"),
        cons=("API enorme", "instalação complexa em alguns SOs"),
    ),
]
