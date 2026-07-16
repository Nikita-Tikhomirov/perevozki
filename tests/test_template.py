
from __future__ import annotations

import re
import unittest
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX_PATH = ROOT / "index.html"
CSS_PATH = ROOT / "assets" / "styles.css"

EXPECTED_SECTION_ORDER = [
    "intro",
    "prices",
    "private-clients",
    "business-clients",
    "process",
    "fleet",
    "benefits",
    "quick-contact",
    "faq",
    "gallery",
    "contact",
    "cities",
]

PRIVATE_SERVICES = [
    "Квартирный переезд",
    "Домашний переезд",
    "Перевозка мебели",
    "Перевозка бытовой техники",
    "Перевозка личных вещей",
    "Перевозка стройматериалов",
    "Перевозка покупок",
    "Перевозка на дачу",
]

BUSINESS_SERVICES = [
    "Перевозка товаров",
    "Перевозка оборудования",
    "Перевозка коммерческих грузов",
    "Доставка по магазинам",
    "Доставка на склады",
    "Перевозка офисной мебели",
    "Перевозка документов",
    "Регулярные перевозки",
]

SERVICE_LINKS = {
    "Квартирный переезд": "/gruzoperevozki-pereezd",
    "Домашний переезд": "/",
    "Перевозка мебели": "/perevozka-mebeli",
    "Перевозка бытовой техники": "/perevezti-xolodilnik",
    "Перевозка личных вещей": "/perevozka-veshhej",
    "Перевозка стройматериалов": "/perevozka-stroitelnyix-gruzov",
    "Перевозка покупок": "/",
    "Перевозка на дачу": "/perevezti-mebel-na-dachu",
    "Перевозка товаров": "/",
    "Перевозка оборудования": "/",
    "Перевозка коммерческих грузов": "/",
    "Доставка по магазинам": "/",
    "Доставка на склады": "/",
    "Перевозка офисной мебели": "/ofisnyij-pereezd-minsk",
    "Перевозка документов": "/",
    "Регулярные перевозки": "/gruzoperevozki-po-belarusi",
}


class TemplateParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.section_ids: list[str] = []
        self.headings: dict[str, list[str]] = {"h1": [], "h2": [], "h3": []}
        self.images: list[dict[str, str]] = []
        self.links: list[str] = []
        self.details_count = 0
        self._heading_tag: str | None = None
        self._heading_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key: value or "" for key, value in attrs}
        if tag == "section" and values.get("id"):
            self.section_ids.append(values["id"])
        if tag in self.headings:
            self._heading_tag = tag
            self._heading_parts = []
        if tag == "img":
            self.images.append({"src": values.get("src", ""), "alt": values.get("alt", "")})
        if tag == "a":
            self.links.append(values.get("href", ""))
        if tag == "details":
            self.details_count += 1

    def handle_endtag(self, tag: str) -> None:
        if tag == self._heading_tag:
            self.headings[tag].append(" ".join("".join(self._heading_parts).split()))
            self._heading_tag = None
            self._heading_parts = []

    def handle_data(self, data: str) -> None:
        if self._heading_tag:
            self._heading_parts.append(data)


class RouteTemplateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.html = INDEX_PATH.read_text(encoding="utf-8")
        cls.document = TemplateParser()
        cls.document.feed(cls.html)
        cls.visible_text = " ".join(re.sub(r"<[^>]+>", " ", cls.html).split())

    def test_sections_follow_docx_order(self) -> None:
        actual = [item for item in self.document.section_ids if item in EXPECTED_SECTION_ORDER]
        self.assertEqual(actual, EXPECTED_SECTION_ORDER)
        self.assertNotIn('id="cargo-types"', self.html)

    def test_h1_and_xlsx_intro_are_exact(self) -> None:
        self.assertEqual(self.document.headings["h1"], ["Перевозка грузов Минск – Узда"])
        self.assertIn(
            "Перевозка грузов Минск – Узда с компанией Perewozki.by — это надежный способ быстро и безопасно доставить любые грузы.",
            self.visible_text,
        )

    def test_client_city_declension_is_used(self) -> None:
        self.assertNotIn("Уздай", self.html)
        self.assertIn("между Минском и Уздой", self.visible_text)

    def test_price_block_matches_docx_table(self) -> None:
        for fragment in (
            "Грузовые машины до 1,5 тонн",
            "Грузовые машины от 1,5 тонн до 2 тонн",
            "Грузовые машины от 2 тонн до 3 тонн",
            "Грузовые машины от 3 тонн до 5 тонн",
            "от 35 BYN/1 час",
            "от 0,90 BYN/1 км",
            "от 40 BYN/1 час",
            "от 0,95 BYN/1 км",
            "от 45 BYN/1 час",
            "от 1,3 BYN/1 км",
            "Услуги грузчиков от 10 BYN/час",
            "Минимальный заказ 2 часа",
        ):
            self.assertIn(fragment, self.visible_text)

    def test_private_and_business_cards_match_docx(self) -> None:
        for item in PRIVATE_SERVICES + BUSINESS_SERVICES:
            self.assertIn(item, self.visible_text)
        self.assertEqual(self.html.count('data-audience="private"'), 8)
        self.assertEqual(self.html.count('data-audience="business"'), 8)
        self.assertEqual(self.html.count("seo-card-art seo-private-art"), 8)
        self.assertEqual(self.html.count("seo-card-art seo-business-art"), 8)
        self.assertTrue((ROOT / "assets" / "private-services-sprite.jpg").exists())
        self.assertTrue((ROOT / "assets" / "business-services-sprite.jpg").exists())

    def test_service_cards_link_to_existing_site_pages_or_home(self) -> None:
        self.assertEqual(self.html.count('class="seo-service-card-link"'), 16)
        for label, href in SERVICE_LINKS.items():
            pattern = (
                rf'<a class="seo-service-card-link" href="{re.escape(href)}">'
                rf'.*?<h3>{re.escape(label)}</h3>'
            )
            self.assertRegex(self.html, pattern)

    def test_five_ton_card_uses_large_client_truck(self) -> None:
        self.assertIn('src="assets/photos/truck-5t.jpg"', self.html)
        photo = ROOT / "assets" / "photos" / "truck-5t.jpg"
        self.assertTrue(photo.exists())
        self.assertGreater(photo.stat().st_size, 300_000)

    def test_order_steps_are_exact(self) -> None:
        positions = [self.visible_text.index(label) for label in (
            "Позвонили",
            "Назвали груз",
            "Получили стоимость",
            "Машина приехала",
        )]
        self.assertEqual(positions, sorted(positions))

    def test_modx_chunk_markers_are_in_required_positions(self) -> None:
        inquiry = self.html.index("MODX:S-QUESTION")
        process = self.html.index('id="process"')
        fleet = self.html.index('id="fleet"')
        services = self.html.index("MODX:S-SERVICES")
        advantages = self.html.index("MODX:S-ADV")
        gallery = self.html.index('id="gallery"')
        contact = self.html.index('id="contact"')
        self.assertLess(process, inquiry)
        self.assertLess(inquiry, fleet)
        self.assertLess(gallery, services)
        self.assertLess(services, contact)
        self.assertLess(fleet, advantages)
        self.assertLess(advantages, self.html.index('id="benefits"'))

    def test_faq_comes_from_first_xlsx_row(self) -> None:
        self.assertEqual(self.document.details_count, 12)
        self.assertIn("Вопросы и ответы о перевозке грузов Минск – Узда", self.visible_text)
        self.assertIn("Какие грузы вы перевозите по маршруту Минск – Узда?", self.visible_text)
        self.assertIn("Как оформить заказ на перевозку грузов Минск – Узда?", self.visible_text)

    def test_photo_heading_comes_from_xlsx(self) -> None:
        self.assertIn("Фотографии перевозки грузов Минск – Узда", self.document.headings["h2"])
        client_images = [image for image in self.document.images if image["src"].startswith("assets/photos/")]
        self.assertGreaterEqual(len(client_images), 7)
        self.assertTrue(all(image["alt"] for image in client_images))

    def test_real_contacts_are_used(self) -> None:
        self.assertIn("tel:+375297016011", self.document.links)
        self.assertIn("mailto:perewozki.by@mail.ru", self.document.links)
        self.assertTrue(any("wa.me/375297016011" in link for link in self.document.links))
        self.assertTrue(any("viber.click/375297016011" in link for link in self.document.links))

    def test_no_invented_or_foreign_brand_content(self) -> None:
        for forbidden in (
            "Около 1 часа 20 минут",
            "от 1,00 BYN/км",
            "Perevozkin.by",
            "ПЕРЕВОЗКИН",
            "фейковые отзывы",
        ):
            self.assertNotIn(forbidden, self.html)

    def test_site_palette_and_responsive_rules_exist(self) -> None:
        css = CSS_PATH.read_text(encoding="utf-8").lower()
        self.assertIn("--seo-green: #23725b", css)
        self.assertIn("--seo-green-dark: #1b5c45", css)
        self.assertIn("@media (max-width: 760px)", css)
        self.assertIn("font-family: rubik", css)
        self.assertIn("text-shadow: 1px 1px 1px", css)
        self.assertIn("private-services-sprite.jpg", css)
        self.assertIn("business-services-sprite.jpg", css)

    def test_directions_match_open_three_column_docx_design(self) -> None:
        self.assertEqual(self.html.count('class="seo-direction-column"'), 3)
        self.assertEqual(self.html.count('class="seo-direction-list"'), 6)
        self.assertNotIn("sell-card", self.html[self.html.index('id="cities"'):])
        self.assertNotIn("sell-card__open", self.html[self.html.index('id="cities"'):])

    def test_tall_sections_use_compact_layouts(self) -> None:
        css = CSS_PATH.read_text(encoding="utf-8")
        self.assertRegex(
            css,
            r"\.seo-benefit-list\s*\{[^}]*grid-template-columns:\s*repeat\(3,\s*minmax\(0,\s*1fr\)\)",
        )
        self.assertRegex(
            css,
            r"\.seo-contact-card\s*\{[^}]*height:\s*430px",
        )
        self.assertRegex(
            css,
            r"\.s-adv__card img\s*\{[^}]*display:\s*inline-block",
        )

    def test_new_sections_use_only_site_green_palette(self) -> None:
        css = CSS_PATH.read_text(encoding="utf-8").lower()
        self.assertNotIn("#f58b32", css)
        self.assertNotIn("#fff3e8", css)
        self.assertNotIn("seo-button-orange", self.html)
        self.assertEqual(self.html.count("seo-button-green"), 2)

    def test_gallery_cards_have_premium_overlay_structure(self) -> None:
        self.assertEqual(self.html.count("seo-gallery-card"), 3)
        self.assertEqual(self.html.count("seo-gallery-overlay"), 3)

    def test_generator_is_not_connected(self) -> None:
        lowered = self.html.lower()
        self.assertNotIn("openai", lowered)
        self.assertNotIn("generator", lowered)


if __name__ == "__main__":
    unittest.main()

