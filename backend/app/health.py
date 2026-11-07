"""Health probes that stay free of secrets, filesystem paths, and hostnames."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.maintenance_status import default_status_path, public_view, read_status


def chroma_is_healthy(agent: object) -> bool:
    """Return whether the process can read the already-open Chroma collection.

    Uses the client opened at startup. A second PersistentClient would contend
    for the same SQLite file and could turn a healthy process into a false 503.
    """
    retriever = getattr(agent, "retriever", None)
    store = getattr(retriever, "vector_store", None)
    collection = getattr(store, "_collection", None)
    count_fn = getattr(collection, "count", None)
    if not callable(count_fn):
        return False
    try:
        count = count_fn()
    except Exception:
        return False
    if isinstance(count, bool) or not isinstance(count, int):
        return False
    return count >= 0


def maintenance_data_document(path: Path | None = None) -> dict[str, Any]:
    """Public maintenance snapshot. Missing or corrupt files become an empty document."""
    return public_view(read_status(path or default_status_path()))
