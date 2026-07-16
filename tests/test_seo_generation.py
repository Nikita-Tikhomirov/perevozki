import unittest
from pathlib import Path

from bs4 import BeautifulSoup

from scripts.seo_generation import (
    BATCH_MARKER_PREFIX,
    build_generated_pages,
    load_seo_rows,
    replace_placeholders,
    slugify_ru,
    validate_resource_ownership,
)
from scripts.deploy_modx_generated import upsert_generated_resource


ROOT = Path(__file__).resolve().parents[1]
WORKBOOK = Path(
    "C:/Users/user/Downloads/Telegram Desktop/СЕО для ГЕНЕРАЦИИ.xlsx"
)


@unittest.skipUnless(WORKBOOK.exists(), "The supplied SEO workbook is not available")
class SeoWorkbookTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = load_seo_rows(WORKBOOK)

    def test_supplied_workbook_maps_all_24_rows(self):
        self.assertEqual(24, len(self.rows))
        first = self.rows[0]
        self.assertEqual("Перевозка грузов", first.query)
        self.assertEqual(5, len(first.titles))
        self.assertEqual(5, len(first.descriptions))
        self.assertEqual(5, len(first.intros))
        self.assertIn("стоимость перевозки грузов", first.price_intro.lower())
        self.assertIn("для частных лиц", first.private_intro.lower())
        self.assertIn("для бизнеса", first.business_intro.lower())
        self.assertTrue(first.faq_heading.startswith("Вопросы и ответы"))
        self.assertEqual(12, first.faq_html.count("<details"))
        self.assertTrue(first.contact_heading.startswith("Заказать"))
        self.assertTrue(first.gallery_heading.startswith("Фотографии"))
        self.assertEqual("Домашний переезд", self.rows[-1].query)

    def test_all_queries_have_unique_ascii_slugs(self):
        slugs = [slugify_ru(row.query) for row in self.rows]
        self.assertEqual(24, len(set(slugs)))
        self.assertEqual("perevozka-gruzov", slugs[0])
        self.assertEqual("gruzovoe-taksi", slugs[1])
        self.assertEqual("gruzoperevozki-do-5-tonn", slugs[18])
        for slug in slugs:
            self.assertRegex(slug, r"^[a-z0-9-]+$")

    def test_renderer_applies_excel_content_without_inventing_copy(self):
        pages = build_generated_pages(
            (ROOT / "index.html").read_text(encoding="utf-8"),
            self.rows,
            city1="Минск",
            city2="Узда",
            variant=1,
            batch_slug="minsk-uzda",
        )
        self.assertEqual(24, len(pages))
        self.assertEqual(24, len({page.alias for page in pages}))
        self.assertEqual(
            "seo-2026-perevozka-gruzov-minsk-uzda", pages[0].alias
        )
        self.assertEqual(
            "seo-2026-gruzovoe-taksi-minsk-uzda", pages[1].alias
        )

        taxi = pages[1]
        soup = BeautifulSoup(taxi.html, "html.parser")
        self.assertEqual(
            "Грузовое такси Минск – Узда | Заказать грузовую машину",
            soup.title.get_text(strip=True),
        )
        self.assertEqual("Грузовое такси Минск – Узда", soup.select_one("h1").get_text(strip=True))
        self.assertEqual(
            replace_placeholders(self.rows[1].intros[0], "Минск", "Узда"),
            soup.select_one("#intro .seo-intro-copy > p").get_text(" ", strip=True),
        )
        self.assertEqual(
            replace_placeholders(self.rows[1].price_intro, "Минск", "Узда"),
            soup.select_one("#prices .seo-price-lead > div > p").get_text(" ", strip=True),
        )
        self.assertEqual(
            "Грузовое такси для частных лиц",
            soup.select_one("#private-clients h2").get_text(" ", strip=True),
        )
        self.assertEqual(
            "Грузовое такси для бизнеса",
            soup.select_one("#business-clients h2").get_text(" ", strip=True),
        )
        self.assertEqual(12, len(soup.select("#faq .seo-faq-list details")))
        self.assertEqual(
            replace_placeholders(self.rows[1].gallery_heading, "Минск", "Узда"),
            soup.select_one("#gallery h2").get_text(" ", strip=True),
        )
        self.assertEqual(
            replace_placeholders(self.rows[1].contact_heading, "Минск", "Узда"),
            soup.select_one("#contact h2").get_text(" ", strip=True),
        )
        self.assertNotIn("{Город", taxi.html)
        self.assertIn(taxi.marker, taxi.html)


