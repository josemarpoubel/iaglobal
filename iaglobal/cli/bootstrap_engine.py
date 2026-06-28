# iaglobal/cli/bootstrap_engine.py

import importlib
import pkgutil
import inspect
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class BootstrapEngine:
    """
    🧠 Kernel de auto-descoberta robusto
    """

    def __init__(self, base_package="iaglobal"):
        self.base_package = base_package
        self.registry: Dict[str, Any] = {}
        self._booted = False

    def boot(self) -> Dict[str, Any]:
        if self._booted:
            return self.registry

        logger.info("🚀 Bootstrapping system...")
        
        # Otimização: Discovery e Load em uma única passagem para evitar overhead
        modules = self._discover_modules()
        self._load_modules(modules)
        self._register_plugins()

        self._booted = True
        logger.info(f"✅ Bootstrap complete. Total items in registry: {len(self.registry)}")
        return self.registry

    def _discover_modules(self) -> List[str]:
        try:
            package = importlib.import_module(self.base_package)
            # Verifica se o package possui __path__
            if not hasattr(package, "__path__"):
                return []
            
            return [name for _, name, _ in pkgutil.walk_packages(
                package.__path__, package.__name__ + "."
            )]
        except ImportError as e:
            logger.error(f"❌ Failed to import base package {self.base_package}: {e}")
            return []

    def _load_modules(self, modules: List[str]):
        logger.info("📦 Loading modules dynamically...")
        for module_name in modules:
            try:
                # Importação lazy garante que evitamos erros de módulos faltantes parciais
                self.registry[module_name] = importlib.import_module(module_name)
            except Exception as e:
                logger.warning(f"⚠️ Failed loading module {module_name}: {e}")

    def _register_plugins(self):
        logger.info("🧩 Registering plugins...")
        # Iteramos sobre uma cópia das chaves para permitir registro seguro
        for name, module in list(self.registry.items()):
            # Evita registrar plugins de sub-módulos que já foram processados
            if not inspect.ismodule(module):
                continue

            for attr_name in dir(module):
                try:
                    attr = getattr(module, attr_name)
                    # Verifica se é classe e se pertence ao próprio módulo (evita imports cruzados)
                    if inspect.isclass(attr) and inspect.getmodule(attr) == module:
                        if "Agent" in attr_name or "Engine" in attr_name:
                            key = f"{name}:{attr_name}"
                            self.registry[key] = attr
                            logger.debug(f"🧠 Registered plugin: {key}")
                except Exception:
                    continue

    def get(self, key: str, default=None):
        return self.registry.get(key, default)
