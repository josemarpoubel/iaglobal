"""Runtime environment for code execution."""

from typing import Any, Dict, Optional

class Runtime:
    """Manages the execution runtime environment."""
    
    def __init__(self):
        self.global_scope = {}
        self.local_scope = {}
        self.execution_history = []
    
    def execute(self, code: str, globals_dict: Dict = None, locals_dict: Dict = None) -> Any:
        """Execute code in the runtime environment."""
        try:
            globals_dict = globals_dict or self.global_scope
            locals_dict = locals_dict or self.local_scope
            result = eval(code, globals_dict, locals_dict)
            self.execution_history.append({'code': code, 'result': result, 'error': None})
            return result
        except Exception as e:
            self.execution_history.append({'code': code, 'result': None, 'error': str(e)})
            raise
    
    def get_history(self) -> list:
        """Get execution history."""
        return self.execution_history