class SeoGenerationHelpersTests(unittest.TestCase):
    def test_placeholder_replacement_is_exact(self):
        self.assertEqual(
            "Маршрут Минск – Узда",
            replace_placeholders("Маршрут {Город1} – {Город2}", "Минск", "Узда"),
        )

    def test_resource_ownership_rejects_foreign_content(self):
        marker = f"{BATCH_MARKER_PREFIX}minsk-uzda"
        validate_resource_ownership(f"<!-- {marker} --><p>Owned</p>", marker, "safe")
        with self.assertRaisesRegex(RuntimeError, "Refusing to overwrite"):
            validate_resource_ownership("<p>Existing page</p>", marker, "foreign")


class FakeModxClient:
    def __init__(self, existing=None):
        self.existing = existing
        self.calls = []

    def call(self, action, **data):
        self.calls.append((action, data))
        if action == "resource/getlist":
            if data.get("query"):
                return {"results": [], "total": 0}
            results = [] if self.existing is None else [self.existing]
            return {"results": results, "total": len(results)}
        if action == "resource/get":
            return {"object": self.existing}
        if action == "resource/create":
            return {"object": {"id": 901}}
        if action == "resource/update":
            return {"object": {"id": data["id"]}}
        raise AssertionError(f"Unexpected action: {action}")


class ModxGenerationSafetyTests(unittest.TestCase):
    def setUp(self):
        self.page = type(
            "Page",
            (),
            {
                "query": "Грузовое такси",
                "alias": "seo-2026-gruzovoe-taksi-minsk-uzda",
                "title": "Грузовое такси Минск – Узда | Заказать",
                "description": "Описание",
                "marker": f"{BATCH_MARKER_PREFIX}minsk-uzda",
                "html": (
                    f"<!-- {BATCH_MARKER_PREFIX}minsk-uzda -->"
                    + (ROOT / "index.html").read_text(encoding="utf-8")
                ),
            },
        )()

    def test_new_resource_is_created_hidden_and_noindex_template_ready(self):
        client = FakeModxClient()
        resource_id = upsert_generated_resource(client, 10, self.page)
        self.assertEqual(901, resource_id)
        action, values = client.calls[-1]
        self.assertEqual("resource/create", action)
        self.assertEqual(1, values["published"])
        self.assertEqual(1, values["hidemenu"])
        self.assertEqual(0, values["searchable"])
        self.assertEqual(self.page.alias, values["alias"])

    def test_owned_resource_is_updated(self):
        existing = {
            "id": 700,
            "alias": self.page.alias,
            "content": self.page.html,
        }
        client = FakeModxClient(existing)
        self.assertEqual(700, upsert_generated_resource(client, 10, self.page))
        self.assertEqual("resource/update", client.calls[-1][0])

    def test_foreign_resource_is_never_updated(self):
        existing = {
            "id": 700,
            "alias": self.page.alias,
            "content": "<main>Existing production page</main>",
        }
        client = FakeModxClient(existing)
        with self.assertRaisesRegex(RuntimeError, "Refusing to overwrite"):
            upsert_generated_resource(client, 10, self.page)
        self.assertNotIn("resource/update", [action for action, _ in client.calls])


if __name__ == "__main__":
    unittest.main()
