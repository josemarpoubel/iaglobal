"""
Bridge para iaglobal.storage.batch_writer.

⚠️ DEPRECATED: Este módulo existia como um BatchWriter separado com schema próprio.
Para manter consistência, agora re-exporta o singleton de storage.batch_writer,
que escreve em core.db (via _paths.CORE_DB).

Use diretamente:
    from iaglobal.storage.batch_writer import batch_writer
"""

import warnings

from iaglobal._paths import PROVIDER_EVENTS_DB
from iaglobal.storage.batch_writer import BatchWriter, batch_writer

warnings.warn(
    "iaglobal.providers.batch_writer is deprecated. "
    "Use 'from iaglobal.storage.batch_writer import batch_writer' instead.",
    DeprecationWarning,
    stacklevel=2,
)

DB_PATH = PROVIDER_EVENTS_DB

__all__ = ["BatchWriter", "batch_writer", "DB_PATH"]
