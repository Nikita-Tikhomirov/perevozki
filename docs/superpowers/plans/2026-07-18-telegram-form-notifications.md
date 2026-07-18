# Telegram Form Notifications Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Дублировать все заявки Perewozki.by из FormIt в Telegram клиента и заменить технический дамп FormIt на аккуратное HTML-письмо без отдельного сервера и без влияния ошибок Telegram на email или успешный ответ формы.

**Architecture:** В репозитории хранятся проверяемые источники PHP-snippets и HTML-шаблона письма, а также безопасный скрипт развертывания. `NormalizeFormLead` приводит поля четырёх форм к единому набору placeholder-полей до сохранения, `TelegramFormNotify` отправляет их в Telegram после сохранения, а `PerewozkiFormEmail` формирует письмо перед стандартным hook `email`.

**Implementation note:** Для безопасного независимого email-only развертывания нормализация выделена из Telegram-hook в отдельный `NormalizeFormLead`. Итоговый порядок hooks: `rcv3,NormalizeFormLead,FormItSaveForm,TelegramFormNotify,email`; в режиме `--email-only` Telegram-hook не добавляется.

**Tech Stack:** Python 3.10+, unittest, requests, MODX Revolution connectors, FormIt/AjaxForm, PHP/cURL, Telegram Bot API.

## Global Constraints

- Отдельный сервер и постоянно работающий процесс не используются.
- Токен бота и chat ID не сохраняются в Git, шаблонах или клиентском JavaScript.
- Существующие hooks `rcv3`, `FormItSaveForm` и `email` сохраняются.
- Ошибка Telegram не должна менять успешный ответ формы или мешать email.
- Пользовательские значения экранируются перед отправкой с `parse_mode=HTML`.
- Служебные поля FormIt и reCAPTCHA не выводятся в email.
- Все исходники и конфигурация репозитория сохраняются в UTF-8.

---

### Task 1: Проверяемый источник FormIt-hook

**Files:**
- Create: `scripts/telegram_notifications.py`
- Test: `tests/test_telegram_notifications.py`

**Interfaces:**
- Produces: `build_telegram_hook_source() -> str`
- Produces: `build_email_template_source() -> str`
- Produces: `insert_telegram_hook(hooks: str) -> str`

- [ ] **Step 1: Write the failing tests**

```python
from scripts.telegram_notifications import (
    build_email_template_source,
    build_telegram_hook_source,
    insert_telegram_hook,
)


def test_insert_hook_after_save_and_before_email():
    assert insert_telegram_hook("rcv3,FormItSaveForm,email") == (
        "rcv3,FormItSaveForm,TelegramFormNotify,email"
    )


def test_insert_hook_is_idempotent():
    hooks = "rcv3,FormItSaveForm,TelegramFormNotify,email"
    assert insert_telegram_hook(hooks) == hooks


def test_snippet_reads_secret_settings_and_escapes_values():
    source = build_telegram_hook_source()
    assert "telegram_bot_token" in source
    assert "telegram_chat_id" in source
    assert "htmlspecialchars" in source
    assert "parse_mode" in source
    assert "CURLOPT_TIMEOUT" in source
    assert "Telegram notification failed" in source
    assert source.rstrip().endswith("return true;")


def test_email_template_contains_only_normalized_fields():
    template = build_email_template_source()
    for placeholder in (
        "lead_page_title",
        "lead_page_url",
        "lead_name",
        "lead_phone",
        "lead_email",
        "lead_message",
        "lead_received_at",
    ):
        assert f"[[+{placeholder}]]" in template
    for technical in ("g-recaptcha-response", "savedForm.", "remote_addr"):
        assert technical not in template
    assert "#23725b" in template
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
python -m unittest tests.test_telegram_notifications -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.telegram_notifications'`.

- [ ] **Step 3: Implement the minimal source builder**

Create `scripts/telegram_notifications.py` with:

