"""Read the approved SEO workbook and render route pages deterministically."""

from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree

from bs4 import BeautifulSoup

from scripts.route_catalog import ROUTE_GROUPS, all_routes


BATCH_MARKER_PREFIX = "SEO-GENERATED:seo-2026-"
PRODUCTION_MARKER = "SEO-GENERATED:seo-2026-production"
ALIAS_PREFIX = "seo-2026"
XLSX_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PACKAGE_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"


@dataclass(frozen=True)
class SeoRow:
    """One service row from the approved generation workbook."""

    query: str
    titles: tuple[str, ...]
    descriptions: tuple[str, ...]
    intros: tuple[str, ...]
    price_intro: str
    private_intro: str
    business_intro: str
    faq_heading: str
    faq_html: str
    contact_heading: str
    gallery_heading: str


@dataclass(frozen=True)
class GeneratedPage:
    """A generated standalone page and the MODX values derived from it."""

    query: str
    alias: str
    title: str
    description: str
    marker: str
    html: str
    city1: str
    city2: str
    variant: int


def _column_number(cell_reference: str) -> int:
    letters = re.match(r"[A-Z]+", cell_reference)
    if not letters:
        raise ValueError(f"Invalid XLSX cell reference: {cell_reference}")
    number = 0
    for letter in letters.group(0):
        number = number * 26 + ord(letter) - ord("A") + 1
    return number


def _xml_text(element: ElementTree.Element | None) -> str:
    if element is None:
        return ""
    return "".join(element.itertext())


def _shared_strings(archive: zipfile.ZipFile) -> list[str]:
    try:
        root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    return [_xml_text(item) for item in root.findall(f"{{{XLSX_NS}}}si")]


def _first_sheet_path(archive: zipfile.ZipFile) -> str:
    workbook = ElementTree.fromstring(archive.read("xl/workbook.xml"))
    sheet = workbook.find(f".//{{{XLSX_NS}}}sheet")
    if sheet is None:
        raise ValueError("The XLSX workbook contains no worksheets")
    relationship_id = sheet.get(f"{{{REL_NS}}}id")
    relationships = ElementTree.fromstring(
        archive.read("xl/_rels/workbook.xml.rels")
    )
    for relationship in relationships.findall(f"{{{PACKAGE_REL_NS}}}Relationship"):
        if relationship.get("Id") == relationship_id:
            target = relationship.get("Target", "")
            if target.startswith("/"):
                return target.lstrip("/")
            return f"xl/{target.lstrip('/')}"
    raise ValueError("The first worksheet relationship was not found")


def _worksheet_values(path: Path) -> list[list[str]]:
    with zipfile.ZipFile(path) as archive:
        shared = _shared_strings(archive)
        root = ElementTree.fromstring(archive.read(_first_sheet_path(archive)))

    rows: list[list[str]] = []
    for row in root.findall(f".//{{{XLSX_NS}}}row"):
        values: list[str] = []
        for cell in row.findall(f"{{{XLSX_NS}}}c"):
            index = _column_number(cell.get("r", "")) - 1
            while len(values) <= index:
                values.append("")

            cell_type = cell.get("t")
            if cell_type == "inlineStr":
                value = _xml_text(cell.find(f"{{{XLSX_NS}}}is"))
            else:
                raw = _xml_text(cell.find(f"{{{XLSX_NS}}}v"))
                if cell_type == "s" and raw:
                    value = shared[int(raw)]
                else:
                    value = raw
            values[index] = value.strip()
        rows.append(values)
    return rows


def _required_columns(values: list[str], row_number: int) -> list[str]:
    padded = values + [""] * (23 - len(values))
    selected = padded[:23]
    if any(not value for value in selected):
        missing = [str(index + 1) for index, value in enumerate(selected) if not value]
        raise ValueError(
            f"SEO workbook row {row_number} has empty required columns: {', '.join(missing)}"
        )
    return selected


def load_seo_rows(path: Path | str) -> list[SeoRow]:
    """Load all non-empty data rows from the first worksheet."""

    workbook_path = Path(path)
    if not workbook_path.is_file():
        raise FileNotFoundError(f"SEO workbook was not found: {workbook_path}")
    worksheet = _worksheet_values(workbook_path)
    if len(worksheet) < 2:
        raise ValueError("SEO workbook has no data rows")

    result: list[SeoRow] = []
    for row_number, raw in enumerate(worksheet[1:], start=2):
        if not raw or not raw[0].strip():
            continue
        values = _required_columns(raw, row_number)
        result.append(
            SeoRow(
                query=values[0],
                titles=tuple(values[1:6]),
                descriptions=tuple(values[6:11]),
                intros=tuple(values[11:16]),
                price_intro=values[16],
                private_intro=values[17],
                business_intro=values[18],
                faq_heading=values[19],
                faq_html=values[20],
                contact_heading=values[21],
                gallery_heading=values[22],
            )
        )
    return result


