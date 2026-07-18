"""Deploy Telegram and branded email notifications to the live MODX site."""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if __package__ in (None, ""):
    sys.path.insert(0, str(ROOT))

from scripts.deploy_modx_preview import ModxClient
from scripts.telegram_notifications import (
    EMAIL_CHUNK_NAME,
    HOOK_NAME,
    NORMALIZE_HOOK_NAME,
    QUICK_CALLBACK_CHUNK_NAME,
    build_email_template_source,
    build_normalize_hook_source,
    build_quick_callback_ajaxform_call,
    build_quick_callback_form_source,
    build_telegram_hook_source,
    insert_normalize_hook,
    insert_telegram_hook,
)


AJAXFORM_RE = re.compile(r"\[\[!AjaxForm\?(.*?)\]\]", re.DOTALL)
HOOKS_RE = re.compile(r"(&hooks=`)([^`]+)(`)")
EMAIL_TPL_RE = re.compile(r"&emailTpl=`[^`]*`")
QUICK_CALLBACK_FORM_RE = re.compile(
    r'<form\b[^>]*class=["\'][^"\']*\bs-questions__form\b[^"\']*["\'][^>]*>'
    r"[\s\S]*?</form>",
    re.IGNORECASE,
)


def _patch_ajaxform_config(
    chunk_content: str,
    *,
    include_telegram: bool,
) -> tuple[str, int]:
    """Connect the selected notification features to every AjaxForm."""

    changed = 0

    def patch_call(call_match: re.Match[str]) -> str:
        nonlocal changed
        body = call_match.group(1)
        hooks_match = HOOKS_RE.search(body)
        if hooks_match is None:
            return call_match.group(0)

        hooks = insert_normalize_hook(hooks_match.group(2))
        hooks = (
            insert_telegram_hook(hooks)
            if include_telegram
            else hooks
        )
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


def patch_email_template_config(chunk_content: str) -> tuple[str, int]:
    """Connect only the branded email template, leaving hooks unchanged."""

    return _patch_ajaxform_config(chunk_content, include_telegram=False)


def patch_ajaxform_config(chunk_content: str) -> tuple[str, int]:
    """Connect Telegram and the branded email template."""

    return _patch_ajaxform_config(chunk_content, include_telegram=True)


def replace_quick_callback_form(
    chunk_content: str,
    *,
    include_telegram: bool = True,
) -> tuple[str, int]:
    """Replace the non-functional visual form in s-question exactly once."""

    if QUICK_CALLBACK_CHUNK_NAME in chunk_content:
        return chunk_content, 0
    patched, changed = QUICK_CALLBACK_FORM_RE.subn(
        build_quick_callback_ajaxform_call(include_telegram=include_telegram),
        chunk_content,
        count=1,
    )
    return patched, changed


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


def upsert_snippet(
    client: ModxClient,
    *,
    name: str,
    description: str,
    source: str,
) -> int:
    """Create or update a server-side FormIt hook."""

    current = _find_element(
        client,
        action="element/snippet/getlist",
        name_field="name",
        name=name,
    )
    values = {
        "name": name,
        "description": description,
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


def upsert_chunk(
    client: ModxClient,
    content: str,
    *,
    name: str = EMAIL_CHUNK_NAME,
    description: str = "HTML-письмо о новой заявке Perewozki.by",
) -> int:
    """Create or update a reusable MODX chunk."""

    current = _find_element(
        client,
        action="element/chunk/getlist",
        name_field="name",
        name=name,
    )
    values = {
        "name": name,
        "description": description,
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


def update_quick_callback(
    client: ModxClient,
    *,
    include_telegram: bool = True,
) -> int:
    """Wire the shared questions block to the notification pipeline."""

    current = _find_element(
        client,
        action="element/chunk/getlist",
        name_field="name",
        name="s-question",
    )
    if current is None:
        raise RuntimeError("MODX s-question chunk was not found")

    result = client.call("element/chunk/get", id=current["id"])
    chunk = result.get("object") or {}
    source = str(chunk.get("snippet") or "")
    patched, changed = replace_quick_callback_form(
        source,
        include_telegram=include_telegram,
    )
    if not changed and QUICK_CALLBACK_CHUNK_NAME not in source:
        raise RuntimeError("Static callback form was not found in s-question")
    if changed:
        client.call(
            "element/chunk/update",
            id=current["id"],
            name="s-question",
            description=chunk.get("description", ""),
            snippet=patched,
            category=chunk.get("category", 0),
            source=chunk.get("source", 1),
            static=chunk.get("static", 0),
        )
    return changed


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


def update_footer(client: ModxClient, *, include_telegram: bool = True) -> int:
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
    if include_telegram:
        patched, changed = patch_ajaxform_config(source)
    else:
        patched, changed = patch_email_template_config(source)
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


def _required_environment(*, include_telegram: bool = True) -> dict[str, str]:
    names = [
        "PEREWOZKI_MODX_USER",
        "PEREWOZKI_MODX_PASSWORD",
    ]
    if include_telegram:
        names.extend(
            [
                "PEREWOZKI_TELEGRAM_BOT_TOKEN",
                "PEREWOZKI_TELEGRAM_CHAT_ID",
            ]
        )
    values = {name: os.environ.get(name, "").strip() for name in names}
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise RuntimeError(
            "Missing required environment variables: " + ", ".join(missing)
        )
    return values


def main(argv: list[str] | None = None) -> int:
    """Deploy all notification components without exposing credentials."""

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--email-only",
        action="store_true",
        help="Deploy the branded email template without Telegram settings",
    )
    args = parser.parse_args(argv)
    include_telegram = not args.email_only

    env = _required_environment(include_telegram=include_telegram)
    client = ModxClient(
        env["PEREWOZKI_MODX_USER"],
        env["PEREWOZKI_MODX_PASSWORD"],
    )
    email_chunk_id = upsert_chunk(client, build_email_template_source())
    quick_callback_chunk_id = upsert_chunk(
        client,
        build_quick_callback_form_source(),
        name=QUICK_CALLBACK_CHUNK_NAME,
        description="Компактная форма обратного звонка Perewozki.by",
    )
    normalize_snippet_id = upsert_snippet(
        client,
        name=NORMALIZE_HOOK_NAME,
        description="Нормализация полей заявок Perewozki.by",
        source=build_normalize_hook_source(),
    )
    snippet_id: int | None = None
    if include_telegram:
        snippet_id = upsert_snippet(
            client,
            name=HOOK_NAME,
            description="Отправка заявки Perewozki.by в Telegram",
            source=build_telegram_hook_source(),
        )
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
    changed_forms = update_footer(client, include_telegram=include_telegram)
    changed_quick_callback = update_quick_callback(
        client,
        include_telegram=include_telegram,
    )
    client.call("system/clearcache")

    print(f"snippet_id={snippet_id if snippet_id is not None else 'skipped'}")
    print(f"normalize_snippet_id={normalize_snippet_id}")
    print(f"email_chunk_id={email_chunk_id}")
    print(f"quick_callback_chunk_id={quick_callback_chunk_id}")
    print(f"changed_forms={changed_forms}")
    print(f"changed_quick_callback={changed_quick_callback}")
    print("settings_configured=true")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
