#!/usr/bin/env python3
"""
Toy test script to quickly validate the smart incremental update flow.

Flow:
- Download latest dumps (vosdroits, etc.)
- Stage only the first 10 XML files into a toy directory
- Run SmartXMLUpdater with an isolated test ChromaDB
- Simulate a change in exactly one file and run again
- Print concise stats to verify only that file was re-embedded
"""

import os
import shutil
import sys
import time
from pathlib import Path
from typing import List

import dotenv
from loguru import logger


def ensure_mistral_key() -> None:
    if not os.getenv("MISTRAL_API_KEY"):
        logger.error(
            "MISTRAL_API_KEY is not set. Export it in your environment before running."
        )
        sys.exit(1)


def download_latest() -> None:
    try:
        # Prefer absolute import if called from repo root
        from database.download import main as download_main
    except Exception:
        from download import main as download_main

    logger.info("Downloading latest datasets (if not already present)…")
    download_main()


def stage_first_n_xml(src_dir: Path, dst_dir: Path, n: int = 10) -> List[Path]:
    if dst_dir.exists():
        shutil.rmtree(dst_dir, ignore_errors=True)
    dst_dir.mkdir(parents=True, exist_ok=True)

    xml_files = sorted(src_dir.rglob("*.xml"))
    if not xml_files:
        raise RuntimeError(
            f"No XML files found in {src_dir}. Did the download succeed?"
        )

    selected = xml_files[:n]
    for p in selected:
        shutil.copy2(p, dst_dir / p.name)
    logger.info(f"Staged {len(selected)} XML files into {dst_dir}")
    return [dst_dir / p.name for p in selected]


def run_updater_toy(data_dir: Path, persist_dir: Path) -> dict:
    # Import and monkeypatch smart_parser constants so we use an isolated Chroma instance
    try:
        from database import smart_parser as sp
    except Exception:
        import smart_parser as sp

    sp.PERSIST_DIR = str(persist_dir)
    sp.TRACKING_DB_PATH = str(persist_dir / "chroma.sqlite3")
    sp.COLLECTION_NAME = "service_public_toy"

    updater = sp.SmartXMLUpdater(data_dirs=[str(data_dir)])
    result = updater.run(cleanup_removed=True)
    return result


def main() -> int:
    dotenv.load_dotenv()
    ensure_mistral_key()

    repo_root = Path(__file__).resolve().parent
    data_root = repo_root / "data" / "service-public"
    vosdroits_latest = data_root / "vosdroits-latest"
    toy_dir = data_root / "toy-latest"
    test_persist = repo_root / "chroma_db_toy"

    # 1) Download
    download_latest()

    # 2) Stage first 10 files
    staged_files = stage_first_n_xml(vosdroits_latest, toy_dir, n=10)

    # 3) Ensure a fresh toy chroma dir
    if test_persist.exists():
        shutil.rmtree(test_persist, ignore_errors=True)
    test_persist.mkdir(parents=True, exist_ok=True)

    # 4) First run: expect all 10 files to be new
    logger.info("Running first update (expecting 10 new files)…")
    result1 = run_updater_toy(toy_dir, test_persist)
    logger.info(
        f"First run → New: {result1['new_files']}, Updated: {result1['updated_files']}, "
        f"Unchanged: {result1['unchanged_files']}, Deleted: {result1['deleted_files']}, "
        f"Embedded: {result1['embedded_chunks']}, Baseline: {result1['baseline_chunks']}"
    )

    # 5) Simulate a change in exactly one file (touch to update mtime)
    changed_file = staged_files[2] if len(staged_files) >= 3 else staged_files[0]
    now = time.time()
    os.utime(changed_file, (now, now))
    logger.info(f"Simulated change by touching: {changed_file}")

    # 6) Second run: expect 0 new, 1 updated, others unchanged
    logger.info("Running second update (expecting 1 updated file)…")
    result2 = run_updater_toy(toy_dir, test_persist)
    logger.info(
        f"Second run → New: {result2['new_files']}, Updated: {result2['updated_files']}, "
        f"Unchanged: {result2['unchanged_files']}, Deleted: {result2['deleted_files']}, "
        f"Embedded: {result2['embedded_chunks']}, Baseline: {result2['baseline_chunks']}, "
        f"Saved: {result2['compute_savings_percent']}%"
    )

    # 7) Quick checks
    ok = True
    if result1["new_files"] != 10:
        logger.error("Expected 10 new files on first run.")
        ok = False
    if result2["updated_files"] != 1:
        logger.error("Expected exactly 1 updated file on second run.")
        ok = False
    if result2["new_files"] != 0:
        logger.error("Expected 0 new files on second run.")
        ok = False

    if ok:
        logger.success("Toy update test passed ✅")
        return 0
    else:
        logger.error("Toy update test failed ❌")
        return 1


if __name__ == "__main__":
    sys.exit(main())
