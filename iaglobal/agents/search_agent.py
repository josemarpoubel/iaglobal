# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
# agentes/search_agent.py

import re
import threading

from iaglobal.agents.agent_base import AgentBase
from iaglobal.tools.search_tools import SearchTools
from iaglobal.memory.memory_vector import store
from iaglobal.memory.db_manager import db
from iaglobal.utils.logger import logger

# Flag de validação one-shot do contrato de retorno do ddgs (title/href/body)
_DDGS_SHAPE_VALIDADO = False
_SHAPE_LOCK = threading.Lock()

class SearchAgent(AgentBase):
    def __init__(self):
        super().__init__(agent_name="search")

    def pesquisar_e_aprender(self, termo_busca: str) -> bool:
        """Busca na web estruturada, limpa o texto relevante e consolida no core.db/cbor2."""
        logger.info(f"🛰️ [SEARCH AGENT]: Iniciando rotina de aprendizado para a query: '{termo_busca}'")
        
        # 1. Higienização da Query para focar no assunto técnico e passar pelos firewalls
        query_limpa = termo_busca.lower()
        comandos_remover = [
            "crie uma função que", "crie uma", "função de", "criar função de", 
            "escreva um", "desenvolva", "faça um algoritmo", "script em python"
        ]
        for comando in comandos_remover:
            query_limpa = query_limpa.replace(comando, "")
        
        # Remove caracteres especiais e espaços extras redundantes
        query_limpa = re.sub(r'[^\w\s]', ' ', query_limpa)
        query_limpa = " ".join(query_limpa.split())
        
        logger.info(f"🛰️ [SEARCH AGENT]: Termo refinado para o buscador: '{query_limpa}'")
        
        search_success = False
        try:
            # 2. Busca estruturada via ddgs (lib mantida) — elimina scraping regex frágil.
            # Chamada síncrona de rede: segura pois pesquisar_e_aprender roda dentro de
            # _sync_execute_and_learn (despachado via asyncio.to_thread no node).
            resultados = SearchTools.search_and_fetch_raw(query_limpa, max_results=3)
            if not resultados:
                logger.warning("⚠️ [SEARCH AGENT]: ddgs não retornou resultados para a query.")
                return False

            # Validação one-shot do contrato de retorno (title/href/body)
            SearchAgent._validar_shape_ddgs(resultados)

            # Limita a 3 resultados para manter o contexto do prompt limpo e performático
            resultados_processados = 0
            max_resultados = 3

            for item in resultados[:max_resultados]:
                url = str(item.get("href", "")).strip()
                title = str(item.get("title", "")).strip() or "Sem título"
                snippet = str(item.get("body", "")).strip()

                # Evita salvar blocos sem substância semântica
                if not url or snippet in ("", "Sem conteúdo") or len(snippet) < 15:
                    continue

                # 3. Formatação e injeção direta no pipeline de memória persistente
                conhecimento_formatado = (
                    f"FONTE WEB CONSOLIDADA ({url})\n"
                    f"ASSUNTO: {title}\n"
                    f"CONTEÚDO EXTENSIONADO: {snippet}"
                )

                # store grava no core.db usando modo WAL e descarrega no binário .cbor2
                store(text=conhecimento_formatado, mtype="web_search")
                resultados_processados += 1

            if resultados_processados == 0:
                logger.warning("⚠️ [SEARCH AGENT]: Resultados ddgs analisados, mas nenhum continha dados válidos.")
                return False

            search_success = True
            logger.info(f"✅ [SEARCH AGENT]: Sucesso! {resultados_processados} novos dados sincronizados no cbor2.")
            return True

        except Exception as e:
            logger.error(f"❌ [SEARCH AGENT]: Falha crítica ao aprender via ddgs: {e}")
            return False

        finally:
            try:
                from iaglobal.observability.search_bridge import search_bridge as _sb
                _sb.auto_report_search(search_success, termo_busca)
            except Exception:
                pass

    @staticmethod
    def _validar_shape_ddgs(resultados: list) -> None:
        """Validação one-shot do contrato de retorno do ddgs (title/href/body).

        Protege contra regressão silenciosa: se a lib mudar o shape, logamos ANTES
        de persistir lixo no core.db (conforme alerta de shape do ciclo metabólico).
        """
        global _DDGS_SHAPE_VALIDADO
        with _SHAPE_LOCK:
            if _DDGS_SHAPE_VALIDADO:
                return
            _DDGS_SHAPE_VALIDADO = True
        if not isinstance(resultados, list):
            logger.error("⚠️ [SHAPE] ddgs retornou tipo inesperado: %s", type(resultados).__name__)
            return
        amostra = resultados[0] if resultados else {}
        chaves_esperadas = {"title", "href", "body"}
        if not isinstance(amostra, dict) or not chaves_esperadas.issubset(amostra.keys()):
            actual = sorted(amostra.keys()) if isinstance(amostra, dict) else type(amostra).__name__
            logger.error("⚠️ [SHAPE] ddgs retornou contrato inesperado: %s (esperado: %s)",
                         actual, sorted(chaves_esperadas))
        else:
            logger.info("[SHAPE] Contrato ddgs validado: %s", sorted(amostra.keys()))

    async def process_task(self, task: str) -> str:
        cache_key = f"search:{hash(task)}"
        cached = db.get_cached_search(cache_key)
        if cached:
            logger.info(f"🧠 [SEARCH AGENT]: Cache hit para '{task[:60]}...'")
            return cached

        logger.info(f"🛰️ [SEARCH AGENT]: processando tarefa: '{task[:100]}'")
        if "código" in task.lower() or "html" in task.lower() or "github" in task.lower():
            result = await SearchTools.search_and_fetch_code(task)
        else:
            snippets = SearchTools.search_and_fetch_raw(task, max_results=3)
            result = "\n\n".join(
                f"• {s['title']}\n  {s['href']}\n  {s['body']}"
                for s in snippets
            ) if snippets else "Nenhum resultado encontrado."

        if result and result not in ("Nenhum resultado encontrado.", "Erro ao extrair código."):
            db.cache_search_result(cache_key, result)

        return result



