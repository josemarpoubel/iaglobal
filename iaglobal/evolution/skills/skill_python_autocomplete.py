# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
Skill Python Autocomplete — Análise estática com Jedi LSP.

Usa o motor Jedi para:
  - Analisar código Python estaticamente
  - Sugerir correções baseadas em tipos e símbolos disponíveis
  - Completar código parcialmente escrito
  - Detectar imports faltantes
  - Analisar assinaturas de funções

Integração:
  - SkillDebugUnificado usa esta skill para sugestões
  - no_lsp_validator pode usar para diagnósticos mais ricos
"""
import asyncio
from typing import List, Dict, Any, Optional
from pathlib import Path

from iaglobal.evolution.skills.skill import Skill
from iaglobal.models.task import Task
from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.skills.python_autocomplete")


class SkillPythonAutocomplete(Skill):
    """
    Skill de autocomplete e análise Python com Jedi.
    
    Jedi é um motor de análise estática que entende:
      - Tipos de variáveis
      - Imports disponíveis
      - Assinaturas de funções
      - Classes e métodos
      - Símbolos do escopo atual
    """

    def __init__(self):
        super().__init__(
            name="python_autocomplete",
            description="Autocomplete e análise estática Python com Jedi LSP",
            inputs=["code", "line", "column", "context_symbols"],
            outputs=["suggestions", "analysis", "corrected_code"],
            constraints=["python_syntax"],
            tags=["autocomplete", "lsp", "jedi", "analysis", "python"],
            version="1.0.0",
        )

    async def execute(self, task: Task) -> Dict[str, Any]:
        """
        Executa análise e autocomplete Python.
        
        Args:
            task: Task com:
                - code: Código Python para analisar
                - context["line"]: Linha do cursor (opcional)
                - context["column"]: Coluna do cursor (opcional)
                - context["context_symbols"]: Símbolos disponíveis (opcional)
        
        Returns:
            Dict com:
                - suggestions: Lista de sugestões de autocomplete
                - analysis: Análise estática do código
                - corrected_code: Código corrigido (se aplicável)
        """
        code = getattr(task, "code", None) or task.context.get("code", "")
        line = task.context.get("line", None)
        column = task.context.get("column", None)
        context_symbols = task.context.get("context_symbols", [])
        
        if not code:
            logger.warning("[AUTOCOMPLETE] Nenhum código para analisar")
            return {"suggestions": [], "analysis": {}, "corrected_code": ""}
        
        logger.info(
            "[AUTOCOMPLETE] Analisando | code=%d chars | line=%s | col=%s",
            len(code), line, column,
        )
        
        try:
            import jedi
        except ImportError:
            logger.error("[AUTOCOMPLETE] jedi não instalado — pip install jedi")
            return {"suggestions": [], "analysis": {"error": "jedi not installed"}, "corrected_code": code}
        
        # Cria script Jedi para análise
        script = jedi.Script(code=code, path="example.py")
        
        # Análise estática completa
        analysis = await self._analyze_code(script, code)
        
        # Autocomplete se linha/coluna fornecidas
        suggestions = []
        if line is not None and column is not None:
            suggestions = await self._get_completions(script, line, column)
        
        # Detecção de problemas e correções
        corrected_code = await self._suggest_corrections(script, code, analysis)
        
        result = {
            "suggestions": suggestions,
            "analysis": analysis,
            "corrected_code": corrected_code,
        }
        
        logger.info(
            "[AUTOCOMPLETE] Análise concluída | suggestions=%d | issues=%d",
            len(suggestions), len(analysis.get("issues", [])),
        )
        
        return result

    async def _analyze_code(self, script: Any, code: str) -> Dict[str, Any]:
        """
        Análise estática completa do código.
        
        Retorna:
            - issues: Problemas detectados
            - symbols: Símbolos definidos
            - imports: Imports analisados
            - types: Tipos inferidos
        """
        issues = []
        symbols = []
        imports = []
        types = {}
        
        # 1. Detecta problemas com pyflakes (mais rápido para erros básicos)
        try:
            import pyflakes.api
            import pyflakes.messages
            
            class IssueCollector:
                def __init__(self):
                    self.issues = []
                
                def unexpectedError(self, filename, msg):
                    self.issues.append({"type": "error", "message": msg, "line": 1})
                
                def syntaxError(self, filename, msg, lineno, offset, text):
                    self.issues.append({
                        "type": "syntax",
                        "message": msg,
                        "line": lineno,
                        "column": offset,
                        "text": text,
                    })
                
                def flake(self, msg):
                    self.issues.append({
                        "type": "warning",
                        "message": str(msg),
                        "line": getattr(msg, "lineno", 1),
                        "column": getattr(msg, "col", 0),
                    })
            
            collector = IssueCollector()
            pyflakes.api.check(code, "example.py", collector)
            issues.extend(collector.issues)
        except Exception as e:
            logger.debug("[AUTOCOMPLETE] Pyflakes falhou: %s", e)
        
        # 2. Analisa símbolos com Jedi
        try:
            # Símbolos no escopo atual
            completions = script.complete()
            for c in completions[:50]:  # Limita a 50 símbolos
                symbols.append({
                    "name": c.name,
                    "type": c.type,
                    "description": c.description,
                })
            
            # Imports usados
            imports_used = script.get_references()
            for ref in imports_used[:20]:
                if ref.module_name:
                    imports.append({
                        "module": ref.module_name,
                        "name": ref.name,
                        "line": ref.line,
                    })
        except Exception as e:
            logger.debug("[AUTOCOMPLETE] Jedi análise falhou: %s", e)
        
        # 3. Inferência de tipos
        try:
            # Tenta inferir tipos de variáveis principais
            for scope in script.get_context():
                types[scope.name] = {
                    "type": scope.type,
                    "description": scope.description,
                }
        except Exception:
            pass
        
        return {
            "issues": issues,
            "symbols": symbols[:30],  # Limita output
            "imports": imports[:20],
            "types": types,
            "has_syntax_error": any(i["type"] == "syntax" for i in issues),
            "has_import_error": any("import" in i.get("message", "").lower() for i in issues),
        }

    async def _get_completions(
        self,
        script: Any,
        line: int,
        column: int,
    ) -> List[Dict[str, Any]]:
        """
        Obtém sugestões de autocomplete para uma posição.
        
        Args:
            script: Script Jedi
            line: Linha (1-indexed)
            column: Coluna (0-indexed)
        
        Returns:
            Lista de sugestões com nome, tipo, descrição
        """
        suggestions = []
        
        try:
            completions = script.complete(line, column)
            
            for c in completions[:10]:  # Top 10 sugestões
                suggestion = {
                    "name": c.name,
                    "type": c.type,
                    "description": c.description,
                    "signature": None,
                    "docstring": None,
                }
                
                # Tenta pegar assinatura para funções
                if c.type == "function":
                    try:
                        sig = c.get_signatures()
                        if sig:
                            suggestion["signature"] = sig[0].to_string()
                    except Exception:
                        pass
                
                # Tenta pegar docstring
                try:
                    doc = c.docstring()
                    if doc:
                        suggestion["docstring"] = doc[:200]  # Limita
                except Exception:
                    pass
                
                suggestions.append(suggestion)
        except Exception as e:
            logger.warning("[AUTOCOMPLETE] Completions falhou: %s", e)
        
        return suggestions

    async def _suggest_corrections(
        self,
        script: Any,
        code: str,
        analysis: Dict[str, Any],
    ) -> str:
        """
        Sugere correções baseadas na análise.
        
        Para erros de sintaxe ou imports, tenta sugerir código corrigido.
        
        Returns:
            Código corrigido ou código original se não há correções
        """
        issues = analysis.get("issues", [])
        
        if not issues:
            return code  # Sem erros, sem correções
        
        # Para erros de import, sugere remover ou corrigir
        import_errors = [i for i in issues if "import" in i.get("message", "").lower()]
        if import_errors:
            # Tenta identificar imports problemáticos
            lines = code.split("\n")
            corrected_lines = []
            for i, line in enumerate(lines, 1):
                # Verifica se esta linha tem erro de import
                has_error = any(
                    err.get("line") == i and "import" in err.get("message", "").lower()
                    for err in import_errors
                )
                if not has_error:
                    corrected_lines.append(line)
                else:
                    # Comenta import problemático
                    corrected_lines.append(f"# {line}  # Import problemático")
            
            return "\n".join(corrected_lines)
        
        # Para erros de sintaxe, não tenta corrigir automaticamente
        # (muito arriscado sem contexto semântico)
        syntax_errors = [i for i in issues if i["type"] == "syntax"]
        if syntax_errors:
            logger.info("[AUTOCOMPLETE] Erro de sintaxe detectado — requer LLM para correção")
        
        return code  # Retorna original se não conseguiu corrigir

    def get_type_hint(self, code: str, var_name: str) -> Optional[str]:
        """
        Obtém dica de tipo para uma variável/função.
        
        Útil para o DebuggerAgent entender tipos antes de corrigir.
        """
        try:
            import jedi
            script = jedi.Script(code=code, path='test.py')
            
            # Busca o símbolo pelo nome
            names = script.get_names(all_scopes=True, definitions=True)
            for name in names:
                if name.name == var_name:
                    # Tenta inferir o tipo
                    try:
                        for inferred in name.infer():
                            return f"{inferred.type}: {inferred.description}"
                    except Exception:
                        # Fallback para descrição direta
                        return f"{name.type}: {name.description}"
            
            # Se não encontrou nas definições, busca referências
            for ref in script.search(var_name):
                return f"{ref.type}: {ref.description}"
                
        except Exception:
            pass
        
        return None


# Instância global para registro
skill_python_autocomplete = SkillPythonAutocomplete()