def replace_placeholders(text: str, city1: str, city2: str) -> str:
    """Replace only the two placeholders defined by the workbook contract."""

    return text.replace("{Город1}", city1).replace("{Город2}", city2)


_TRANSLITERATION = str.maketrans(
    {
        "а": "a",
        "б": "b",
        "в": "v",
        "г": "g",
        "д": "d",
        "е": "e",
        "ё": "e",
        "ж": "zh",
        "з": "z",
        "и": "i",
        "й": "i",
        "к": "k",
        "л": "l",
        "м": "m",
        "н": "n",
        "о": "o",
        "п": "p",
        "р": "r",
        "с": "s",
        "т": "t",
        "у": "u",
        "ф": "f",
        "х": "h",
        "ц": "ts",
        "ч": "ch",
        "ш": "sh",
        "щ": "shch",
        "ъ": "",
        "ы": "y",
        "ь": "",
        "э": "e",
        "ю": "yu",
        "я": "ya",
        "ў": "u",
        "і": "i",
    }
)


def slugify_ru(value: str) -> str:
    """Return a stable ASCII alias segment for Russian or Belarusian text."""

    transliterated = value.casefold().translate(_TRANSLITERATION)
    slug = re.sub(r"[^a-z0-9]+", "-", transliterated).strip("-")
    if not slug:
        raise ValueError(f"Cannot build an alias from: {value!r}")
    return slug


def production_alias(query: str, city1: str, city2: str) -> str:
    """Build the public alias for one service and one real route."""

    return "-".join((slugify_ru(query), slugify_ru(city1), slugify_ru(city2)))


def _personalize_static_route(source_html: str, city1: str, city2: str) -> str:
    """Replace route copy that belongs to the approved base template, not Excel."""

    route = f"{city1} – {city2}"
    reverse_route = f"{city2} – {city1}"
    replacements = (
        ("между Минском и Уздой", f"по маршруту {route}"),
        ("как в Минске, так и в Узде", f"на всём маршруте {route}"),
        ("Минск, Узда и вся Беларусь", f"{city1}, {city2} и вся Беларусь"),
        ("Узда – Минск", reverse_route),
        ("Минск – Узда", route),
    )
    for old, new in replacements:
        source_html = source_html.replace(old, new)
    return source_html


def _apply_direction_catalog(soup: BeautifulSoup, query: str) -> None:
    """Render every unique Minsk route as a real page link in three columns."""

    grid = soup.select_one("#cities .seo-directions-grid")
    if grid is None:
        raise ValueError("Approved template is missing the route-linking grid")
    grid.clear()

    # Keep the approved desktop layout: three columns with two regional lists.
    for group_indexes in ((0, 3), (1, 4), (2, 5)):
        column = soup.new_tag("div")
        column["class"] = ["seo-direction-column"]
        for group_index in group_indexes:
            group = ROUTE_GROUPS[group_index]
            section = soup.new_tag("section")
            section["class"] = ["seo-direction-group"]
            heading = soup.new_tag("h3")
            heading.string = group.title
            section.append(heading)
            route_list = soup.new_tag("ul")
            route_list["class"] = ["seo-direction-list"]
            for city in group.cities:
                item = soup.new_tag("li")
                link = soup.new_tag(
                    "a",
                    href=f"/{production_alias(query, 'Минск', city)}/",
                )
                link.string = f"Минск – {city}"
                item.append(link)
                route_list.append(item)
            section.append(route_list)
            column.append(section)
        grid.append(column)


def populate_direction_catalog(source_html: str, query: str) -> str:
    """Populate the approved route block for preview or MODX extraction."""

    soup = BeautifulSoup(source_html, "html.parser")
    _apply_direction_catalog(soup, query)
    return str(soup)


def _set_text(soup: BeautifulSoup, selector: str, value: str) -> None:
    element = soup.select_one(selector)
    if element is None:
        raise ValueError(f"Approved template is missing required selector: {selector}")
    element.clear()
    element.append(value)


def _apply_faq(
    soup: BeautifulSoup, faq_heading: str, faq_html: str, city1: str, city2: str
) -> None:
    _set_text(soup, "#faq h2", replace_placeholders(faq_heading, city1, city2))
    target = soup.select_one("#faq .seo-faq-list")
    if target is None:
        raise ValueError("Approved template is missing the FAQ list")

    source = BeautifulSoup(replace_placeholders(faq_html, city1, city2), "html.parser")
    details = source.select("details")
    if not details:
        raise ValueError("SEO workbook FAQ HTML contains no details elements")

    target.clear()
    for item in details:
        question = item.select_one("summary")
        if question is None:
            raise ValueError("SEO workbook FAQ item has no summary")
        question_text = question.get_text(" ", strip=True).removeprefix("▶").strip()
        rendered = soup.new_tag("details")
        summary = soup.new_tag("summary")
        summary.string = question_text
        rendered.append(summary)
        paragraphs = item.select(".faq-answer p") or item.select("p")
        for paragraph in paragraphs:
            rendered_paragraph = soup.new_tag("p")
            rendered_paragraph.string = paragraph.get_text(" ", strip=True)
            rendered.append(rendered_paragraph)
        target.append(rendered)


