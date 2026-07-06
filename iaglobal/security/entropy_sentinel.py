"""Wrapper: re-export EntropySentinel do módulo immunity para security.

Mantém compatibilidade com imports existentes em:
- iaglobal.security.entropy_sentinel
- iaglobal.security.__init__.py
"""

from iaglobal.immunity.entropy_sentinel import EntropySentinel, entropy_sentinel

__all__ = ["EntropySentinel", "entropy_sentinel"]
