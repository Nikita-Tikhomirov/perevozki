
"""Build and publish the isolated SEO-template preview in MODX.

Credentials are read from environment variables and are never stored in the
repository. The deployment creates or updates one MODX template, one hidden
resource, and a dedicated directory under ``/assets``.
"""

from __future__ import annotations

import io
import os
import sys
from ftplib import FTP, error_perm
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup, Comment, NavigableString
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


ROOT = Path(__file__).resolve().parents[1]
if __package__ in (None, ""):
    sys.path.insert(0, str(ROOT))
BASE_URL = "https://perewozki.by"
RESOURCE_ALIAS = "seo-preview-2026"
TEMPLATE_NAME = "SEO 2026 — предпросмотр"
REMOTE_ASSET_DIR = "/www/perewozki.by/assets/seo-preview-2026"
HTTP_TIMEOUT = 90


def build_modx_template(*, noindex: bool = True) -> str:
    """Return a template that reuses the site's existing structural chunks."""

    robots = '<meta name="robots" content="noindex, nofollow">' if noindex else ""
    return f"""[[$head:replace=`</head>=={robots}<link rel="stylesheet" href="/assets/seo-preview-2026/styles.css?v=20260716-2"></head>`]]
[[$header]]
[[$index-menu]]
[[*content]]
[[$footer]]
"""


def build_modx_content(
    source_html: str,
    *,
    direction_query: str = "Перевозка грузов",
    populate_directions: bool = True,
) -> str:
    """Extract only new route-page sections from the standalone prototype."""

    if populate_directions:
        from scripts.seo_generation import populate_direction_catalog

        source_html = populate_direction_catalog(source_html, direction_query)
    soup = BeautifulSoup(source_html, "html.parser")
    main = soup.find("main")
    sprite = soup.select_one("svg.seo-icons")
    if main is None or sprite is None:
        raise ValueError("Standalone prototype is missing main content or icon sprite")

    chunk_markers = {
        "MODX:S-QUESTION": "[[$s-question]]",
        "MODX:S-SERVICES": "[[$s-services]]",
        "MODX:S-ADV": "[[$s-adv]]",
    }
    for comment in main.find_all(string=lambda value: isinstance(value, Comment)):
        marker = str(comment).strip()
        if marker in chunk_markers:
            comment.replace_with(NavigableString(chunk_markers[marker]))

    for link in main.select('a[href="#contact"]'):
        link.name = "button"
        link.attrs.pop("href", None)
        link["type"] = "button"
        link["data-modal"] = "#request"

    for image in main.select('img[src^="assets/photos/"]'):
        image["src"] = image["src"].replace(
            "assets/photos/", "/assets/seo-preview-2026/photos/", 1
        )

    wrapper = soup.new_tag("div")
    wrapper["class"] = ["seo-route"]
    wrapper.append(sprite.extract())
    for child in list(main.children):
        wrapper.append(child.extract())
    return str(wrapper)


def build_scoped_css(source_css: str) -> str:
    """Scope prototype rules so existing MODX chunks retain their own styles."""

    scoped = source_css.replace(".seo-route", ":scope")
    return f"@scope (.seo-route) {{\n{scoped}\n}}\n"


