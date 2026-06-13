# syntax.py (Syntax validation module for Python code.)

import ast
from typing import Tuple, Dict, Any, Optional
import builtins
from iaglobal.utils.logger import logger

import ast


def validar_sintaxe(code: str) -> None:
    """
    ÚNICO ponto do sistema onde ast.parse é permitido.
    """

    try:
        ast.parse(code)

    except SyntaxError as e:
        raise SyntaxError(f"Invalid syntax: {e}")

class ScopeAnalyzer(ast.NodeVisitor):
    """Analisa estaticamente o escopo para encontrar variáveis não declaradas e erros óbvios."""
    def __init__(self):
        self.scopes = [set()]  # Pilha de escopos (começa com o global)
        self.errors = []

    def visit_FunctionDef(self, node):
        # Entra em um novo escopo de função
        func_scope = set()
        
        # Adiciona os argumentos da função ao escopo local
        for arg in node.args.args:
            func_scope.add(arg.arg)
        if node.args.vararg:
            func_scope.add(node.args.vararg.arg)
        if node.args.kwarg:
            func_scope.add(node.args.kwarg.arg)
            
        self.scopes.append(func_scope)
        self.generic_visit(node)
        self.scopes.pop()  # Sai do escopo da função

    def visit_Assign(self, node):
        # Mapeia variáveis e iterações locais (ex: for i in range)
        for target in node.targets:
            if isinstance(target, ast.Name):
                self.scopes[-1].add(target.id)
            elif isinstance(target, ast.Tuple) or isinstance(target, ast.List):
                for elt in target.elts:
                    if isinstance(elt, ast.Name):
                        self.scopes[-1].add(elt.id)
        self.generic_visit(node)

    def visit_For(self, node):
        # Mapeia a variável do loop de repetição no escopo atual
        if isinstance(node.target, ast.Name):
            self.scopes[-1].add(node.target.id)
        self.generic_visit(node)

    def visit_Name(self, node):
        # Verifica se a variável que está sendo lida existe em algum escopo ativo
        if isinstance(node.ctx, ast.Load):
            is_builtin = hasattr(builtins, node.id)
            found = any(node.id in scope for scope in self.scopes)
            
            if not found and not is_builtin:
                self.errors.append(f"Variável não declarada: '{node.id}' na linha {node.lineno}")
        self.generic_visit(node)

    def visit_BinOp(self, node):
        # Pega divisão estática por zero
        if isinstance(node.op, ast.Div) and isinstance(node.right, ast.Constant) and node.right.value == 0:
            self.errors.append(f"Divisão estática por zero detectada na linha {node.lineno}")
        self.generic_visit(node)


def validate_syntax(codigo: str) -> Tuple[bool, Optional[str]]:
    """
    Validate Python code syntax and static semantic scope.
    Returns (valid: bool, error_message: str or None).
    """
    if not codigo or not codigo.strip():
        return False, "Code is empty"
    
    try:
        tree = ast.parse(codigo)
        
        analyzer = ScopeAnalyzer()
        analyzer.visit(tree)
        
        if analyzer.errors:
            error_msg = "; ".join(analyzer.errors)
            logger.warning(f"SEMANTIC CHECK FAILED: {error_msg}")
            return False, error_msg
            
        return True, None
    except SyntaxError as e:
        error_msg = f"Line {e.lineno}: {e.msg}"
        logger.warning(f"SYNTAX CHECK: {error_msg}")
        return False, error_msg
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        logger.error(f"SYNTAX CHECK: {error_msg}")
        return False, error_msg


def codigo_python_valido(codigo: str) -> bool:
    """Check if code has valid Python syntax and scope."""
    valid, _ = validate_syntax(codigo)
    return valid


def is_compilable(codigo: str) -> bool:
    """Check if code can be compiled and is valid."""
    return codigo_python_valido(codigo)


def get_syntax_report(codigo: str) -> Dict[str, Any]:
    """Get detailed syntax validation report."""
    valid, error = validate_syntax(codigo)
    
    report = {
        'valid': valid,
        'error': error,
        'line_count': len(codigo.splitlines()) if codigo else 0,
        'char_count': len(codigo) if codigo else 0
    }
    
    if valid:
        try:
            tree = ast.parse(codigo)
            
            node_count = sum(1 for _ in ast.walk(tree))
            report['ast_nodes'] = node_count
            
            functions = sum(1 for node in ast.walk(tree) if isinstance(node, ast.FunctionDef))
            classes = sum(1 for node in ast.walk(tree) if isinstance(node, ast.ClassDef))
            report['functions'] = functions
            report['classes'] = classes
        except:
            pass
    
    return report


def validar_saida(saida: str) -> bool:
    if not saida or not saida.strip():
        return False
    if len(saida.strip()) < 2:
        return False
    return True


def check_indentation(codigo: str) -> bool:
    """Check if code has proper indentation."""
    if not codigo:
        return True
    
    lines = codigo.splitlines()
    for line in lines:
        if not line.strip():
            continue
        
        indent = len(line) - len(line.lstrip())
        if indent % 4 != 0:
            logger.warning(f"INDENTATION: Non-4-space indentation detected")
            return False
            
    return True

