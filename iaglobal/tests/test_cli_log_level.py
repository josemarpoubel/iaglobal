# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""Prova empírica da causa raiz do desvio: um log INFO silenciosamente
suprimido como WARNING no subprocesso do CLI escondeu a membrana.

Regressão: o logger 'iaglobal' (usado pela membrana/IVM) deve ter nível
efetivo <= INFO para que sinais de observabilidade apareçam no CLI.
"""
import logging


def test_iaglobal_logger_emits_info_after_fix():
    """setup_logger() deve subir o logger 'iaglobal' para INFO.

    Causa raiz do desvio: o código antigo comparava `logger.level == WARNING`,
    mas um logger recém-criado tem nível NOTSET (0) -> a subida nunca ocorria
    e todo INFO era suprimido (nível efetivo = WARNING do root).
    """
    from iaglobal.utils.logger import setup_logger

    lg = setup_logger("iaglobal")
    assert lg.level <= logging.INFO, (
        f"logger 'iaglobal' deveria estar em INFO+, mas está em "
        f"{logging.getLevelName(lg.level)}"
    )
    assert lg.getEffectiveLevel() <= logging.INFO


def test_info_suppressed_at_warning_but_visible_at_info():
    """Mecânica que escondeu a membrana: INFO desaparece em WARNING e volta em INFO."""
    records = []
    handler = logging.Handler()
    handler.emit = lambda r: records.append(r)

    lg = logging.getLogger("__probe_cli_loglevel__")
    lg.setLevel(logging.WARNING)
    lg.addHandler(handler)
    lg.propagate = False
    try:
        lg.info("[MEMBRANA] teste")
        assert not any("MEMBRANA" in r.getMessage() for r in records), \
            "INFO não deveria aparecer em nível WARNING (mecânica do bug)"

        records.clear()
        lg.setLevel(logging.INFO)
        lg.info("[MEMBRANA] teste")
        assert any("MEMBRANA" in r.getMessage() for r in records), \
            "INFO deve aparecer em nível INFO (correção)"
    finally:
        lg.removeHandler(handler)
