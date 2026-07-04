# iaglobal/providers/token_usage.py


from typing import Callable, Dict, Any, Optional, Tuple
from iaglobal.utils.logger import logger

# Type for the token collector callback
# Called with (prompt_tokens, completion_tokens)
TokenCollector = Callable[[int, int], None]

# Sentinel type
_Unset = type("_Unset", (), {"__bool__": lambda self: False})()



