import time
import zipfile
from datetime import datetime
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# URLs for the archives
stable_urls = {
    "vosdroits": (
        "https://www.data.gouv.fr/fr/datasets/r/0ed10f28-d197-4324-97b3-037f625095ac",
        "data/service-public/vosdroits-latest",
    ),
    "schema": (
        "https://www.data.gouv.fr/fr/datasets/r/d1b0f744-c997-48d2-9ec4-1c64e82202d6",
        "data/service-public",
    ),
    "entreprendre": (
        "https://www.data.gouv.fr/fr/datasets/r/93c81767-6ae6-4b31-8dd7-2158e560d181",
        "data/service-public/entreprendre-latest",
    ),
    "schema_entreprendre": (
        "https://www.data.gouv.fr/fr/datasets/r/0c56e5ae-e047-45dc-953a-f8b41e0d533e",
        "data/service-public",
    ),
}

DOWNLOAD_TIMEOUT_SEC = 120
DOWNLOAD_RETRIES = 5


def _session() -> requests.Session:
    retry = Retry(
        total=DOWNLOAD_RETRIES,
        connect=DOWNLOAD_RETRIES,
        read=DOWNLOAD_RETRIES,
        backoff_factor=2,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET", "HEAD"),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    sess = requests.Session()
    sess.mount("https://", adapter)
    sess.mount("http://", adapter)
    return sess


def download_file(url: str, output_path: Path) -> None:
    """Download a file from a URL to the specified path (atomic replace)."""
    print(f"Downloading {url}...")
    part_path = output_path.with_suffix(output_path.suffix + ".part")
    sess = _session()
    last_error: Exception | None = None
    for attempt in range(1, DOWNLOAD_RETRIES + 1):
        try:
            response = sess.get(url, stream=True, timeout=DOWNLOAD_TIMEOUT_SEC)
            response.raise_for_status()
            with open(part_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            part_path.replace(output_path)
            print(f"Downloaded to {output_path}")
            return
        except (requests.RequestException, OSError) as exc:
            last_error = exc
            part_path.unlink(missing_ok=True)
            wait = min(2**attempt, 60)
            print(f"Download attempt {attempt}/{DOWNLOAD_RETRIES} failed: {exc}; retry in {wait}s")
            time.sleep(wait)
    raise RuntimeError(f"Failed to download {url} after {DOWNLOAD_RETRIES} attempts") from last_error


def extract_archive(archive_path: Path, extract_to: Path) -> None:
    """Extract a zip file to the specified directory."""
    print(f"Extracting {archive_path} to {extract_to}...")
    with zipfile.ZipFile(archive_path, "r") as zip_ref:
        zip_ref.extractall(extract_to)
    print(f"Extracted to {extract_to}")


def main() -> None:
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)

    for source_name, (url, dest_dir) in stable_urls.items():
        print(f"\nProcessing {source_name}...")
        dest_path = Path(dest_dir)
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        zip_path = data_dir / f"{source_name}.zip"
        download_file(url, zip_path)
        extract_archive(zip_path, dest_path)
        zip_path.unlink()

    update_date = datetime.now().strftime("%d/%m/%Y")
    with open("last_update.txt", "w") as f:
        f.write(update_date)

    print("\nDownload and extraction completed successfully!")
    print(f"Database last updated: {update_date}")


if __name__ == "__main__":
    main()
