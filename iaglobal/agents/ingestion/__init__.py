# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
from iaglobal.agents.ingestion.file_ingestion_agent import FileIngestionAgent
from iaglobal.agents.ingestion.paper_ingestor import PaperIngestor, ingest_batch
from iaglobal.agents.ingestion.paper_parser import (
    PaperParser,
    parse_paper_file,
    PaperMetadata,
)
from iaglobal.agents.ingestion.hypothesis_generator import (
    HypothesisGenerator,
    Hypothesis,
    generate_hypotheses_for_paper,
    validate_hypothesis_schema,
)
from iaglobal.agents.ingestion.experiment_runner import (
    ExperimentRunner,
    ExperimentResult,
    run_experiment_for_hypothesis,
    validate_hypotheses,
)
from iaglobal.agents.ingestion.consolidation import (
    ResearchConsolidator,
    ConsolidatedPaper,
    consolidate_paper,
    consolidate_full_pipeline,
)
from iaglobal.agents.ingestion.meta_learner import (
    MetaLearner,
    PaperRecommendation,
    MetaAnalysis,
    run_meta_learning,
)

__all__ = [
    "FileIngestionAgent",
    "PaperIngestor",
    "ingest_batch",
    "PaperParser",
    "parse_paper_file",
    "PaperMetadata",
    "HypothesisGenerator",
    "Hypothesis",
    "generate_hypotheses_for_paper",
    "validate_hypothesis_schema",
    "ExperimentRunner",
    "ExperimentResult",
    "run_experiment_for_hypothesis",
    "validate_hypotheses",
    "ResearchConsolidator",
    "ConsolidatedPaper",
    "consolidate_paper",
    "consolidate_full_pipeline",
    "MetaLearner",
    "PaperRecommendation",
    "MetaAnalysis",
    "run_meta_learning",
]
