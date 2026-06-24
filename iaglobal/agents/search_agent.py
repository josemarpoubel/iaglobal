# agentes/search_agent.py

import os
import re
import requests

from iaglobal.tools.search_tools import SearchTools
from iaglobal.memory.memory_vector import store
from iaglobal.memory.db_manager import db
from iaglobal.utils.logger import logger
from iaglobal.providers.provider_router import route_generate

class SearchAgent:
    def __init__(self):
        # Endpoint HTML estável que não exige JavaScript e evita telas de desafio anti-bot
        self.search_url = "https://duckduckgo.com?"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.8,en-US;q=0.5,en;q=0.3"
        }

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
        
        try:
            # 2. Montagem e envio da requisição HTTP usando biblioteca nativa
            params = urllib.parse.urlencode({"q": query_limpa})
            req = urllib.request.Request(self.search_url + params, headers=self.headers)
            
            with urllib.request.urlopen(req, timeout=10) as response:
                html = response.read().decode("utf-8")

            # 3. Captura dos blocos de resultados (Suporta layouts clássicos e de tabelas simplificadas)
            blocos_resultados = re.findall(r'<div class="[^"]*results_links_deep.*?">.*?</div>\s*</div>\s*</div>', html, re.DOTALL)
            if not blocos_resultados:
                blocos_resultados = re.findall(r'<td class="result-snippet">.*?</td>', html, re.DOTALL)

            if not blocos_resultados:
                logger.warning("⚠️ [SEARCH AGENT]: DuckDuckGo não retornou nenhum snippet estruturado.")
                return False

            # Limita a 3 resultados para manter o contexto do prompt limpo e performático
            resultados_processados = 0
            max_resultados = 3
            
            for bloco in blocos_resultados[:max_resultados]:
                # Regex adaptativas para capturar URL, Título e Snippet de conteúdo
                match_url = re.search(r'href="([^"]*?uddg=[^"]*?)"', bloco) or re.search(r'href="([^"]*?)"', bloco)
                match_title = re.search(r'class="result__url"[^>]*>(.*?)</a>', bloco, re.DOTALL) or re.search(r'<a class="result-link"[^>]*>(.*?)</a>', bloco, re.DOTALL)
                match_snippet = re.search(r'class="result__snippet"[^>]*>(.*?)</a>', bloco, re.DOTALL) or re.search(r'<td class="result-snippet"[^>]*>(.*?)</td>', bloco, re.DOTALL)

                # Tratamento e decodificação segura da URL final de destino
                url_bruta = match_url.group(1) if match_url else "Sem URL"
                if "uddg=" in url_bruta:
                    try:
                        url_bruta = url_bruta.split("uddg=")[1].split("&")[0]
                    except IndexError:
                        pass
                
                url = urllib.parse.unquote(url_bruta)
                title = re.sub(r'<[^>]+>', '', match_title.group(1)).strip() if match_title else "Sem título"
                snippet = re.sub(r'<[^>]+>', '', match_snippet.group(1)).strip() if match_snippet else "Sem conteúdo"

                # Evita salvar blocos sem substância semântica
                if snippet == "Sem conteúdo" or len(snippet) < 15:
                    continue

                # 4. Formatação e injeção direta no pipeline de memória persistente
                conhecimento_formatado = (
                    f"FONTE WEB CONSOLIDADA ({url})\n"
                    f"ASSUNTO: {title}\n"
                    f"CONTEÚDO EXTENSIONADO: {snippet}"
                )

                # store grava no core.db usando modo WAL e descarrega no binário .cbor2
                store(text=conhecimento_formatado, mtype="web_search")
                resultados_processados += 1

            if resultados_processados == 0:
                logger.warning("⚠️ [SEARCH AGENT]: Blocos HTML analisados, mas nenhum continha dados válidos.")
                return False

            logger.info(f"✅ [SEARCH AGENT]: Sucesso! {resultados_processados} novos dados sincronizados no cbor2.")
            return True
            
        except Exception as e:
            logger.error(f"❌ [SEARCH AGENT]: Falha crítica ao aprender via DuckDuckGo: {e}")
            return False

    def process_task(self, task: str) -> str:
        cache_key = f"search:{hash(task)}"
        cached = db.get_cached_search(cache_key)
        if cached:
            logger.info(f"🧠 [SEARCH AGENT]: Cache hit para '{task[:60]}...'")
            return cached

        logger.info(f"🛰️ [SEARCH AGENT]: processando tarefa: '{task[:100]}'")
        if "código" in task.lower() or "html" in task.lower() or "github" in task.lower():
            result = SearchTools.search_and_fetch_code(task)
        else:
            snippets = SearchTools.search_and_fetch_raw(task, max_results=3)
            result = "\n\n".join(
                f"• {s['title']}\n  {s['href']}\n  {s['body']}"
                for s in snippets
            ) if snippets else "Nenhum resultado encontrado."

        if result and result not in ("Nenhum resultado encontrado.", "Erro ao extrair código."):
            db.cache_search_result(cache_key, result)

        return result



