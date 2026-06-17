from iaglobal.utils.logger import logger

_DOMAIN_NODE_MAP = {
    "web": ["pm", "requirements", "domain_analysis", "architect", "system_design", "api_design", "frontend_builder"],
    "api": ["pm", "requirements", "domain_analysis", "architect", "system_design", "api_design"],
    "ia": ["pm", "requirements", "domain_analysis", "architect", "system_design", "api_design", "database_design"],
    "dados": ["pm", "requirements", "domain_analysis", "architect", "system_design", "database_design"],
    "banco": ["pm", "requirements", "domain_analysis", "database_design"],
    "automacao": ["pm", "requirements", "domain_analysis", "architect"],
    "mobile": ["pm", "requirements", "domain_analysis", "architect", "api_design"],
    "seguranca": ["pm", "requirements", "domain_analysis", "security_design", "threat_modeling"],
    "cli": ["pm", "requirements", "domain_analysis"],
    "financeiro": ["pm", "requirements", "domain_analysis", "architect", "database_design"],
    "devops": ["pm", "requirements", "domain_analysis"],
    "falha": ["pm", "requirements", "domain_analysis", "failure_analysis"],
}


class OrchestratorAgent:
    def route(self, enhancement: dict = None, requirements: dict = None) -> dict:
        if not enhancement or not isinstance(enhancement, dict):
            return {"next_phase": "definition", "active_nodes": self._default_nodes()}

        scope = enhancement.get("scope") or {}
        intents = enhancement.get("intents_detected", [])

        if not isinstance(intents, list):
            intents = []

        phases = scope.get("phases", ["definition"])
        next_phase = phases[0] if phases else "definition"

        if intents:
            domain = intents[0]
            active = _DOMAIN_NODE_MAP.get(domain, self._default_nodes())
        else:
            active = self._default_nodes()

        logger.info(
            "[ORCHESTRATOR] next_phase=%s domain=%s active_nodes=%d",
            next_phase, intents[0] if intents else "unknown", len(active),
        )

        return {
            "next_phase": next_phase,
            "active_nodes": active,
        }

    def _default_nodes(self) -> list:
        return ["pm", "requirements", "domain_analysis"]
