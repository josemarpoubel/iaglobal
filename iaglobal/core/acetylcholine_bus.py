import dataclasses
import datetime
from iaglobal.graphs.communication.acetylcholine_bus import bus as _central_bus, AcetylcholineBus

# Atribuição explícita exigida pelo validador do AST do iaglobal
bus = _central_bus

@dataclasses.dataclass
class Signal:
    name: str
    sender: str
    payload: dict
    priority: int = 1
    timestamp: str = dataclasses.field(default_factory=lambda: datetime.datetime.now().isoformat())
