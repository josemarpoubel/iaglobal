# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# iaglobal/agents/planner_agent.py

import json
import asyncio
from typing import Dict, Any, Optional, Union, List

from iaglobal.models.task import Task
from iaglobal.agents.agent_base import AgentBase
from iaglobal.execution.executor import executar
from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.agents.planner_agent")


class PlannerAgent(AgentBase):
    """
    PlannerAgent Evoluído

    Agora o planner:
    - planeja arquitetura
    - identifica riscos reais de execução
    - gera estratégia de validação
    - prepara pipeline autocorretivo
    - orienta agentes usando feedback runtime
    - prepara o código para testes reais Python

    Filosofia:
    O Python é a fonte da verdade.
    A LLM apenas propõe soluções.
    """

    MAX_ETAPAS = 6

    def __init__(self):
        # Inicializa AgentBase com nome único
        super().__init__(agent_name="planner")

        self.execution_history: List[Dict[str, Any]] = []

    # =========================================================
    # INTERNAL UTILITIES (FIX CRÍTICO DO PIPELINE)
    # =========================================================

    def _extrair_task(self, task: Union[str, Task, Dict[str, Any]]) -> str:
        """
        Normaliza a entrada de dados da tarefa de forma polimórfica para string pura.
        Blinda o pipeline contra falhas de tipo (NoneType) e incompatibilidades de objetos.
        """
        # 1. Trava de segurança contra chamadas nulas acidentais
        if task is None:
            logger.error(
                "⚠️ [PLANNER]: Recebido objeto de tarefa nulo (None) para extração."
            )
            return ""

        # 2. Se já for uma string legítima, limpa e retorna diretamente
        if isinstance(task, str):
            return task.strip()

        # 3. Varredura defensiva baseada em atributos dinâmicos do objeto Task
        if hasattr(task, "text") and task.text is not None:
            return str(task.text).strip()

        if hasattr(task, "description") and task.description is not None:
            return str(task.description).strip()

        if hasattr(task, "task") and task.task is not None:
            # Captura caso o atributo interno da classe chame-se literalmente 'task'
            return str(task.task).strip()

        # 4. Varredura defensiva caso o orquestrador tenha empacotado em um dicionário de payload
        if isinstance(task, dict):
            for chave in ["task", "description", "texto", "text", "descricao"]:
                if chave in task and task[chave] is not None:
                    return str(task[chave]).strip()
            # Se for um dicionário mas não achar as chaves tradicionais, converte o objeto inteiro
            return str(task).strip()

        # 5. Último recurso de sobrevivência (Fallback polimórfico)
        texto_extraido = str(task).strip()

        # Se a conversão literal retornar a representação em memória do objeto, limpa para não poluir o prompt
        if texto_extraido.startswith("<") and texto_extraido.endswith(">"):
            logger.warning(
                f"⚠️ [PLANNER]: Extração falhou na varredura de atributos. Usando fallback de string genérica."
            )
            return "Desenvolver código funcional conforme especificações do sistema."

        return texto_extraido

    def _limpar_json(self, resposta: str) -> str:
        """
        Remove resíduos textuais, tags markdown e blinda o framework extraindo
        estritamente o bloco JSON puro, prevenindo exceções de JSONDecodeError.
        """
        if not resposta:
            return ""

        import re

        texto = str(resposta).strip()

        # 1. Remove blocos markdown clássicos (```json ... ```)
        try:
            match_markdown = re.search(
                r"```(?:json)?\s*(.*?)\s*```", texto, re.DOTALL | re.IGNORECASE
            )
            if match_markdown:
                texto = match_markdown.group(1).strip()
        except Exception as re_err:
            logger.warning(
                f"⚠️ [PLANNER]: Falha não-bloqueante na varredura regex do markdown: {re_err}"
            )

        # 2. Remove prefixos conversacionais comuns (Aqui está o plano:, etc.)
        prefixes_to_remove = [
            r"^Aqui está o plano\s*[:\-]\s*",
            r"^Aqui está o JSON\s*[:\-]\s*",
            r"^O plano é\s*[:\-]\s*",
            r"^Resultado\s*[:\-]\s*",
            r"^Resposta\s*[:\-]\s*",
            r"^```\s*",
            r"```\s*$",
        ]
        for prefix in prefixes_to_remove:
            texto = re.sub(prefix, "", texto, flags=re.IGNORECASE)

        # 3. FILTRO ANATÔMICO - Localiza o JSON válido mais externo
        # Procura o primeiro { e o último } que formam um JSON balanceado
        def extract_balanced_json(text: str) -> str:
            """Extrai o primeiro objeto JSON balanceado completo."""
            start = text.find("{")
            if start == -1:
                return text

            # Encontra o } correspondente balanceando chaves
            depth = 0
            in_string = False
            escape = False
            end = -1

            for i, char in enumerate(text[start:], start):
                if escape:
                    escape = False
                    continue
                if char == "\\" and in_string:
                    escape = True
                    continue
                if char == '"' and not escape:
                    in_string = not in_string
                    continue
                if not in_string:
                    if char == "{":
                        depth += 1
                    elif char == "}":
                        depth -= 1
                        if depth == 0:
                            end = i
                            break

            if end != -1:
                return text[start : end + 1]
            return text[start:]

        texto_filtrado = extract_balanced_json(texto)

        # 4. Sanitização final
        texto_sanitizado = texto_filtrado.strip()
        texto_sanitizado = re.sub(r"\n\s*\n", "\n", texto_sanitizado)
        texto_sanitizado = re.sub(
            r",\s*}", "}", texto_sanitizado
        )  # Remove trailing commas
        texto_sanitizado = re.sub(
            r",\s*]", "]", texto_sanitizado
        )  # Remove trailing commas in arrays

        return texto_sanitizado

    def _sanitizar_json(self, texto: str) -> str:
        """
        Sanitiza JSON para parse usando maquina de estados.

        Problema que resolve:
          JSON invalido: {"desc": "abc
          def"}  <- newline dentro de string

          JSON valido: {
            "desc": "abc"  <- newline entre tokens (OK)
          }

        Estrategia:
          1. Rastreia se esta DENTRO ou FORA de string
          2. Dentro de string: escapa newlines/tabs/carriage returns
          3. Fora de string: preserva formatacao (newlines sao validos)
          4. Escapa caracteres de controle U+0000-U+001F (exceto os ja tratados)

        Args:
            texto: String contendo JSON potencialmente mal-formado

        Returns:
            Texto sanitizado pronto para json.loads()
        """
        resultado = []
        dentro_string = False
        escape_prox = False
        chars_alterados = 0

        i = 0
        while i < len(texto):
            char = texto[i]
            char_code = ord(char)

            # Detecta se e caractere de escape
            if char == "\\" and not escape_prox:
                escape_prox = True
                resultado.append(char)
                i += 1
                continue

            # Se estava em escape, reseta flag
            if escape_prox:
                escape_prox = False
                resultado.append(char)
                i += 1
                continue

            # Detecta entrada/saida de string
            if char == '"':
                dentro_string = not dentro_string
                resultado.append(char)
                i += 1
                continue

            # Se esta DENTRO de string, precisa escapar caracteres problematicos
            if dentro_string:
                if char_code == 0x0A:  # \n dentro de string
                    resultado.append("\\n")
                    chars_alterados += 1
                elif char_code == 0x0D:  # \r dentro de string
                    resultado.append("\\r")
                    chars_alterados += 1
                elif char_code == 0x09:  # \t dentro de string
                    resultado.append("\\t")
                    chars_alterados += 1
                elif char_code < 0x20:  # Outros caracteres de controle
                    resultado.append(f"\\u{char_code:04x}")
                    chars_alterados += 1
                else:
                    resultado.append(char)
            else:
                # FORA de string: preserva tudo (incluindo newlines de formatacao)
                resultado.append(char)

            i += 1

        logger.info(
            "[SANITIZE] JSON sanitizado: %d caracteres escapados",
            chars_alterados,
        )

        return "".join(resultado)

    def _enriquecer_plano(self, plano: Dict[str, Any]) -> Dict[str, Any]:
        """
        Injeta e força metadados estruturais para garantir que a autocorreção em runtime
        e a validação sintática (AST) funcionem, mesmo se a LLM omitir ou corromper esses campos.
        """
        if not isinstance(plano, dict):
            logger.error("🚫 [PLANNER] Objeto inválido passado para enriquecimento.")
            return self._fallback_plan("Falha estrutural ao enriquecer plano.")

        # 1. GARANTE A ARVORE DE ESTRATÉGIA DE VALIDAÇÃO (Força True nas flags críticas)
        if "estrategia_validacao" not in plano or not isinstance(
            plano["estrategia_validacao"], dict
        ):
            plano["estrategia_validacao"] = {}

        estrategia = plano["estrategia_validacao"]
        estrategia["usar_ast"] = bool(estrategia.get("usar_ast", True))
        estrategia["usar_execucao_real"] = bool(
            estrategia.get("usar_execucao_real", True)
        )
        estrategia["usar_testes_unitarios"] = bool(
            estrategia.get("usar_testes_unitarios", True)
        )
        estrategia["usar_autocorrecao"] = bool(
            estrategia.get("usar_autocorrecao", True)
        )

        # 2. SELETOR DE MODOS CONFIGURADO NA ORIGEM
        plano["modo_execucao"] = (
            str(plano.get("modo_execucao", "autocorretivo")).strip().lower()
        )
        if plano["modo_execucao"] not in ["autocorretivo", "direto"]:
            plano["modo_execucao"] = "autocorretivo"

        # 3. HIGIENIZAÇÃO E ESPELHAMENTO DE CHAVES EM SUBTAREFAS (Tratamento Anti-Alucinação)
        subtarefas = plano.get("subtarefas", [])
        if isinstance(subtarefas, list):
            subtarefas_limpas = []
            for i, st in enumerate(subtarefas):
                if not isinstance(st, dict):
                    continue

                # Garante e força ID sequencial válido caso a nuvem gere texto ou pule o índice
                st_id = st.get("id")
                try:
                    st["id"] = int(st_id) if st_id is not None else i + 1
                except (ValueError, TypeError):
                    st["id"] = i + 1

                # Polymorphic field mirroring (Translation and Fallback keys)
                st["titulo"] = str(
                    st.get("titulo", st.get("title", "Technical Implementation Stage"))
                ).strip()
                st["description"] = str(
                    st.get(
                        "description",
                        st.get(
                            "descricao", "Develop functional logic according to plan."
                        ),
                    )
                ).strip()
                st["descricao"] = st["description"]  # Ensures parity for local agents

                st["validacao_runtime"] = str(
                    st.get("validacao_runtime", "Execute basic runtime assertions.")
                ).strip()

                # Normalization of expected errors list
                erros = st.get("possiveis_erros", st.get("possible_errors", []))
                if not isinstance(erros, list):
                    erros = [str(erros)] if erros else ["Exception"]
                st["possiveis_erros"] = [str(e).strip() for e in erros if e]
                if not st["possiveis_erros"]:
                    st["possiveis_erros"] = ["TypeError", "ValueError", "RuntimeError"]

                st["alertas_seguranca"] = str(
                    st.get("alertas_seguranca", "Sandbox mode enabled.")
                ).strip()
                subtarefas_limpas.append(st)

            plano["subtarefas"] = subtarefas_limpas
        else:
            # If the subtasks field came corrupted from the cloud, inject a basic default structure
            plano["subtarefas"] = [
                {
                    "id": 1,
                    "titulo": "Modular Generation",
                    "descricao": "Develop the main logic of the component.",
                    "validacao_runtime": "Compile in interpreter and capture tracebacks.",
                    "possiveis_erros": ["TypeError", "ValueError", "RuntimeError"],
                    "alertas_seguranca": "Sandbox mode active.",
                }
            ]

        return plano

    def _fallback_plan(self, task_text: str) -> Dict[str, Any]:
        """
        Resilient contingency plan with string sanitization to avoid
        truncation in logs or subsequent agents.
        """
        logger.warning("⚠️ [PLANNER AGENT]: Activating resilient contingency mode.")

        # 1. Sanitization and Integrity Protection
        # Ensures we don't have empty strings or partial cuts due to line breaks
        enunciado_base = str(task_text).strip().replace("\n", " ")
        enunciado_limpo = (
            enunciado_base
            if len(enunciado_base) > 5
            else "Develop the function requested by the user."
        )

        # Safe debug: log only the beginning to avoid console spam
        logger.debug(
            f"DEBUG: Sanitized statement ({len(enunciado_limpo)} chars): {enunciado_limpo[:50]}..."
        )

        # 2. Structure definition with mirrored keys
        # Shielding against KeyError in different LLM environments
        return {
            "complexidade": "UNKNOWN",
            "arquitetura_proposta": "Defensive design based on direct execution and Sandbox traceback.",
            "estrategia_validacao": {
                "usar_ast": True,
                "usar_execucao_real": True,
                "usar_testes_unitarios": True,
                "usar_autocorrecao": True,
            },
            "subtarefas": [
                {
                    "id": 1,
                    # Block in English (primary)
                    "titulo": "Direct Execution",
                    "descricao": f"Code a robust Python solution to achieve the following goal: {enunciado_limpo}",
                    "validacao_runtime": "Compile in sandbox and capture real exceptions.",
                    "possiveis_erros": [
                        "TypeError",
                        "ValueError",
                        "NameError",
                        "SyntaxError",
                        "RuntimeError",
                        "Exception",
                    ],
                    "alertas_seguranca": "Contingency mode: Sandbox enabled.",
                    # Mirrored keys in English (Agent Shielding)
                    "title": "Direct Code Implementation and Generation",
                    "description": f"Write a robust Python script to solve the following objective: {enunciado_limpo}",
                    "possible_errors": [
                        "TypeError",
                        "ValueError",
                        "NameError",
                        "SyntaxError",
                        "RuntimeError",
                    ],
                }
            ],
        }

    # =========================================================
    # PUBLIC API
    # =========================================================

    async def criar_plano_execucao(
        self,
        task: Union[str, Task],
        contexto_memoria: Optional[str] = None,
        erros_anteriores: Optional[List[str]] = None,
    ) -> Dict[str, Any]:

        logger.info("📐 [PLANNER AGENT]: Projetando arquitetura autocorretiva...")

        # =====================================================
        # NORMALIZAÇÃO DE ENTRADA (anti-falhas de tipo)
        # =====================================================
        task_text = self._extrair_task(task)
        contexto_memoria = contexto_memoria or "Nenhum contexto disponível."
        erros_anteriores = erros_anteriores or []

        # =====================================================
        # PROMPT ESTRUTURADO DE COMPORTAMENTO ESTREITO
        # =====================================================
        # Injeta as heurísticas de poucas tentativas (Few-Shot) para blindar modelos menores do OpenRouter
        prompt = f"""
Você é um Engenheiro e Arquiteto de Software Principal. 
Sua missão é quebrar a tarefa do usuário em subtarefas estruturadas sequencialmente em formato JSON válido para nossa esteira de desenvolvimento de agentes competitivos.

[TAREFA DO USUÁRIO]:
{task_text}

[CONTEXTO DE MEMÓRIA DE SUPORTE]:
{contexto_memoria}

[ERROS DE EXECUÇÕES ANTERIORES QUE DEVEM SER EVITADOS]:
{", ".join(erros_anteriores) if erros_anteriores else "Nenhum erro registrado."}

REGRAS DE COMPORTAMENTO CRUCIAIS:
1. Responda EXCLUSIVAMENTE com o objeto JSON estruturado válido.
2. NUNCA adicione saudações, introduções, justificativas ou notas explicativas fora das chaves do JSON.
3. NÃO adicione marcações de bloco markdown como ```json ou ```. Comece diretamente com {{ e termine com }}.
4. Certifique-se de que todas as chaves e strings usem aspas duplas de forma estrita.

EXEMPLO DE RETORNO EXATO DE MARCAÇÃO ESPERADO (SIGA ESTA ARQUITETURA):
{{
  "complexidade": "MÉDIA",
  "subtarefas": [
    {{
      "id": 1,
      "descricao": "Crie a assinatura de escopo limpo e implemente a lógica de cálculo do primeiro dígito verificador."
    }},
    {{
      "id": 2,
      "descricao": "Implemente a validação incremental do segundo dígito e o retorno booleano definitivo."
    }}
  ]
}}
"""

        modelo = ""

        try:
            # =================================================
            # EXECUÇÃO LLM (com 2 retries e fallback)
            # =================================================
            resposta = ""
            for attempt in range(3):
                resposta = await executar(
                    modelo, {"task": prompt, "system_constraints": []}
                )
                if resposta:
                    break
                logger.warning(
                    "[PLANNER] Tentativa %d/3 retornou vazia — retrying...", attempt + 1
                )
                if attempt < 2:
                    await asyncio.sleep(1.0 * (attempt + 1))

            if not resposta:
                logger.error("Planner retornou resposta vazia após 3 tentativas.")
                return self._fallback_plan(task_text)

            # =================================================
            # SANITIZAÇÃO E LIMPEZA POLIMÓRFICA DO JSON
            # =================================================
            # Intercepta e remove quaisquer ruídos de conversação ou tags de markdown deixadas por nuvens livres
            texto_bruto = str(resposta).strip()

            # Remove blocos clássicos de marcação markdown ```json ou ```
            import re

            texto_bruto = re.sub(r"```json\s*", "", texto_bruto, flags=re.IGNORECASE)
            texto_bruto = re.sub(r"```\s*", "", texto_bruto)
            texto_bruto = texto_bruto.strip()

            # Localiza cirurgicamente onde o primeiro { e o último } residem (Isola conversas extras)
            inicio_json = texto_bruto.find("{")
            fim_json = texto_bruto.rfind("}")

            if inicio_json != -1 and fim_json != -1 and fim_json > inicio_json:
                texto_limpo = texto_bruto[inicio_json : fim_json + 1]
            else:
                texto_limpo = self._limpar_json(resposta)

            if not texto_limpo:
                logger.error("Planner retornou JSON vazio após limpeza de escopo.")
                return self._fallback_plan(task_text)

            # =================================================
            # DETECÇÃO DE MÚLTIPLOS DOCUMENTOS JSON
            # =================================================
            # Verifica se há múltiplos objetos JSON (ex: {} {})
            texto_trimmed = texto_limpo.strip()
            json_objects = []
            decoder = json.JSONDecoder()
            pos = 0

            while pos < len(texto_trimmed):
                # Pula whitespace
                while pos < len(texto_trimmed) and texto_trimmed[pos].isspace():
                    pos += 1

                if pos >= len(texto_trimmed):
                    break

                try:
                    # Tenta parsear um objeto JSON
                    obj, end_pos = decoder.raw_decode(texto_trimmed, pos)
                    json_objects.append(obj)
                    pos += end_pos
                except json.JSONDecodeError:
                    # Não conseguiu parsear, para
                    break

            # Se encontrou exatamente um objeto, usa ele diretamente
            if len(json_objects) == 1:
                texto_limpo = json.dumps(json_objects[0])
            # Se encontrou múltiplos objetos, usa scoring para selecionar o melhor
            elif len(json_objects) > 1:
                logger.warning(
                    "[PLANNER] Múltiplos documentos JSON detectados (%d) — aplicando scoring",
                    len(json_objects),
                )

                # Scoring de candidatos
                def score_plan_candidate(obj: Any) -> int:
                    """Score heuristic para selecionar melhor plano entre múltiplos JSON."""
                    score = 0
                    if not isinstance(obj, dict):
                        return score

                    # Subtarefas é o campo mais importante
                    if "subtarefas" in obj:
                        score += 50
                        subtarefas = obj.get("subtarefas")
                        if isinstance(subtarefas, list):
                            score += min(
                                len(subtarefas) * 10, 30
                            )  # Bônus por quantidade
                            if len(subtarefas) > 0 and isinstance(subtarefas[0], dict):
                                score += 10  # Estrutura rica
                        else:
                            score -= 20  # Subtarefas não é lista
                    else:
                        score -= 50  # Penaliza fortemente quem não tem subtarefas

                    # Campos secundários
                    if obj.get("objetivo"):
                        score += 10
                    if obj.get("etapas"):
                        score += 10
                    if obj.get("complexidade"):
                        score += 5
                    if obj.get("estrategia_validacao"):
                        score += 5

                    return score

                # Seleciona melhor candidato
                best_candidate = max(json_objects, key=score_plan_candidate)
                best_score = score_plan_candidate(best_candidate)

                logger.info(
                    "[PLANNER] Selecionado candidato com score=%d (entre %d opções)",
                    best_score,
                    len(json_objects),
                )

                # Log de debugging
                if best_score < 50:
                    logger.warning(
                        "[PLANNER] Melhor candidato tem score baixo (%d) — plano pode ser incompleto",
                        best_score,
                    )

                texto_limpo = json.dumps(best_candidate)

            # =================================================
            # PARSE DEFENSIVO ANTI-QUEBRA — FLUXO EM ETAPAS
            # =================================================
            # Etapa 1: Tentar parse direto (JSON já válido)
            try:
                plano = json.loads(texto_limpo)
                logger.debug("[PLANNER] JSON parseado direto sem sanitização")
            except json.JSONDecodeError:
                # Etapa 2: Tentar ast.literal_eval (aceita single quotes de Python repr)
                try:
                    import ast
                    plano = ast.literal_eval(texto_limpo)
                    logger.debug("[PLANNER] JSON parseado via ast.literal_eval")
                except (ValueError, SyntaxError):
                    # Etapa 3: Sanitizar apenas o necessário
                    texto_sanitizado = self._sanitizar_json(texto_limpo)

                    # Etapa 4: Tentar parse com texto sanitizado
                    try:
                        plano = json.loads(texto_sanitizado)
                        logger.debug("[PLANNER] JSON parseado após sanitização")
                    except json.JSONDecodeError as je:
                        error_type = (
                            "multiple_json_documents"
                            if len(json_objects) > 1
                            else "invalid_json"
                        )
                        logger.error(
                            f"JSON inválido do planner: {je} | "
                            f"Tipo: {error_type} | "
                            f"Texto original: {texto_limpo[:100]}... | "
                            f"Texto sanitizado: {texto_sanitizado[:100]}..."
                        )
                        # Etapa 5: Fallback se tudo falhar
                        return self._fallback_plan(task_text)

            # =================================================
            # VALIDAÇÃO MÍNIMA DA ÁRVORE DO PLANO
            # =================================================
            if not isinstance(plano, dict) or "subtarefas" not in plano:
                logger.error("Plano inválido (estrutura incorreta ou chaves ausentes).")
                return self._fallback_plan(task_text)

            # =================================================
            # ENRIQUECIMENTO
            # =================================================
            plano = self._enriquecer_plano(plano)

            # =================================================
            # HISTÓRICO
            # =================================================
            self.execution_history.append({"task": task_text, "plano": plano})

            logger.info(
                "📐 [PLANNER AGENT]: Plano gerado com sucesso | "
                f"Complexidade: {plano.get('complexidade', 'DESCONHECIDA')}"
            )

            return plano

        except Exception as e:
            logger.warning(
                f"⚠️ [PLANNER AGENT]: Falha na execução estrutural: {e} — ativando fallback."
            )
            return self._fallback_plan(task_text)
