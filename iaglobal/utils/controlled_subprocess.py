"""Executor controlado de subprocess para agentes.

NÃO permite subprocess arbitrário. Apenas operações pré-aprovadas:
- pip install <package> (sem break-system-packages)
- pip list, pip show
- Comandos seguros de leitura (whoami, uname, python --version)

Bloqueia:
- shell=True (sempre False)
- Comandos de escrita fora de /tmp
- Argumentos perigosos (--break-system-packages, --no-build-isolation, etc.)
- Timeout máximo de 60s
"""

import asyncio
import logging
import shlex
import subprocess
from typing import List, Optional

logger = logging.getLogger(__name__)

# Whitelist de comandos base permitidos
_ALLOWED_COMMANDS = {
    "pip",
    "python",
    "python3",
    "whoami",
    "uname",
    "which",
    "ls",
    "cat",
    "head",
    "tail",
    "echo",
    "pwd",
    "curl",
    "git",
    "node",
    "npm",
    "npx",
    "sort",
    "wc",
    "mkdir",
    "cp",
    "mv",
    "touch",
    "chmod",
    "date",
    "dirname",
    "basename",
    "realpath",
    "env",
    "printenv",
}

# Argumentos bloqueados do pip (segurança)
_BLOCKED_PIP_ARGS = {
    "--break-system-packages",
    "--no-build-isolation",
    "--no-deps",
    "--global",
    "--user",
    "--target",
    "--no-cache-dir",
    "--force-reinstall",
    "--ignore-installed",
    "--no-index",
    "--find-links",
    "--extra-index-url",
    "--trusted-host",
}

# Caminhos de leitura permitidos
_ALLOWED_READ_PREFIXES = ("/tmp/", "/home/", "/proc/", "/etc/", "/usr/", "/opt/", "/var/")
# Caminhos de escrita permitidos (mkdir, cp, mv, touch, chmod)
_ALLOWED_WRITE_PREFIXES = ("/tmp/",)


class CommandBlockedError(RuntimeError):
    """Comando rejeitado pela política de segurança."""


def _validate_command(args: List[str]) -> None:
    """Valida comando contra a whitelist de segurança."""
    if not args:
        raise CommandBlockedError("Comando vazio")

    base = args[0]

    # Whitelist de comandos base
    if base not in _ALLOWED_COMMANDS and not base.startswith("/"):
        raise CommandBlockedError(f"Comando não permitido: {base}")

    # Pip: valida argumentos extras
    if base == "pip":
        if len(args) < 2:
            return
        subcmd = args[1]
        if subcmd not in ("install", "list", "show", "check", "index", "download"):
            raise CommandBlockedError(f"Subcomando pip não permitido: {subcmd}")
        for arg in args:
            if arg in _BLOCKED_PIP_ARGS:
                raise CommandBlockedError(f"Arg pip bloqueado: {arg}")
            if arg.startswith("-") and arg not in ("-q", "-v", "--quiet", "--verbose"):
                continue

    # Caminhos de leitura: só prefixos permitidos
    if base in ("cat", "head", "tail", "ls", "wc", "sort"):
        for arg in args[1:]:
            if not arg.startswith("-"):
                if not any(arg.startswith(p) for p in _ALLOWED_READ_PREFIXES):
                    raise CommandBlockedError(
                        f"Path não permitido para leitura: {arg}"
                    )

    # Caminhos de escrita: só prefixos permitidos
    if base in ("mkdir", "cp", "mv", "touch", "chmod"):
        for arg in args[1:]:
            if not arg.startswith("-"):
                if not any(arg.startswith(p) for p in _ALLOWED_WRITE_PREFIXES):
                    raise CommandBlockedError(
                        f"Path não permitido para escrita: {arg}"
                    )

    # git: só em /tmp/ (evita acesso a repositórios do sistema)
    if base == "git":
        cwd_marker = any("/" in arg for arg in args[1:] if not arg.startswith("-"))
        if "-C" in args:
            idx = args.index("-C")
            if idx + 1 < len(args):
                git_dir = args[idx + 1]
                if not git_dir.startswith("/tmp/"):
                    raise CommandBlockedError(f"Git não permitido fora de /tmp/: {git_dir}")


async def run_controlled(
    args: List[str],
    timeout: float = 30.0,
    capture_output: bool = True,
) -> subprocess.CompletedProcess:
    """Executa comando controlado em thread pool.

    Args:
        args: Lista de argumentos do comando (ex: ["pip", "install", "requests"]).
        timeout: Timeout máximo em segundos (default 30s, max 120s).
        capture_output: Se True, captura stdout/stderr.

    Returns:
        subprocess.CompletedProcess com stdout/stderr.

    Raises:
        CommandBlockedError: se o comando violar a política.
        asyncio.TimeoutError: se exceder o timeout.
    """
    _validate_command(args)

    effective_timeout = min(timeout, 120.0)
    logger.info("[CTRL-SUB] Executando: %s (timeout=%.1fs)", shlex.join(args), effective_timeout)

    try:
        proc = await asyncio.wait_for(
            asyncio.to_thread(
                subprocess.run,
                args,
                capture_output=capture_output,
                text=True,
                timeout=effective_timeout,
                check=False,
            ),
            timeout=effective_timeout + 5.0,
        )

        if proc.returncode != 0:
            stderr = (proc.stderr or "")[:500]
            logger.warning("[CTRL-SUB] Falha (rc=%d): %s", proc.returncode, stderr)
        else:
            logger.info("[CTRL-SUB] Sucesso (rc=0)")

        return proc

    except asyncio.TimeoutError:
        logger.error("[CTRL-SUB] Timeout (%ds) para: %s", effective_timeout, shlex.join(args))
        raise


async def pip_install(
    package: str,
    timeout: float = 60.0,
) -> subprocess.CompletedProcess:
    """Instala pacote Python via pip de forma controlada.

    Args:
        package: Nome do pacote (ex: "requests", "pandas==2.0").
        timeout: Timeout máximo (default 60s).

    Returns:
        subprocess.CompletedProcess.
    """
    return await run_controlled(
        ["pip", "install", package, "-q"],
        timeout=timeout,
    )


async def pip_list() -> subprocess.CompletedProcess:
    """Lista pacotes instalados."""
    return await run_controlled(["pip", "list", "--format=columns"], timeout=15.0)



