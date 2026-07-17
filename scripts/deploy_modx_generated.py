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
    build_all_route_pages,
    build_generated_pages,
    load_seo_rows,
    slugify_ru,
    validate_resource_ownership,
)


PRODUCTION_TEMPLATE_NAME = "SEO 2026 — маршрутные страницы"


class ModxCaller(Protocol):
    def call(self, action: str, **data: Any) -> dict[str, Any]: ...


def _find_exact_resource(modx: ModxCaller, alias: str) -> dict[str, Any] | None:
    cached = getattr(modx, "_seo_resource_cache", None)
    if cached is not None:
        return cached.get(alias)

    resources: list[dict[str, Any]] = []
    start = 0
    limit = 1000
    while True:
        result = modx.call(
            "resource/getlist",
            start=start,
            limit=limit,
            sort="id",
            dir="ASC",
            context_key="web",
        )
        batch = result.get("results", [])
        resources.extend(batch)
        total = int(result.get("total", len(resources)))
        if len(resources) >= total or not batch:
            break
        start += len(batch)
    if len(resources) < total:
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
    modx: ModxCaller,
    template_id: int,
    page: GeneratedPage,
    *,
    production: bool = False,
) -> int:
    """Create a generated resource or update only an owned exact-alias match."""

    current = _find_exact_resource(modx, page.alias)
    if current:
        loaded = modx.call("resource/get", id=current["id"]).get("object", {})
        validate_resource_ownership(
            str(loaded.get("content", "")), page.marker, page.alias
        )

    content = (
        f"<!-- {page.marker} -->\n"
        f"{build_modx_content(page.html, populate_directions=False)}"
    )
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
        "searchable": 1 if production else 0,
        "cacheable": 1 if production else 0,
        "richtext": 0,
        "isfolder": 0,
        "context_key": "web",
        "class_key": "modDocument",
        "content_type": 1,
        "syncsite": 0 if production else 1,
    }
    if current:
        modx.call("resource/update", id=current["id"], **values)
        return int(current["id"])
    created = modx.call("resource/create", **values)
    resource_id = int(created["object"]["id"])
    cache = getattr(modx, "_seo_resource_cache", None)
    if cache is not None:
        cache[page.alias] = {"id": resource_id, "alias": page.alias}
    return resource_id


def _manifest_entry(page: GeneratedPage, resource_id: int | None = None) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "query": page.query,
        "city1": page.city1,
        "city2": page.city2,
        "variant": page.variant,
        "title_variant": page.title_variant,
        "description_variant": page.description_variant,
        "intro_variant": page.intro_variant,
        "alias": page.alias,
        "url": f"{BASE_URL}/{page.alias}/",
        "title": page.title,
        "description": page.description,
    }
    if resource_id is not None:
        entry["resource_id"] = resource_id
    return entry


def write_manifest(
    path: Path,
    entries: list[dict[str, Any]],
    *,
    dry_run: bool,
    batch: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "batch": batch,
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
    if args.all_routes:
        return build_all_route_pages(source_html, rows, city1=args.city1)
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

    modx = ModxClient(
        required_env("MODX_USERNAME"), required_env("MODX_PASSWORD")
    )
    production = bool(args.all_routes)

    completed: dict[str, dict[str, Any]] = {}
    if args.resume and args.manifest.exists():
        payload = json.loads(args.manifest.read_text(encoding="utf-8"))
        completed = {
            entry["alias"]: entry
            for entry in payload.get("pages", [])
            if entry.get("resource_id")
        }

    # Load the full alias cache before the first mutation. This also protects
    # later creates when the total resource count crosses a pagination boundary.
    _find_exact_resource(modx, "__seo_preflight_missing_alias__")
    conflicts: list[str] = []
    cache = getattr(modx, "_seo_resource_cache", {})
    completed = {
        alias: entry for alias, entry in completed.items() if alias in cache
    }
    for page in pages:
        current = cache.get(page.alias)
        if not current or page.alias in completed:
            continue
        loaded = modx.call("resource/get", id=current["id"]).get("object", {})
        try:
            validate_resource_ownership(
                str(loaded.get("content", "")), page.marker, page.alias
            )
        except RuntimeError:
            conflicts.append(page.alias)
    if conflicts:
        preview = ", ".join(conflicts[:10])
        raise RuntimeError(
            f"Found {len(conflicts)} existing unowned aliases; no pages were changed: {preview}"
        )

    source_css = (ROOT / "assets" / "styles.css").read_text(encoding="utf-8")
    upload_assets(
        required_env("FTP_HOST"),
        required_env("FTP_USERNAME"),
        required_env("FTP_PASSWORD"),
        build_scoped_css(source_css),
    )
    if production:
        template_id = modx.upsert_template(
            build_modx_template(noindex=False),
            name=PRODUCTION_TEMPLATE_NAME,
            description=(
                "Публичный шаблон SEO 2026 для сгенерированных маршрутных страниц"
            ),
        )
    else:
        template_id = modx.upsert_template(build_modx_template())

    entries: list[dict[str, Any]] = []
    try:
        for index, page in enumerate(pages, start=1):
            if page.alias in completed:
                entries.append(completed[page.alias])
                continue
            resource_id = upsert_generated_resource(
                modx, template_id, page, production=production
            )
            entries.append(_manifest_entry(page, resource_id))
            if production and (index % 10 == 0 or index == len(pages)):
                write_manifest(
                    args.manifest,
                    entries,
                    dry_run=False,
                    batch="seo-2026-all-minsk-routes",
                )
            if index % 25 == 0 or index == len(pages):
                print(f"Published {index}/{len(pages)} pages", flush=True)
    except Exception:
        if production and entries:
            write_manifest(
                args.manifest,
                entries,
                dry_run=False,
                batch="seo-2026-all-minsk-routes",
            )
        raise
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
        "--all-routes",
        action="store_true",
        help="Generate all 24 services for every unique approved Minsk route",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip resource IDs already saved in the manifest",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=ROOT / "outputs" / "seo-2026-minsk-uzda.json",
    )
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.all_routes and args.manifest == ROOT / "outputs" / "seo-2026-minsk-uzda.json":
        args.manifest = ROOT / "outputs" / "seo-2026-all-minsk-routes.json"
    if not args.batch_slug:
        args.batch_slug = f"{slugify_ru(args.city1)}-{slugify_ru(args.city2)}"
    entries = deploy_batch(args)
    write_manifest(
        args.manifest,
        entries,
        dry_run=args.dry_run,
        batch=("seo-2026-all-minsk-routes" if args.all_routes else "seo-2026-minsk-uzda"),
    )
    print(
        f"Prepared {len(entries)} pages; manifest: {args.manifest.resolve()}"
    )


if __name__ == "__main__":
    main()
