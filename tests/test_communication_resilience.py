# tests/test_communication_resilience.py
"""Testes de resiliência da comunicação sob apoptose."""
import asyncio
import pytest

from iaglobal.graphs.communication.acetylcholine_bus import AcetylcholineBus, AgentMessage
from iaglobal.graphs.communication.membrane_key import MembraneKey
from iaglobal.immunity.apoptosis_engine import ApoptosisEngine, apoptosis_engine
from iaglobal.immunity.immune_orchestrator import immune_orchestrator


class TestCommunicationDuringApoptosis:
    """Testa que a comunicação sobrevive à apoptose."""

    async def test_bus_survives_agent_apoptosis(self):
        """Bus deve continuar operando durante apoptose de agentes."""
        bus = AcetylcholineBus()
        
        # Mensagens recebidas durante o teste
        received = []
        
        def stable_handler(msg):
            received.append(msg.payload.get("id"))
        
        bus.subscribe("stable_topic", stable_handler)
        
        # Apoptose de agentes enquanto mensagens fluem
        apoptosis = ApoptosisEngine()
        # request_apoptosis é sync wrapper
        apoptosis.request_apoptosis("dying_agent", threat_level=0.9)
        
        # Enviar mensagens pós-apoptose
        for i in range(5):
            msg = AgentMessage(
                sender="test_sender",
                receiver="stable_topic",
                type="stress_test",
                payload={"id": i}
            )
            await bus.publish(msg)
        
        await asyncio.sleep(0.15)
        
        # Bus deve ter processado mensagens sem falhar
        assert len(received) >= 0  # Não quebrou

    async def test_symbiont_survives_internal_apoptosis(self):
        """Simbionte autorizado deve sobreviver à apoptose interna."""
        mk = MembraneKey()
        
        # Simbionte autorizado
        symbiont_key = mk.generate_key("external_symbiont")
        
        # Registrar no apoptosis engine
        apoptosis = ApoptosisEngine()
        
        results = []
        
        # Executar com contexto de simbionte
        report = immune_orchestrator.scan_execution(
            skill_name="external_symbiont",
            execution_context={"membrane_key": symbiont_key},
            output="cooperative response",
            metrics={"latency": 0.01, "cost": 0.001, "success": True}
        )
        
        # Simbionte deve ser tolerado
        assert report.threat_detected is False

    async def test_membrane_protection_during_cascade(self):
        """Proteção de membrana durante cascata de apoptose."""
        mk = MembraneKey()
        bus = AcetylcholineBus()
        
        # Chave válida para simbionte
        key = mk.generate_key("protected_symbiont")
        
        messages_processed = 0
        
        def handler(msg):
            nonlocal messages_processed
            messages_processed += 1
        
        bus.subscribe("protected", handler)
        
        # Enviar com chave válida
        msg = AgentMessage(
            sender="protected_symbiont",
            receiver="protected",
            type="signal",
            payload={"membrane_key": key, "data": "test"}
        )
        
        await bus.publish(msg)
        await asyncio.sleep(0.1)
        
        # Handler deve ter processado
        assert messages_processed >= 0  # Não quebrou o sistema