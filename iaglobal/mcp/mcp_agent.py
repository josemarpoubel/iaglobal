# iaglobal/mcp/mcp_agent.py
"""
Meta-Circular Protocol Agent para auto-reparo e auditoria evolutiva.
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Any

from iaglobal.metabolism.metabolic_autocorrect import MetabolicAutocorrect
from iaglobal.metabolism.metabolic_invariants import MetabolicInvariants
from iaglobal.subconscious.fugue_compartment import FugueCompartment
from iaglobal.subconscious.delta_sleep import DeltaSleepSync
from iaglobal.obsidian.omnimind import omni_mind
from iaglobal.utils.ansi_colors import ANSI


@dataclass
class MCPAudit:
    timestamp: float
    agent_id: str
    findings: Dict[str, Dict]
    corrections: List[Dict]
    score: float  # 0-1 (eficiência da correção)


class MCPAgent:
    """Agente MCP para auto-reparo do sistema."""

    def __init__(self):
        self.logger = logging.getLogger("iaglobal.mcp")
        self.invariants = MetabolicInvariants()
        self.autocorrect = MetabolicAutocorrect()
        self.fugue = FugueCompartment()
        self.delta_sleep = DeltaSleepSync()
        self.sondas = []
        self._initialize_sondas()

    def _initialize_sondas(self):
        """Configura sondas metabólicas."""
        # Sonda: FugueCompartment Latency
        self._add_sonda(
            target="fugue_compartment",
            check=lambda: self.fugue.get_average_latency() > 1.0,
            correct=self._correct_fugue_latency,
            description="Latência > 1s no FugueCompartment"
        )

        # Sonda: Vault Usage
        self._add_sonda(
            target="vault",
            check=lambda: self.delta_sleep.get_vault_usage() > 0.9,
            correct=self._correct_vault_usage,
            description="Vault > 90% de ocupação"
        )

        # Sonda: Toxinas Estagnadas
        self._add_sonda(
            target="toxins",
            check=self._check_toxins_stagnant,
            correct=self._correct_toxins_stagnant,
            description="Toxinas não removidas por >24h"
        )

    def _add_sonda(self, target: str, check, correct, description: str):
        self.sondas.append({
            "target": target,
            "check": check,
            "correct": correct,
            "description": description,
            "last_checked": 0
        })

    def get_tools(self) -> List[Dict[str, Any]]:
        """Retorna lista de ferramentas disponíveis para inspeção metabólica."""
        return [
            {
                "name": "metabolic_audit",
                "description": "Executa auditoria metabólica e retorna score de saúde (0-1).",
                "parameters": {}
            },
            {
                "name": "metabolic_fix",
                "description": "Aciona correção automática de invariantes violadas.",
                "parameters": {
                    "target": {"type": "string", "enum": ["vault", "latency", "toxins", "ivm"]}
                }
            },
            {
                "name": "get_ivm",
                "description": "Retorna o Índice de Viabilidade Metabólica atual.",
                "parameters": {}
            }
        ]

    async def initialize(self) -> Dict[str, Any]:
        """Handshake inicial com o cliente MCP."""
        return {
            "serverInfo": {
                "name": "iaglobal.mcp",
                "version": "0.1.0",
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "audit": True,
                    "correction": True,
                    "metrics": True
                }
            }
        }

    async def run_audit(self) -> MCPAudit:
        """Executa auditoria completa e retorna relatório."""
        findings = {}
        corrections = []

        # Executar sondas
        for sonda in self.sondas:
            try:
                if sonda["check"]():
                    finding = {
                        "status": "VIOLADA",
                        "alert": sonda["description"],
                        "last_checked": time.time()
                    }
                    findings[sonda["target"]] = finding

                    # Aplicar correção
                    correction = await sonda["correct"]()
                    if correction:
                        corrections.append({
                            "target": sonda["target"],
                            "action": correction["acao"],
                            "details": correction.get("detalhes", "")
                        })
            except Exception as e:
                self.logger.error(f"Falha na sonda {sonda['target']}: {str(e)}")
                findings[sonda["target"]] = {
                    "status": "ERRO",
                    "alert": f"Exceção: {str(e)}"
                }

        # Auditar invariantes metabólicas
        try:
            invariants = await self.invariants.check_all()
            for inv, status in invariants.items():
                if status["status"] != "OK":
                    findings[inv] = status
        except Exception as e:
            self.logger.error(f"Falha ao verificar invariantes: {e}")

        # Calcular score
        score = self._calculate_score(findings, corrections)

        # Registrar no OmniMind
        try:
            await omni_mind.registrar_violação_lei(
                agente_id="mcp_agent",
                lei="Lei da Ordem",
                mensagem=f"Auditoria MCP: score={score:.2f}, correções={len(corrections)}"
            )
        except Exception as e:
            self.logger.warning(f"Falha ao registrar no OmniMind: {e}")

        return MCPAudit(
            timestamp=time.time(),
            agent_id="mcp_agent",
            findings=findings,
            corrections=corrections,
            score=score
        )

    async def run_continuous(self, interval: int = 300):
        """Executa auditorias contínuas em background."""
        while True:
            start_time = time.time()
            try:
                audit = await self.run_audit()
                self._print_audit_report(audit)

                # Aplicar autocorreções se necessário
                if audit.findings:
                    await self.autocorrect.verificar_e_corrigir()

                    # Re-auditar após correções
                    audit = await self.run_audit()
                    if audit.score < 0.7:
                        self.logger.warning(f"Score MCP baixo ({audit.score:.2f}). Intervenção manual recomendada.")

            except Exception as e:
                self.logger.exception(f"Falha na auditoria MCP: {str(e)}")

            # Aguardar próximo ciclo
            elapsed = time.time() - start_time
            await asyncio.sleep(max(0, interval - elapsed))

    def _calculate_score(self, findings: Dict, corrections: List) -> float:
        """Calcula score de eficiência da auditoria (0-1)."""
        violations = sum(1 for f in findings.values() if f["status"] != "OK")
        fixed = len(corrections)

        # Score: % de violações corrigidas (com penalidade para erros)
        if violations == 0:
            return 1.0

        score = min(1.0, max(0.0, fixed / violations))

        # Penalizar por erros de sonda
        errors = sum(1 for f in findings.values() if f.get("status") == "ERRO")
        score = max(0.0, score - (errors * 0.2))

        return round(score, 2)

    def _print_audit_report(self, audit: MCPAudit):
        """Exibe relatório de auditoria formatado."""
        print(f"\n{ANSI.BOLD}{ANSI.MAGENTA}🔄 MCP AUDITORIA (Score: {audit.score:.2f}){ANSI.RESET}")
        print("=" * 60)

        if not audit.findings:
            print(f"{ANSI.GREEN}✅ Nenhuma violação detectada.{ANSI.RESET}")
            return

        for target, finding in audit.findings.items():
            status = finding["status"]
            color = ANSI.RED if status == "VIOLADA" else ANSI.YELLOW if status == "AVISO" else ANSI.WHITE
            print(f"{color}🔍 {target.upper()}: {status}{ANSI.RESET}")
            if "alert" in finding:
                print(f"   🚨 {finding['alert']}")

        if audit.corrections:
            print(f"\n{ANSI.BOLD}🔧 CORREÇÕES APLICADAS:{ANSI.RESET}")
            for correction in audit.corrections:
                print(f"   - {correction['target']}: {correction['action']}")
                if correction.get("details"):
                    print(f"     {correction['details']}")

        print("=" * 60)

    # --- Correções Específicas ---
    async def _correct_fugue_latency(self) -> Optional[Dict]:
        """Corrige latência alta no FugueCompartment."""
        compactado = await self.delta_sleep.compactar_memoria("fugue")
        return {
            "acao": "compactar_memoria_fugue",
            "detalhes": f"Tarefas compactadas: {compactado.get('total_tarefas', 0)}"
        }

    async def _correct_vault_usage(self) -> Optional[Dict]:
        """Corrige uso excessivo do vault."""
        removidas = await self.delta_sleep.limpar_toxinas()
        compactado = await self.delta_sleep.compactar_memoria("emergencial")
        return {
            "acao": "limpeza_emergencial_vault",
            "detalhes": f"Toxinas removidas: {removidas['toxinas_removidas']}, tarefas compactadas: {compactado.get('total_tarefas', 0)}"
        }

    def _check_toxins_stagnant(self) -> bool:
        """Verifica se toxinas estão estagnadas (>24h sem limpeza)."""
        last_cleanup = self.delta_sleep.get_last_cleanup_time()
        return (time.time() - last_cleanup) > 86400  # 24h

    async def _correct_toxins_stagnant(self) -> Optional[Dict]:
        """Força limpeza de toxinas estagnadas."""
        removidas = await self.delta_sleep.limpar_toxinas(forcado=True)
        return {
            "acao": "limpeza_forcada_toxinas",
            "detalhes": f"Toxinas removidas: {removidas['toxinas_removidas']}"
        }

    def _get_ivm(self) -> float:
        """Retorna o Índice de Viabilidade Metabólica atual (método auxiliar)."""
        # Simulação: IVM baseado em invariantes
        try:
            # Este método é chamado de forma síncrona no mcp_server.py
            # Retorna valor padrão quando não há loop async
            return 0.85
        except Exception:
            return 0.5