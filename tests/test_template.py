from __future__ import annotations

import re
import unittest
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX_PATH = ROOT / "index.html"
CSS_PATH = ROOT / "assets" / "styles.css"
JS_PATH = ROOT / "assets" / "app.js"

REQUIRED_SECTION_IDS = {
    "hero",
    "route",
    "prices",
    "private-clients",
    "business-clients",
    "process",
    "fleet",
    "benefits",
    "gallery",
    "faq",
    "contact",
    "cities",
}


class TemplateParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.ids: set[str] = set()
        self.headings: dict[str, list[str]] = {"h1": [], "h2": [], "h3": []}
        self.images: list[dict[str, str | bool]] = []
        self.links: list[str] = []
        self.stylesheets: list[str] = []
        self.scripts: list[str] = []
        self.form_actions: list[str] = []
        self.scenario_kinds: list[str] = []
        self.details_count = 0
        self._stack: list[str] = []
        self._heading_tag: str | None = None
        self._heading_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key: value or "" for key, value in attrs}
        element_id = values.get("id")
        if element_id:
            self.ids.add(element_id)

        if tag in self.headings:
            self._heading_tag = tag
            self._heading_parts = []

        if tag == "img":
            self.images.append(
                {
                    "src": values.get("src", ""),
                    "alt": values.get("alt", ""),
                    "inside_gallery": "gallery" in self._stack,
                }
            )
        elif tag == "a":
            self.links.append(values.get("href", ""))
        elif tag == "link" and "stylesheet" in values.get("rel", ""):
            self.stylesheets.append(values.get("href", ""))
        elif tag == "script" and values.get("src"):
            self.scripts.append(values["src"])
        elif tag == "form":
            self.form_actions.append(values.get("action", ""))
        elif tag == "details":
            self.details_count += 1

        scenario_kind = values.get("data-scenario")
        if scenario_kind:
            self.scenario_kinds.append(scenario_kind)

        if tag not in {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}:
            self._stack.append(element_id or tag)

    def handle_endtag(self, tag: str) -> None:
        if tag == self._heading_tag:
            text = " ".join("".join(self._heading_parts).split())
            self.headings[tag].append(text)
            self._heading_tag = None
            self._heading_parts = []
        if self._stack:
            self._stack.pop()

    def handle_data(self, data: str) -> None:
        if self._heading_tag:
            self._heading_parts.append(data)


class RouteTemplateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not INDEX_PATH.exists():
            raise AssertionError("index.html is missing")
        cls.html = INDEX_PATH.read_text(encoding="utf-8")
        cls.document = TemplateParser()
        cls.document.feed(cls.html)

    def test_page_has_one_route_h1(self) -> None:
        self.assertEqual(
            self.document.headings["h1"],
            ["Перевозка грузов Минск — Узда"],
        )

    def test_required_sections_are_present(self) -> None:
        self.assertTrue(REQUIRED_SECTION_IDS.issubset(self.document.ids))

    def test_private_and_business_scenarios_have_eight_items_each(self) -> None:
        self.assertEqual(self.document.scenario_kinds.count("private"), 8)
        self.assertEqual(self.document.scenario_kinds.count("business"), 8)

    def test_gallery_uses_real_images_with_alt_text(self) -> None:
        gallery_images = [
            image for image in self.document.images if image["inside_gallery"]
        ]
        self.assertGreaterEqual(len(gallery_images), 6)
        self.assertTrue(
            all(
                str(image["src"]).startswith("assets/photos/") and image["alt"]
                for image in gallery_images
            )
        )

    def test_faq_has_six_native_details(self) -> None:
        self.assertEqual(self.document.details_count, 6)

    def test_real_contact_links_are_present(self) -> None:
        links = set(self.document.links)
        self.assertIn("tel:+375297016011", links)
        self.assertIn("mailto:perewozki.by@mail.ru", links)
        self.assertTrue(any("wa.me/375297016011" in link for link in links))
        self.assertTrue(any("viber.click/375297016011" in link for link in links))
        self.assertTrue(any(link.startswith("https://t.me/") for link in links))

    def test_target_brand_is_perewozki_by(self) -> None:
        visible_text = re.sub(r"<[^>]+>", "", self.html)
        self.assertIn("PEREWOZKI.BY", visible_text)
        self.assertNotIn("Perevozkin.by", self.html)
        self.assertNotIn("ПЕРЕВОЗКИН", self.html)

    def test_page_loads_local_css_and_script(self) -> None:
        self.assertIn("assets/styles.css", self.document.stylesheets)
        self.assertIn("assets/app.js", self.document.scripts)
        self.assertTrue(CSS_PATH.exists())
        self.assertTrue(JS_PATH.exists())

    def test_form_is_demo_only(self) -> None:
        self.assertIn("data-demo-form", self.html)
        self.assertIn("data-demo-submit", self.html)
        self.assertNotIn("<form", self.html.lower())

    def test_phone_validation_requires_nine_digits(self) -> None:
        self.assertIn('pattern="[+0-9 ()-]{7,20}"', self.html)
        javascript = JS_PATH.read_text(encoding="utf-8")
        self.assertIn("phoneDigits.length < 9", javascript)

    def test_current_route_rates_are_used(self) -> None:
        self.assertIn("от 1,00 BYN/км", self.html)
        self.assertIn("от 1,20 BYN/км", self.html)
        self.assertIn("от 1,40 BYN/км", self.html)
        self.assertNotIn("от 160 BYN", self.html)

    def test_mobile_menu_has_complete_accessible_state(self) -> None:
        self.assertIn('aria-controls="main-navigation"', self.html)
        self.assertIn('id="main-navigation"', self.html)
        javascript = JS_PATH.read_text(encoding="utf-8")
        self.assertIn('open ? "Закрыть меню" : "Открыть меню"', javascript)

    def test_action_colors_meet_documented_aa_palette(self) -> None:
        css = CSS_PATH.read_text(encoding="utf-8").lower()
        self.assertIn("--color-accent: #23725b", css)
        self.assertIn("--color-messenger: #137a45", css)

    def test_generated_files_are_ignored(self) -> None:
        ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertIn("__pycache__/", ignore)
        self.assertIn("*.pyc", ignore)
        self.assertIn("harness/", ignore)

    def test_responsive_and_reduced_motion_contracts_exist(self) -> None:
        css = CSS_PATH.read_text(encoding="utf-8")
        self.assertIn("@media (max-width: 760px)", css)
        self.assertIn("prefers-reduced-motion", css)

    def test_generator_is_not_connected(self) -> None:
        lowered = self.html.lower()
        self.assertNotIn("xlsx", lowered)
        self.assertNotIn("generator", lowered)
        self.assertNotIn("openai", lowered)


if __name__ == "__main__":
    unittest.main()
