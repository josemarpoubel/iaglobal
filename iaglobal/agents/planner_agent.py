# iaglobal/agents/planner_agent.py

import json
from typing import Dict, Any, Optional, Union, List

from iaglobal.models.task import Task
from iaglobal.core.assistant import Assistant
from iaglobal.utils.logger import logger
from iaglobal.providers.provider_router import route_generate
from iaglobal.execution.executor import executar

import logging

from iaglobal.utils.logger import logger

logger = logging.getLogger("ia-global")

class PlannerAgent:
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
            logger.error("⚠️ [PLANNER]: Recebido objeto de tarefa nulo (None) para extração.")
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
            logger.warning(f"⚠️ [PLANNER]: Extração falhou na varredura de atributos. Usando fallback de string genérica.")
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
            match_markdown = re.search(r"```(?:json)?\s*(.*?)\s*```", texto, re.DOTALL | re.IGNORECASE)
            if match_markdown:
                texto = match_markdown.group(1).strip()
        except Exception as re_err:
            logger.warning(f"⚠️ [PLANNER]: Falha não-bloqueante na varredura regex do markdown: {re_err}")

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
            start = text.find('{')
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
                if char == '\\' and in_string:
                    escape = True
                    continue
                if char == '"' and not escape:
                    in_string = not in_string
                    continue
                if not in_string:
                    if char == '{':
                        depth += 1
                    elif char == '}':
                        depth -= 1
                        if depth == 0:
                            end = i
                            break
            
            if end != -1:
                return text[start:end+1]
            return text[start:]

        texto_filtrado = extract_balanced_json(texto)

        # 4. Sanitização final
        texto_sanitizado = texto_filtrado.strip()
        texto_sanitizado = re.sub(r'\n\s*\n', '\n', texto_sanitizado)
        texto_sanitizado = re.sub(r',\s*}', '}', texto_sanitizado)  # Remove trailing commas
        texto_sanitizado = re.sub(r',\s*]', ']', texto_sanitizado)  # Remove trailing commas in arrays

        return texto_sanitizado



    def _enriquecer_plano(self, plano: Dict[str, Any]) -> Dict[str, Any]:
        """
        Injeta e força metadados estruturais para garantir que a autocorreção em runtime
        e a validação sintática (AST) funcionem, mesmo se a LLM omitir ou corromper esses campos.
        """
        if not isinstance(plano, dict):
            logger.error("🚫 [PLANNER] Objeto inválido passado para enriquecimento.")
            return self._fallback_plan("Falha estrutural ao enriquecer plano.")

        # 1. GARANTE A ARVORE DE ESTRATÉGIA DE VALIDAÇÃO (Força True nas flags críticas)
        if "estrategia_validacao" not in plano or not isinstance(plano["estrategia_validacao"], dict):
            plano["estrategia_validacao"] = {}
            
        estrategia = plano["estrategia_validacao"]
        estrategia["usar_ast"] = bool(estrategia.get("usar_ast", True))
        estrategia["usar_execucao_real"] = bool(estrategia.get("usar_execucao_real", True))
        estrategia["usar_testes_unitarios"] = bool(estrategia.get("usar_testes_unitarios", True))
        estrategia["usar_autocorrecao"] = bool(estrategia.get("usar_autocorrecao", True))

        # 2. SELETOR DE MODOS CONFIGURADO NA ORIGEM
        plano["modo_execucao"] = str(plano.get("modo_execucao", "autocorretivo")).strip().lower()
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

                # Espelhamento polimórfico de campos (Tradução e Fallback de chaves)
                st["titulo"] = str(st.get("titulo", st.get("title", "Etapa de Implementação Técnica"))).strip()
                st["description"] = str(st.get("description", st.get("descricao", "Desenvolver lógica funcional conforme plano."))).strip()
                st["descricao"] = st["description"]  # Garante paridade em português para os agentes locais
                
                st["validacao_runtime"] = str(st.get("validacao_runtime", "Executar asserções básicas de runtime.")).strip()
                
                # Normalização da lista de erros esperados
                erros = st.get("possiveis_erros", st.get("possible_errors", []))
                if not isinstance(erros, list):
                    erros = [str(erros)] if erros else ["Exception"]
                st["possiveis_erros"] = [str(e).strip() for e in erros if e]
                if not st["possiveis_erros"]:
                    st["possiveis_erros"] = ["TypeError", "ValueError", "RuntimeError"]

                st["alertas_seguranca"] = str(st.get("alertas_seguranca", "Modo Sandbox ativado.")).strip()
                subtarefas_limpas.append(st)
                
            plano["subtarefas"] = subtarefas_limpas
        else:
            # Se o campo de subtarefas veio corrompido da nuvem, injeta uma estrutura básica padrão
            plano["subtarefas"] = [
                {
                    "id": 1,
                    "titulo": "Geração Modular",
                    "descricao": "Desenvolver a lógica principal do componente.",
                    "validacao_runtime": "Compilar no interpretador e capturar tracebacks.",
                    "possiveis_erros": ["TypeError", "ValueError", "RuntimeError"],
                    "alertas_seguranca": "Modo Sandbox ativo."
                }
            ]

        return plano


    def _fallback_plan(self, task_text: str) -> Dict[str, Any]:
        """
        Plano de contingência resiliente com higienização de string para evitar 
        truncamento em logs ou agentes subsequentes.
        """
        logger.warning("⚠️ [PLANNER AGENT]: Ativando modo de contingência resiliente.")

        # 1. Higienização e Proteção de Integridade
        # Garante que não teremos strings vazias ou cortes parciais por quebras de linha
        enunciado_base = str(task_text).strip().replace('\n', ' ')
        enunciado_limpo = enunciado_base if len(enunciado_base) > 5 else "Desenvolver função solicitada pelo usuário."

        # Debug seguro: log apenas o início para evitar spam no console
        logger.debug(f"DEBUG: Enunciado sanitizado ({len(enunciado_limpo)} chars): {enunciado_limpo[:50]}...")

        # 2. Definição da estrutura com chaves espelhadas
        # Blindagem contra KeyError em diferentes ambientes de LLM
        return {
            "complexidade": "DESCONHECIDA",
            "arquitetura_proposta": "Design defensivo baseado em execução direta e traceback Sandbox.",
            "estrategia_validacao": {
                "usar_ast": True,
                "usar_execucao_real": True,
                "usar_testes_unitarios": True,
                "usar_autocorrecao": True
            },
            "subtarefas": [
                {
                    "id": 1,
                    # Bloco em Português
                    "titulo": "Execução Direta",
                    "descricao": f"Codifique uma solução Python robusta para cumprir a seguinte meta: {enunciado_limpo}",
                    "validacao_runtime": "Compilar em sandbox e capturar exceções reais.",
                    "possiveis_erros": ["TypeError", "ValueError", "NameError", "SyntaxError", "RuntimeError", "Exception"],
                    "alertas_seguranca": "Modo contingência: Sandbox ativado.",
                    
                    # Chaves espelhadas em Inglês (Blindagem de Agentes)
                    "title": "Direct Code Implementation and Generation",
                    "description": f"Write a robust Python script to solve the following objective: {enunciado_limpo}",
                    "possible_errors": ["TypeError", "ValueError", "NameError", "SyntaxError", "RuntimeError"]
                }
            ]
        }

    # =========================================================
    # PROMPT INJECTION ENGINE (FIX CRÍTICO EVOLUÍDO)
    # =========================================================

    def injetar_plano_no_prompt(
        self,
        plano: Dict[str, Any],
        subtarefa_atual_id: int
    ) -> str:
        """
        Injeta o plano de execução no prompt do Coder Agent
        com contexto de estado, progresso e rastreabilidade estrita.
        Limpa indentações e blinda a esteira contra falhas de tipo (NoneType).
        """
        if not isinstance(plano, dict):
            logger.error("🚫 [PLANNER] Plano fornecido para injeção não é um dicionário.")
            return "[ERRO DE CONTEXTO: Plano de arquitetura inválido ou corrompido]"

        subtarefas = plano.get("subtarefas", [])
        if not isinstance(subtarefas, list):
            subtarefas = []

        buffer = [
            "\n==================================================",
            "📋 PLANO DE EXECUÇÃO AUTOCORRETIVO DA ARQUITETURA",
            "==================================================",
            f"Arquitetura Proposta : {plano.get('arquitetura_proposta', 'Não definida pelo arquiteto.')}",
            f"Complexidade Geral   : {plano.get('complexidade', 'DESCONHECIDA')}",
            "--------------------------------------------------",
        ]

        # Varre a árvore de subtarefas gerando as tags de estado
        for st in subtarefas:
            if not isinstance(st, dict):
                continue

            st_id = st.get("id")
            if st_id is None:
                continue

            try:
                st_id_int = int(st_id)
            except (ValueError, TypeError):
                continue

            # Máquina de estados linear para guiar o foco (Attention) do Coder
            if st_id_int < subtarefa_atual_id:
                status = "✔ Concluída"
            elif st_id_int == subtarefa_atual_id:
                status = "🚀 EXECUTANDO AGORA (FOCO TOTAL AQUI)"
            else:
                status = "⏳ PENDENTE"

            titulo = st.get("titulo", st.get("title", "Sem título técnico"))
            descricao = st.get("descricao", st.get("description", "Sem descrição de engenharia"))
            validacao = st.get("validacao_runtime", "Não definida para esta etapa.")
            erros = st.get("possiveis_erros", st.get("possible_errors", []))

            # Tratamento defensivo polimórfico para a lista de exceções mapeadas
            if isinstance(erros, list):
                erros_limpos = ", ".join([str(e) for e in erros if e is not None])
            else:
                erros_limpos = str(erros)
            
            if not erros_limpos.strip():
                erros_limpos = "Nenhum erro crítico mapeado para esta etapa."

            # Strings multi-linha limpas de recuos ocultos na margem esquerda (Evita quebrar o prompt do Coder)
            bloco_etapa = (
                f"ETAPA #{st_id_int} [{status}]\n"
                f"----------------------------------------\n"
                f"TÍTULO: {titulo}\n\n"
                f"DESCRIÇÃO TÉCNICA:\n{descricao}\n\n"
                f"VALIDAÇÃO EM RUNTIME:\n{validacao}\n\n"
                f"EXCEÇÕES E ERROS ESPERADOS:\n{erros_limpos}\n"
                f"----------------------------------------"
            )
            buffer.append(bloco_etapa)

        buffer.append("\n==================================================\n")

        return "\n".join(buffer)


    # =========================================================
    # PUBLIC API
    # =========================================================

    async def criar_plano_execucao(
        self,
        task: Union[str, Task],
        contexto_memoria: Optional[str] = None,
        erros_anteriores: Optional[List[str]] = None
    ) -> Dict[str, Any]:

        logger.info(
            "📐 [PLANNER AGENT]: Projetando arquitetura autocorretiva..."
        )

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
            # EXECUÇÃO LLM
            # =================================================
            resposta = await executar(
                modelo,
                {
                    "task": prompt,
                    "system_constraints": []
                }
            )

            if not resposta:
                logger.error("Planner retornou resposta vazia.")
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
                texto_limpo = texto_bruto[inicio_json:fim_json + 1]
            else:
                texto_limpo = self._limpar_json(resposta)

            if not texto_limpo:
                logger.error("Planner retornou JSON vazio após limpeza de escopo.")
                return self._fallback_plan(task_text)

            # =================================================
            # PARSE DEFENSIVO ANTI-QUEBRA
            # =================================================
            try:
                plano = json.loads(texto_limpo)
            except json.JSONDecodeError as je:
                logger.error(f"JSON inválido do planner: {je} | Texto que quebrou: {texto_limpo[:100]}...")
                # Se falhar o parse da nuvem, aciona o fallback resiliente local para não parar o pipeline
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
            self.execution_history.append({
                "task": task_text,
                "plano": plano
            })

            logger.info(
                "📐 [PLANNER AGENT]: Plano gerado com sucesso | "
                f"Complexidade: {plano.get('complexidade', 'DESCONHECIDA')}"
            )

            return plano

        except Exception as e:
            logger.warning(f"⚠️ [PLANNER AGENT]: Falha na execução estrutural: {e} — ativando fallback.")
            return self._fallback_plan(task_text)


    # =========================================================
    # PROMPT ENGINEERING
    # =========================================================

    def _montar_prompt_planejamento(
        self,
        task: str,
        contexto_memoria: Optional[str],
        erros_anteriores: Optional[List[str]]
    ) -> str:

        historico_erros = "\n".join(erros_anteriores) if erros_anteriores else "Nenhum erro anterior registrado."
        contexto_memoria = contexto_memoria or "Nenhum contexto disponível."

        template_json = """{
  "complexidade": "BAIXA|MEDIA|ALTA",
  "arquitetura_proposta": "descrição técnica objetiva do design do código",
  "estrategia_validacao": {
      "usar_ast": true,
      "usar_execucao_real": true,
      "usar_testes_unitarios": true,
      "usar_autocorrecao": true
  },
  "subtarefas": [
    {
      "id": 1,
      "titulo": "titulo técnico da etapa",
      "descricao": "ação técnica objetiva que o programador deve codificar",
      "validacao_runtime": "asserção ou teste de validação em runtime",
      "possiveis_erros": [
          "TypeError",
          "ImportError",
          "IndexError",
          "ValueError"
      ],
      "alertas_seguranca": "restrições e travas de escopo"
    }
  ]
}"""

        prompt = (
            "Você é um Arquiteto de Sistemas Autônomos especializado em agentes autocorretivos Python.\n"
            "Sua missão NÃO é apenas quebrar a tarefa em subtarefas simples. Você deve projetar uma malha estável de software.\n\n"
            "DIRETRIZES DE ARQUITETURA:\n"
            "- Planejar geração incremental de código limpo e desacoplado\n"
            "- Prever erros reais de runtime e falhas de tipagem estática\n"
            "- Projetar validação automática rigorosa baseada em asserções\n"
            "- Preparar autocorreção baseada em traceback REAL do Python sandboxed\n\n"
            "REGRA DE INFRAESTRUTURA:\n"
            "O sistema executará o código em runtime REAL usando Python isolado (Sandbox).\n"
            "Os erros reais capturados de tracebacks serão repassados automaticamente para os sub-agentes de debug.\n\n"
            "==================================================\n"
            "TAREFA ORIGINAL DO USUÁRIO\n"
            "==================================================\n"
            f"{task}\n\n"
            "==================================================\n"
            "CONTEXTO DE MEMÓRIA RECUPERADO\n"
            "==================================================\n"
            f"{contexto_memoria}\n\n"
            "==================================================\n"
            "HISTÓRICO DE ERROS ANTERIORES A SEREM EVITADOS\n"
            "==================================================\n"
            f"{historico_erros}\n\n"
            "==================================================\n"
            "INSTRUÇÕES DE PLANEJAMENTO RESTRITIVAS\n"
            "==================================================\n"
            f"1. Divida a lógica em no máximo {self.MAX_ETAPAS} subtarefas modulares.\n"
            "2. Cada subtarefa deve ser pequena, isolada e perfeitamente validável via Python runtime.\n"
            "3. Identifique riscos reais de execução: TypeError, IndexError, ImportError, ValueError, Timeout, loops infinitos ou problemas de escopo local.\n"
            "4. NÃO use placeholders, comentários vazios, reticências (...) ou implementações fictícias (Ex: '# código vai aqui').\n"
            "5. NÃO escreva exemplos genéricos de código dentro do plano. O plano deve ser puramente estrutural e executável.\n\n"
            "==================================================\n"
            "REGRAS DE FORMATAÇÃO DO SISTEMA (OBRIGATÓRIO)\n"
            "==================================================\n"
            "- Retorne EXCLUSIVAMENTE o objeto JSON válido, seguindo o esquema técnico exato abaixo.\n"
            "- É PROIBIDO incluir qualquer texto explicativo, saudações, introduções ou notas fora do bloco JSON.\n"
            "- É PROIBIDO envelopar o JSON em blocos de marcação markdown como ```json ou ```. Comece diretamente com '{' e termine com '}'.\n"
            "- Certifique-se de usar aspas duplas de forma estrita em todas as chaves e strings.\n\n"
            "ESQUEMA JSON EXATO REQUERIDO:\n"
            f"{template_json}"
        )

        return prompt

