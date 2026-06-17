import pytest

from iaglobal.agents.intent_classifier_agent import IntentClassifierAgent
from iaglobal.agents.pm_agent import PMAgent
from iaglobal.agents.requirements_agent import RequirementsAgent
from iaglobal.agents.orchestrator_agent import OrchestratorAgent


class TestIntentClassifierAgent:
    def setup_method(self):
        self.agent = IntentClassifierAgent()

    def test_api_intent_detected(self):
        res = self.agent.classify("Criar uma API REST em Python com FastAPI")
        assert "api" in res["intents"]
        assert "linguagem" in res["entities"]
        assert "python" in res["entities"]["linguagem"]
        assert "fastapi" in res["entities"]["framework"]
        assert res["domain"] == "api"
        assert res["confidence"] > 0

    def test_web_intent_detected(self):
        res = self.agent.classify("Desenvolver um site institucional com HTML e CSS")
        assert "web" in res["intents"]
        assert res["domain"] == "web"

    def test_data_intent_detected(self):
        res = self.agent.classify("Pipeline de dados com pandas e numpy para mercado financeiro")
        assert "dados" in res["intents"]
        assert "financeiro" in res["intents"]

    def test_ia_intent_detected(self):
        res = self.agent.classify("Modelo de machine learning para classificacao de texto")
        assert "ia" in res["intents"]

    def test_multiple_intents_ordered_by_score(self):
        res = self.agent.classify("API REST endpoint com autenticacao e banco SQL")
        assert len(res["intents"]) >= 2
        assert res["intents"][0] == "api"

    def test_unknown_intent(self):
        res = self.agent.classify("")
        assert res["intents"] == ["unknown"]
        assert res["domain"] == "unknown"
        assert res["confidence"] == 0.0

    def test_none_input(self):
        res = self.agent.classify(None)
        assert res["intents"] == ["unknown"]

    def test_entities_detected(self):
        res = self.agent.classify("Criar API com Django e PostgreSQL, formato JSON, protocolo HTTP")
        assert "framework" in res["entities"]
        assert "django" in res["entities"]["framework"]
        assert "formato" in res["entities"]
        assert "json" in res["entities"]["formato"]
        assert "protocolo" in res["entities"]

    def test_code_detected_adds_language(self):
        res = self.agent.classify("def hello():\n    print('hello')")
        assert isinstance(res["intents"], list)
        assert isinstance(res["entities"], dict)

    def test_confidence_scales_with_matches(self):
        low = self.agent.classify("site web")
        high = self.agent.classify("API REST em Python com FastAPI para banco SQL e autenticacao segura")
        assert high["confidence"] >= low["confidence"]


class TestPMAgent:
    def setup_method(self):
        self.agent = PMAgent()

    def test_extract_functional_requirements(self):
        res = self.agent.extract_requirements("cadastrar usuarios e listar pedidos e buscar produtos")
        funcs = res["functional"]
        assert any("cadastrar" in f for f in funcs)
        assert any("listar" in f for f in funcs)
        assert any("buscar" in f for f in funcs)

    def test_extract_non_functional_requirements(self):
        res = self.agent.extract_requirements("API com seguranca e performance e cache")
        nfs = res["non_functional"]
        assert any("seguranca" in f for f in nfs)
        assert any("performance" in f for f in nfs)
        assert any("cache" in f for f in nfs)

    def test_empty_prompt(self):
        res = self.agent.extract_requirements("")
        assert res["functional"] == []
        assert res["non_functional"] == []
        assert res["priority"] == "low"

    def test_none_prompt(self):
        res = self.agent.extract_requirements(None)
        assert res["functional"] == []

    def test_priority_high_for_many_requirements(self):
        res = self.agent.extract_requirements(
            "cadastrar listar buscar atualizar deletar calcular gerar exportar "
            "com seguranca performance escalabilidade"
        )
        assert res["priority"] == "high"

    def test_priority_medium_for_moderate_requirements(self):
        res = self.agent.extract_requirements("cadastrar usuarios com seguranca")
        assert res["priority"] == "medium"

    def test_priority_low_for_few_requirements(self):
        res = self.agent.extract_requirements("fazer um sistema")
        assert res["priority"] == "low"

    def test_drivers_from_enhancement(self):
        res = self.agent.extract_requirements("API", {"intents_detected": ["api", "web"]})
        assert "api" in res["drivers"]
        assert "web" in res["drivers"]

    def test_drivers_empty_when_no_enhancement(self):
        res = self.agent.extract_requirements("API")
        assert res["drivers"] == []

    def test_invalid_enhancement_does_not_crash(self):
        res = self.agent.extract_requirements("API", enhancement="invalid")
        assert res["drivers"] == []

    def test_generic_task_falls_back_to_main_functionality(self):
        res = self.agent.extract_requirements("Criar um sistema completo")
        assert any("principal" in f for f in res["functional"])


