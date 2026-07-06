from enum import Enum, auto


class PipelineStage(Enum):
    INIT = auto()

    MEMORY = auto()

    PLANNING = auto()

    GENERATION = auto()

    METABOLISM = auto()

    VALIDATION = auto()

    SECURITY = auto()

    TESTING = auto()

    EXECUTION = auto()

    REFLECTION = auto()

    PERSISTENCE = auto()

    COMPLETE = auto()

    FAILED = auto()
