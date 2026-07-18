"""Build the MODX sources used for lead email and Telegram notifications."""

from __future__ import annotations


HOOK_NAME = "TelegramFormNotify"
EMAIL_CHUNK_NAME = "PerewozkiFormEmail"


def insert_telegram_hook(hooks: str) -> str:
    """Insert the notification hook before FormIt's email hook."""

    parts = [part.strip() for part in hooks.split(",") if part.strip()]
    if HOOK_NAME in parts:
        return ",".join(parts)
    index = parts.index("email") if "email" in parts else len(parts)
    parts.insert(index, HOOK_NAME)
    return ",".join(parts)


def build_telegram_hook_source() -> str:
    """Return the PHP source for the fail-open FormIt notification hook."""

    return r"""$token = trim((string) $modx->getOption('telegram_bot_token'));
$chatId = trim((string) $modx->getOption('telegram_chat_id'));

$values = $hook->getValues();
$escape = static function ($value) {
    return htmlspecialchars(
        trim((string) $value),
        ENT_QUOTES | ENT_SUBSTITUTE,
        'UTF-8'
    );
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

$pageTitle = $modx->resource
    ? (string) $modx->resource->get('pagetitle')
    : 'Perewozki.by';
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

if ($token === '' || $chatId === '') {
    $modx->log(
        modX::LOG_LEVEL_ERROR,
        'Telegram notification skipped: settings are empty'
    );
    return true;
}
if (!function_exists('curl_init')) {
    $modx->log(
        modX::LOG_LEVEL_ERROR,
        'Telegram notification failed: cURL is unavailable'
    );
    return true;
}

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

$payload = json_encode(
    [
        'chat_id' => $chatId,
        'text' => implode("\n", $lines),
        'parse_mode' => 'HTML',
        'disable_web_page_preview' => true,
    ],
    JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES
);
$url = 'https://api.telegram.org/bot' . $token . '/sendMessage';
$lastError = '';

for ($attempt = 0; $attempt < 2; $attempt++) {
    $curl = curl_init($url);
    curl_setopt_array(
        $curl,
        [
            CURLOPT_POST => true,
            CURLOPT_POSTFIELDS => $payload,
            CURLOPT_HTTPHEADER => ['Content-Type: application/json'],
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_CONNECTTIMEOUT => 4,
            CURLOPT_TIMEOUT => 8,
        ]
    );
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
    """Return a compact inline-styled email template for FormIt."""

    return """<!doctype html>
<html lang="ru">
<body style="margin:0;background:#f4f6f5;font-family:Arial,sans-serif;color:#17212b">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0"
         style="background:#f4f6f5">
    <tr>
      <td align="center" style="padding:24px 12px">
        <table role="presentation" width="640" cellspacing="0" cellpadding="0"
               style="max-width:640px;width:100%;background:#fff;
                      border:1px solid #dfe6e2;border-radius:8px;overflow:hidden">
          <tr>
            <td style="background:#23725b;padding:20px 24px;color:#fff">
              <div style="font-size:12px;letter-spacing:.08em;text-transform:uppercase">
                Perewozki.by
              </div>
              <div style="font-size:24px;font-weight:700;margin-top:6px">
                Новая заявка
              </div>
            </td>
          </tr>
          <tr>
            <td style="padding:24px">
              <p style="margin:0 0 18px;font-size:16px;line-height:1.45">
                <strong>[[+lead_page_title:htmlent]]</strong><br>
                <a href="[[+lead_page_url:htmlent]]" style="color:#23725b">
                  [[+lead_page_url:htmlent]]
                </a>
              </p>
              <table role="presentation" width="100%" cellspacing="0" cellpadding="9"
                     style="border-collapse:collapse;font-size:15px;line-height:1.4">
                <tr style="border-top:1px solid #edf1ef">
                  <td style="color:#66736d;width:130px">Имя</td>
                  <td><strong>[[+lead_name:htmlent]]</strong></td>
                </tr>
                <tr style="border-top:1px solid #edf1ef">
                  <td style="color:#66736d">Телефон</td>
                  <td><strong>[[+lead_phone:htmlent]]</strong></td>
                </tr>
                <tr style="border-top:1px solid #edf1ef">
                  <td style="color:#66736d">Email</td>
                  <td>[[+lead_email:htmlent]]</td>
                </tr>
                <tr style="border-top:1px solid #edf1ef">
                  <td style="color:#66736d;vertical-align:top">Сообщение</td>
                  <td>[[+lead_message:htmlent]]</td>
                </tr>
                <tr style="border-top:1px solid #edf1ef">
                  <td style="color:#66736d">Получено</td>
                  <td>[[+lead_received_at:htmlent]]</td>
                </tr>
              </table>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""
