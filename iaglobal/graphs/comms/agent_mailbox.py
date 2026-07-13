# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
AgentMailbox — Caixa postal individual com motor de dispatch reativo (Projeto Synapse).

Fase 3.0: Transforma comunicação de "passiva" para "ativa" (dispatch-based),
permitindo que agentes processem tarefas automaticamente conforme mensagens chegam.

Fase 3.1: Governança Synapse — Veracidade de nós com assinatura de linhagem.

Leis de Holliwell aplicadas:
- Lei da Não-Resistência: Não força execução se fila vazia — flui para próximo agente
- Axioma da Cooperação: Agente finalizado posta resultado na inbox do sucessor
- Lei da Obediência: Executor só é registrado se agente tem compliance aprovado
- Lei da Veracidade: Mensagens sem assinatura de linhagem são patógenos
"""

import os
import asyncio
import hashlib
import time
import json
from pathlib import Path
from typing import Dict, Any, Callable, List, Optional, Awaitable

from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal")

# Genesis Hash oficial para assinatura de linhagem
GENESIS_HASH_OFFICIAL = "cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136"


class AgentMailbox:
    """Caixa postal individual com motor de dispatch e governança de linhagem."""

    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self.inbox: List[Dict[str, Any]] = []
        self.outbox: List[Dict[str, Any]] = []
        self.executor: Optional[Callable[..., Awaitable[Any]]] = None
        self._compliance_approved = False
        self._messages_processed = 0
        self._last_heartbeat = 0.0
        self._lineage_id = hashlib.sha3_512(
            f"{agent_name}:{time.time()}".encode()
        ).hexdigest()[:16]
        self._monitor = None

    def clear(self):
        """Limpa inbox, outbox e contadores."""
        self.inbox.clear()
        self.outbox.clear()
        self._messages_processed = 0

    @staticmethod
    def sign_message(message: Dict[str, Any], sender_lineage: str) -> Dict[str, Any]:
        """
        Fase 3.1: Assina mensagem com lineage_signature.

        Protocolo de Confiança:
        - origin_id: quem enviou
        - lineage_signature: SHA3-512(sender_lineage + GENESIS_HASH + timestamp)
        - compliance_hash: hash do compliance.json no momento do envio
        """
        timestamp = time.time()
        signature_input = f"{sender_lineage}:{GENESIS_HASH_OFFICIAL}:{timestamp}"
        lineage_signature = hashlib.sha3_512(signature_input.encode()).hexdigest()

        message["metadata"] = {
            "origin_id": sender_lineage,
            "lineage_signature": lineage_signature,
            "compliance_hash": hashlib.sha3_512(
                str(sorted(message.get("payload", {}))).encode()
            ).hexdigest()[:16],
            "timestamp": timestamp,
            "genesis_marker": GENESIS_HASH_OFFICIAL[:16],
        }
        return message

    @staticmethod
    def verify_lineage(
        message: Dict[str, Any], expected_sender: str
    ) -> tuple[bool, str]:
        """
        Fase 3.1: Verifica assinatura de linhagem da mensagem.

        Retorna: (valid, reason)
        - valid=True se assinatura válida e genesis correto
        - valid=False + motivo se patógeno/injetado
        """
        metadata = message.get("metadata")
        if not metadata:
            return False, "metadata ausente — possivel injecao de patogene"

        genesis_marker = metadata.get("genesis_marker")
        if genesis_marker != GENESIS_HASH_OFFICIAL[:16]:
            return False, "genesis_marker invalido — origem desconhecida"

        timestamp = metadata.get("timestamp", 0)
        if time.time() - timestamp > 60:
            return False, "mensagem expirada — replay attack possivel"

        origin_id = metadata.get("origin_id")
        lineage_signature = metadata.get("lineage_signature")

        signature_input = f"{origin_id}:{GENESIS_HASH_OFFICIAL}:{timestamp}"
        expected_signature = hashlib.sha3_512(signature_input.encode()).hexdigest()

        if lineage_signature != expected_signature:
            return False, "lineage_signature invalida — agente corrompido ou malicioso"
        return True, "linhagem verificada"

    def receive(self, message: Dict[str, Any], verify: bool = True):
        """
        Recebe mensagem e adiciona à inbox.

        Fase 3.1: Verifica lineage_signature antes de aceitar.
        Se verify=False, aceita sem validação (apenas para bootstrap).
        """
        if verify:
            valid, reason = self.verify_lineage(message, self._lineage_id)
            if not valid:
                logger.error(
                    "[SECURITY] 🚨 %s: Tentativa de injecao de tarefa nao assinada detectada | agent=%s | reason=%s",
                    self.agent_name,
                    message.get("sender", "unknown"),
                    reason,
                )
                self._log_security_violation(message, reason)
                if self._monitor is not None:
                    self._monitor.report_violation(self.agent_name, reason)
                return  # Rejeita mensagem patógena

        self.inbox.append(message)
        logger.info(
            "[%s] Mensagem recebida: type=%s | inbox_size=%d | lineage=valid",
            self.agent_name,
            message.get("type", "unknown"),
            len(self.inbox),
        )

    def _log_security_violation(self, message: Dict[str, Any], reason: str):
        """Registra tentativa de injeção no ancestry_tree.jsonl."""
        try:
            import json

            record = {
                "type": "SECURITY_VIOLATION",
                "node_id": "mailbox_security",
                "agent_target": self.agent_name,
                "reason": reason,
                "message_type": message.get("type", "unknown"),
                "sender": message.get("sender", "unknown"),
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "lineage_marker": GENESIS_HASH_OFFICIAL[:16],
            }

            ancestry_path = None
            try:
                from iaglobal._paths import DATA_DIR

                ancestry_path = DATA_DIR / "ancestry_tree.jsonl"
            except Exception:
                import tempfile

                ancestry_path = (
                    Path(tempfile.gettempdir()) / "iaglobal_ancestry_tree.jsonl"
                )

            ancestry_path.parent.mkdir(parents=True, exist_ok=True)
            with open(str(ancestry_path), "a") as f:
                f.write(json.dumps(record) + "\n")

            logger.warning(
                "[SECURITY] Violação registrada em ancestry_tree: %s", reason
            )
        except Exception as e:
            logger.debug("[SECURITY] Falha ao registrar violação: %s", e)

    def send(self, message: Dict[str, Any]):
        """Envia mensagem para outbox."""
        signed_message = self.sign_message(message, self._lineage_id)
        self.outbox.append(signed_message)
        logger.debug(
            "[%s] Mensagem enviada: type=%s | outbox_size=%d",
            self.agent_name,
            message.get("type", "unknown"),
            len(self.outbox),
        )

    def set_executor(
        self, func: Callable[..., Awaitable[Any]], compliance_approved: bool = False
    ):
        """Define o executor (função async) que processará mensagens."""
        if not compliance_approved:
            logger.warning(
                "[COMPLIANCE] %s nao aprovado — executor ignorado (Lei da Obediencia)",
                self.agent_name,
            )
            raise ValueError(
                f"Agent {self.agent_name} não tem compliance. Registre via compliance.json."
            )
        self.executor = func
        self._compliance_approved = True
        logger.info("[%s] Executor registrado com compliance=True", self.agent_name)

    async def process_next(self, ctx: Optional[Dict[str, Any]] = None) -> Optional[Any]:
        """
        Processa próxima mensagem da inbox.
        """
        if not self.inbox or not self.executor:
            return None

        task = self.inbox.pop(0)
        logger.info(
            "[%s] Processando: type=%s | payload_len=%d | ctx_keys=%s",
            self.agent_name,
            task.get("type"),
            len(str(task.get("payload", {}))),
            list(ctx.keys()) if ctx else [],
        )

        try:
            result = await self.executor(task, ctx)
            if result:
                self._messages_processed += 1
                self.send(
                    {
                        "type": "result",
                        "payload": result,
                        "processed_by": self.agent_name,
                        "source_message": task,
                    }
                )
            return result
        except Exception as e:
            logger.error("[%s] Erro ao processar: %s", self.agent_name, e)
            return None


class JobTicket:
    """Contrato de trabalho qualificado (Fase 3.1)."""

    def __init__(
        self,
        intent: str,
        payload: str,
        compliance_level: str = "strict",
        priority: str = "medium",
        required_agents: Optional[List[str]] = None,
    ):
        self.ticket_id = (
            str(time.time()) + "-" + str(hashlib.sha256(os.urandom(16)).hexdigest()[:8])
        )
        self.intent = intent
        self.payload = payload
        self.compliance_level = compliance_level
        self.priority = priority
        self.required_agents = required_agents or [
            "PlannerAgent",
            "CoderAgent",
            "CriticAgent",
        ]
        self.origin_hash = GENESIS_HASH_OFFICIAL[:16]
        self.created_at = time.time()

    def to_dict(self):
        return {
            "ticket_id": self.ticket_id,
            "intent": self.intent,
            "payload": self.payload,
            "compliance_level": self.compliance_level,
            "priority": self.priority,
            "required_agents": self.required_agents,
            "origin_hash": self.origin_hash,
        }

    def validate(self):
        if not self.intent:
            return False, "intent vazio"
        if self.compliance_level not in ["strict", "normal", "relaxed"]:
            return False, f"compliance_level invalido: {self.compliance_level}"
        if self.priority not in ["high", "medium", "low"]:
            return False, f"priority invalida: {self.priority}"
        return True, "valid"


class SynapseMonitor:
    """Observador de saúde e gargalos do pipeline."""

    def __init__(self, manager):
        self.manager = manager
        self._violations_detected = 0

    def scan_health(self):
        stats = self.manager.get_all_stats()
        bottlenecks = {
            agent: {"inbox": st["inbox_size"], "compliance": st["compliance_approved"]}
            for agent, st in stats.items()
        }
        return {
            "agents_count": len(stats),
            "total_inbox": sum(st["inbox_size"] for st in stats.values()),
            "agents": bottlenecks,
            "violations_detected": self._violations_detected,
        }

    def report_violation(self, agent_name: str, reason: str):
        """Reporta violação para registro no monitor."""
        self._violations_detected += 1
        logger.warning(
            "[SYNAPSE] Violacao #%d: agent=%s | reason=%s",
            self._violations_detected,
            agent_name,
            reason,
        )

    def export_status(self, filepath=None):
        """Exporta relatório de saúde JSON."""
        status = self.scan_health()
        import tempfile

        path = Path(filepath or tempfile.gettempdir() / "iaglobal_synapse_status.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(status, f, indent=2)
        return path


class MailboxManager:
    """Gerenciador central de mailboxes com governança."""

    def __init__(self):
        self._mailboxes: Dict[str, AgentMailbox] = {}
        self._compliance_registry: Dict[str, bool] = {}
        self.monitor = SynapseMonitor(self)

    def create_job_ticket(
        self,
        intent,
        payload,
        compliance_level="strict",
        priority="medium",
        required_agents=None,
    ):
        """Fase 3.1: Cria JobTicket qualificado para dispatch."""
        try:
            pass
        except:
            pass
        ticket = JobTicket(intent, payload, compliance_level, priority, required_agents)
        valid, reason = ticket.validate()
        if not valid:
            logger.error("[JOBTICKET] Invalido: %s", reason)
            raise ValueError(f"JobTicket invalido: {reason}")
        logger.info("[JOBTICKET] Criado: %s | intent=%s", ticket.ticket_id[:6], intent)
        return ticket

    def dispatch_job_ticket(self, ticket: JobTicket, first_agent: str):
        """Dispatch seguro para primeiro agente da cadeia."""
        message = {
            "type": "job_ticket",
            "receiver": first_agent,
            "sender": "orchestrator",
            "payload": ticket.to_dict(),
        }
        self.route_message(message)
        logger.info(
            "[SYNAPSE] JobTicket %s dispatchado para %s → cadeia=%r",
            ticket.ticket_id[:8],
            first_agent,
            ticket.required_agents,
        )

    def is_compliance_approved(self, agent_name: str) -> bool:
        """Agente tem compliance aprovado?"""
        return self._compliance_registry.get(agent_name, False)

    def register_compliance(self, agent_name: str, approved: bool):
        """Registra compliance do agente."""
        self._compliance_registry[agent_name] = approved
        logger.info("[COMPLIANCE] %s: approved=%s", agent_name, approved)

    def bind_executor(self, agent_name: str, func: Callable):
        """Registra executor aprovado para agente."""
        approved = self.is_compliance_approved(agent_name)
        mailbox = self.get_or_create(agent_name)
        mailbox._monitor = self.monitor
        mailbox.set_executor(func, approved)

    def get_or_create(self, agent_name: str) -> AgentMailbox:
        """Obtém ou cria caixa postal."""
        if agent_name not in self._mailboxes:
            self._mailboxes[agent_name] = AgentMailbox(agent_name)
            self._mailboxes[agent_name]._monitor = self.monitor
            logger.info("[MAILBOX] %s criado", agent_name)
        return self._mailboxes[agent_name]

    def route_message(self, message: Dict[str, Any]):
        """Roteia mensagem internamente."""
        sender = message.get("sender", "orchestrator")
        if sender not in ["orchestrator", "system", "SynapseMonitor"]:
            # Membrana: somente senders conhecidos + compliance aprovado
            if not self.is_compliance_approved(sender):
                logger.error(
                    "[SECURITY] 🚨 %s bloqueado: compliance nao aprovado", sender
                )
                return

        try:
            sender_mailbox = self.get_or_create(sender)
            signed_message = AgentMailbox.sign_message(
                message, sender_mailbox._lineage_id
            )

            receiver = message.get("receiver")
            if receiver:
                try:
                    mailbox = self.get_or_create(receiver)
                    mailbox.receive(signed_message)
                except Exception as e:
                    logger.warn("[MAILBOX] Falha ao entregar: %s", e)
        except Exception as e:
            logger.warn("[SYNAPSE] Falha de routing: %s", e)

    def run_heartbeat_loop(self):
        """Monitor de inbox ativado para RAF use."""

        async def _heartbeat():
            while True:
                await asyncio.sleep(0.5)
                for agent_name, mailbox in list(self._mailboxes.items()):
                    if mailbox.inbox or mailbox._messages_processed < 5:
                        await mailbox.process_next()

        return _heartbeat()

    def clear_all(self):
        """Limpa todas as mailboxes."""
        for mb in self._mailboxes.values():
            mb.clear()
        self._mailboxes.clear()

    def count(self) -> int:
        """Contagem de mailboxes."""
        return len(self._mailboxes)

    def get_all_stats(self):
        """Estatísticas de todas as mailboxes."""
        return {
            name: {
                "inbox_size": len(mb.inbox),
                "outbox_size": len(mb.outbox),
                "messages_processed": mb._messages_processed,
                "compliance_approved": mb._compliance_approved,
            }
            for name, mb in self._mailboxes.items()
        }


# Singleton ready-to-use
mailbox_manager = MailboxManager()
