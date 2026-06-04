import ast
import logging

from dataclasses import dataclass
from typing import Tuple, List, Optional

from .ast_security import validate_ast_security
from .syntax import validar_sintaxe
from .normalization import normalizar_codigo

logger = logging.getLogger("IA_GLOBAL_VALIDATION")


@dataclass
class ValidationResult:
    valid: bool
    code: Optional[str]
    errors: List[str]


class ValidationEngine:
    """
    ÚNICO ponto de verdade para validação de código.
    """

    def validate(self, code: str) -> ValidationResult:

        errors = []

        try:
            # 1. Normalização (LLM cleanup)
            code = normalizar_codigo(code)

            # 2. Syntax check (ÚNICO ast.parse do sistema)
            validar_sintaxe(code)

            tree = ast.parse(code)

            # 3. Security AST validation
            validate_ast_security(tree)

            logger.info("✅ [VALIDATION] Code approved")

            return ValidationResult(
                valid=True,
                code=code,
                errors=[]
            )

        except SyntaxError as e:
            errors.append(f"SyntaxError: {e}")

        except Exception as e:
            errors.append(str(e))

        logger.warning(
            f"🚫 [VALIDATION] Failed: {errors}"
        )

        return ValidationResult(
            valid=False,
            code=None,
            errors=errors
        )