```python
from __future__ import annotations


HOOK_NAME = "TelegramFormNotify"


def insert_telegram_hook(hooks: str) -> str:
    parts = [part.strip() for part in hooks.split(",") if part.strip()]
    if HOOK_NAME in parts:
        return ",".join(parts)
    index = parts.index("email") if "email" in parts else len(parts)
    parts.insert(index, HOOK_NAME)
    return ",".join(parts)


def build_telegram_hook_source() -> str:
    return r"""<?php
$token = trim((string) $modx->getOption('telegram_bot_token'));
$chatId = trim((string) $modx->getOption('telegram_chat_id'));
if ($token === '' || $chatId === '') {
    $modx->log(modX::LOG_LEVEL_ERROR, 'Telegram notification skipped: settings are empty');
    return true;
}

$values = $hook->getValues();
$escape = static function ($value) {
    return htmlspecialchars(trim((string) $value), ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
};
$findValue = static function (array $source, array $prefixes) {
    foreach ($source as $key => $value) {
        foreach ($prefixes as $prefix) {
            if (preg_match('/^' . preg_quote($prefix, '/') . '\d*$/i', (string) $key)) {
                return is_scalar($value) ? trim((string) $value) : '';
            }
        }
    }
    return '';
};

$pageTitle = $modx->resource ? (string) $modx->resource->get('pagetitle') : 'Perewozki.by';
$pageUrl = $modx->resource
    ? $modx->makeUrl((int) $modx->resource->get('id'), '', '', 'full')
    : $modx->getOption('site_url');
$fields = [
    'Имя' => $findValue($values, ['name']),
    'Телефон' => $findValue($values, ['phone']),
    'Email' => $findValue($values, ['email']),
    'Сообщение' => $findValue($values, ['text', 'message']),
];
$receivedAt = date('d.m.Y H:i');
$normalized = [
    'lead_page_title' => $pageTitle,
    'lead_page_url' => $pageUrl,
    'lead_name' => $fields['Имя'],
    'lead_phone' => $fields['Телефон'],
    'lead_email' => $fields['Email'],
    'lead_message' => $fields['Сообщение'],
    'lead_received_at' => $receivedAt,
];
foreach ($normalized as $key => $value) {
    $hook->setValue($key, $value);
}
$hook->formit->config['emailSubject'] = 'Новая заявка с Perewozki.by'
    . ($fields['Телефон'] !== '' ? ' — ' . $fields['Телефон'] : '');

$lines = [
    '<b>Новая заявка с Perewozki.by</b>',
    '<b>Страница:</b> ' . $escape($pageTitle),
    '<b>URL:</b> ' . $escape($pageUrl),
];
foreach ($fields as $label => $value) {
    if ($value !== '') {
        $lines[] = '<b>' . $escape($label) . ':</b> ' . $escape($value);
    }
}
$lines[] = '<b>Время:</b> ' . $escape($receivedAt);

$payload = json_encode([
    'chat_id' => $chatId,
    'text' => implode("\n", $lines),
    'parse_mode' => 'HTML',
    'disable_web_page_preview' => true,
], JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);

$url = 'https://api.telegram.org/bot' . $token . '/sendMessage';
$lastError = '';
for ($attempt = 0; $attempt < 2; $attempt++) {
    $curl = curl_init($url);
    curl_setopt_array($curl, [
        CURLOPT_POST => true,
        CURLOPT_POSTFIELDS => $payload,
        CURLOPT_HTTPHEADER => ['Content-Type: application/json'],
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_CONNECTTIMEOUT => 4,
        CURLOPT_TIMEOUT => 8,
    ]);
    $response = curl_exec($curl);
    $status = (int) curl_getinfo($curl, CURLINFO_HTTP_CODE);
    $lastError = curl_error($curl);
    curl_close($curl);
    if ($response !== false && $status >= 200 && $status < 300) {
        return true;
    }
}

$modx->log(
    modX::LOG_LEVEL_ERROR,
    'Telegram notification failed: HTTP request did not succeed; ' . $lastError
);
return true;"""


def build_email_template_source() -> str:
    return """<!doctype html>
<html lang="ru">
<body style="margin:0;background:#f4f6f5;font-family:Arial,sans-serif;color:#17212b">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0">
    <tr><td align="center" style="padding:24px 12px">
      <table role="presentation" width="640" cellspacing="0" cellpadding="0"
             style="max-width:640px;width:100%;background:#fff;border:1px solid #dfe6e2">
        <tr><td style="background:#23725b;padding:20px 24px;color:#fff">
          <div style="font-size:12px;letter-spacing:.08em;text-transform:uppercase">
            Perewozki.by
          </div>
          <div style="font-size:24px;font-weight:700;margin-top:6px">Новая заявка</div>
        </td></tr>
        <tr><td style="padding:24px">
          <p style="margin:0 0 18px"><strong>[[+lead_page_title]]</strong><br>
            <a href="[[+lead_page_url]]" style="color:#23725b">[[+lead_page_url]]</a>
          </p>
          <table role="presentation" width="100%" cellspacing="0" cellpadding="8"
                 style="border-collapse:collapse">
            <tr><td style="color:#66736d;width:130px">Имя</td><td><strong>[[+lead_name]]</strong></td></tr>
            <tr><td style="color:#66736d">Телефон</td><td><strong>[[+lead_phone]]</strong></td></tr>
            <tr><td style="color:#66736d">Email</td><td>[[+lead_email]]</td></tr>
            <tr><td style="color:#66736d">Сообщение</td><td>[[+lead_message]]</td></tr>
            <tr><td style="color:#66736d">Получено</td><td>[[+lead_received_at]]</td></tr>
          </table>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""
```

