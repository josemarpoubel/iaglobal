import os
import sys
import unittest

raiz_projeto = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
src_path = os.path.join(raiz_projeto, "src")
if raiz_projeto not in sys.path:
    sys.path.insert(0, raiz_projeto)
if src_path not in sys.path:
    sys.path.insert(0, src_path)


class TestEventBus(unittest.TestCase):

    def setUp(self):
        from iaglobal.models.event_bus import EventBus, Event, EventType
        self.EventBus = EventBus
        self.Event = Event
        self.EventType = EventType
        self.bus = EventBus()
        self.bus.reset()

    def test_singleton(self):
        outro = self.EventBus()
        self.assertIs(self.bus, outro)

    def test_subscribe_and_publish(self):
        received = []
        def handler(event):
            received.append(event)
        self.bus.subscribe("test_event", handler)
        self.bus.publish("test_event", {"key": "value"}, source="test")
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].type, "test_event")
        self.assertEqual(received[0].data["key"], "value")
        self.assertEqual(received[0].source, "test")

    def test_multiple_handlers(self):
        received1 = []
        received2 = []
        def h1(e): received1.append(e)
        def h2(e): received2.append(e)
        self.bus.subscribe("multi", h1)
        self.bus.subscribe("multi", h2)
        self.bus.publish("multi", {}, "test")
        self.assertEqual(len(received1), 1)
        self.assertEqual(len(received2), 1)

    def test_unsubscribe(self):
        received = []
        def handler(e): received.append(e)
        self.bus.subscribe("unsub", handler)
        self.bus.publish("unsub", {}, "test")
        self.assertEqual(len(received), 1)
        self.bus.unsubscribe("unsub", handler)
        self.bus.publish("unsub", {}, "test")
        self.assertEqual(len(received), 1)

    def test_publish_without_subscribers_does_not_error(self):
        self.bus.publish("no_subscribers", {"data": 1}, "test")

    def test_event_default_fields(self):
        event = self.Event()
        self.assertTrue(event.id)
        self.assertEqual(event.type, "")
        self.assertEqual(event.data, {})
        self.assertTrue(event.timestamp)

    def test_event_str(self):
        event = self.Event(type="test_type", data={"x": 1}, source="src")
        s = str(event)
        self.assertIn("test_type", s)
        self.assertIn("src", s)

    def test_handler_exception_does_not_bubble(self):
        def bad_handler(e):
            raise ValueError("handler error")
        self.bus.subscribe("bad", bad_handler)
        self.bus.publish("bad", {}, "test")

    def test_history_records_all_events(self):
        self.bus.publish("ev1", {"a": 1}, "src1")
        self.bus.publish("ev2", {"b": 2}, "src2")
        hist = self.bus.history()
        self.assertEqual(len(hist), 2)

    def test_history_filter_by_type(self):
        self.bus.publish("type_a", {"x": 1}, "src")
        self.bus.publish("type_b", {"y": 2}, "src")
        self.bus.publish("type_a", {"z": 3}, "src")
        hist_a = self.bus.history(event_type="type_a")
        self.assertEqual(len(hist_a), 2)
        for e in hist_a:
            self.assertEqual(e.type, "type_a")

    def test_history_limit(self):
        for i in range(10):
            self.bus.publish("lim", {"i": i}, "src")
        hist = self.bus.history(limit=3)
        self.assertLessEqual(len(hist), 3)

    def test_reset_clears_state(self):
        self.bus.publish("ev", {}, "src")
        self.bus.reset()
        self.assertEqual(len(self.bus.history()), 0)
        self.bus.publish("after_reset", {}, "src")
        self.assertEqual(len(self.bus.history()), 1)

    def test_all_event_types_are_strings(self):
        for et in self.EventType.ALL:
            self.assertIsInstance(et, str)

    def test_tracing_handler_does_not_crash(self):
        self.bus.publish(self.EventType.TASK_CREATED, {"task": "teste"}, "test")
        self.bus.publish(self.EventType.SOLUTION_GENERATED, {"agent": "fast"}, "test")
        self.bus.publish(self.EventType.EXECUTION_FAILED, {"error": "fail"}, "test")
        self.bus.publish(self.EventType.REFLECTION_COMPLETED, {"status": "ok"}, "test")
        self.bus.publish(self.EventType.MEMORY_SAVED, {"memory_type": "vec"}, "test")

    def test_publish_returns_event(self):
        event = self.bus.publish("ret", {"d": 1}, "src")
        self.assertIsInstance(event, self.Event)
        self.assertEqual(event.type, "ret")
        self.assertEqual(event.data["d"], 1)


if __name__ == "__main__":
    unittest.main()
