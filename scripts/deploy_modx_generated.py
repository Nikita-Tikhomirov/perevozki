"""Generate and safely publish an Excel-driven SEO batch to MODX."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Protocol

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.deploy_modx_preview import (
    BASE_URL,
    ROOT,
    ModxClient,
    build_modx_content,
    build_modx_template,
    build_scoped_css,
    required_env,
    upload_assets,
)
from scripts.seo_generation import (
    GeneratedPage,
    build_generated_pages,
    load_seo_rows,
    slugify_ru,
    validate_resource_ownership,
)


class ModxCaller(Protocol):
    def call(self, action: str, **data: Any) -> dict[str, Any]: ...


def _find_exact_resource(modx: ModxCaller, alias: str) -> dict[str, Any] | None:
    cached = getattr(modx, "_seo_resource_cache", None)
    if cached is not None:
        return cached.get(alias)

    result = modx.call(
        "resource/getlist",
        start=0,
        limit=2000,
        sort="id",
        dir="ASC",
        context_key="web",
    )
    resources = result.get("results", [])
    total = int(result.get("total", len(resources)))
    if total > len(resources):
        raise RuntimeError(
            f"MODX returned an incomplete resource list ({len(resources)} of {total}); "
            "generation stopped to protect existing aliases"
        )
    cache = {
        item["alias"]: item
        for item in resources
        if item.get("alias")
    }
    setattr(modx, "_seo_resource_cache", cache)
    return cache.get(alias)


def upsert_generated_resource(
    modx: ModxCaller, template_id: int, page: GeneratedPage
) -> int:
    """Create a generated resource or update only an owned exact-alias match."""

    current = _find_exact_resource(modx, page.alias)
    if current:
        loaded = modx.call("resource/get", id=current["id"]).get("object", {})
        validate_resource_ownership(
            str(loaded.get("content", "")), page.marker, page.alias
        )

    content = f"<!-- {page.marker} -->\n{build_modx_content(page.html)}"
    values = {
        "pagetitle": page.title.split("|", 1)[0].strip(),
        "longtitle": page.title,
        "description": page.description,
        "alias": page.alias,
        "parent": 0,
        "template": template_id,
        "content": content,
        "published": 1,
        "hidemenu": 1,
        "searchable": 0,
        "cacheable": 0,
        "richtext": 0,
        "isfolder": 0,
        "context_key": "web",
        "class_key": "modDocument",
        "content_type": 1,
        "syncsite": 1,
    }
    if current:
        modx.call("resource/update", id=current["id"], **values)
        return int(current["id"])
    created = modx.call("resource/create", **values)
    return int(created["object"]["id"])


def _manifest_entry(page: GeneratedPage, resource_id: int | None = None) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "query": page.query,
        "alias": page.alias,
        "url": f"{BASE_URL}/{page.alias}/",
        "title": page.title,
        "description": page.description,
    }
    if resource_id is not None:
        entry["resource_id"] = resource_id
    return entry


def write_manifest(path: Path, entries: list[dict[str, Any]], *, dry_run: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "batch": "seo-2026-minsk-uzda",
        "dry_run": dry_run,
        "count": len(entries),
        "pages": entries,
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def build_batch(args: argparse.Namespace) -> list[GeneratedPage]:
    rows = load_seo_rows(args.xlsx)
    if len(rows) != 24:
        raise RuntimeError(f"Expected 24 SEO rows, found {len(rows)}")
    source_html = (ROOT / "index.html").read_text(encoding="utf-8")
    return build_generated_pages(
        source_html,
        rows,
        city1=args.city1,
        city2=args.city2,
        variant=args.variant,
        batch_slug=args.batch_slug,
    )


def deploy_batch(args: argparse.Namespace) -> list[dict[str, Any]]:
    pages = build_batch(args)
    if args.dry_run:
        return [_manifest_entry(page) for page in pages]

    source_css = (ROOT / "assets" / "styles.css").read_text(encoding="utf-8")
    upload_assets(
        required_env("FTP_HOST"),
        required_env("FTP_USERNAME"),
        required_env("FTP_PASSWORD"),
        build_scoped_css(source_css),
    )
    modx = ModxClient(
        required_env("MODX_USERNAME"), required_env("MODX_PASSWORD")
    )
    template_id = modx.upsert_template(build_modx_template())
    entries = [
        _manifest_entry(
            page, upsert_generated_resource(modx, template_id, page)
        )
        for page in pages
    ]
    modx.call("system/clearcache")
    return entries


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate and publish the approved SEO route-page batch"
    )
    parser.add_argument("--xlsx", type=Path, required=True)
    parser.add_argument("--city1", default="Минск")
    parser.add_argument("--city2", default="Узда")
    parser.add_argument("--variant", type=int, choices=range(1, 6), default=1)
    parser.add_argument("--batch-slug", default="minsk-uzda")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=ROOT / "outputs" / "seo-2026-minsk-uzda.json",
    )
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.batch_slug:
        args.batch_slug = f"{slugify_ru(args.city1)}-{slugify_ru(args.city2)}"
    entries = deploy_batch(args)
    write_manifest(args.manifest, entries, dry_run=args.dry_run)
    print(
        f"Prepared {len(entries)} pages; manifest: {args.manifest.resolve()}"
    )


if __name__ == "__main__":
    main()
