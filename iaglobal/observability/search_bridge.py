# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
PhospholipidSearchBridge — ponte entre SearchAgent e PhospholipidRegistry.

Fornece load balancing para serviços de busca (DuckDuckGo, Bing, Google etc.)
com fallback automático e adaptive decay.

Fluxo:
  1. SearchAgent quer pesquisar
  2. Bridge.search(query) → verifica registry
  3. Se há search services registrados → load balancer seleciona o mais saudável
  4. Executa busca → reporta health
  5. Se falha → adaptive decay + fallback para próximo search service
  6. Se nenhum service registrado → usa ddgs local (default)
"""

import time
from typing import Any, Optional

from iaglobal.observability.registry import (
    ServiceInstance,
    registry as default_registry,
)
from iaglobal.observability.load_balancer import PhospholipidLoadBalancer
from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.observability.search_bridge")

SEARCH_SERVICE_PREFIX = "search"


class PhospholipidSearchBridge:
    """Bridge entre SearchAgent e PhospholipidRegistry para LB de search."""

    def __init__(
        self,
        registry: Any = None,
        load_balancer: Any = None,
    ):
        self.registry = registry or default_registry
        if load_balancer is not None:
            self.load_balancer = load_balancer
        else:
            self.load_balancer = PhospholipidLoadBalancer(registry=self.registry)

    def register_search_service(
        self,
        name: str,
        endpoint: str,
        weight: float = 1.0,
        capacity: int = 10,
    ) -> ServiceInstance:
        """Registra um serviço de busca no PhospholipidRegistry.

        O nome deve começar com 'search-' para ser reconhecido.
        Exemplo:
          bridge.register_search_service("search-ddgs", "https://duckduckgo.com")
          bridge.register_search_service("search-bing", "https://api.bing.com")
        """
        full_name = (
            name
            if name.startswith(SEARCH_SERVICE_PREFIX)
            else f"{SEARCH_SERVICE_PREFIX}-{name}"
        )
        return self.registry.register(
            full_name, endpoint, weight=weight, capacity=capacity
        )

    def has_search_services(self) -> bool:
        """Verifica se há search services registrados e saudáveis."""
        self.registry.check_timeouts()
        services = self.registry.healthy_services()
        return any(s.name.startswith(SEARCH_SERVICE_PREFIX) for s in services)

    async def select_search(self) -> Optional[ServiceInstance]:
        """Seleciona o search service mais saudável."""
        return await self.load_balancer.select(service_type=SEARCH_SERVICE_PREFIX)

    def report_success(self, service_name: str, latency_ms: float = 0.0):
        """Reporta sucesso ao registry."""
        self.load_balancer.report_success(service_name)
        self.registry.report_health(service_name, latency_ms=latency_ms, error=False)
        logger.info(
            "[PHOSPHOLIPID_SEARCH] Sucesso: %s (latency=%.1fms)",
            service_name,
            latency_ms,
        )

    def report_failure(self, service_name: str, error: Exception):
        """Reporta falha com adaptive decay."""
        instance = self.registry.get(service_name)
        if instance:
            self.load_balancer._handle_failure(instance, error)
        else:
            logger.warning(
                "[PHOSPHOLIPID_SEARCH] Instância não encontrada: %s",
                service_name,
            )

    async def search_with_lb(
        self,
        query: str,
        max_results: int = 3,
    ) -> list[dict[str, str]]:
        """Executa busca usando o search service saudável, com fallback para ddgs.

        Se há search services registrados:
          - Seleciona o mais saudável
          - Executa busca via endpoint registrado
          - Monitora saúde
          - Fallback para próxima instância se falhar

        Se não há services registrados:
          - Usa ddgs local (default)
        """
        from iaglobal.tools.search_tools import SearchTools

        if not self.has_search_services():
            logger.info(
                "[PHOSPHOLIPID_SEARCH] Sem search services registrados → ddgs local"
            )
            try:
                return SearchTools.search_and_fetch_raw(query, max_results=max_results)
            except Exception as e:
                logger.warning("[PHOSPHOLIPID_SEARCH] ddgs local falhou: %s", e)
                return []

        start = time.time()

        instance = await self.select_search()
        if instance is None:
            logger.info(
                "[PHOSPHOLIPID_SEARCH] Nenhum search service saudável → ddgs local"
            )
            return SearchTools.search_and_fetch_raw(query, max_results=max_results)

        try:
            results = await self._execute_search(instance, query)
            latency_ms = (time.time() - start) * 1000
            self.report_success(instance.name, latency_ms)

            if results:
                return results
        except Exception as e:
            latency_ms = (time.time() - start) * 1000
            self.report_failure(instance.name, e)
            logger.warning(
                "[PHOSPHOLIPID_SEARCH] %s falhou, tentando fallback...",
                instance.name,
            )

            instance2 = await self.select_search()
            if instance2 and instance2.name != instance.name:
                try:
                    results = await self._execute_search(instance2, query)
                    latency_ms = (time.time() - start) * 1000
                    self.report_success(instance2.name, latency_ms)
                    if results:
                        return results
                except Exception as e2:
                    self.report_failure(instance2.name, e2)

        logger.info("[PHOSPHOLIPID_SEARCH] Fallback para ddgs local")
        try:
            return SearchTools.search_and_fetch_raw(query, max_results=max_results)
        except Exception as e:
            logger.warning("[PHOSPHOLIPID_SEARCH] ddgs local (fallback) falhou: %s", e)
            return []

    async def search_and_learn_with_lb(
        self,
        termo_busca: str,
        max_results: int = 3,
    ) -> bool:
        """Busca com LB + aprendizado integrado.

        Similar a SearchAgent.pesquisar_e_aprender() mas usando o
        PhospholipidRegistry para seleção de search service.

        Returns:
            True se conseguiu buscar e armazenar aprendizado
        """
        results = await self.search_with_lb(termo_busca, max_results=max_results)

        if not results:
            logger.warning(
                "[PHOSPHOLIPID_SEARCH] Nenhum resultado para '%s'",
                termo_busca,
            )
            return False

        from iaglobal.memory.memory_vector import store

        stored = 0
        for item in results:
            url = str(item.get("href", "")).strip()
            title = str(item.get("title", "")).strip() or "Sem título"
            snippet = str(item.get("body", "")).strip()

            if not url or len(snippet) < 15:
                continue

            conhecimento = (
                f"FONTE WEB CONSOLIDADA ({url})\n"
                f"ASSUNTO: {title}\n"
                f"CONTEÚDO EXTENSIONADO: {snippet}"
            )
            store(text=conhecimento, mtype="web_search")
            stored += 1

        logger.info(
            "[PHOSPHOLIPID_SEARCH] Aprendizado: %d resultados armazenados para '%s'",
            stored,
            termo_busca,
        )
        return stored > 0

    def auto_report_search(self, success: bool, query: str = ""):
        """Auto-report metrics ao registry após busca.

        Chamado do SearchAgent após pesquisar_e_aprender().
        Atualiza indicadores de saúde dos search services registrados.
        """
        if not self.has_search_services():
            return
        for svc in list(self.registry._services.values()):
            if svc.name.startswith(SEARCH_SERVICE_PREFIX):
                self.registry.report_health(svc.name, error=not success)
                if not success:
                    svc.consecutive_failures += 1
                    if svc.weight < 0.2:
                        svc.health = False

    async def _execute_search(
        self,
        instance: ServiceInstance,
        query: str,
        max_results: int = 3,
    ) -> list[dict[str, str]]:
        """Executa busca via endpoint do search service registrado."""
        import httpx

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                instance.endpoint,
                params={"q": query, "max_results": max_results},
                timeout=15.0,
            )
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, list):
                return data
            return data.get("results", data.get("items", []))


search_bridge = PhospholipidSearchBridge()
