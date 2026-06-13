# iaglobal/validation/parser.py

import ast

from typing import Tuple


def parse_codigo(codigo: str) -> Tuple[bool, object, str]:

    """
    Parsing centralizado da AST.
    """

    try:
        
        tree = ValidationEngine().validate(codigo)
        
        return True, tree, ""

    except SyntaxError as e:
        return False, None, str(e)
