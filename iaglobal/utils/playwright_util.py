"""Auto-install lazy do Playwright (Chromium + Firefox).

Garante que os browsers estejam instalados na primeira tentativa de uso.
Executa `playwright install chromium firefox` automaticamente se necessário.
Cache global por processo — só tenta instalar 1 vez.
"""

import logging
import subprocess
import sys

logger = logging.getLogger(__name__)

_PLAYWRIGHT_READY = False
_PLAYWRIGHT_TRIED = False
_PLAYWRIGHT_BROWSERS = ["chromium", "firefox"]


def _try_launch_any() -> bool:
    """Tenta launch de cada browser instalado. Retorna True se algum funcionar."""
    for browser_name in _PLAYWRIGHT_BROWSERS:
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                browser = getattr(p, browser_name).launch(
                    headless=True,
                    args=["--no-sandbox", "--disable-dev-shm-usage"],
                )
                browser.close()
            return True
        except Exception:
            continue
    return False


def ensure_playwright_browsers(browsers: list[str] | None = None) -> bool:
    """Verifica se os browsers estão instalados; instala automaticamente se faltar.

    Args:
        browsers: Lista de browsers para instalar (default: ['chromium', 'firefox']).

    Returns:
        True se os browsers estão prontos, False se falhou.
    """
    global _PLAYWRIGHT_READY, _PLAYWRIGHT_TRIED

    if _PLAYWRIGHT_READY:
        return True
    if _PLAYWRIGHT_TRIED:
        return False

    _PLAYWRIGHT_TRIED = True
    to_install = browsers or _PLAYWRIGHT_BROWSERS

    # Tenta launch — se funcionar, já está instalado
    if _try_launch_any():
        _PLAYWRIGHT_READY = True
        logger.info("[PLAYWRIGHT] Browsers já instalados e funcionais")
        return True

    # Auto-install
    browsers_str = " ".join(to_install)
    logger.info(
        "[PLAYWRIGHT] Browsers não encontrados — instalando %s (pode levar 2-3 min)...",
        browsers_str,
    )
    try:
        result = subprocess.run(
            [sys.executable, "-m", "playwright", "install", *to_install],
            capture_output=True, text=True, timeout=300,
        )
        if result.returncode == 0:
            _PLAYWRIGHT_READY = True
            logger.info("[PLAYWRIGHT] Browsers instalados com sucesso")
            return True
        logger.error(
            "[PLAYWRIGHT] Falha ao instalar %s: %s",
            browsers_str,
            result.stderr.strip()[:300],
        )
    except subprocess.TimeoutExpired:
        logger.error("[PLAYWRIGHT] Instalação excedeu 300s")
    except Exception as e:
        logger.error("[PLAYWRIGHT] Erro na instalação: %s", e)

    return False