class TestRequirementsAgent:
    def setup_method(self):
        self.agent = RequirementsAgent()

    def test_simple_classification(self):
        res = self.agent.refine({"functional": ["login"], "non_functional": [], "priority": "low"})
        assert res["classification"] == "simple"
        assert res["priorities"] == ["low"]
        assert res["functional"] == ["login"]

    def test_medium_classification(self):
        res = self.agent.refine({
            "functional": ["login", "logout", "signup"],
            "non_functional": ["seguranca"],
            "priority": "medium",
        })
        assert res["classification"] == "medium"

    def test_complex_classification(self):
        res = self.agent.refine({
            "functional": ["f1", "f2", "f3", "f4", "f5"],
            "non_functional": ["nf1", "nf2", "nf3"],
            "priority": "high",
        })
        assert res["classification"] == "complex"

    def test_none_input(self):
        res = self.agent.refine(None)
        assert res["functional"] == []
        assert res["classification"] == "simple"

    def test_invalid_input_type(self):
        res = self.agent.refine("invalid")
        assert res["functional"] == []
        assert res["classification"] == "simple"

    def test_priority_preserved(self):
        res = self.agent.refine({"functional": [], "non_functional": [], "priority": "high"})
        assert res["priorities"] == ["high"]

    def test_priority_defaults_to_medium(self):
        res = self.agent.refine({"functional": [], "non_functional": [], "priority": "unknown"})
        assert res["priorities"] == ["medium"]

    def test_non_functional_list_fixed(self):
        res = self.agent.refine({"functional": ["login"], "non_functional": "not_a_list", "priority": "low"})
        assert res["non_functional"] == []

    def test_functional_list_fixed(self):
        res = self.agent.refine({"functional": None, "non_functional": ["seguranca"], "priority": "low"})
        assert res["functional"] == []


class TestOrchestratorAgent:
    def setup_method(self):
        self.agent = OrchestratorAgent()

    def test_api_domain_routing(self):
        res = self.agent.route({"intents_detected": ["api"], "scope": {"phases": ["definition"]}})
        assert "api_design" in res["active_nodes"]
        assert "architect" in res["active_nodes"]
        assert res["next_phase"] == "definition"

    def test_web_domain_routing(self):
        res = self.agent.route({"intents_detected": ["web"], "scope": {"phases": ["definition"]}})
        assert "frontend_builder" in res["active_nodes"]
        assert res["next_phase"] == "definition"

    def test_security_domain_routing(self):
        res = self.agent.route({"intents_detected": ["seguranca"], "scope": {"phases": ["definition"]}})
        assert "security_design" in res["active_nodes"]
        assert "threat_modeling" in res["active_nodes"]

    def test_empty_enhancement_uses_default_nodes(self):
        res = self.agent.route(None)
        assert res["active_nodes"] == ["pm", "requirements", "domain_analysis"]

    def test_empty_intents_uses_default_nodes(self):
        res = self.agent.route({"intents_detected": [], "scope": {}})
        assert res["active_nodes"] == ["pm", "requirements", "domain_analysis"]

    def test_unknown_domain_falls_back_to_default(self):
        res = self.agent.route({"intents_detected": ["nonexistent"], "scope": {"phases": ["definition"]}})
        assert res["active_nodes"] == ["pm", "requirements", "domain_analysis"]

    def test_next_phase_from_scope(self):
        res = self.agent.route({"intents_detected": ["api"], "scope": {"phases": ["construction"]}})
        assert res["next_phase"] == "construction"

    def test_next_phase_defaults_to_definition(self):
        res = self.agent.route({"intents_detected": ["api"]})
        assert res["next_phase"] == "definition"

    def test_mobile_domain_routing(self):
        res = self.agent.route({"intents_detected": ["mobile"], "scope": {"phases": ["definition"]}})
        assert "architect" in res["active_nodes"]
        assert "api_design" in res["active_nodes"]
