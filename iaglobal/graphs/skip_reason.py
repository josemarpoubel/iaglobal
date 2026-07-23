# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
Skip reasons for node execution tracking.

Each constant maps to a human-readable explanation used in
pipeline coverage reports and observability dashboards.
"""

DEPENDENCY_NOT_MET = "dependency_not_met"
ALREADY_EXECUTED = "already_executed"
ABORTED_BY_SANITY = "aborted_by_sanity_barrier"
ABORTED_BY_RECOVERY = "aborted_by_recovery"
NOT_READY = "not_ready"
NO_INPUT_CANDIDATES = "no_input_candidates"
NOT_IN_TOPOLOGY = "not_in_topology"
OPTIONAL_SKIPPED = "optional_node_skipped"
TIMEOUT = "timeout"
NOT_IN_BUILDER = "not_in_builder_graph"

REASON_LABELS: dict[str, str] = {
    DEPENDENCY_NOT_MET: "Dependência pendente",
    ALREADY_EXECUTED: "Já executado (checkpoint)",
    ABORTED_BY_SANITY: "Abortado — Sanity Barrier",
    ABORTED_BY_RECOVERY: "Abortado — RecoveryPolicy ABORT",
    NOT_READY: "Ainda não pronto no ciclo atual",
    NO_INPUT_CANDIDATES: "Sem candidatos de entrada (fusion)",
    NOT_IN_TOPOLOGY: "Não classificado na topologia",
    OPTIONAL_SKIPPED: "Nó opcional pulado",
    TIMEOUT: "Timeout de execução",
    NOT_IN_BUILDER: "Presente na skill list mas não no grafo executável",
}
