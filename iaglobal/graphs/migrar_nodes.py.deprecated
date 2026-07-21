import os
import re

folder_path = "./nodes"  # Pasta com os 94 arquivos fatiados
nodes_py_path = "./nodes.py"  # Arquivo que vamos sobrescrever

class_regex = re.compile(r"^class\s+([A-Za-z0-9_]+)\b")

imports = []
mixin_classes = []

# Varre a pasta de nós para coletar os Mixins
files = sorted(os.listdir(folder_path))
for filename in files:
    if (
        filename.endswith(".py")
        and filename != "__init__.py"
        and not filename.startswith("_disk")
    ):
        module_name = filename[:-3]
        file_path = os.path.join(folder_path, filename)

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                for line in f:
                    match = class_regex.match(line)
                    if match:
                        class_name = match.group(1)
                        imports.append(
                            f"from iaglobal.graphs.nodes.{module_name} import {class_name}"
                        )
                        mixin_classes.append(class_name)
                        break
        except Exception as e:
            print(f"Erro ao ler {filename}: {e}")

# Monta o conteúdo preservando seu cabeçalho original e adicionando os Mixins
content = [
    '"""',
    "Pipeline Director — Node Director do IAGlobal V3+ (Modularizado).",
    '"""',
    "import logging",
    "import functools",
    "from typing import Dict, Any, Callable, Optional",
    "",
    "# ─── IMPORTS DOS NÓS MODULARIZADOS ─────────────────────────────────",
]

content.extend(imports)
content.append("\nlogger = logging.getLogger(__name__)\n")

# Se existirem Mixins, coloca na herança múltipla
if mixin_classes:
    parents = ",\n    ".join(mixin_classes)
    content.append(f"class Nodes(\n    {parents}\n):")
else:
    content.append("class Nodes:")

content.append('''    """
    Pipeline Director — Node Director do IAGlobal V3+.

    Responsável por:
    - Orquestrar execução centralizada dos 55 nós determinísticos
    - Registry global de handlers compatível with execution_graph/builder
    - Garantir singleton pra injeção global e meta-aprendizado
    - Auto-registro via decorator e métodos run_*
    """

    # registry global de nós (nome -> método run_xxx)
    _registry: Dict[str, Callable] = {}

    # ==========================================================
    # INIT
    # ==========================================================

    _instance = None

    def __new__(cls, logger_instance=None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._context_cache: Dict[str, Any] = {}
            cls._instance.logger = logger_instance or logger
            cls._instance._auto_register_nodes()
            cls._instance.logger.info("🧠 Nodes Pipeline Director Singleton initialized via Mixins")
        return cls._instance

    def __init__(self, logger_instance=None):
        """
        Inicializa o director de nós. Chamado apenas na primeira instanciação pelo singleton.
        """
        self.logger = logger_instance or logger
        self._context_cache = {}

    # ==========================================================
    # CLASSMETHODS
    # ==========================================================

    @classmethod
    def _apply_node_registration(cls, name: str, func: Callable) -> Callable:
        cls._registry[name] = func
        return func

    @classmethod
    def register_node(cls, name: str):
        """
        Decorator para registrar nós no registry.
        """
        return functools.partial(cls._apply_node_registration, name)

    @classmethod
    def get_node(cls, name: str) -> Optional[Callable]:
        """
        Recupera um nó registrado.
        """
        return cls._registry.get(name)

    @classmethod
    def list_nodes(cls) -> Dict[str, Callable]:
        """
        Lista todos os nós registrados.
        """
        return dict(cls._registry)

    @classmethod
    def has_node(cls, name: str) -> bool:
        """
        Verifica existência de nó.
        """
        return name in cls._registry

    # ==========================================================
    # INTERNAL HELPERS
    # ==========================================================

    def _auto_register_nodes(self):
        """
        Auto-registra métodos run_* herdados dos Mixins como nós executáveis.
        """
        registered = self.list_nodes()
        for attr_name in dir(self):
            if attr_name.startswith("run_"):
                method = getattr(self, attr_name)
                if callable(method):
                    node_name = attr_name[len("run_"):]
                    if self.get_node(node_name) is None:
                        self.register_node(node_name)(method)
                        registered = self.list_nodes()
                        self.logger.debug("📌 Node registrado dinamicamente: %s (total=%d)", node_name, len(registered))

    # ==========================================================
    # CONTEXT HELPERS
    # ==========================================================

    def _get_task(self, ctx: dict) -> str:
        return (ctx.get("input", {}) or {}).get("task", "")

    def _get_wd(self, ctx: dict):
        return ctx.get("working_directory")

    def _log(self, ctx: dict, msg: str):
        self.logger.info("📦 %s", msg)
        ctx.setdefault("logs", []).append(msg)

    async def _call_llm(self, ctx: dict, prompt: str):
        llm = ctx.get("llm")
        if not llm:
            return None
        return await llm(prompt)

    def _resolve_model(self, ctx: dict) -> str:
        return ""
''')

with open(nodes_py_path, "w", encoding="utf-8") as f:
    f.write("\n".join(content) + "\n")

print(f"✅ nodes.py restaurado! Singleton ativo com {len(mixin_classes)} nós herdados.")
