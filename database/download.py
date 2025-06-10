import zipfile
from pathlib import Path

import requests

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
}


def download_file(url: str, output_path: Path) -> None:
    """Download a file from a URL to the specified path."""
    print(f"Downloading {url}...")
    response = requests.get(url, stream=True)
    response.raise_for_status()

    with open(output_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
    print(f"Downloaded to {output_path}")


def extract_archive(archive_path: Path, extract_to: Path) -> None:
    """Extract a zip file to the specified directory."""
    print(f"Extracting {archive_path} to {extract_to}...")
    with zipfile.ZipFile(archive_path, "r") as zip_ref:
        zip_ref.extractall(extract_to)
    print(f"Extracted to {extract_to}")


def main():
    # Create data directory if it doesn't exist
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)

    # Process each source in stable_urls
    for source_name, (url, dest_dir) in stable_urls.items():
        print(f"\nProcessing {source_name}...")

        # Create destination directory
        dest_path = Path(dest_dir)
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        # Download and extract
        zip_path = data_dir / f"{source_name}.zip"
        download_file(url, zip_path)
        extract_archive(zip_path, dest_path)
        zip_path.unlink()  # Remove the zip file after extraction

    print("\nDownload and extraction completed successfully!")


if __name__ == "__main__":
    main()
