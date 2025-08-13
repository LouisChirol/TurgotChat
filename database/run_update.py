#!/usr/bin/env python3
import argparse
import shutil
import sys
from pathlib import Path
from typing import List

from loguru import logger

# Local imports
try:
    # Prefer absolute imports if run from repo root
    from database.download import main as download_main
    from database.smart_parser import SmartXMLUpdater
except Exception:
    # Fallback when executed from within the database directory
    from download import main as download_main
    from smart_parser import SmartXMLUpdater


DEFAULT_DATA_DIRS: List[str] = [
    "data/service-public/vosdroits-latest",
    "data/service-public/entreprendre-latest",
]


def cleanup_old_dumps(base_dir: str = "data/service-public") -> int:
    """Remove old dumps, keeping only '*-latest' (and leaving non-matching dirs like schema intact).

    Returns number of directories removed.
    """
    removed = 0
    base = Path(base_dir)
    if not base.exists():
        return 0

    for child in base.iterdir():
        if not child.is_dir():
            continue
        name = child.name
        # Remove dated dumps like 'vosdroits-2024-07-01', keep 'vosdroits-latest' and 'entreprendre-latest'
        if (
            name.startswith("vosdroits-") or name.startswith("entreprendre-")
        ) and not name.endswith("-latest"):
            logger.info(f"Removing old dump directory: {child}")
            shutil.rmtree(child, ignore_errors=True)
            removed += 1
    return removed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run full update: download + smart incremental parse"
    )
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="Skip the download step (use current local dumps)",
    )
    parser.add_argument(
        "--data-dirs",
        nargs="+",
        default=DEFAULT_DATA_DIRS,
        help="Directories containing XML dumps to process",
    )
    parser.add_argument(
        "--no-cleanup-removed",
        action="store_true",
        help="Do not remove vectors/tracking for files missing from the dataset",
    )
    parser.add_argument(
        "--cleanup-old-dumps",
        action="store_true",
        help="After a successful run, delete old dump directories (keep only '*-latest')",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if not args.skip_download:
        logger.info("Step 1/3: Downloading and extracting latest dumps…")
        download_main()
    else:
        logger.info("Skipping download step as requested.")

    logger.info("Step 2/3: Running smart incremental updater…")
    updater = SmartXMLUpdater(data_dirs=args.data_dirs)
    result = updater.run(cleanup_removed=not args.no_cleanup_removed)

    logger.info("Step 3/3: Finalizing…")
    removed_dirs = 0
    if args.cleanup_old_dumps:
        removed_dirs = cleanup_old_dumps()

    # Short summary
    logger.success(
        " | ".join(
            [
                f"New: {result['new_files']}",
                f"Updated: {result['updated_files']}",
                f"Unchanged: {result['unchanged_files']}",
                f"Deleted: {result['deleted_files']}",
                f"Embedded chunks: {result['embedded_chunks']}",
                f"Baseline: {result['baseline_chunks']}",
                f"Saved: {result['compute_savings_percent']}%",
                f"Vectors: {result['initial_vector_count']} -> {result['final_vector_count']} (+{result['vectors_added']})",
                f"Old dump dirs removed: {removed_dirs}",
            ]
        )
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