- [ ] **Step 4: Run tests and verify GREEN**

Run:

```powershell
python -m unittest tests.test_telegram_notifications -v
```

Expected: 3 tests PASS.

- [ ] **Step 5: Commit**

```powershell
git add scripts/telegram_notifications.py tests/test_telegram_notifications.py
git commit -m "feat: add telegram FormIt hook source"
```

---

### Task 2: Безопасное развертывание в MODX

**Files:**
- Create: `scripts/deploy_telegram_notifications.py`
- Modify: `tests/test_telegram_notifications.py`

**Interfaces:**
- Consumes: `build_telegram_hook_source()`, `build_email_template_source()` and `insert_telegram_hook()`
- Produces: `patch_ajaxform_config(chunk_content: str) -> tuple[str, int]`
- Produces: CLI requiring `PEREWOZKI_MODX_USER`, `PEREWOZKI_MODX_PASSWORD`, `PEREWOZKI_TELEGRAM_BOT_TOKEN`, `PEREWOZKI_TELEGRAM_CHAT_ID`

- [ ] **Step 1: Add failing deployment transformation tests**

```python
from scripts.deploy_telegram_notifications import patch_ajaxform_config


def test_patch_updates_all_four_ajaxforms():
    source = "\n".join(
        "[[!AjaxForm? &hooks=`rcv3,FormItSaveForm,email`]]" for _ in range(4)
    )
    patched, changed = patch_ajaxform_config(source)
    assert changed == 4
    assert patched.count("FormItSaveForm,TelegramFormNotify,email") == 4
    assert patched.count("&emailTpl=`PerewozkiFormEmail`") == 4


def test_patch_does_not_duplicate_existing_hook():
    source = "[[!AjaxForm? &hooks=`rcv3,FormItSaveForm,TelegramFormNotify,email`]]"
    patched, changed = patch_ajaxform_config(source)
    assert changed == 0
    assert patched == source
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
python -m unittest tests.test_telegram_notifications -v
```

Expected: FAIL because `scripts.deploy_telegram_notifications` does not exist.

- [ ] **Step 3: Implement deployment script**

Create `scripts/deploy_telegram_notifications.py` that:

1. imports `ModxClient` from `scripts.deploy_modx_preview`;
2. validates all four environment variables and never prints their values;
3. upserts snippet `TelegramFormNotify` through `element/snippet/getlist`,
   `element/snippet/create`, or `element/snippet/update`;
4. upserts chunk `PerewozkiFormEmail` through `element/chunk/getlist`,
   `element/chunk/create`, or `element/chunk/update`;
5. upserts settings `telegram_bot_token` and `telegram_chat_id` through
   `system/settings/create` or `system/settings/update`;
6. reads the `footer` chunk, applies `patch_ajaxform_config`, requires exactly
   four changed AjaxForm calls on first deployment or zero on an idempotent run,
   and updates the chunk with `element/chunk/update`;
7. clears MODX cache using `system/clearcache`;
8. prints only snippet ID, email chunk ID, changed form count, and
   `settings_configured=true`.

The transformer implementation must use the existing backtick-delimited
`&hooks` property:

