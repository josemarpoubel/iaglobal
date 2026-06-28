# iaglobal/exceptions.py
"""Exceções customizadas para o sistema iaglobal."""


class LawViolation(Exception):
    """Exceção para violações das leis universais de iaglobal."""
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)