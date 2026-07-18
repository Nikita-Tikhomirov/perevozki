import subprocess
import sys
import unittest
from pathlib import Path

from scripts.deploy_telegram_notifications import (
    patch_ajaxform_config,
    patch_email_template_config,
    replace_quick_callback_form,
)
from scripts.telegram_notifications import (
    QUICK_CALLBACK_CHUNK_NAME,
    build_email_template_source,
    build_normalize_hook_source,
    build_quick_callback_ajaxform_call,
    build_quick_callback_form_source,
    build_telegram_hook_source,
    insert_normalize_hook,
    insert_telegram_hook,
)


class TelegramNotificationSourceTests(unittest.TestCase):
    def test_insert_normalize_hook_before_save(self):
        self.assertEqual(
            "rcv3,NormalizeFormLead,FormItSaveForm,email",
            insert_normalize_hook("rcv3,FormItSaveForm,email"),
        )

    def test_normalize_hook_sets_email_fields_and_subject(self):
        source = build_normalize_hook_source()
        for field in (
            "lead_page_title",
            "lead_page_url",
            "lead_name",
            "lead_phone",
            "lead_email",
            "lead_message",
            "lead_received_at",
        ):
            self.assertIn(field, source)
        self.assertIn("emailSubject", source)
        self.assertTrue(source.rstrip().endswith("return true;"))

    def test_insert_hook_after_save_and_before_email(self):
        self.assertEqual(
            "rcv3,FormItSaveForm,TelegramFormNotify,email",
            insert_telegram_hook("rcv3,FormItSaveForm,email"),
        )

    def test_insert_hook_is_idempotent(self):
        hooks = "rcv3,FormItSaveForm,TelegramFormNotify,email"
        self.assertEqual(hooks, insert_telegram_hook(hooks))

    def test_snippet_reads_secret_settings_and_escapes_values(self):
        source = build_telegram_hook_source()
        self.assertIn("telegram_bot_token", source)
        self.assertIn("telegram_chat_id", source)
        self.assertIn("htmlspecialchars", source)
        self.assertIn("parse_mode", source)
        self.assertIn("CURLOPT_TIMEOUT", source)
        self.assertIn("Telegram notification failed", source)
        self.assertTrue(source.rstrip().endswith("return true;"))

    def test_email_template_contains_only_normalized_fields(self):
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
            self.assertIn(f"[[+{placeholder}:htmlent]]", template)
        for technical in ("g-recaptcha-response", "savedForm.", "remote_addr"):
            self.assertNotIn(technical, template)
        self.assertIn("#23725b", template)

    def test_quick_callback_form_is_ajaxform_ready(self):
        source = build_quick_callback_form_source()
        self.assertIn('class="s-questions__form ajax_form"', source)
        self.assertIn('method="post"', source)
        self.assertIn('name="phone33"', source)
        self.assertIn('name="g-recaptcha-response"', source)
        self.assertIn('type="submit"', source)
        self.assertIn("[[+fi.successMessage]]", source)

    def test_quick_callback_call_uses_notification_pipeline(self):
        call = build_quick_callback_ajaxform_call()
        self.assertIn(f"&form=`{QUICK_CALLBACK_CHUNK_NAME}`", call)
        self.assertIn(
            "&hooks=`rcv3,NormalizeFormLead,FormItSaveForm,"
            "TelegramFormNotify,email`",
            call,
        )
        self.assertIn("&emailTpl=`PerewozkiFormEmail`", call)
        self.assertIn("&validate=`phone33:required`", call)

    def test_quick_callback_email_only_call_skips_telegram(self):
        call = build_quick_callback_ajaxform_call(include_telegram=False)
        self.assertIn(
            "&hooks=`rcv3,NormalizeFormLead,FormItSaveForm,email`",
            call,
        )
        self.assertNotIn("TelegramFormNotify", call)


class TelegramNotificationDeploymentTests(unittest.TestCase):
    def test_deploy_script_help_runs_from_project_root(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [
                sys.executable,
                str(root / "scripts" / "deploy_telegram_notifications.py"),
                "--help",
            ],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("--email-only", result.stdout)

    def test_email_only_patch_does_not_add_telegram_hook(self):
        source = "[[!AjaxForm? &hooks=`rcv3,FormItSaveForm,email`]]"
        patched, changed = patch_email_template_config(source)
        self.assertEqual(1, changed)
        self.assertIn("&emailTpl=`PerewozkiFormEmail`", patched)
        self.assertIn("rcv3,NormalizeFormLead,FormItSaveForm,email", patched)
        self.assertNotIn("TelegramFormNotify", patched)

    def test_patch_updates_all_four_ajaxforms(self):
        source = "\n".join(
            "[[!AjaxForm? &hooks=`rcv3,FormItSaveForm,email`]]" for _ in range(4)
        )
        patched, changed = patch_ajaxform_config(source)
        self.assertEqual(4, changed)
        self.assertEqual(
            4,
            patched.count(
                "NormalizeFormLead,FormItSaveForm,TelegramFormNotify,email"
            ),
        )
        self.assertEqual(4, patched.count("&emailTpl=`PerewozkiFormEmail`"))

    def test_patch_is_idempotent(self):
        source = (
            "[[!AjaxForm?\n"
            "    &hooks=`rcv3,NormalizeFormLead,FormItSaveForm,"
            "TelegramFormNotify,email`\n"
            "    &emailTpl=`PerewozkiFormEmail`\n"
            "]]"
        )
        patched, changed = patch_ajaxform_config(source)
        self.assertEqual(0, changed)
        self.assertEqual(source, patched)

    def test_patch_replaces_an_existing_email_template(self):
        source = (
            "[[!AjaxForm?\n"
            "    &hooks=`rcv3,FormItSaveForm,email`\n"
            "    &emailTpl=`OldDumpTemplate`\n"
            "]]"
        )
        patched, changed = patch_ajaxform_config(source)
        self.assertEqual(1, changed)
        self.assertIn("&emailTpl=`PerewozkiFormEmail`", patched)
        self.assertNotIn("OldDumpTemplate", patched)

    def test_replace_quick_callback_form_preserves_surrounding_chunk(self):
        source = (
            '<section><h2>Остались вопросы?</h2>'
            '<form class="s-questions__form">'
            '<input type="text" placeholder="Ваш номер" />'
            "<button>Заказать звонок</button></form></section>"
        )
        patched, changed = replace_quick_callback_form(source)
        self.assertEqual(1, changed)
        self.assertTrue(patched.startswith("<section>"))
        self.assertTrue(patched.endswith("</section>"))
        self.assertIn("[[!AjaxForm?", patched)
        self.assertNotIn('<form class="s-questions__form">', patched)

    def test_replace_quick_callback_form_is_idempotent(self):
        source = "<section>" + build_quick_callback_ajaxform_call() + "</section>"
        patched, changed = replace_quick_callback_form(source)
        self.assertEqual(0, changed)
        self.assertEqual(source, patched)


if __name__ == "__main__":
    unittest.main()
