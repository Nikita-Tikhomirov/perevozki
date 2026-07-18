import unittest

from scripts.deploy_telegram_notifications import patch_ajaxform_config
from scripts.telegram_notifications import (
    build_email_template_source,
    build_telegram_hook_source,
    insert_telegram_hook,
)


class TelegramNotificationSourceTests(unittest.TestCase):
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


class TelegramNotificationDeploymentTests(unittest.TestCase):
    def test_patch_updates_all_four_ajaxforms(self):
        source = "\n".join(
            "[[!AjaxForm? &hooks=`rcv3,FormItSaveForm,email`]]" for _ in range(4)
        )
        patched, changed = patch_ajaxform_config(source)
        self.assertEqual(4, changed)
        self.assertEqual(
            4,
            patched.count("FormItSaveForm,TelegramFormNotify,email"),
        )
        self.assertEqual(4, patched.count("&emailTpl=`PerewozkiFormEmail`"))

    def test_patch_is_idempotent(self):
        source = (
            "[[!AjaxForm?\n"
            "    &hooks=`rcv3,FormItSaveForm,TelegramFormNotify,email`\n"
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


if __name__ == "__main__":
    unittest.main()
