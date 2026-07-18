"""Deploy Telegram and branded email notifications to the live MODX site."""

from __future__ import annotations

import os
import re
from typing import Any

from scripts.deploy_modx_preview import ModxClient
from scripts.telegram_notifications import (
    EMAIL_CHUNK_NAME,
    HOOK_NAME,
    build_email_template_source,
    build_telegram_hook_source,
    insert_telegram_hook,
)


AJAXFORM_RE = re.compile(r"\[\[!AjaxForm\?(.*?)\]\]", re.DOTALL)
HOOKS_RE = re.compile(r"(&hooks=`)([^`]+)(`)")
EMAIL_TPL_RE = re.compile(r"&emailTpl=`[^`]*`")


def patch_ajaxform_config(chunk_content: str) -> tuple[str, int]:
    """Connect the hook and email template to every configured AjaxForm."""

    changed = 0

    def patch_call(call_match: re.Match[str]) -> str:
        nonlocal changed
        body = call_match.group(1)
        hooks_match = HOOKS_RE.search(body)
        if hooks_match is None:
            return call_match.group(0)

        hooks = insert_telegram_hook(hooks_match.group(2))
        patched = HOOKS_RE.sub(
            lambda match: f"{match.group(1)}{hooks}{match.group(3)}",
            body,
            count=1,
        )
        if EMAIL_TPL_RE.search(patched):
            patched = EMAIL_TPL_RE.sub(
                f"&emailTpl=`{EMAIL_CHUNK_NAME}`",
                patched,
                count=1,
            )
        else:
            patched += f"\n    &emailTpl=`{EMAIL_CHUNK_NAME}`"

        if patched != body:
            changed += 1
        return f"[[!AjaxForm?{patched}]]"

    return AJAXFORM_RE.sub(patch_call, chunk_content), changed


def _find_element(
    client: ModxClient,
    *,
    action: str,
    name_field: str,
    name: str,
) -> dict[str, Any] | None:
    result = client.call(
        action,
        start=0,
        limit=1000,
        sort=name_field,
        dir="ASC",
    )
    return next(
        (item for item in result.get("results", []) if item.get(name_field) == name),
        None,
    )


def upsert_snippet(client: ModxClient, source: str) -> int:
    """Create or update the server-side FormIt hook."""

    current = _find_element(
        client,
        action="element/snippet/getlist",
        name_field="name",
        name=HOOK_NAME,
    )
    values = {
        "name": HOOK_NAME,
        "description": "Отправка заявки Perewozki.by в Telegram",
        "snippet": source,
        "category": 0,
        "source": 1,
        "static": 0,
    }
    if current:
        client.call("element/snippet/update", id=current["id"], **values)
        return int(current["id"])
    created = client.call("element/snippet/create", **values)
    return int(created["object"]["id"])


def upsert_chunk(client: ModxClient, content: str) -> int:
    """Create or update the branded FormIt email chunk."""

    current = _find_element(
        client,
        action="element/chunk/getlist",
        name_field="name",
        name=EMAIL_CHUNK_NAME,
    )
    values = {
        "name": EMAIL_CHUNK_NAME,
        "description": "HTML-письмо о новой заявке Perewozki.by",
        "snippet": content,
        "category": 0,
        "source": 1,
        "static": 0,
    }
    if current:
        client.call("element/chunk/update", id=current["id"], **values)
        return int(current["id"])
    created = client.call("element/chunk/create", **values)
    return int(created["object"]["id"])


def upsert_setting(client: ModxClient, key: str, value: str) -> None:
    """Store a secret operational setting without printing its value."""

    result = client.call(
        "system/settings/getlist",
        start=0,
        limit=1000,
        query=key,
        sort="key",
        dir="ASC",
    )
    current = next(
        (item for item in result.get("results", []) if item.get("key") == key),
        None,
    )
    values = {
        "key": key,
        "value": value,
        "xtype": "textfield",
        "namespace": "core",
        "area": "telegram",
    }
    if current:
        client.call("system/settings/update", **values)
        return
    client.call("system/settings/create", **values)


def update_footer(client: ModxClient) -> int:
    """Patch the shared footer chunk and return the number of changed forms."""

    current = _find_element(
        client,
        action="element/chunk/getlist",
        name_field="name",
        name="footer",
    )
    if current is None:
        raise RuntimeError("MODX footer chunk was not found")

    result = client.call("element/chunk/get", id=current["id"])
    chunk = result.get("object") or {}
    source = str(chunk.get("snippet") or "")
    patched, changed = patch_ajaxform_config(source)
    form_count = len(AJAXFORM_RE.findall(source))
    if form_count != 4:
        raise RuntimeError(f"Expected 4 AjaxForm calls in footer, found {form_count}")
    if changed:
        client.call(
            "element/chunk/update",
            id=current["id"],
            name="footer",
            description=chunk.get("description", ""),
            snippet=patched,
            category=chunk.get("category", 0),
            source=chunk.get("source", 1),
            static=chunk.get("static", 0),
        )
    return changed


def _required_environment() -> dict[str, str]:
    names = (
        "PEREWOZKI_MODX_USER",
        "PEREWOZKI_MODX_PASSWORD",
        "PEREWOZKI_TELEGRAM_BOT_TOKEN",
        "PEREWOZKI_TELEGRAM_CHAT_ID",
    )
    values = {name: os.environ.get(name, "").strip() for name in names}
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise RuntimeError(
            "Missing required environment variables: " + ", ".join(missing)
        )
    return values


def main() -> int:
    """Deploy all notification components without exposing credentials."""

    env = _required_environment()
    client = ModxClient(
        env["PEREWOZKI_MODX_USER"],
        env["PEREWOZKI_MODX_PASSWORD"],
    )
    snippet_id = upsert_snippet(client, build_telegram_hook_source())
    email_chunk_id = upsert_chunk(client, build_email_template_source())
    upsert_setting(
        client,
        "telegram_bot_token",
        env["PEREWOZKI_TELEGRAM_BOT_TOKEN"],
    )
    upsert_setting(
        client,
        "telegram_chat_id",
        env["PEREWOZKI_TELEGRAM_CHAT_ID"],
    )
    changed_forms = update_footer(client)
    client.call("system/clearcache")

    print(f"snippet_id={snippet_id}")
    print(f"email_chunk_id={email_chunk_id}")
    print(f"changed_forms={changed_forms}")
    print("settings_configured=true")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
