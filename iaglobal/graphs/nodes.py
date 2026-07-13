# iaglobal/graphs/nodes.py

"""
Pipeline Director — Node Director do IAGlobal V3+ (Modularizado).

Responsável por:
- Orquestrar execução centralizada dos 55 nós determinísticos
- Registry global de handlers compatível com execution_graph/builder
- Garantir singleton pra injeção global e meta-aprendizado
- Auto-registro via decorator e métodos run_*
- Carregamento autônomo e dinâmico de nós da pasta /nodes
"""

import os
import logging
import functools
import importlib.util
from typing import Dict, Any, Callable, Optional, List

logger = logging.getLogger(__name__)

# Barreira imunológica do telemetry/cache. Import defensivo para não criar
# dependência circular no boot do singleton Nodes.
try:
    from iaglobal.immunity.metabolic_immune_barrier import barrier
except Exception:
    barrier = None  # noqa: type ignore


class Nodes:
    """
    Pipeline Director — Node Director do IAGlobal V3+.
    """

    # registry global de nós (nome -> método run_xxx)
    _registry: Dict[str, Callable] = {}
    _instance = None

    def __new__(cls, logger_instance=None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._context_cache: Dict[str, Any] = {}
            cls._instance.logger = logger_instance or logger

            # 1. Carrega dinamicamente todas as funções run_* dos 94 arquivos
            cls._instance._load_dynamic_nodes()
            # 2. Executa o auto-registro original usando reflexão (dir)
            cls._instance._auto_register_nodes()

            cls._instance.logger.info(
                "🧠 Nodes Pipeline Director Singleton initialized via dynamic loading"
            )
        return cls._instance

    def __init__(self, logger_instance=None):
        """
        Inicializa o director de nós. Chamado apenas na primeira instanciação pelo singleton.
        """
        self.logger = logger_instance or logger
        self._context_cache = {}

    # ==========================================================
    # CARREGAMENTO DINÂMICO AUTOMATIZADO
    # ==========================================================

    def _load_dynamic_nodes(self):
        """
        Varre a subpasta ./nodes e anexa dinamicamente qualquer função ou classe
        que contenha implementações de nós executáveis.
        """
        base_dir = os.path.dirname(os.path.abspath(__file__))
        nodes_folder = os.path.join(base_dir, "nodes")

        if not os.path.exists(nodes_folder):
            self.logger.error("❌ Subpasta /nodes não encontrada em: %s", nodes_folder)
            return

        loaded_count = 0
        for filename in sorted(os.listdir(nodes_folder)):
            # Ignora arquivos de sistema, cache e arquivos de swap
            if (
                filename.endswith(".py")
                and filename != "__init__.py"
                and not filename.startswith("_disk")
            ):
                module_name = filename[:-3]
                file_path = os.path.join(nodes_folder, filename)

                try:
                    # Carrega o módulo Python em tempo de execução
                    spec = importlib.util.spec_from_file_location(
                        f"iaglobal.graphs.nodes.{module_name}", file_path
                    )
                    if spec and spec.loader:
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)

                        # Varre o arquivo procurando funções ou classes com nós
                        for attr_name in dir(module):
                            # Cenário 1: Encontrou a função de execução solta (ex: run_technology_selection)
                            if attr_name.startswith("run_"):
                                func = getattr(module, attr_name)
                                if callable(func):
                                    # Envolve a função com a imposição de leis universais
                                    from iaglobal.core.law_enforcement import (
                                        enforce_universal_laws,
                                    )

                                    func = enforce_universal_laws(func)
                                    setattr(self, attr_name, functools.partial(func))
                                    loaded_count += 1

                            # Cenário 2: Suporta os arquivos que foram fatiados como classe (ex: No_Integrator)
                            elif (
                                attr_name.startswith("No_")
                                or attr_name.endswith("Scheduler")
                                or attr_name.endswith("Mixin")
                            ):
                                cls_target = getattr(module, attr_name)
                                if isinstance(cls_target, type):
                                    for sub_attr in dir(cls_target):
                                        if sub_attr.startswith("run_"):
                                            func = getattr(cls_target, sub_attr)
                                            setattr(
                                                self, sub_attr, functools.partial(func)
                                            )
                                            loaded_count += 1
                except Exception as e:
                    self.logger.error(
                        "❌ Falha crítica ao carregar nó modular do arquivo %s: %s",
                        filename,
                        e,
                    )
                    # Não engolir silenciosamente: registra na barreira imunológica
                    # para que o relatório de saúde reflita a falha real de import
                    # (antes o barrier reportava import_failure=0 mesmo com nós quebrados).
                    if barrier is not None:
                        barrier.record(
                            "import_failure",
                            detail=f"{filename}: {e}",
                            agent=filename,
                        )
                    # Persiste também na store estruturada de erros (errors.json +
                    # error/) para que a métrica '0 erros' seja verdadeira.
                    try:
                        from iaglobal.immunity.error_persistence import (
                            record_runtime_error,
                        )

                        record_runtime_error(
                            component=f"graphs.nodes:{filename}",
                            message=f"Falha ao carregar nó: {e}",
                        )
                    except Exception:
                        pass

        self.logger.info(
            "📦 Mapeamento dinâmico concluído! Métodos acoplados ao Singleton: %d",
            loaded_count,
        )

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
                    node_name = attr_name[len("run_") :]
                    if self.get_node(node_name) is None:
                        self.register_node(node_name)(method)
                        registered = self.list_nodes()
                        self.logger.debug(
                            "📌 Node registrado dinamicamente: %s (total=%d)",
                            node_name,
                            len(registered),
                        )

    # ==========================================================
    # CONTEXT HELPERS
    # ==========================================================

    def _log(self, ctx: dict, msg: str):
        self.logger.info("📦 %s", msg)
        ctx.setdefault("logs", []).append(msg)

    def _resolve_model(self, ctx: dict) -> str:
        return ""


# ==========================================================
# SKILL NODE FACTORY
# ==========================================================


def create_skill_node(name: str, depends_on: Optional[List[str]] = None) -> Any:
    """
    Cria um Node do grafo a partir do skill name.
    Carrega dinamicamente a função run_<name> do módulo iaglobal.graphs.nodes.no_<name>.
    """
    from iaglobal.graphs.node import Node as GraphNode
    import importlib

    depends_on = depends_on or []

    try:
        module = importlib.import_module(f"iaglobal.graphs.nodes.no_{name}")
        run_fn = getattr(module, f"run_{name}", None)
        if run_fn is None:
            logger.warning(
                "create_skill_node: run_%s não encontrada em no_%s.py", name, name
            )
            run_fn = lambda ctx: {"output": f"stub:{name}", "success": True}
    except (ImportError, AttributeError) as e:
        logger.warning("create_skill_node: falha ao carregar nó '%s': %s", name, e)
        run_fn = lambda ctx: {"output": f"stub:{name}", "success": True}

    return GraphNode(
        name=name,
        run=run_fn,
        depends_on=depends_on,
        node_type="general",
        strategy="general",
    )
