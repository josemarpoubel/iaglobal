"""Resource limits module for sandbox execution."""

import resource
import sys


MAX_MEMORIA_MB = 256
MAX_CPU_SEGUNDOS = 10
MAX_ARQUIVO_BYTES = 1024 * 1024
MAX_PROCESSOS = 20  # Permite processos filhos essenciais para fpdf


def limitar_recursos_sandbox():
    try:
        limite_memoria_bytes = MAX_MEMORIA_MB * 1024 * 1024
        resource.setrlimit(
            resource.RLIMIT_AS, (limite_memoria_bytes, limite_memoria_bytes)
        )
        resource.setrlimit(resource.RLIMIT_CPU, (MAX_CPU_SEGUNDOS, MAX_CPU_SEGUNDOS))
        resource.setrlimit(
            resource.RLIMIT_FSIZE, (MAX_ARQUIVO_BYTES, MAX_ARQUIVO_BYTES)
        )
        resource.setrlimit(resource.RLIMIT_NPROC, (MAX_PROCESSOS, MAX_PROCESSOS))
    except Exception as e:
        sys.exit(f"Critical security error applying resource limits: {e}")