def _render_page(
    source_html: str,
    row: SeoRow,
    city1: str,
    city2: str,
    variant: int,
    batch_slug: str,
    *,
    production: bool = False,
) -> GeneratedPage:
    if variant not in range(1, 6):
        raise ValueError("Variant must be between 1 and 5")
    index = variant - 1
    soup = BeautifulSoup(
        _personalize_static_route(source_html, city1, city2), "html.parser"
    )

    title = replace_placeholders(row.titles[index], city1, city2)
    description = replace_placeholders(row.descriptions[index], city1, city2)
    _set_text(soup, "title", title)
    description_tag = soup.select_one('meta[name="description"]')
    if description_tag is None:
        raise ValueError("Approved template is missing meta description")
    description_tag["content"] = description

    route = f"{city1} – {city2}"
    _set_text(soup, "#intro h1", f"{row.query} {route}")
    _set_text(
        soup,
        "#intro .seo-intro-copy > p",
        replace_placeholders(row.intros[index], city1, city2),
    )
    _set_text(soup, "#prices h2", f"{row.query} {route}: цена")
    _set_text(
        soup,
        "#prices .seo-price-lead > div > p",
        replace_placeholders(row.price_intro, city1, city2),
    )
    _set_text(soup, "#private-clients h2", f"{row.query} для частных лиц")
    _set_text(
        soup,
        "#private-clients .seo-heading > p",
        replace_placeholders(row.private_intro, city1, city2),
    )
    _set_text(soup, "#business-clients h2", f"{row.query} для бизнеса")
    _set_text(
        soup,
        "#business-clients .seo-heading > p",
        replace_placeholders(row.business_intro, city1, city2),
    )
    _set_text(soup, "#process h2", f"Как заказать {row.query.casefold()}")
    _set_text(soup, "#fleet h2", f"Наш автопарк и услуги для маршрута {route}")
    _apply_faq(soup, row.faq_heading, row.faq_html, city1, city2)
    _set_text(
        soup,
        "#gallery h2",
        replace_placeholders(row.gallery_heading, city1, city2),
    )
    _set_text(
        soup,
        "#contact h2",
        replace_placeholders(row.contact_heading, city1, city2),
    )
    _set_text(soup, "#cities h2", f"{row.query} из Минска по всей Беларуси")
    _apply_direction_catalog(soup, row.query)

    if production:
        alias = production_alias(row.query, city1, city2)
        marker = PRODUCTION_MARKER
    else:
        alias = "-".join(
            (ALIAS_PREFIX, slugify_ru(row.query), slugify_ru(batch_slug))
        )
        marker = f"{BATCH_MARKER_PREFIX}{batch_slug}"
    html = f"<!-- {marker} -->\n{str(soup)}"
    if "{Город" in html:
        raise ValueError(f"Unresolved city placeholder in generated page: {row.query}")
    return GeneratedPage(
        query=row.query,
        alias=alias,
        title=title,
        description=description,
        marker=marker,
        html=html,
        city1=city1,
        city2=city2,
        variant=variant,
    )


def build_generated_pages(
    source_html: str,
    rows: Iterable[SeoRow],
    *,
    city1: str,
    city2: str,
    variant: int = 1,
    batch_slug: str | None = None,
) -> list[GeneratedPage]:
    """Render a complete batch and reject duplicate aliases before publishing."""

    normalized_batch = batch_slug or f"{slugify_ru(city1)}-{slugify_ru(city2)}"
    pages = [
        _render_page(source_html, row, city1, city2, variant, normalized_batch)
        for row in rows
    ]
    aliases = [page.alias for page in pages]
    if len(aliases) != len(set(aliases)):
        raise ValueError("Generated SEO aliases are not unique")
    return pages


def build_all_route_pages(
    source_html: str,
    rows: Iterable[SeoRow],
    *,
    city1: str = "Минск",
) -> list[GeneratedPage]:
    """Render every workbook service for every unique approved destination."""

    routes = all_routes()
    pages = [
        _render_page(
            source_html,
            row,
            city1,
            route.city,
            route_index % 5 + 1,
            f"{slugify_ru(city1)}-{slugify_ru(route.city)}",
            production=True,
        )
        for row in rows
        for route_index, route in enumerate(routes)
    ]
    aliases = [page.alias for page in pages]
    if len(aliases) != len(set(aliases)):
        raise ValueError("Generated production aliases are not unique")
    return pages


def validate_resource_ownership(content: str, marker: str, alias: str) -> None:
    """Prevent a generated alias from overwriting an unrelated MODX resource."""

    if marker not in content:
        raise RuntimeError(
            f"Refusing to overwrite existing MODX resource without generation marker: {alias}"
        )
