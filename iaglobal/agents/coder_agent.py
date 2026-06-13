# iaglobal/agents/coder_agent.py

import re
import ast
import traceback
import asyncio
from dataclasses import dataclass, field
from typing import Union, Dict

from iaglobal.models.task import Task
from iaglobal.validation.engine import ValidationEngine
from iaglobal.observability.tracing import Tracer
from iaglobal.graphs.bandit import BanditPolicy
from iaglobal.graphs.credit import CreditAssignmentEngine
from iaglobal.execution.executor import executar
from iaglobal._paths import _detect_extension

from iaglobal.utils.logger import get_logger

@dataclass
class CodeArtifact:
    code: str = ""
    files: Dict[str, str] = field(default_factory=dict)

from iaglobal.graphs.policy import PolicyRegistry

class CoderAgent:
    def __init__(self, temperatura: float = 0.5, estilo: str = "direto, minimalista"):
        self.temperatura = temperatura
        self.estilo = estilo
        # Delegacia: mantém uma Bandit por domínio
        self.policy_registry = PolicyRegistry()
        # Polícia: pega a Bandit oficial do domínio "coder"
        self.bandit = self.policy_registry.get("coder")

    def gerar_codigo(
        self,
        task: Union[str, 'Task'],
        contexto: str = "",
        erros_contexto: str = "",
        security_feedback: str = ""
    ) -> CodeArtifact:
        task_str = task.text if hasattr(task, 'text') else str(task)

        # Seleciona modelo via BanditPolicy (delegacia -> polícia)
        chosen_model = self.bandit.select_model(
            node="coder_agent",
            strategy="code_generation"
        )

        logger.info(f"💻 [CODER AGENT]: Gerando código via {chosen_model} (estilo: {self.estilo})...")

        try:
            # Executa o modelo escolhido
            result = asyncio.run(
                self.bandit.async_execute_model(
                    model=chosen_model,
                    prompt=task_str,
                    task_type="code"
                )
            )

            # Atualiza política com feedback simplificado
            self.bandit.update_policy(
                node="coder_agent",
                model=chosen_model,
                strategy="code_generation",
                success=True,
                latency=0.5,   # valor simbólico, pode ser medido real
                reward=1.0
            )

            # Encapsula saída em CodeArtifact
            artifact = CodeArtifact(
                code=result,
                files={"output.py": result}  # extensão pode ser adaptada via _detect_extension
            )

            # Se houver alerta de segurança, adiciona seção
            if security_feedback:
                logger.warning(f"🚨 ALERTA DE SEGURANÇA DETECTADO: {security_feedback}")

            return artifact

        except Exception as e:
            logger.error(f"❌ [CODER AGENT]: Falha ao gerar código com {chosen_model}: {e}")
            self.bandit.update_policy(
                node="coder_agent",
                model=chosen_model,
                strategy="code_generation",
                success=False,
                latency=0.0,
                reward=0.0
            )
            return CodeArtifact(code="", files={})

        # Prompt atualizado com diretrizes avançadas de arquitetura e qualidade
        
        prompt = f"""
        Você é um Engenheiro de Software Sênior e Arquiteto de Sistemas.
        Estilo: {self.estilo}.
        Contexto: {contexto or "Nenhum."}
        Erros a reparar: {erros_contexto or "Nenhum."}
        Tarefa: {task_str}{security_section}

        DIRETRIZES DE LOGGING (OBRIGATÓRIO):
        - NÃO utilize `print()`.
        - Sempre use o módulo nativo `logging`.
        - Configure o logger no escopo global: `logger = logging.getLogger(__name__)`.
        - Use `logger.info()` para fluxos normais e `logger.error()` ou `logger.exception()` para falhas.

        DIRETRIZES DE ARQUITETURA:
        - Estruture o código de forma clara, modular e reutilizável.
        - Prefira funções puras e bem definidas, evitando efeitos colaterais desnecessários.
        - Documente funções críticas com docstrings concisas e objetivas.
        - Evite redundância e código boilerplate; mantenha simplicidade e legibilidade.
        - Garanta compatibilidade com execução em sandbox e respeite restrições de segurança.

        DIRETRIZES DE SEGURANÇA:
        - NÃO utilize imports inseguros ou bibliotecas não autorizadas.
        - Evite chamadas diretas ao sistema operacional que possam comprometer o ambiente.
        - Todo acesso a modelos deve passar pela BanditPolicy para garantir conformidade e otimização.
        - Corrija imediatamente qualquer violação de sandbox ou policy.

        DIRETRIZES DE QUALIDADE:
        - O código deve ser eficiente e escalável, evitando complexidade desnecessária.
        - Sempre valide entradas e trate exceções de forma robusta.
        - Inclua comentários apenas quando agregarem clareza arquitetural.
        - Garanta que o código seja sintaticamente válido e pronto para execução.

        REGRAS DE RETORNO:
        - Retorne ESTRITAMENTE o código dentro de um bloco markdown da linguagem correspondente (ex: ```python ... ```).
        - NÃO inclua explicações textuais fora do bloco.
        """
                
        codigo = ""
        # Estratégia de Fallback (Bandit / Multi-Modelo)
        for modelo_alvo in [MODELO_ONLINE, MODELO_LOCAL]:
            try:
                logger.info(f"⚙️ Tentando execução com: {modelo_alvo}")
                resposta = chamar_modelo(modelo_alvo, prompt)
                codigo = self._extrair_codigo_puro(resposta)
                
                if codigo and self._sintaxe_valida(codigo):
                    return codigo
                else:
                    logger.warning(f"⚠️ [CODER AGENT]: Código inválido ou vazio retornado por {modelo_alvo}.")
            
            except Exception:
                logger.warning(f"⚠️ [CODER AGENT]: Falha no {modelo_alvo} — tentando próximo modelo.")
                continue

        logger.critical("🚨 [CODER AGENT]: Todos os modelos falharam na geração.")
        return ""

    def _extrair_codigo_puro(self, resposta: str, task: str = "") -> CodeArtifact:
        import re
        # Captura blocos ```python, ```html, ```css, ```javascript ou apenas ```
        match = re.search(
            r"```(?:python|html|css|javascript|php)?\s*(.*?)\s*```",
            resposta,
            re.DOTALL | re.IGNORECASE
        )
        codigo = match.group(1).strip() if match else resposta.strip()

        # Detecta extensão automaticamente com base no conteúdo e na task
        ext = _detect_extension(codigo, task)
        filename = f"output{ext}"

        # Retorna já no formato esperado pelo pipeline
        return CodeArtifact(
            code=codigo,
            files={filename: codigo}
        )

    def _extrair_codigo_por_ast(self, texto: str, task: str = "") -> CodeArtifact:
        """
        Extrai automaticamente o maior bloco Python válido e retorna como CodeArtifact.
        """

        linhas = texto.splitlines()
        inicio_codigo = None

        marcadores = (
            "def ",
            "class ",
            "import ",
            "from ",
            "@",
            "async def ",
            "if __name__",
        )

        for i, linha in enumerate(linhas):
            if linha.lstrip().startswith(marcadores):
                inicio_codigo = i
                break

        if inicio_codigo is None:
            return CodeArtifact(code="", files={})

        codigo = "\n".join(linhas[inicio_codigo:])

        while codigo:
            try:
                ast.parse(codigo)
                codigo = codigo.strip()
                # Detecta extensão automaticamente
                ext = _detect_extension(codigo, task)
                filename = f"output{ext}"
                return CodeArtifact(code=codigo, files={filename: codigo})
            except SyntaxError as erro:
                linhas_codigo = codigo.splitlines()
                if erro.lineno is not None:
                    indice = erro.lineno - 1
                    if indice < len(linhas_codigo):
                        linhas_codigo.pop(indice)
                    else:
                        linhas_codigo.pop()
                else:
                    linhas_codigo.pop()
                codigo = "\n".join(linhas_codigo)

        return CodeArtifact(code="", files={})

    def _encontrar_maior_bloco_python(self, texto: str, task: str = "") -> CodeArtifact:
        """
        Procura o maior trecho sintaticamente válido de Python
        dentro de um texto arbitrário e retorna como CodeArtifact.
        """

        linhas = texto.splitlines()
        melhor_codigo = ""
        maior_tamanho = 0

        for inicio in range(len(linhas)):
            buffer = []
            for fim in range(inicio, len(linhas)):
                buffer.append(linhas[fim])
                candidato = "\n".join(buffer).strip()

                if not candidato:
                    continue

                try:
                    ast.parse(candidato)
                    tamanho = len(candidato)
                    if tamanho > maior_tamanho:
                        maior_tamanho = tamanho
                        melhor_codigo = candidato
                except SyntaxError:
                    pass

        if not melhor_codigo:
            return CodeArtifact(code="", files={})

        # Detecta extensão automaticamente
        ext = _detect_extension(melhor_codigo, task)
        filename = f"output{ext}"

        return CodeArtifact(
            code=melhor_codigo,
            files={filename: melhor_codigo}
        )

    def _sintaxe_valida(self, artifact: CodeArtifact) -> bool:
        """
        Verifica a validade do código através de análise estática (AST)
        e validação lógica pelo motor de testes.
        """
        codigo = artifact.code

        if not codigo or not codigo.strip():
            logger.warning("🔍 [VALIDAÇÃO]: Código vazio ou apenas espaços.")
            return False

        try:
            # 1. Verificação de Sintaxe via AST (nativa do Python)
            ast.parse(codigo)
        except SyntaxError as e:
            logger.error(f"❌ [VALIDAÇÃO]: Erro de sintaxe detectado: {e.msg} na linha {e.lineno}")
            return False
        except Exception as e:
            logger.error(f"❌ [VALIDAÇÃO]: Erro inesperado na análise AST: {e}")
            return False

        # 2. Validação Semântica/Lógica via ValidationEngine
        try:
            result = ValidationEngine().validate(codigo)
            if not result.valid:
                logger.warning(
                    f"⚠️ [VALIDAÇÃO]: Código falhou na validação de regras: {getattr(result, 'message', 'Sem detalhes')}"
                )
            return result.valid
        except Exception as e:
            logger.error(f"❌ [VALIDAÇÃO]: Falha crítica no ValidationEngine: {e}")
            return False

    def run(self, task) -> CodeArtifact:
        Tracer.trace_event("AgentStarted", {"agent": "CoderAgent"})

        try:
            # Gera o código usando o método principal
            artifact = self.gerar_codigo(task)

            # Valida sintaxe e regras
            if not self._sintaxe_valida(artifact):
                logger.warning("⚠️ [CODER AGENT]: Código inválido ou falhou na validação.")
                # Se falhar, tenta extrair o maior bloco válido
                artifact = self._extrair_codigo_por_ast(artifact.code, str(task))

            Tracer.trace_event("AgentFinished", {"agent": "CoderAgent"})
            return artifact

        except Exception as e:
            logger.exception(f"❌ [CODER AGENT]: Falha crítica durante execução: {e}")
            Tracer.trace_event("AgentFailed", {"agent": "CoderAgent", "error": str(e)})
            # Retorna artefato vazio para não quebrar pipeline
            return CodeArtifact(code="", files={})

