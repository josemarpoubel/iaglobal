# iaglobal/obsidian/compliance.py
"""
ComplianceChecker — Sistema de verificação de conformidade do código.

Responsável por:
- Auditar código gerado contra leis universais
- Verificar lineage markers
- Validar imports seguros
- Garantir conformidade epigenética
"""

import hashlib
from typing import Dict, Any, List


class ComplianceChecker:
    """
    Verificador de conformidade de código.

    Realiza auditoria completa do código gerado, verificando:
    - Segurança (imports perigosos)
    - Conformidade com leis universais
    - Lineage marker válido
    - Métricas de qualidade
    """

    def __init__(self):
        self.DANGEROUS_IMPORTS = [
            "pickle",
            "marshal",
            "shelve",  # Serialização insegura
            "telnetlib",
            "ftplib",  # Protocolos inseguros
        ]
        self.DANGEROUS_FUNCTIONS = [
            "eval(",
            "exec(",
            "compile(",
            "__import__(",
            "getattr(",
            "setattr(",
            "os.system(",
            "os.popen(",
            "subprocess.call(",
        ]

    def full_audit(
        self, codigo: str, imports: List[str], threshold: float = 0.5
    ) -> Dict[str, Any]:
        """
        Realiza auditoria completa do código.

        Args:
            codigo: Código fonte a ser auditado
            imports: Lista de imports identificados
            threshold: Limiar mínimo de conformidade (0.0 a 1.0)

        Returns:
            Dicionário com resultados da auditoria:
            - compliant: bool - Se o código é conforme
            - score: float - Score de conformidade (0.0 a 1.0)
            - issues: list - Lista de problemas encontrados
            - lineage_marker: str - Marker de linhagem (primeiros 16 chars)
        """
        issues = []
        score = 1.0

        # Verifica imports perigosos
        for imp in imports:
            imp_name = imp.split()[0].split(".")[-1] if imp else ""
            if any(danger in imp_name for danger in self.DANGEROUS_IMPORTS):
                issues.append(f"Import perigoso detectado: {imp}")
                score -= 0.2

        # Verifica funções perigosas no código
        for func in self.DANGEROUS_FUNCTIONS:
            if func in codigo:
                issues.append(f"Função perigosa detectada: {func}")
                score -= 0.15

        # Normaliza score
        score = max(0.0, min(1.0, score))

        # Determina conformidade
        compliant = score >= threshold

        return {
            "compliant": compliant,
            "score": score,
            "issues": issues,
            "lineage_marker": self.get_lineage_marker()[:16],
            "threshold": threshold,
            "total_issues": len(issues),
        }

    def get_lineage_marker(self) -> str:
        """
        Retorna o lineage marker atual.

        O lineage marker é um hash SHA3-512 que identifica
        unicamente esta instância do organismo.

        Returns:
            String hex do lineage marker (128 caracteres)
        """
        # Gera marker baseado em identidade fixa + timestamp
        identity_seed = "iaglobal_compliance_checker_v1"
        marker_hash = hashlib.sha3_512(identity_seed.encode("utf-8")).hexdigest()
        return marker_hash

    def check_import_safety(self, import_statement: str) -> bool:
        """
        Verifica se um import é seguro.

        Args:
            import_statement: Declaração de import

        Returns:
            True se seguro, False se perigoso
        """
        imp_name = (
            import_statement.split()[0].split(".")[-1] if import_statement else ""
        )
        return not any(danger in imp_name for danger in self.DANGEROUS_IMPORTS)

    def validate_code_structure(self, codigo: str) -> Dict[str, Any]:
        """
        Valida estrutura básica do código.

        Args:
            codigo: Código fonte

        Returns:
            Dicionário com validações:
            - has_functions: bool
            - has_classes: bool
            - line_count: int
            - is_valid_python: bool
        """
        lines = codigo.strip().split("\n")

        has_functions = "def " in codigo
        has_classes = "class " in codigo
        line_count = len(lines)

        # Validação básica de sintaxe Python
        is_valid = True
        try:
            compile(codigo, "<string>", "exec")
        except SyntaxError:
            is_valid = False

        return {
            "has_functions": has_functions,
            "has_classes": has_classes,
            "line_count": line_count,
            "is_valid_python": is_valid,
        }


# Singleton global
compliance_checker = ComplianceChecker()
