# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136

# test_normalizer_pipeline.py

"""
Exemplo de uso do PythonNormalizer no pipeline de geração de código.

Demonstra:
1. Geração de código por LLM (simulado)
2. Normalização sintática
3. Validação
4. Reparo (se necessário)
5. Persistência
"""

import asyncio
from iaglobal.diagnostics.python_normalizer import PythonNormalizer
from iaglobal.agents.semantic_validator import SemanticValidatorAgent, ValidationResult, Language
from iaglobal.diagnostics.repair_engine import RepairEngine


async def exemplo_pipeline_completo():
    """Exemplo completo do pipeline de normalização."""
    
    print("=" * 60)
    print("EXEMPLO: Pipeline de Normalização Sintática")
    print("=" * 60)
    
    # Simula código gerado por LLM
    llm_code = """
Aqui está o código que você pediu:

```python
import sys
import os
import asyncio

async def main( ):
    # Função principal
    print( 'Olá, mundo!' )
    print( os.getcwd( ) )
    await asyncio.sleep( 0 )

if __name__ == "__main__":
    asyncio.run( main( ) )
```

Espero que ajude! Me avise se precisar de mais alguma coisa.
"""
    
    print("\n1. Código original (LLM output):")
    print("-" * 60)
    print(llm_code[:200] + "...")
    
    # Etapa 1: Normalização
    print("\n2. Normalizando código...")
    normalizer = PythonNormalizer()
    result = normalizer.normalize(llm_code)
    
    print(f"   - Sanitized: {len(result.sanitized)} chars")
    print(f"   - Formatted: {len(result.formatted)} chars")
    print(f"   - Fixed: {len(result.fixed)} chars")
    print(f"   - Syntax valid: {result.syntax_valid}")
    print(f"   - Ruff format errors: {len(result.ruff_format_errors)}")
    print(f"   - Ruff check errors: {len(result.ruff_check_errors)}")
    
    if result.ruff_check_errors:
        print(f"   - Fixes applied: {result.ruff_check_errors[0]}")
    
    print("\n3. Código normalizado:")
    print("-" * 60)
    print(result.fixed)
    
    # Etapa 2: Validação semântica
    print("\n4. Validação semântica...")
    validator = SemanticValidatorAgent()
    validation_dict = validator.validate(result.fixed, "Criar função async que imprime Olá Mundo")
    
    # Converte dict para ValidationResult se necessário
    if isinstance(validation_dict, dict):
        validation_result = ValidationResult(
            valid=validation_dict.get("valid", False),
            score=validation_dict.get("score", 0.0),
            language=Language(validation_dict.get("details", {}).get("language", "python")),
            errors=validation_dict.get("errors", []),
            suggestions=[],
            elapsed_ms=0.0,
        )
    else:
        validation_result = validation_result
    
    print(f"   - Válido: {validation_result.valid}")
    print(f"   - Score: {validation_result.score:.2f}")
    print(f"   - Linguagem: {validation_result.language.value}")
    print(f"   - Erros: {len(validation_result.errors)}")
    print(f"   - Sugestões: {len(validation_result.suggestions)}")
    print(f"   - Tempo: {validation_result.elapsed_ms:.2f}ms")
    
    # Etapa 3: Se inválido, enviar para RepairEngine
    if not validation_result.valid:
        print("\n5. Código inválido → RepairEngine...")
        repair_engine = RepairEngine()
        
        # Simula erro
        error = SyntaxError("Exemplo de erro")
        repair_report = await repair_engine.repair(
            code=result.fixed,
            error=error,
            context={"task": "Criar função async"},
        )
        
        print(f"   - Reparo succeeded: {repair_report.success}")
        print(f"   - Estratégia: {repair_report.strategy_used}")
        print(f"   - Tentativas: {repair_report.attempt}")
        
        if repair_report.success:
            final_code = repair_report.after_code
        else:
            final_code = result.fixed
    else:
        final_code = result.fixed
    
    print("\n6. Código final:")
    print("-" * 60)
    print(final_code)
    
    print("\n" + "=" * 60)
    print("Pipeline completo!")
    print("=" * 60)


def exemplo_extracao_markdown():
    """Exemplo de extração de código de markdown."""
    
    print("\n" + "=" * 60)
    print("EXEMPLO: Extração de Markdown")
    print("=" * 60)
    
    llm_output = '''
Claro! Vou criar uma função para você.

```python
def calcular_area_circulo(raio):
    """Calcula a área de um círculo."""
    pi = 3.14159
    return pi * (raio ** 2)
```

Essa função recebe o raio como parâmetro e retorna a área.

Precisa de mais alguma coisa?
'''
    
    normalizer = PythonNormalizer()
    result = normalizer.normalize(llm_output)
    
    print("\nCódigo extraído:")
    print("-" * 60)
    print(result.fixed)
    print("-" * 60)
    
    print(f"\n✓ Markdown removido: {'```' not in result.fixed}")
    print(f"✓ Texto externo removido: {'Claro' not in result.fixed}")
    print(f"✓ Sintaxe válida: {result.syntax_valid}")


def exemplo_correcao_imports():
    """Exemplo de organização de imports."""
    
    print("\n" + "=" * 60)
    print("EXEMPLO: Organização de Imports")
    print("=" * 60)
    
    code = """
import sys
import os
import asyncio
import json

async def process_data(data):
    result = json.dumps(data)
    print(os.getcwd())
    print(sys.version)
    await asyncio.sleep(0.1)
    return result
"""
    
    normalizer = PythonNormalizer()
    result = normalizer.normalize(code)
    
    print("\nCódigo com imports organizados:")
    print("-" * 60)
    print(result.fixed)
    print("-" * 60)
    
    # Verifica ordem dos imports
    lines = result.fixed.split("\n")
    import_lines = [l for l in lines if l.startswith("import ")]
    
    print(f"\n✓ Imports em ordem: {import_lines == sorted(import_lines)}")
    print(f"✓ Imports: {', '.join(import_lines)}")


if __name__ == "__main__":
    # Executa exemplos
    exemplo_extracao_markdown()
    exemplo_correcao_imports()
    asyncio.run(exemplo_pipeline_completo())
