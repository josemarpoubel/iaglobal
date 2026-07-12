"""EmbeddingPruner — arquiva embeddings antigos em CBOR2."""

import time
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

MAX_AGE_DAYS = 30
MAX_AGE_SECONDS = MAX_AGE_DAYS * 86400


class EmbeddingPruner:
    """Arquiva embeddings não acessados há mais de N dias."""

    def __init__(self, max_age_days: int = MAX_AGE_DAYS):
        self.max_age = max_age_days * 86400

    def prune(self, embeddings: List[Dict[str, Any]]) -> Dict[str, Any]:
        now = time.time()
        archived = []
        kept = []

        for emb in embeddings:
            last_access = emb.get("last_access", emb.get("timestamp", 0))
            if last_access and (now - last_access) > self.max_age:
                archived.append(emb)
            else:
                kept.append(emb)

        return {
            "archived": len(archived),
            "kept": len(kept),
            "total_before": len(embeddings),
            "total_after": len(kept),
            "archived_entries": archived[:10],
        }

    def estimate_bytes_saved(self, archived_count: int, avg_embedding_bytes: int = 4096) -> int:
        return archived_count * avg_embedding_bytes
