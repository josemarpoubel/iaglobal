# iaglobal/core/assistant.py

import os
import re
import html
import json
import urllib.request
import urllib.parse
from typing import Union, Optional, List, Dict

import logging

from iaglobal.utils.logger import logger

logger = logging.getLogger("ia-global")

class Assistant:
    def __init__(self, web_enabled: bool = True, kb_learning: bool = True,
                 skill_generation: bool = True, proxy_mode: bool = False):
        self.web_enabled = web_enabled
        self.kb_learning = kb_learning
        self.skill_generation = skill_generation
        self.proxy_mode = proxy_mode
        
        self.stm = ShortTermMemory(max_size=50, ttl_seconds=1800, db_path=MEMORIES_DB)
        self.ltm = LongTermMemory(max_size=500, db_path=MEMORIES_DB)
        self.webbrain = WebBrain()
        self.consolidation = ConsolidationEngine(long_term_memory=self.ltm)
        self.ranking = CognitiveRanking()
        
        # Importação local (Lazy Import) para quebrar o ciclo de inicialização
        if skill_generation:
            from iaglobal.agents.skill_generator_agent import SkillGeneratorAgent
            self.skill_gen = SkillGeneratorAgent()
        else:
            self.skill_gen = None
            
        self.kb_writer = KnowledgeWriterAgent() if kb_learning else None
        self.proxy = CognitiveProxy(web_enabled=web_enabled) if proxy_mode else None

    def __call__(self, prompt: Union[str, Task]) -> str:
        return self.process(prompt)

    def process(self, prompt: Union[str, Task]) -> str:
        if self.proxy_mode:
            return self._proxy_process(prompt)
        return self._processar_assistente(prompt)

    def _proxy_process(self, prompt: Union[str, Task]) -> str:
        """Usa CognitiveProxy como pipeline principal."""
        prompt_str = self._normalizar_prompt(prompt)
        result = self.proxy.run(prompt_str)
        if result.success:
            return result.output
        return f"Erro no CognitiveProxy: {result.error}"

    def _processar_assistente(self, prompt: Union[str, Task]) -> str:

        prompt_str = self._normalizar_prompt(prompt)

        bus.publish(
            EventType.TASK_CREATED,
            {"task": prompt_str[:200]},
            source="assistant"
        )

        # 1. Memory Retrieval (local)
        contexto_memoria = self._buscar_memoria(prompt_str)
        contexto_ltm = self._buscar_ltm(prompt_str)
        contexto_stm = self._buscar_stm(prompt_str)

        # 2. Web Retrieval (online)
        contexto_web = ""
        web_results = []
        if self.web_enabled:
            contexto_web, web_results = self._buscar_web_cme(prompt_str)

        # 3. Consistency check (web vs local)
        consistencia = self._verificar_consistencia(web_results, contexto_memoria)

        # 4. Build unified context
        ctx = self._build_unified_context(
            prompt_str, contexto_stm, contexto_ltm, contexto_memoria,
            contexto_web, consistencia
        )

        # 5. Model routing
        modelo = escolher_modelo(prompt_str)
        resposta_func = self._criar_funcao_modelo(modelo)
        prompt_final = self._montar_prompt_cognitivo(ctx)

        # 6. LLM with optional reflection
        if self._eh_teorico(prompt_str):
            resposta = resposta_func(prompt_final)
        else:
            resposta = reflexion_loop(resposta_func, prompt_final)

        # 7. Persist
        self._persistir(prompt_str, resposta)

        # 8. Knowledge Writer Agent (aprende da conversa)
        if self.kb_writer:
            self.kb_writer.learn_from_conversation(prompt_str, resposta)

        # 9. Skill Generator Agent (analisa KB e gera novas skills)
        if self.skill_gen and self.kb_writer:
            kb_stats = self.kb_writer.get_knowledge_base_stats()
            if kb_stats.get("total_entries", 0) % 5 == 1:
                new_skills = self.skill_gen.analyze_and_generate()
                if new_skills:
                    logger.info(f"[ASSISTANT] {len(new_skills)} novas skills geradas da KB")

        # 10. Post-response consolidation (learning cycle)
        self._consolidate_knowledge(prompt_str, resposta, web_results)

        # 11. Store in short-term memory
        self.stm.add(f"USER: {prompt_str}", {"type": "user"})
        self.stm.add(f"AI: {resposta}", {"type": "ai"})

        return resposta

    # =========================================================
    # NORMALIZAÇÃO
    # =========================================================
    def _normalizar_prompt(self, prompt: Union[str, Task]) -> str:
        if prompt is None:
            return ""
        if isinstance(prompt, str):
            return prompt.strip()
        if hasattr(prompt, "text"):
            return str(prompt.text).strip()
        if hasattr(prompt, "description"):
            return str(prompt.description).strip()
        return str(prompt).strip()

    # =========================================================
    # WEB (CME-ONLINE)
    # =========================================================
    def _buscar_web_cme(self, prompt: str):
        """WebBrain search — retorna (texto_formatado, lista_resultados)."""
        try:
            results = self.webbrain.search(prompt, max_results=5)
            if not results:
                return "", []

            lines = []
            for r in results:
                snippet = (r.get("content") or "")[:200]
                source = r.get("source", "web")
                title = r.get("title", "Sem título")
                lines.append(f"[{source}] {title}\n  {snippet}")

            texto = "\n\n".join(lines)

            for r in results:
                r["cognitive_score"] = self.ranking.score(r)

            return texto, results
        except Exception:
            return "", []

    def _limpar_query(self, text: str) -> str:
        text = text.lower()
        stop = ["explique", "o que é", "me diga", "sobre", "conceito de"]
        for s in stop:
            text = text.replace(s, "")
        text = re.sub(r"[^\w\s]", " ", text)
        return " ".join(text.split()).strip()

    # =========================================================
    # MEMÓRIA LOCAL (VETORIAL + LTM + STM)
    # =========================================================
    def _buscar_memoria(self, prompt: str) -> str:
        mem = search(prompt)
        if not mem:
            return ""
        lines = ["MEMÓRIA RELEVANTE:"]
        for item in mem[:5]:
            try:
                if isinstance(item, (list, tuple)) and len(item) == 2:
                    score, data = item
                    text = data.get("text", str(data)) if isinstance(data, dict) else str(data)
                    lines.append(f"- {text} (score={score:.2f})")
                else:
                    lines.append(f"- {str(item)}")
            except Exception:
                continue
        return "\n".join(lines)

    def _buscar_ltm(self, prompt: str) -> str:
        memories = self.ltm.retrieve(prompt, top_k=3)
        if not memories:
            return ""
        lines = ["MEMÓRIA DE LONGO PRAZO:"]
        for m in memories:
            content = (m.get("content") or "")[:150]
            source = m.get("source", "?")
            importance = m.get("importance", 0)
            lines.append(f"- [{source}] {content} (importância={importance:.2f})")
        return "\n".join(lines)

    def _buscar_stm(self, prompt: str) -> str:
        recent = self.stm.get_recent_with_metadata(5)
        if not recent:
            return ""
        lines = ["MEMÓRIA DE CURTO PRAZO (histórico recente):"]
        for entry in recent:
            content = entry["content"]
            mtype = entry.get("metadata", {}).get("type", "?")
            lines.append(f"[{mtype}] {content[:120]}")
        return "\n".join(lines)

    # =========================================================
    # CONSISTÊNCIA COGNITIVA
    # =========================================================
    def _verificar_consistencia(self, web_results: List[Dict], memoria_str: str) -> str:
        """Detecta conflitos entre web e memória local."""
        if not web_results or not memoria_str:
            return ""
        conflicts = []
        for wr in web_results[:3]:
            conflict = self.ranking.detect_conflict(
                wr, {"content": memoria_str, "source": "memory"}
            )
            if conflict:
                conflicts.append(conflict)
        return "\n".join(conflicts[:2])

    # =========================================================
    # UNIFIED KNOWLEDGE CONTEXT
    # =========================================================
    def _build_unified_context(
        self,
        prompt: str,
        stm: str,
        ltm: str,
        vector_mem: str,
        web: str,
        consistencia: str
    ) -> dict:
        return {
            "prompt": prompt,
            "stm": stm,
            "ltm": ltm,
            "vector_memoria": vector_mem,
            "web": web,
            "consistencia": consistencia,
            "memoria_evolutiva": carregar() or "vazia",
        }

    # =========================================================
    # MODEL ROUTER WRAPPER
    # =========================================================
    def _criar_funcao_modelo(self, modelo: str):

        def executar_modelo(prompt: str) -> str:
            try:
                return self._dispatch_modelo(modelo, prompt)
            except Exception as e:
                print(f"⚠️ [MODEL ERROR] {e}")
                return blackjack_executar_local("iaglobal-coder-9b", prompt)

        return executar_modelo

    def _dispatch_modelo(self, modelo: str, prompt: str) -> str:
        model_name = modelo.lower().strip()

        if "gemini" in model_name:
            from google import genai
            genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
            model = genai.GenerativeModel(model_name)
            return model.generate_content(prompt).text

        if model_name.startswith("nvidia/"):
            from openai import OpenAI
            client = OpenAI(
                base_url="https://integrate.api.nvidia.com/v1",
                api_key=os.getenv("NVIDIA_API_KEY"),
                max_retries=0
            )
            response = client.chat.completions.create(
                model=model_name.replace("nvidia/", ""),
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2
            )
            return response.choices[0].message.content

        if model_name.startswith("openrouter/"):
            from openai import OpenAI
            client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=ProviderConfig.OPENROUTER_API_KEY,
                max_retries=0
            )
            response = client.chat.completions.create(
                model=model_name.replace("openrouter/", ""),
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2
            )
            return response.choices[0].message.content

        return blackjack_executar_local(
            model_name.replace("ollama/", ""),
            prompt
        )

    # =========================================================
    # PROMPT COGNITIVO (CME-ONLINE)
    # =========================================================
    def _montar_prompt_cognitivo(self, ctx: dict) -> str:
        sections = []

        sections.append("[INSTRUÇÃO]")
        sections.append("Você é um assistente com capacidade de consultar memória local e conhecimento da internet. Responda com base no contexto unificado abaixo.")

        sections.append("\n[MEMÓRIA LOCAL]")
        local_parts = []
        if ctx["stm"]:
            local_parts.append(ctx["stm"])
        if ctx["ltm"]:
            local_parts.append(ctx["ltm"])
        if ctx["vector_memoria"]:
            local_parts.append(ctx["vector_memoria"])
        sections.append("\n".join(local_parts) if local_parts else "(sem memória local relevante)")

        sections.append("\n[CONHECIMENTO DA INTERNET]")
        sections.append(ctx["web"] if ctx["web"] else "(sem consulta web)")

        if ctx["consistencia"]:
            sections.append("\n[NOTA DE CONSISTÊNCIA]")
            sections.append(ctx["consistencia"])

        sections.append("\n[CONSOLIDAÇÃO]")
        sections.append("Use o contexto acima para responder com base em conhecimento atualizado. Se houver conflito entre web e memória, prefira a web por ser mais recente.")

        sections.append("\n[MEMÓRIA EVOLUTIVA]")
        sections.append(ctx["memoria_evolutiva"])

        sections.append("\n[TAREFA]")
        sections.append(ctx["prompt"])

        return "\n".join(sections)

    # =========================================================
    # DETECÇÃO DE INTENÇÃO
    # =========================================================
    def _eh_teorico(self, prompt: str) -> bool:
        keywords = [
            "explique", "o que é", "conceito",
            "teoria", "descreva"
        ]
        return any(
            re.search(rf"\b{kw}\b", prompt.lower())
            for kw in keywords
        )

    # =========================================================
    # PERSISTÊNCIA
    # =========================================================
    def _persistir(self, prompt: str, resposta: str):
        try:
            memoria = f"USER: {prompt}\nAI: {resposta}"
            salvar(memoria)
            store(text=memoria, mtype="dialog")
        except Exception as e:
            print(f"⚠️ [MEMORY ERROR] {e}")

    def _store_ltm(self, content: str, source: str = "dialog"):
        try:
            self.ltm.store(content, {"source": source}, source=source)
        except Exception as e:
            print(f"⚠️ [LTM ERROR] {e}")

    # =========================================================
    # LEARNING CYCLE (CONSOLIDAÇÃO PÓS-RESPOSTA)
    # =========================================================
    def _consolidate_knowledge(self, prompt: str, resposta: str, web_results: List[Dict]):
        """Etapa 6-7 do ciclo: reflection → memory consolidation."""
        try:
            local_memories = search(prompt)
            summaries = self.consolidation.consolidate_web_knowledge(
                web_results, local_memories
            )
            if summaries:
                for s in summaries:
                    self._store_ltm(s["content"], "consolidated")
        except Exception as e:
            print(f"⚠️ [CONSOLIDATION ERROR] {e}")


def processar_assistente(prompt: Union[str, Task]) -> str:
    return Assistant()(prompt)
