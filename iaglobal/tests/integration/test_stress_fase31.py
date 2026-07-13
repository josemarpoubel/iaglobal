# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
Stress Test — Fase 3.1: Integração completa Planner → Coder → Critic

Força o enxame a usar:
  - JobTicket (intenção)
  - LineageGate (DNA)
  - AgentMailbox (comunicação)
  - Compliance (segurança)

Objetivo: Identificar gargalos antes da Fase 3.2
"""

import asyncio
import json
import time
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime, timezone

import pytest

from iaglobal.graphs.comms.agent_mailbox import (
    MailboxManager,
    GENESIS_HASH_OFFICIAL,
)
from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.stress_test_fase31")

ANCESTRY_TREE = Path(
    "/home/kitohamachi/projeto-iaglobal/iaglobal/memory/data/ancestry_tree.jsonl"
)


@pytest.fixture
def mailbox_manager():
    """MailboxManager limpo para cada teste."""
    manager = MailboxManager()
    yield manager
    manager.clear_all()


@pytest.fixture
def registered_manager(mailbox_manager):
    """Registra Planner, Coder, Critic com executors 100% async."""
    for agent_name in ["PlannerAgent", "CoderAgent", "CriticAgent"]:
        mailbox_manager.register_compliance(agent_name, approved=True)

        async def _executor(ctx: dict, name: str = agent_name) -> dict:
            await asyncio.sleep(0)  # yield — echt async
            return {
                "output": f"[{name}] Processado",
                "execution_metrics": {
                    "model": "stub_async",
                    "success": True,
                    "latency": 0.5,
                    "cost": 0.0,
                },
            }

        mailbox_manager.bind_executor(agent_name, _executor)

    return mailbox_manager


def _read_ancestry_tail(n: int = 20) -> List[Dict]:
    if not ANCESTRY_TREE.exists():
        return []
    try:
        lines = ANCESTRY_TREE.read_text(encoding="utf-8").strip().splitlines()
        return [json.loads(l) for l in lines[-n:]]
    except Exception as e:
        logger.warning("[STRESS] Falha ao ler ancestry_tree: %s", e)
        return []


def _analyze_violations(entries: List[Dict]) -> Dict[str, Any]:
    security = [e for e in entries if e.get("type") == "SECURITY_VIOLATION"]
    lineage = [e for e in entries if e.get("type") == "Cognitive_Escalation"]
    psc = [e for e in entries if e.get("type") == "psc_blocked"]
    return {
        "security_violations_count": len(security),
        "lineage_proof_count": len(lineage),
        "psc_blocked_count": len(psc),
        "security_violations": security,
        "last_10_entries": entries[-10:],
    }


@pytest.mark.asyncio
async def test_stress_fase31_complete_flow(registered_manager):
    """
    Executa o prompt de stress test completo.
    """
    prompt_de_estresse = {
        "intent": "generate_component",
        "task": "Criar um componente 'HealthDashboard.jsx' que exibe o status de 3 agentes (Planner, Coder, Critic) usando Framer Motion para transições.",
        "compliance_level": "strict",
        "priority": "high",
        "requirements": {
            "framework": "react",
            "styling": "tailwind",
            "animations": "framer-motion",
        },
    }

    report: Dict[str, Any] = {
        "test_name": "stress_fase31",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "prompt": prompt_de_estresse,
        "scenarios": {},
        "metrics": {},
        "issues": [],
        "status": "UNKNOWN",
    }

    # Limpa ancestry_tree antes do teste
    if ANCESTRY_TREE.exists():
        ANCESTRY_TREE.write_text("", encoding="utf-8")

    # ----------------------------------------------------------------
    # Passo 1: Criar JobTicket legítimo
    # ----------------------------------------------------------------
    logger.info("[STRESS] === PASSO 1: CRIAR JOBTICKET ===")
    t0 = time.time()

    ticket = registered_manager.create_job_ticket(
        intent=prompt_de_estresse["intent"],
        payload=json.dumps(prompt_de_estresse["task"]),
        compliance_level=prompt_de_estresse["compliance_level"],
        priority=prompt_de_estresse["priority"],
        required_agents=["PlannerAgent", "CoderAgent", "CriticAgent"],
    )

    t1 = time.time()
    report["scenarios"]["job_ticket_creation"] = {
        "status": "PASS",
        "ticket_id": ticket.ticket_id,
        "latency_ms": round((t1 - t0) * 1000, 2),
    }
    logger.info(
        "[STRESS] JobTicket criado: %s | latency=%.2fms",
        ticket.ticket_id,
        (t1 - t0) * 1000,
    )

    # ----------------------------------------------------------------
    # Passo 2: Dispatch para PlannerAgent
    # ----------------------------------------------------------------
    logger.info("[STRESS] === PASSO 2: DISPATCH PARA PLANNER ===")
    t2 = time.time()

    registered_manager.dispatch_job_ticket(ticket, "PlannerAgent")

    t3 = time.time()
    planner_mb = registered_manager.get_or_create("PlannerAgent")
    report["scenarios"]["dispatch_planner"] = {
        "status": "PASS",
        "planner_inbox_size": len(planner_mb.inbox),
        "latency_ms": round((t3 - t2) * 1000, 2),
    }
    logger.info(
        "[STRESS] Dispatch → Planner | inbox=%d | latency=%.2fms",
        len(planner_mb.inbox),
        (t3 - t2) * 1000,
    )

    if planner_mb.inbox:
        msg = planner_mb.inbox[0]
        assert "metadata" in msg, "JobTicket sem metadata!"
        assert "lineage_signature" in msg["metadata"], (
            "JobTicket sem lineage_signature!"
        )
        genesis_marker = msg["metadata"].get("genesis_marker", "")
        assert genesis_marker == GENESIS_HASH_OFFICIAL[:16], (
            f"Genesis marker inválido: {genesis_marker}"
        )

    # ----------------------------------------------------------------
    # Passo 3: Processamento sequencial (async real)
    # ----------------------------------------------------------------
    logger.info("[STRESS] === PASSO 3: PROCESSAMENTO SEQUENCIAL ===")

    processing_order = ["PlannerAgent", "CoderAgent", "CriticAgent"]
    agent_latencies: Dict[str, float] = {}

    for agent_name in processing_order:
        mb = registered_manager.get_or_create(agent_name)
        t_start = time.time()
        try:
            result = await mb.process_next(ctx={"orchestrator": None})
            t_end = time.time()
            latency = round((t_end - t_start) * 1000, 2)
            agent_latencies[agent_name] = latency
            if result:
                logger.info("[STRESS] %s processou | latency=%dms", agent_name, latency)
            else:
                logger.warning("[STRESS] %s retornou None", agent_name)
        except Exception as e:
            t_end = time.time()
            agent_latencies[agent_name] = round((t_end - t_start) * 1000, 2)
            logger.error("[STRESS] %s erro: %s", agent_name, e)
            report["issues"].append(
                {
                    "agent": agent_name,
                    "issue": "processing_error",
                    "error": str(e),
                    "latency_ms": agent_latencies[agent_name],
                }
            )

    report["scenarios"]["agent_processing"] = {
        "status": "PASS" if not report["issues"] else "PARTIAL",
        "latencies_ms": agent_latencies,
        "order": processing_order,
    }

    # ----------------------------------------------------------------
    # Passo 4: Análise do ancestry_tree
    # ----------------------------------------------------------------
    logger.info("[STRESS] === PASSO 4: ANÁLISE ANCESTRY_TREE ===")
    time.sleep(0.3)

    entries = _read_ancestry_tail(50)
    analysis = _analyze_violations(entries)

    report["scenarios"]["ancestry_analysis"] = {
        "status": "PASS",
        "total_entries_analyzed": len(entries),
        **analysis,
    }
    logger.info(
        "[STRESS] Ancestry: %d entradas | security=%d | lineage=%d | psc=%d",
        len(entries),
        analysis["security_violations_count"],
        analysis["lineage_proof_count"],
        analysis["psc_blocked_count"],
    )

    # ----------------------------------------------------------------
    # Passo 5: SynapseMonitor
    # ----------------------------------------------------------------
    logger.info("[STRESS] === PASSO 5: SYNAPSE MONITOR ===")

    monitor = registered_manager.monitor
    health = monitor.scan_health()

    report["scenarios"]["synapse_health"] = {
        "status": "PASS",
        "agents_count": health.get("agents_count", 0),
        "total_inbox": health.get("total_inbox", 0),
        "violations_detected": health.get("violations_detected", 0),
    }
    logger.info(
        "[STRESS] SynapseMonitor: agents=%d | inbox=%d | violations=%d",
        health.get("agents_count", 0),
        health.get("total_inbox", 0),
        health.get("violations_detected", 0),
    )

    # ----------------------------------------------------------------
    # Passo 6: Detecção de gargalos
    # ----------------------------------------------------------------
    logger.info("[STRESS] === PASSO 6: DETECÇÃO DE GARGALOS ===")

    bottlenecks: List[Dict[str, Any]] = []

    # 6.1 Handover latency (Planner → Coder)
    if "PlannerAgent" in agent_latencies and "CoderAgent" in agent_latencies:
        handover = agent_latencies["CoderAgent"] - agent_latencies["PlannerAgent"]
        if handover > 1000:
            bottlenecks.append(
                {
                    "type": "handover_latency",
                    "detail": f"Coder iniciou {handover:.0f}ms após Planner",
                    "threshold_ms": 1000,
                    "suggestion": "Aumentar frequência do heartbeat ou priorizar thread do AgentMailbox",
                }
            )

    # 6.2 Churn de segurança (várias validações de DNA para mesmo nó)
    if analysis["security_violations_count"] > 5:
        bottlenecks.append(
            {
                "type": "lineage_gate_churn",
                "detail": f"{analysis['security_violations_count']} validações de DNA detectadas",
                "threshold": 5,
                "suggestion": "Implementar cache LRU de tokens validados no LineageGate",
            }
        )

    # 6.3 Fragmentação de JobTicket (Coder pedindo mais info)
    coder_errors = [i for i in report["issues"] if i.get("agent") == "CoderAgent"]
    if len(coder_errors) > 2:
        bottlenecks.append(
            {
                "type": "job_ticket_fragmentation",
                "detail": f"CoderAgent com {len(coder_errors)} erros — possível fragmentação",
                "threshold": 2,
                "suggestion": "Ajustar prompt_improver.py para injetar mais contexto no JobTicket inicial",
            }
        )

    # 6.4 Engarrafamento no Critic
    if "CriticAgent" in agent_latencies and agent_latencies["CriticAgent"] > 5000:
        bottlenecks.append(
            {
                "type": "critic_bottleneck",
                "detail": f"CriticAgent demorou {agent_latencies['CriticAgent']:.0f}ms",
                "threshold_ms": 5000,
                "suggestion": "Simplificar whitelist de compliance ou adicionar pre-check cache",
            }
        )

    report["bottlenecks"] = bottlenecks
    report["metrics"] = {
        "total_latency_ms": round(sum(agent_latencies.values()), 2),
        "avg_latency_ms": round(sum(agent_latencies.values()) / len(agent_latencies), 2)
        if agent_latencies
        else 0.0,
        "agents_processed": len(agent_latencies),
        "violations_detected": health.get("violations_detected", 0),
    }

    critical_pass = (
        report["scenarios"]["job_ticket_creation"]["status"] == "PASS"
        and report["scenarios"]["dispatch_planner"]["status"] == "PASS"
        and len(bottlenecks) == 0
    )
    report["status"] = "PASS" if critical_pass else "NEEDS_TUNING"

    logger.info(
        "[STRESS] Resultado final: %s | bottlenecks=%d | total_latency=%.2fms",
        report["status"],
        len(bottlenecks),
        report["metrics"]["total_latency_ms"],
    )
    return report


if __name__ == "__main__":
    import sys

    async def _stub(ctx: dict, name: str) -> dict:
        await asyncio.sleep(0)
        return {
            "output": f"[{name}] Processado",
            "execution_metrics": {
                "model": "stub_async",
                "success": True,
                "latency": 0.5,
                "cost": 0.0,
            },
        }

    async def run():
        manager = MailboxManager()
        for name in ["PlannerAgent", "CoderAgent", "CriticAgent"]:
            manager.register_compliance(name, approved=True)
            manager.bind_executor(name, _stub)

        report = await test_stress_fase31_complete_flow(manager)

        report_path = Path("/tmp/stress_fase31_report.json")
        report_path.write_text(
            json.dumps(report, indent=2, ensure_ascii=False, default=str)
        )
        print(f"\n{'=' * 60}")
        print(f"RELATÓRIO DE STRESS TEST — Fase 3.1")
        print(f"Status: {report['status']}")
        print(f"Bottlenecks: {len(report.get('bottlenecks', []))}")
        print(f"Latência total: {report['metrics']['total_latency_ms']:.2f}ms")
        print(f"Relatório: {report_path}")
        print(f"{'=' * 60}")

        if report.get("bottlenecks"):
            print("\n⚠️  GARGALOS DETECTADOS:")
            for b in report["bottlenecks"]:
                print(f"  • {b['type']}: {b['detail']}")
                print(f"    Sugestão: {b['suggestion']}")

        sys.exit(0 if report["status"] == "PASS" else 1)

    asyncio.run(run())
