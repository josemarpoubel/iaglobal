# iaglobal/core/bootstrap_engine.py

import importlib
import pkgutil
import inspect
import logging
from typing import Dict, Type, Any

logger = logging.getLogger("BOOTSTRAP_ENGINE")


class BootstrapEngine:
    """
    🧠 Kernel de auto-descoberta

    - escaneia módulos do iaglobal
    - importa dinamicamente
    - registra plugins/agentes
    - inicializa sistemas automaticamente
    """

    def __init__(self, base_package="iaglobal"):
        self.base_package = base_package
        self.registry: Dict[str, Any] = {}

    # =========================================================
    # START BOOTSTRAP
    # =========================================================

    def boot(self):
        logger.info("🚀 Bootstrapping system...")

        modules = self._discover_modules()
        self._load_modules(modules)
        self._register_plugins()

        logger.info(f"✅ Bootstrap complete. Modules: {len(self.registry)}")

        return self.registry

    # =========================================================
    # MODULE DISCOVERY
    # =========================================================

    def _discover_modules(self):
        logger.info("🔍 Discovering modules...")

        package = importlib.import_module(self.base_package)

        modules = []

        for _, name, is_pkg in pkgutil.walk_packages(
            package.__path__,
            package.__name__ + "."
        ):
            modules.append(name)

        return modules

    # =========================================================
    # DYNAMIC IMPORT
    # =========================================================

    def _load_modules(self, modules):
        logger.info("📦 Loading modules dynamically...")

        for module_name in modules:
            try:
                module = importlib.import_module(module_name)
                self.registry[module_name] = module

            except Exception as e:
                logger.warning(f"⚠️ Failed loading {module_name}: {e}")

    # =========================================================
    # PLUGIN DETECTION
    # =========================================================

    def _register_plugins(self):
        logger.info("🧩 Registering plugins...")

        for name, module in self.registry.items():

            for attr_name in dir(module):
                attr = getattr(module, attr_name)

                if inspect.isclass(attr):

                    # convention: qualquer classe com "Agent" ou "Engine"
                    if "Agent" in attr_name or "Engine" in attr_name:

                        key = f"{name}:{attr_name}"
                        self.registry[key] = attr

                        logger.info(f"🧠 Registered plugin: {key}")

    # =========================================================
    # GET SYSTEM COMPONENT
    # =========================================================

    def get(self, key: str):
        return self.registry.get(key)
