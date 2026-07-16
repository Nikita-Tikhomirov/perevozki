"""Verify every published SEO route page from a deployment manifest."""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
if __package__ in (None, ""):
    sys.path.insert(0, str(ROOT))

from scripts.seo_generation import PRODUCTION_MARKER


def verify_page(entry: dict[str, Any]) -> list[str]:
    """Return validation errors for one live page."""

    url = entry["url"]
    try:
        response = requests.get(url, timeout=60)
        response.raise_for_status()
    except requests.RequestException as error:
        return [f"{url}: {error}"]

    errors: list[str] = []
    html = response.text
    soup = BeautifulSoup(html, "html.parser")
    expected_h1 = f'{entry["query"]} {entry["city1"]} – {entry["city2"]}'
    h1 = soup.select_one("h1")
    if h1 is None or h1.get_text(" ", strip=True) != expected_h1:
        errors.append(f"{url}: unexpected H1")
    if "{Город" in html:
        errors.append(f"{url}: unresolved city placeholder")
    if PRODUCTION_MARKER not in html:
        errors.append(f"{url}: missing production marker")
    robots = soup.select_one('meta[name="robots"]')
    if robots and "noindex" in robots.get("content", "").casefold():
        errors.append(f"{url}: production page is noindex")
    if len(soup.select("#cities .seo-direction-list a")) != 118:
        errors.append(f"{url}: route-link count is not 118")
    if soup.select("#cities .seo-direction-list button"):
        errors.append(f"{url}: route links were rendered as buttons")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()

    payload = json.loads(args.manifest.read_text(encoding="utf-8"))
    entries = payload.get("pages", [])
    errors: list[str] = []
    checked = 0
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(verify_page, entry): entry for entry in entries}
        for future in as_completed(futures):
            errors.extend(future.result())
            checked += 1
            if checked % 250 == 0 or checked == len(entries):
                print(f"Verified {checked}/{len(entries)} pages", flush=True)

    if errors:
        raise SystemExit("\n".join(errors[:100]))
    print(f"All {checked} pages passed live verification")


if __name__ == "__main__":
    main()