class ModxClient:
    """Small authenticated client for the standard MODX connector."""

    def __init__(self, username: str, password: str) -> None:
        self.session = requests.Session()
        retries = Retry(
            total=4,
            connect=4,
            read=4,
            status=4,
            backoff_factor=1,
            status_forcelist=(502, 503, 504),
            allowed_methods=("GET", "POST"),
        )
        self.session.mount("https://", HTTPAdapter(max_retries=retries))
        self.session.get(f"{BASE_URL}/manager/", timeout=HTTP_TIMEOUT).raise_for_status()
        response = self.session.post(
            f"{BASE_URL}/manager/",
            data={
                "login_context": "mgr",
                "username": username,
                "password": password,
                "returnUrl": "/manager/",
                "login": "1",
            },
            timeout=HTTP_TIMEOUT,
        )
        response.raise_for_status()
        if "Панель управления" not in response.text:
            raise RuntimeError("MODX authentication failed")

        marker = 'auth: "'
        start = response.text.find(marker)
        if start < 0:
            raise RuntimeError("MODX authorization token was not found")
        start += len(marker)
        end = response.text.find('"', start)
        self.auth = response.text[start:end]

    def call(self, action: str, **data: Any) -> dict[str, Any]:
        response = self.session.post(
            f"{BASE_URL}/connectors/index.php",
            headers={"modAuth": self.auth},
            data={"action": action, **data},
            timeout=HTTP_TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()
        if not payload.get("success"):
            message = payload.get("message") or f"MODX action failed: {action}"
            details = payload.get("errors") or payload.get("object")
            if details:
                raise RuntimeError(f"{message}; details: {details}")
            raise RuntimeError(message)
        return payload

    def upsert_template(
        self,
        content: str,
        *,
        name: str = TEMPLATE_NAME,
        description: str = "Тестовый шаблон SEO 2026 с существующими блоками сайта",
    ) -> int:
        result = self.call(
            "element/template/getlist",
            start=0,
            limit=100,
            sort="templatename",
            dir="ASC",
        )
        current = next(
            (item for item in result.get("results", []) if item["templatename"] == name),
            None,
        )
        values = {
            "templatename": name,
            "description": description,
            "content": content,
            "category": 0,
            "source": 1,
            "static": 0,
        }
        if current:
            self.call("element/template/update", id=current["id"], **values)
            return int(current["id"])
        created = self.call("element/template/create", **values)
        return int(created["object"]["id"])

    def upsert_resource(self, template_id: int, content: str) -> int:
        result = self.call(
            "resource/getlist",
            start=0,
            limit=500,
            sort="id",
            dir="ASC",
            context_key="web",
        )
        current = next(
            (item for item in result.get("results", []) if item.get("alias") == RESOURCE_ALIAS),
            None,
        )
        values = {
            "pagetitle": "Перевозка грузов Минск – Узда",
            "longtitle": "Перевозка грузов Минск – Узда | Цена, заказать перевозку",
            "description": "Перевозка грузов Минск – Узда. Быстрая и надежная доставка по Беларуси. Собственный транспорт, опытные водители, доступные цены.",
            "alias": RESOURCE_ALIAS,
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
            self.call("resource/update", id=current["id"], **values)
            return int(current["id"])
        created = self.call("resource/create", **values)
        return int(created["object"]["id"])


def ensure_ftp_dir(ftp: FTP, remote_dir: str) -> None:
    """Create a directory tree without touching sibling paths."""

    ftp.cwd("/")
    for part in remote_dir.strip("/").split("/"):
        try:
            ftp.cwd(part)
        except error_perm:
            ftp.mkd(part)
            ftp.cwd(part)


def upload_assets(host: str, username: str, password: str, css: str) -> None:
    """Upload only the dedicated preview assets through FTP."""

    with FTP(host, timeout=45) as ftp:
        ftp.login(username, password)
        ftp.set_pasv(True)
        ensure_ftp_dir(ftp, REMOTE_ASSET_DIR)
        ftp.storbinary("STOR styles.css", io.BytesIO(css.encode("utf-8")))
        for sprite_name in (
            "private-services-sprite.jpg",
            "business-services-sprite.jpg",
        ):
            with (ROOT / "assets" / sprite_name).open("rb") as stream:
                ftp.storbinary(f"STOR {sprite_name}", stream)

        ensure_ftp_dir(ftp, f"{REMOTE_ASSET_DIR}/photos")
        for photo in sorted((ROOT / "assets" / "photos").glob("*.jpg")):
            with photo.open("rb") as stream:
                ftp.storbinary(f"STOR {photo.name}", stream)


def required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Required environment variable is missing: {name}")
    return value


def deploy() -> str:
    source_html = (ROOT / "index.html").read_text(encoding="utf-8")
    source_css = (ROOT / "assets" / "styles.css").read_text(encoding="utf-8")
    content = build_modx_content(source_html)
    css = build_scoped_css(source_css)

    upload_assets(
        required_env("FTP_HOST"),
        required_env("FTP_USERNAME"),
        required_env("FTP_PASSWORD"),
        css,
    )
    modx = ModxClient(
        required_env("MODX_USERNAME"),
        required_env("MODX_PASSWORD"),
    )
    template_id = modx.upsert_template(build_modx_template())
    resource_id = modx.upsert_resource(template_id, content)
    modx.call("system/clearcache")
    return f"{BASE_URL}/{RESOURCE_ALIAS}/ (resource {resource_id}, template {template_id})"


if __name__ == "__main__":
    print(deploy())

