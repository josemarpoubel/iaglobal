# iaglobal/events/event_types.py

"""
Definição de constantes de eventos e passos do pipeline.
Este arquivo deve ser livre de dependências externas para evitar ciclos de importação.
"""


class EventType:
    TASK_CREATED = "task_created"
    ROUTE_DECIDED = "route_decided"
    EXECUTION_STARTED = "execution_started"
    EXECUTION_COMPLETED = "execution_completed"
    EXECUTION_FAILED = "execution_failed"
    NODE_FAILED = "node_failed"
    EXECUTION_ABORTED = "execution_aborted"
    CRITICAL_NODE_FAILED = "critical_node_failed"
    SANITY_BARRIER_TRIGGERED = "sanity_barrier_triggered"
    MEMORY_SAVED = "memory_saved"
    REFLECTION_COMPLETED = "reflection_completed"
    SOLUTION_GENERATED = "solution_generated"
    PIPELINE_METRICS = "pipeline_metrics"
    KNOWLEDGE_FUSED = "knowledge_fused"
    CRITIC_SWARM_COMPLETED = "critic_swarm_completed"
    RANKING_COMPLETED = "ranking_completed"
    DEBUG_ITERATION = "debug_iteration"
    REFLEXION_CYCLE = "reflexion_cycle"

    PIPELINE_STAGE = "pipeline.stage.completed"

    ALL = [
        TASK_CREATED,
        ROUTE_DECIDED,
        EXECUTION_STARTED,
        EXECUTION_COMPLETED,
        EXECUTION_FAILED,
        NODE_FAILED,
        EXECUTION_ABORTED,
        CRITICAL_NODE_FAILED,
        SANITY_BARRIER_TRIGGERED,
        MEMORY_SAVED,
        REFLECTION_COMPLETED,
        SOLUTION_GENERATED,
        PIPELINE_METRICS,
        KNOWLEDGE_FUSED,
        CRITIC_SWARM_COMPLETED,
        RANKING_COMPLETED,
        DEBUG_ITERATION,
        REFLEXION_CYCLE,
        PIPELINE_STAGE,
    ]


class PipelineStep:
    TASK_NORMALIZATION = "task_normalization"
    MEMORY_LOOKUP = "memory_lookup"
    CANDIDATE_SELECTION = "candidate_selection"
    MODEL_SELECTION = "model_selection"
    LOCK = "lock"
    EXECUTION_METRICS = "execution_metrics"
    MEMORY_STORE = "memory_store"
    EVOLUTION_CHECK = "evolution_check"

    ALL = [
        TASK_NORMALIZATION,
        MEMORY_LOOKUP,
        CANDIDATE_SELECTION,
        MODEL_SELECTION,
        LOCK,
        EXECUTION_METRICS,
        MEMORY_STORE,
        EVOLUTION_CHECK,
    ]
