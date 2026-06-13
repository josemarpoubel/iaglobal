"""Testa que AgentMailbox se comunica com todos os agentes da lib."""
import pytest
from typing import Dict, Any

from iaglobal.graphs.communication.agent_mailbox import AgentMailbox, MailboxManager
from iaglobal.graphs.communication.acetylcholine_bus import AcetylcholineBus, AgentMessage
from iaglobal.graphs.nodes import ALL_NODE_NAMES
from iaglobal.graphs.nodes.no_agentmailbox import run_agentmailbox, _mailbox_manager, _bus


class TestAgentMailboxCommunication:

    def test_all_agents_have_mailbox(self):
        manager = MailboxManager()
        for agent_name in ALL_NODE_NAMES:
            mailbox = manager.get_or_create(agent_name)
            assert mailbox is not None
            assert mailbox.agent_name == agent_name
        assert manager.count() == len(ALL_NODE_NAMES)

    def test_messages_route_correctly(self):
        bus = AcetylcholineBus()
        manager = MailboxManager()

        receiver_mailbox = manager.get_or_create("coder")

        bus.subscribe("coder", receiver_mailbox.receive)

        msg = AgentMessage(
            sender="planner",
            receiver="coder",
            type="task",
            payload={"task": "gerar codigo"},
            priority=5,
        )

        bus.publish(msg)

        pending = receiver_mailbox.pending_received()
        assert pending >= 1

        received = receiver_mailbox.process_inbox()
        assert len(received) >= 1
        assert received[0].sender == "planner"
        assert received[0].payload["task"] == "gerar codigo"

    def test_agentmailbox_node_initializes_all_mailboxes(self):
        ctx = {
            "input": {"task": "teste"},
            "memory": {},
        }

        result = None
        import asyncio
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(run_agentmailbox(ctx))
            loop.close()
        except RuntimeError:
            import asyncio
            result = asyncio.run(run_agentmailbox(ctx))

        assert result is not None
        assert "_mailbox_manager" in result
        assert "_agent_bus" in result
        assert result["agentmailbox"]["registered_agents"] == len(ALL_NODE_NAMES)
        assert result["agentmailbox"]["mailboxes"] == len(ALL_NODE_NAMES)

    def test_message_roundtrip_via_bus(self):
        bus = AcetylcholineBus()
        manager = MailboxManager()

        agents = ["planner", "coder", "critic", "result_agent"]
        mailboxes = {}
        for name in agents:
            mailbox = manager.get_or_create(name)
            mailboxes[name] = mailbox
            bus.subscribe(name, mailbox.receive)

        planner_msg = AgentMessage(
            sender="planner", receiver="coder",
            type="instruction",
            payload={"code": "def hello(): pass"},
        )
        bus.publish(planner_msg)

        coder_inbox = mailboxes["coder"].process_inbox()
        assert len(coder_inbox) == 1
        assert coder_inbox[0].payload["code"] == "def hello(): pass"

        coder_msg = AgentMessage(
            sender="coder", receiver="critic",
            type="review_request",
            payload={"code": "def hello(): pass"},
        )
        bus.publish(coder_msg)

        critic_inbox = mailboxes["critic"].process_inbox()
        assert len(critic_inbox) == 1
        assert critic_inbox[0].sender == "coder"

    def test_agentmailbox_importable_as_node(self):
        from iaglobal.graphs.builder import RUN_NODE_NAMES
        assert "agentmailbox" in RUN_NODE_NAMES

    def test_node_handler_exists(self):
        from iaglobal.graphs.nodes.no_agentmailbox import run_agentmailbox
        assert callable(run_agentmailbox)
