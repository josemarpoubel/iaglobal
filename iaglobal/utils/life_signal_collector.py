# iaglobal/utils/life_signal_collector.py

import asyncio
import functools
import logging
import json
import time
import threading
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime


class LifeSignalCollector:
    """
    Coleta telemetria de life-signals emitidos por funções instrumentadas.

    Funciona como um "eletrocardiograma" do sistema — registra cada batimento
    (invocação) das funções críticas para determinar se estão vivas ou mortas.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._signals: Dict[str, List[Dict]] = {}
        self._lock_local = threading.Lock()
        self._log_handler: Optional[logging.Handler] = None
        self._initialized = True

    def install(self, log_file: Optional[Path] = None) -> None:
        """
        Instala handler de log para capturar life-signals.

        Args:
            log_file: Arquivo para persistência (opcional). Se None, apenas memória.
        """
        if self._log_handler is not None:
            return  # Já instalado

        self._log_handler = _LifeSignalHandler(self, log_file)
        self._log_handler.setLevel(
            logging.WARNING
        )  # WARNING+ para nao capturar INFO spam
        self._log_handler.setFormatter(logging.Formatter("%(message)s"))

        # Adiciona ao logger raiz para capturar life-signals de loggers com propagate=True
        logging.getLogger().addHandler(self._log_handler)

        # Também adiciona diretamente aos loggers iaglobal existentes (que podem ter propagate=False)
        for name in logging.Logger.manager.loggerDict:
            if name.startswith("iaglobal"):
                logger_instance = logging.getLogger(name)
                if self._log_handler not in logger_instance.handlers:
                    logger_instance.addHandler(self._log_handler)

        self._log_handlers = [self._log_handler] + [
            logging.getLogger(name)
            for name in logging.Logger.manager.loggerDict
            if name.startswith("iaglobal")
        ]

        logging.getLogger("iaglobal").debug(
            "[LIFE-SIGNAL-COLLECTOR] Instalado e capturando sinais..."
        )

    def uninstall(self) -> None:
        """Remove o handler de log de todos os loggers."""
        if self._log_handler is None:
            return

        # Remove do root
        logging.getLogger().removeHandler(self._log_handler)

        # Remove dos loggers iaglobal
        for name in list(logging.Logger.manager.loggerDict.keys()):
            if name.startswith("iaglobal"):
                logger_instance = logging.getLogger(name)
                if self._log_handler in logger_instance.handlers:
                    logger_instance.removeHandler(self._log_handler)

        self._log_handler.flush()
        self._log_handler = None
        logging.getLogger("iaglobal").debug("[LIFE-SIGNAL-COLLECTOR] Desinstalado.")

    def record(
        self, function_name: str, ctx_keys: List[str], timestamp: Optional[float] = None
    ) -> None:
        """
        Registra um life-signal recebido.

        Args:
            function_name: Nome da função (ex: "_run_evolution_committee")
            ctx_keys: Chaves do contexto de chamada
            timestamp: Timestamp do sinal (default: now)
        """
        ts = timestamp or time.time()
        signal = {
            "function": function_name,
            "ctx_keys": ctx_keys,
            "timestamp": ts,
            "datetime": datetime.fromtimestamp(ts).isoformat(),
        }

        with self._lock_local:
            if function_name not in self._signals:
                self._signals[function_name] = []
            self._signals[function_name].append(signal)

    def get_signals(self, function_name: str) -> List[Dict]:
        """Retorna todos os sinais de uma função."""
        with self._lock_local:
            return list(self._signals.get(function_name, []))

    def get_all_signals(self) -> Dict[str, List[Dict]]:
        """Retorna todos os sinais coletados."""
        with self._lock_local:
            return {k: list(v) for k, v in self._signals.items()}

    def get_status(self, function_name: str, max_age_seconds: float = 3600) -> Dict:
        """
        Retorna status de vida de uma função.

        Args:
            function_name: Nome da função
            max_age_seconds: Considera sinais mais antigos como "não recentes"

        Returns:
            Dict com: alive (bool), last_seen (timestamp), count (int), status (str)
        """
        signals = self.get_signals(function_name)

        if not signals:
            return {
                "function": function_name,
                "alive": False,
                "last_seen": None,
                "count": 0,
                "status": "DEAD (sem sinais)",
            }

        last_signal = signals[-1]
        last_ts = last_signal["timestamp"]
        now = time.time()
        age = now - last_ts

        is_recent = age <= max_age_seconds

        return {
            "function": function_name,
            "alive": is_recent,
            "last_seen": last_ts,
            "last_seen_iso": last_signal["datetime"],
            "count": len(signals),
            "age_seconds": age,
            "status": f"{'ALIVE' if is_recent else 'HIBERNATING'} (último sinal: {age:.0f}s atrás)",
        }

    def get_report(self) -> Dict:
        """
        Gera relatório completo de todas as funções monitoradas.
        """
        all_signals = self.get_all_signals()
        functions = list(all_signals.keys())

        report = {
            "total_functions": len(functions),
            "total_signals": sum(len(s) for s in all_signals.values()),
            "functions": {},
        }

        for func in sorted(functions):
            report["functions"][func] = self.get_status(func)

        return report

    def clear(self) -> None:
        """Limpa todos os sinais coletados (usado para reiniciar observação)."""
        with self._lock_local:
            self._signals.clear()

    def save_to_file(self, path: Path) -> None:
        """Salva todos os sinais em arquivo JSON."""
        data = self.get_all_signals()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False))


class _LifeSignalHandler(logging.Handler):
    """Handler de log especializado para capturar life-signals."""

    def __init__(self, collector: LifeSignalCollector, log_file: Optional[Path] = None):
        super().__init__()
        self.collector = collector
        self.log_file = log_file

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = record.getMessage()
            if not msg.startswith("[LIFE-SIGNAL]"):
                return

            # Parse do formato: [LIFE-SIGNAL] _run_evolution_committee invoked | ctx_keys=['memory']
            try:
                content = msg[len("[LIFE-SIGNAL]") :].strip()
                func_name_end = content.find(" invoked")
                if func_name_end == -1:
                    logging.getLogger("iaglobal").debug(
                        "[LIFE-SIGNAL-COLLECTOR] Parse miss: %s", content
                    )
                    return

                function_name = content[:func_name_end].strip()

                # Extrai ctx_keys
                ctx_part = content[content.find("| ctx_keys=") + len("| ctx_keys=") :]
                ctx_keys = eval(ctx_part)  # seguro aqui pois é log estruturado

                self.collector.record(
                    function_name, ctx_keys if isinstance(ctx_keys, list) else []
                )

            except Exception as exc:
                # Não deixa erros de parsing quebrarem o logging
                logging.getLogger("iaglobal").debug(
                    "[LIFE-SIGNAL-COLLECTOR] Parse error: %s | msg=%s", exc, msg
                )

        except Exception:
            self.handleError(record)

    def flush(self) -> None:
        """Persiste sinais em arquivo se configurado."""
        if self.log_file:
            try:
                self.collector.save_to_file(self.log_file)
            except Exception:
                pass


# Instância global (Singleton)
collector = LifeSignalCollector()


def instrument(name: Optional[str] = None):
    """Decorator que registra life-signal automaticamente a cada chamada bem-sucedida.

    Uso:
        @instrument(name="bandit.generate")
        async def generate(self, ...):
            ...

    O nome padrão é o qualname da função (ex: 'BanditPolicy.generate').
    Funciona com funções sync e async. Não quebra se o collector falhar.
    """

    def decorator(func):
        func_name = name or f"{func.__module__}.{func.__qualname__}"

        if asyncio.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                result = await func(*args, **kwargs)
                _try_record(func_name)
                return result

            return async_wrapper

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            _try_record(func_name)
            return result

        return sync_wrapper

    return decorator


def _try_record(func_name: str):
    """Registra life-signal diretamente no collector (bypassa handler de log).

    Falhas são silenciosas — o decorator nunca quebra a função instrumentada.
    """
    try:
        collector.record(func_name, [], time.time())
    except Exception:
        pass
