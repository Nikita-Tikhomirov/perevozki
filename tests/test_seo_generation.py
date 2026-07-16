import unittest
from pathlib import Path

from bs4 import BeautifulSoup

from scripts.seo_generation import (
    BATCH_MARKER_PREFIX,
    build_all_route_pages,
    build_generated_pages,
    load_seo_rows,
    production_alias,
    replace_placeholders,
    slugify_ru,
    validate_resource_ownership,
)
from scripts.route_catalog import ROUTE_GROUPS, all_routes
from scripts.deploy_modx_generated import upsert_generated_resource
from scripts.deploy_modx_preview import build_modx_content


ROOT = Path(__file__).resolve().parents[1]
WORKBOOK = Path(
    "C:/Users/user/Downloads/Telegram Desktop/СЕО для ГЕНЕРАЦИИ.xlsx"
)


@unittest.skipUnless(WORKBOOK.exists(), "The supplied SEO workbook is not available")
class SeoWorkbookTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = load_seo_rows(WORKBOOK)
        cls._all_pages = None

    @classmethod
    def all_pages(cls):
        if cls._all_pages is None:
            cls._all_pages = build_all_route_pages(
                (ROOT / "index.html").read_text(encoding="utf-8"),
                cls.rows,
            )
        return cls._all_pages

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

    def test_full_generation_covers_every_unique_direction(self):
        routes = all_routes()
        self.assertEqual(6, len(ROUTE_GROUPS))
        self.assertEqual(118, len(routes))
        self.assertEqual(118, len({route.city for route in routes}))

        pages = self.all_pages()
        self.assertEqual(24 * 118, len(pages))
        self.assertEqual(len(pages), len({page.alias for page in pages}))
        self.assertTrue(all(not page.alias.startswith("seo-2026-") for page in pages))

    def test_route_page_has_real_internal_links_and_no_uzda_leakage(self):
        pages = self.all_pages()[:118]
        borisov = next(page for page in pages if page.city2 == "Борисов")
        soup = BeautifulSoup(borisov.html, "html.parser")

        self.assertEqual(
            "Перевозка грузов Минск – Борисов",
            soup.select_one("h1").get_text(" ", strip=True),
        )
        links = [
            (link.get_text(" ", strip=True), link.get("href", ""))
            for link in soup.select("#cities .seo-direction-list a")
        ]
        soup.select_one("#cities").decompose()
        self.assertNotIn("Узд", soup.get_text(" ", strip=True))
        self.assertEqual(118, len(links))
        self.assertTrue(all(href.startswith("/") for _, href in links))
        self.assertTrue(all(href != "#contact" for _, href in links))
        self.assertEqual(
            "/perevozka-gruzov-minsk-borisov/",
            next(href for text, href in links if "Борисов" in text),
        )
        modx_content = build_modx_content(
            borisov.html, populate_directions=False
        )
        self.assertIn('/perevozka-gruzov-minsk-borisov/', modx_content)
        self.assertNotIn('class="seo-direction-list"><li><button', modx_content)

    def test_variant_rotation_uses_all_five_excel_variants(self):
        pages = self.all_pages()[:118]
        self.assertEqual([1, 2, 3, 4, 5, 1], [page.variant for page in pages[:6]])


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

    def test_production_alias_is_query_and_route_specific(self):
        self.assertEqual(
            "gruzovoe-taksi-minsk-buda-koshelevo",
            production_alias("Грузовое такси", "Минск", "Буда-Кошелёво"),
        )


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

    def test_production_resource_is_indexable_and_cacheable(self):
        client = FakeModxClient()
        resource_id = upsert_generated_resource(
            client, 11, self.page, production=True
        )
        self.assertEqual(901, resource_id)
        action, values = client.calls[-1]
        self.assertEqual("resource/create", action)
        self.assertEqual(1, values["searchable"])
        self.assertEqual(1, values["cacheable"])
        self.assertEqual(0, values["syncsite"])

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
