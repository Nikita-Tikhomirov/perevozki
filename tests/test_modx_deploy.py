import unittest
from pathlib import Path

from scripts.deploy_modx_preview import (
    build_modx_content,
    build_modx_template,
    build_scoped_css,
)


ROOT = Path(__file__).resolve().parents[1]


class ModxPreviewBuildTests(unittest.TestCase):
    def test_template_reuses_existing_modx_blocks(self):
        template = build_modx_template()

        self.assertIn("[[$head:replace=", template)
        for chunk in ("header", "index-menu", "s-services", "s-question", "s-about", "s-adv", "footer"):
            self.assertIn(f"[[$%s]]" % chunk, template)
        self.assertIn("[[*content]]", template)
        self.assertIn("/assets/seo-preview-2026/styles.css", template)
        self.assertIn("noindex, nofollow", template)

    def test_content_contains_only_new_route_sections(self):
        content = build_modx_content((ROOT / "index.html").read_text(encoding="utf-8"))

        self.assertIn('class="seo-route"', content)
        self.assertIn('id="route"', content)
        self.assertIn('id="prices"', content)
        self.assertNotIn('class="site-header"', content)
        self.assertNotIn('class="site-footer"', content)
        self.assertNotIn('id="benefits"', content)
        self.assertNotIn('id="contact"', content)
        self.assertNotIn('class="other-services"', content)
        self.assertIn('data-modal="#request"', content)

    def test_css_is_scoped_to_new_content(self):
        css = build_scoped_css((ROOT / "assets" / "styles.css").read_text(encoding="utf-8"))

        self.assertTrue(css.startswith("@scope (.seo-route)"))
        self.assertIn("--color-accent: #23725b", css)
        self.assertNotIn(":scope,\nbutton,", css)
        self.assertNotIn("@scope (.site-header)", css)


if __name__ == "__main__":
    unittest.main()
