# iaglobal/server/mcp_server.py
"""
MCP Server — Meta-Circular Protocol Server para auto-reparo metabólico.

Endpoints:
- GET /health   → Status do servidor
- GET /audit    → Auditoria metabólica em tempo real
- POST /fix     → Acionar correção imediata
- GET /metrics  → Métricas Prometheus
"""

import asyncio
import logging
import json
from typing import Dict, Any

from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from iaglobal.graphs.communication.acetylcholine_bus import AcetylcholineBus
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import PlainTextResponse

from iaglobal.metabolism.metabolic_invariants import MetabolicInvariants
from iaglobal.metabolism.metabolic_autocorrect import MetabolicAutocorrect
from iaglobal.mcp.mcp_agent import MCPAgent
from iaglobal.obsidian.omnimind import omni_mind
from iaglobal.utils.ansi_colors import ANSI
from iaglobal.core.env_loader import load_env
import json
from typing import Dict, Any, List


class MCPServer:
    """Servidor MCP para monitoramento e reparo metabólico."""

    def __init__(self):
        load_env()  # Garantir que variáveis de ambiente estejam carregadas
        self.logger = logging.getLogger("iaglobal.mcp.server")
        self.invariants = MetabolicInvariants()
        self.autocorrect = MetabolicAutocorrect()
        self.mcp_agent = MCPAgent()
        # Configuração de segurança (básica)
        self.security = HTTPBasic()
        self._validate_credentials = self._make_auth_checker()

        # AcetylcholineBus (opcional - não falhar se não disponível)
        self.bus = None
        try:
            self.bus = AcetylcholineBus()
        except Exception as e:
            self.logger.warning(f"AcetylcholineBus não disponível (modo standalone): {e}")

        # FastAPI app
        self.app = FastAPI(title="IAGlobal MCP Server", version="0.1.0")
        self._setup_routes()
        self._setup_middleware()

    def _setup_routes(self):
        """Configura rotas do FastAPI."""
        
        # Rotas públicas
        self.app.get("/health", response_model=Dict[str, str])(self.health_check)
        self.app.get("/metrics")(self.get_metrics)
        
        # JSON-RPC endpoint (compatibilidade com testes)
        self.app.post("/jsonrpc", response_model=Dict[str, Any])(self.json_rpc_handler)
        
        # Rotas protegidas
        self.app.get(
            "/audit", 
            dependencies=[Depends(self._validate_credentials)],
            response_model=Dict[str, Any]
        )(self.run_audit)
        
        self.app.post(
            "/fix",
            dependencies=[Depends(self._validate_credentials)]
        )(self.trigger_autocorrect)

    async def json_rpc_handler(self, request: Request) -> Dict[str, Any]:
        """Handler para protocolo JSON-RPC."""
        try:
            payload = await request.json()
            method = payload.get("method")
            params = payload.get("params", {})
            rpc_id = payload.get("id")
            
            # Mapear métodos RPC para métodos internos
            if method == "initialize":
                result = await self.mcp_agent.initialize()
            elif method == "tools/list":
                result = {"tools": self.mcp_agent.get_tools()}
            else:
                raise HTTPException(status_code=400, detail=f"Method not found: {method}")
            
            return {
                "jsonrpc": "2.0",
                "id": rpc_id,
                "result": result
            }
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": payload.get("id") if payload else None,
                "error": {
                    "code": -32603,
                    "message": str(e)
                }
            }

    def _setup_middleware(self):
        """Configura middlewares."""
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["GET", "POST"],
            allow_headers=["*"],
        )
        
        # Rate limiting simplificado
        @self.app.middleware("http")
        async def rate_limit_middleware(request: Request, call_next):
            return await call_next(request)

    def _make_auth_checker(self):
        """Retorna função de validação de credenciais."""
        from os import getenv
        
        valid_user = getenv("MCP_USER")
        valid_pass = getenv("MCP_PASSWORD")
        
        if not valid_user or not valid_pass:
            self.logger.warning("MCP_USER/MCP_PASSWORD não configurados; endpoints protegidos indisponíveis.")
        
        async def check_credentials(credentials: HTTPBasicCredentials = Depends(self.security)):
            if credentials.username != valid_user or credentials.password != valid_pass:
                self.logger.warning(f"Falha de autenticação: {credentials.username}")
                raise HTTPException(status_code=401, detail="Unauthorized")
            return credentials
        
        return check_credentials

    # --- Endpoints ---
    async def health_check(self) -> Dict[str, str]:
        """Endpoint de health check."""
        return {
            "status": "✅ OK",
            "service": "mcp_server",
            "metabolic_health": (await self.invariants.check_all())["vault"]["status"]
        }

    async def run_audit(self) -> Dict[str, Any]:
        """Endpoint para auditoria metabólica em tempo real."""
        try:
            audit = await self.mcp_agent.run_audit()
            
            # Registrar no OmniMind
            await omni_mind.registrar_violação_lei(
                agente_id="mcp_server",
                lei="Lei da Ordem",
                mensagem=f"Auditoria via endpoint /audit - Score: {audit.score:.2f}"
            )
            
            return {
                "score": audit.score,
                "findings": audit.findings,
                "corrections": audit.corrections,
                "timestamp": audit.timestamp
            }
        except Exception as e:
            self.logger.exception("Falha na auditoria")
            raise HTTPException(status_code=500, detail=str(e))

    async def trigger_autocorrect(self) -> Dict[str, Any]:
        """Endpoint para acionar correção automática."""
        try:
            result = await self.autocorrect.verificar_e_corrigir()
            
            # Registrar no OmniMind
            await omni_mind.registrar_violação_lei(
                agente_id="mcp_server",
                lei="Lei da Ordem",
                mensagem=f"Correção via endpoint /fix - Correções: {len(result['correcoes'])}"
            )
            
            return {
                "status": "✅ Correção aplicada",
                "correcoes": result["correcoes"],
                "invariantes": result["invariantes"]
            }
        except Exception as e:
            self.logger.exception("Falha na autocorreção")
            raise HTTPException(status_code=500, detail=str(e))

    async def get_metrics(self) -> PlainTextResponse:
        """Endpoint de métricas Prometheus."""
        metrics = []
        metrics.append("# HELP iaglobal_mcp_audit_score Score da última auditoria (0-1)")
        metrics.append("# TYPE iaglobal_mcp_audit_score gauge")
        
        # Obter último audit score
        try:
            audit = await self.mcp_agent.run_audit()
            metrics.append(f"iaglobal_mcp_audit_score {audit.score}")
        except:
            metrics.append("iaglobal_mcp_audit_score 0")
        
        # Métricas de invariantes
        invariants = await self.invariants.check_all()
        for inv_name, status in invariants.items():
            safe_name = inv_name.replace(" ", "_").lower()
            metrics.append(f"# HELP iaglobal_invariant_{safe_name}_status Status do invariante (0=VIOLADA, 1=OK)")
            metrics.append(f"# TYPE iaglobal_invariant_{safe_name}_status gauge")
            value = 1 if status["status"] == "OK" else 0
            metrics.append(f"iaglobal_invariant_{safe_name}_status {value}")
        
        return PlainTextResponse("\n".join(metrics))

    # --- Integração com AcetylcholineBus ---
    def _setup_bus_integration(self):
        """Configura ouvintes e publicadores no AcetylcholineBus."""
        try:
            # Publicar métricas a cada 30s
            asyncio.create_task(self._publish_metrics_loop())
            
            # Escutar comandos de correção
            self.bus.subscribe("mcp/autocorrect", self._handle_autocorrect_command)
            
            # Escutar violações de invariantes
            self.bus.subscribe("invariants/violation", self._handle_invariant_violation)
            
            self.logger.info("✅ MCP Server integrado ao AcetylcholineBus")
        except Exception as e:
            self.logger.error(f"❌ Falha ao integrar MCP Server ao AcetylcholineBus: {e}")

    async def _publish_metrics_loop(self):
        """Publica métricas metabólicas no barramento a cada 30s."""
        import time
        while True:
            try:
                invariants = await self.invariants.check_all()
                ivm = self.mcp_agent._get_ivm()
                
                metrics = {
                    "invariants": invariants,
                    "ivm": ivm,
                    "timestamp": time.time()
                }
                
                await self.bus.publish("mcp/metrics", metrics)
                self.logger.debug(f"📊 Métricas publicadas: IVM={ivm:.2f}")
                
            except Exception as e:
                self.logger.error(f"❌ Falha ao publicar métricas: {e}")
            
            await asyncio.sleep(30)

    async def _handle_autocorrect_command(self, payload: Dict[str, Any]):
        """Lida com comandos de correção automática."""
        try:
            self.logger.info(f"⚡ Comando de correção recebido: {payload.get('target')}")
            result = await self.autocorrect.verificar_e_corrigir()
            
            response = {
                "status": "success",
                "corrections": len(result["correcoes"]),
                "details": result["correcoes"]
            }
            
            # Publicar resultado
            await self.bus.publish(f"mcp/autocorrect/response/{payload['command_id']}", response)
            
        except Exception as e:
            await self.bus.publish(f"mcp/autocorrect/response/{payload['command_id']}", {
                "status": "error",
                "error": str(e)
            })

    async def _handle_invariant_violation(self, payload: Dict[str, Any]):
        """Lida com violações de invariantes reportadas no sistema."""
        self.logger.warning(f"🚨 Violação detectada em {payload['invariant']}: {payload['alert']}")
        
        # Registrar no OmniMind
        await omni_mind.registrar_violação_lei(
            agente_id="mcp_server",
            lei="Lei da Ordem",
            mensagem=f"Violação em {payload['invariant']}: {payload['alert']}"
        )
        
        # Acionar correção automática se for crítica
        if payload["status"] == "VIOLADA":
            await self.autocorrect.verificar_e_corrigir()

    async def _start_continuous_audit(self):
        """Inicia auditoria contínua via MCPAgent."""
        while True:
            try:
                self.logger.info("⏳ Executando auditoria MCP contínua...")
                audit = await self.mcp_agent.run_audit()
                
                # Publicar resultado no barramento
                await self.bus.publish("mcp/audit", {
                    "score": audit.score,
                    "findings": audit.findings,
                    "timestamp": audit.timestamp
                })
                
                self.logger.info(f"✅ Auditoria concluída (Score: {audit.score:.2f})")
                
                # Enviar violções para OmniMind
                for target, finding in audit.findings.items():
                    if finding["status"] != "OK":
                        await omni_mind.registrar_violação_lei(
                            agente_id="mcp_agent",
                            lei="Lei da Ordem",
                            mensagem=f"Violação em {target}: {finding.get('alert', 'Sem alerta')}"
                        )
                
            except Exception as e:
                self.logger.error(f"❌ Falha na auditoria contínua: {e}")
            
            # Aguardar próximo ciclo (5 minutos)
            await asyncio.sleep(300)

    def start_blocking(self, host: str = "127.0.0.1", port: int = 8000):
        """Inicia o servidor MCP de forma bloqueante."""
        import uvicorn
        
        # Iniciar auditoria contínua (apenas se integrado ao barramento)
        if hasattr(self, 'bus'):
            asyncio.create_task(self._start_continuous_audit())
        
        self.logger.info(f"🔮 MCP Server iniciado em http://{host}:{port}")
        uvicorn.run(
            self.app,
            host=host,
            port=port,
            log_level="info",
            access_log=True
        )


# Singleton global
mcp_server = MCPServer()


def get_app() -> FastAPI:
    """Retorna a app FastAPI para uso em ASGI."""
    load_env()  # Garantir que variáveis de ambiente estejam carregadas
    global mcp_server
    return mcp_server.app