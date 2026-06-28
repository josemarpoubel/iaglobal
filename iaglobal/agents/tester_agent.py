# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/agents/tester_agent.py

import asyncio
from dataclasses import dataclass
from typing import Union, Dict, Any, List, Optional
from iaglobal.models.task import Task
from iaglobal.utils.logger import logger
from iaglobal.providers.provider_router import route_generate
from iaglobal.providers.task_router import detect_task_type

# Timeout padrão para geração de testes (suítes de teste podem ser longas)
_DEFAULT_TIMEOUT = 180.0

@dataclass
class TestGenerationResult:
    """Contrato de dados rígido para o retorno do agente."""
    success: bool
    test_code: str = ""
    error_message: Optional[str] = None
    language_detected: str = "unknown"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "test_code": self.test_code,
            "error_message": self.error_message,
            "language_detected": self.language_detected,
        }


class TesterAgent:
    __test__ = False
    """
    Agente responsável por gerar testes unitários robustos.
    Desacoplado, poliglota e com contratos de dados rígidos.
    """

    def __init__(self, workdir: Optional[str] = None):
        self.history: List[Dict[str, Any]] = []
        self.workdir = workdir

    async def gerar_testes(
        self, 
        codigo: str, 
        task: Union[str, Task], 
        timeout: float = _DEFAULT_TIMEOUT
    ) -> TestGenerationResult:
        logger.info("🧪 [TESTER AGENT]: Gerando testes...")

        # 1. Validação de entrada (Fail-fast para economizar tokens)
        if not codigo or not str(codigo).strip():
            return TestGenerationResult(success=False, error_message="Código vazio ou nulo fornecido.")

        task_text = str(task)
        lang_hint = self._detect_language(codigo)
        
        # 2. Prompt Engenharia Avançado (Poliglota e Focado em Qualidade)
        prompt = f"""Você é um Engenheiro de QA Sênior. Gere testes unitários robustos para o código abaixo.

==================== TAREFA ====================
{task_text}

==================== CÓDIGO ====================
{codigo}

==================== REGRAS ====================
- Linguagem/Framework alvo: {lang_hint}
- Cubra happy path, edge cases (casos de borda) e tratamento de erros.
- Use mocks/stubs para isolar dependências externas (banco de dados, APIs, arquivos).
- Garanta que os testes sejam independentes.
- Retorne APENAS o código dos testes. NÃO inclua explicações, texto ou blocos markdown (```).
"""

        try:
            task_type = detect_task_type(task_text)
            
            # 3. Timeout e System Prompt adequado
            resposta = await asyncio.wait_for(
                route_generate(
                    "Você é um especialista em testes automatizados e qualidade de software.", 
                    prompt, 
                    task_type=task_type
                ),
                timeout=timeout
            )

            if not resposta:
                err_msg = "LLM retornou resposta vazia."
                logger.warning("⚠️ [TESTER AGENT]: %s", err_msg)
                return TestGenerationResult(success=False, error_message=err_msg, language_detected=lang_hint)

            test_code = str(resposta).strip()
            
            # 4. Limpeza de Markdown (Defesa em profundidade)
            if test_code.startswith("```"):
                test_code = test_code.split("\n", 1)[-1]
            if test_code.endswith("```"):
                test_code = test_code.rsplit("```", 1)[0]
            test_code = test_code.strip()

            result = TestGenerationResult(
                success=True,
                test_code=test_code,
                language_detected=lang_hint
            )
            
            # 5. Histórico (Útil para auditoria ou retentativas)
            self.history.append(result.to_dict())
            
            logger.info("✅ [TESTER AGENT]: Testes gerados com sucesso (%d chars).", len(test_code))
            return result

        except asyncio.TimeoutError:
            err_msg = f"Timeout ao gerar testes após {timeout}s."
            logger.warning("⚠️ [TESTER AGENT]: %s", err_msg)
            return TestGenerationResult(success=False, error_message=err_msg, language_detected=lang_hint)
        except Exception as e:
            err_msg = f"Erro inesperado ao gerar testes: {str(e)}"
            logger.warning("⚠️ [TESTER AGENT]: %s", err_msg, exc_info=True)
            return TestGenerationResult(success=False, error_message=err_msg, language_detected=lang_hint)

    @staticmethod
    def _detect_language(code: str) -> str:
        """Heurística simples para identificar a linguagem e guiar o LLM."""
        code_lower = code.lower()
        if "def " in code or "import " in code or "pytest" in code_lower:
            return "Python (pytest)"
        if "function " in code or "const " in code or "require(" in code:
            return "JavaScript/TypeScript (Jest/Vitest)"
        if "public class " in code or "@Test" in code:
            return "Java (JUnit)"
        if "func " in code and "package " in code:
            return "Go (testing)"
        return "Desconhecida (use o framework padrão da linguagem)"
