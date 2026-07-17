import unittest
from pathlib import Path

from bs4 import BeautifulSoup

from scripts.deploy_modx_generated import build_sitemap_content
from scripts.deploy_modx_preview import build_modx_content, build_modx_template, build_scoped_css


ROOT = Path(__file__).resolve().parents[1]


class ModxPreviewBuildTests(unittest.TestCase):
    def test_template_uses_only_structural_site_chunks(self):
        template = build_modx_template()
        for chunk in ("head", "header", "index-menu", "footer"):
            self.assertIn(chunk, template)
        self.assertIn("[[*content]]", template)
        for misplaced in ("s-services", "s-question", "s-about", "s-adv"):
            self.assertNotIn(misplaced, template)
        self.assertIn("styles.css?v=20260716-2", template)

    def test_production_template_does_not_add_noindex(self):
        template = build_modx_template(noindex=False)
        self.assertNotIn('name="robots"', template)
        self.assertIn(
            '<link rel="canonical" href="[[++site_url]][[*uri]]">',
            template,
        )
        self.assertIn("styles.css?v=20260716-2", template)

    def test_preview_template_does_not_claim_a_canonical(self):
        template = build_modx_template()
        self.assertNotIn('rel="canonical"', template)

    def test_sitemap_includes_hidden_searchable_resources(self):
        sitemap = build_sitemap_content()
        self.assertIn("[[!pdoSitemap?", sitemap)
        self.assertIn("&showHidden=`1`", sitemap)
        self.assertIn("&checkPermissions=`list`", sitemap)

    def test_content_connects_existing_blocks_in_docx_order(self):
        content = build_modx_content((ROOT / "index.html").read_text(encoding="utf-8"))
        self.assertIn('[[$s-question]]', content)
        self.assertIn('[[$s-services]]', content)
        self.assertIn('[[$s-adv]]', content)
        self.assertLess(content.index('id="process"'), content.index('[[$s-question]]'))
        self.assertLess(content.index('[[$s-question]]'), content.index('id="fleet"'))
        self.assertLess(content.index('id="gallery"'), content.index('[[$s-services]]'))
        self.assertLess(content.index('[[$s-services]]'), content.index('id="contact"'))
        self.assertLess(content.index('id="fleet"'), content.index('[[$s-adv]]'))
        self.assertLess(content.index('[[$s-adv]]'), content.index('id="benefits"'))
        self.assertNotIn('class="site-header"', content)
        self.assertNotIn('class="site-footer"', content)

    def test_deployment_rewrites_assets_and_modal_links(self):
        content = build_modx_content((ROOT / "index.html").read_text(encoding="utf-8"))
        self.assertIn('/assets/seo-preview-2026/photos/', content)
        self.assertIn('data-modal="#request"', content)
        soup = BeautifulSoup(content, "html.parser")
        modal_triggers = soup.select('[data-modal="#request"]')
        self.assertTrue(modal_triggers)
        self.assertTrue(all(trigger.name == "button" for trigger in modal_triggers))
        self.assertTrue(all(not trigger.has_attr("href") for trigger in modal_triggers))

        direction_links = soup.select("#cities .seo-direction-list a")
        self.assertEqual(118, len(direction_links))
        self.assertTrue(all(link.get("href", "").startswith("/") for link in direction_links))
        self.assertFalse(soup.select("#cities .seo-direction-list button"))

    def test_generated_service_sprites_are_uploaded(self):
        source = (ROOT / "scripts" / "deploy_modx_preview.py").read_text(encoding="utf-8")
        self.assertIn("private-services-sprite.jpg", source)
        self.assertIn("business-services-sprite.jpg", source)

    def test_css_is_scoped_to_new_content(self):
        css = build_scoped_css((ROOT / "assets" / "styles.css").read_text(encoding="utf-8"))
        self.assertTrue(css.startswith("@scope (.seo-route)"))
        self.assertIn("--seo-green: #23725b", css.lower())
        self.assertNotRegex(css, r"(?m)^\s*body\s*\{")


if __name__ == "__main__":
    unittest.main()

