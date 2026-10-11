#!/usr/bin/env python3
"""Smoke-test Chroma collections after maintenance."""

import sys

from chromadb import PersistentClient

CHROMA_PATH = "/app/database/chroma_db"
REQUIRED = ("service_public", "bofip")


def main() -> int:
    client = PersistentClient(path=CHROMA_PATH)
    names = {c.name for c in client.list_collections()}
    missing = [n for n in REQUIRED if n not in names]
    if missing:
        print(f"ERROR: missing collections: {missing}", file=sys.stderr)
        return 1
    for name in REQUIRED:
        count = client.get_collection(name).count()
        if count <= 0:
            print(f"ERROR: collection {name} is empty", file=sys.stderr)
            return 1
        print(f"OK: {name} count={count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