```python
import re

from scripts.telegram_notifications import insert_telegram_hook


AJAXFORM_RE = re.compile(r"\[\[!AjaxForm\?(.*?)\]\]", re.DOTALL)
HOOKS_RE = re.compile(r"(&hooks=`)([^`]+)(`)")


def patch_ajaxform_config(chunk_content: str) -> tuple[str, int]:
    changed = 0

    def patch_call(call_match: re.Match[str]) -> str:
        nonlocal changed
        body = call_match.group(1)
        hooks_match = HOOKS_RE.search(body)
        if hooks_match is None:
            return call_match.group(0)
        hooks = insert_telegram_hook(hooks_match.group(2))
        patched = HOOKS_RE.sub(
            rf"\1{hooks}\3",
            body,
            count=1,
        )
        if "&emailTpl=`" in patched:
            patched = re.sub(
                r"&emailTpl=`[^`]*`",
                "&emailTpl=`PerewozkiFormEmail`",
                patched,
                count=1,
            )
        else:
            patched += "\n    &emailTpl=`PerewozkiFormEmail`"
        if patched != body:
            changed += 1
        return f"[[!AjaxForm?{patched}]]"

    return AJAXFORM_RE.sub(patch_call, chunk_content), changed
```

- [ ] **Step 4: Run focused and full tests**

Run:

```powershell
python -m unittest tests.test_telegram_notifications -v
python -m unittest discover -s tests -v
C:\Users\user\.codex\scripts\harness.cmd smoke
```

Expected: all unit tests PASS and smoke exits 0.

- [ ] **Step 5: Commit**

```powershell
git add scripts/deploy_telegram_notifications.py tests/test_telegram_notifications.py
git commit -m "feat: deploy telegram notifications to MODX"
```

---

### Task 3: Создание бота и сквозная проверка

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: live MODX deployment CLI from Task 2
- Produces: working bot, numeric chat ID, verified email and Telegram delivery

- [ ] **Step 1: Create the bot**

In the authenticated Telegram session:

1. open `@BotFather`;
2. send `/newbot`;
3. use display name `Perewozki.by — заявки`;
4. try username `PerewozkiByLeadsBot`, then `PerewozkiByOrdersBot` if occupied;
5. copy the generated token directly into the deployment environment without
   adding it to a file or chat report.

- [ ] **Step 2: Activate the recipient**

Send the bot link to `@alexei_1011` and ask the client to press `/start`.
After `/start`, call `getUpdates` once, select the update whose sender username
is `alexei_1011`, and use only its numeric `message.chat.id`.

- [ ] **Step 3: Deploy secrets and hook**

Set the four required environment variables only in the current process and run:

```powershell
python scripts/deploy_telegram_notifications.py
```

Expected:

```text
snippet_id=<number>
email_chunk_id=<number>
changed_forms=4
settings_configured=true
```

On a repeated deployment, expected `changed_forms=0`.

- [ ] **Step 4: Send one labeled end-to-end test**

Submit the live request form with:

```text
Имя: ТЕСТ EMAIL + TELEGRAM
Телефон: +375290000000
Email: perewozki.by@mail.ru
Сообщение: Сквозной тест после подключения. Не обрабатывать.
```

Expected:

- AjaxForm clears the fields and returns success;
- FormIt contains the new record;
- Mail.ru receives the email;
- email contains only the branded lead card and no reCAPTCHA/FormIt dump;
- `@alexei_1011` receives one Telegram message with page title, URL and fields.

- [ ] **Step 5: Check logs and document operation**

Confirm no new `SMTP`, `Telegram notification failed`, PHP warning, or fatal
entries in `core/cache/logs/error.log`. Add to `README.md`:

```markdown
## Telegram-уведомления

Заявки дублируются серверным FormIt-hook `TelegramFormNotify`. Секреты находятся
только в системных настройках MODX `telegram_bot_token` и `telegram_chat_id`.
Повторное развертывание выполняется командой
`python scripts/deploy_telegram_notifications.py` с четырьмя переменными
окружения, перечисленными в самом скрипте.
```

- [ ] **Step 6: Final verification, commit, and push**

Run:

```powershell
python -m unittest discover -s tests -v
C:\Users\user\.codex\scripts\harness.cmd gate
git diff --check
git status --short
```

Expected: tests and gate PASS; diff check is clean; only intended README change
is uncommitted.

Then:

```powershell
git add README.md
git commit -m "docs: document telegram notifications"
git push
```
