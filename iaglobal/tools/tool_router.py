# iaglobal/tools/tool_router.py

class ToolRouter:
    """
    🌐 Camada de expansão cognitiva
    Permite que modelos locais usem internet de forma controlada.
    """

    def __init__(self, tools: dict):
        self.tools = tools

    def resolve(self, model_type: str, task: str) -> str:
        """
        Decide se precisa de ferramentas externas.
        """
        if model_type == "local":
            return self._enhance_with_tools(task)

        # modelos online podem usar tools seletivamente
        if "?" in task or len(task) < 80:
            return self._enhance_with_tools(task)

        return task

    def _enhance_with_tools(self, task: str) -> str:
        if "search" in self.tools:
            try:
                result = self.tools["search"](task)
                return f"{task}\n\n[WEB CONTEXT]\n{result}"
            except Exception:
                return task
        return task
