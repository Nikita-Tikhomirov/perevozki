"""Approved Minsk route catalogue from the live site block referenced in the DOCX."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Route:
    """One unique destination used for generation and internal linking."""

    city: str
    group_title: str


@dataclass(frozen=True)
class RouteGroup:
    """A regional column in the route-linking block."""

    title: str
    cities: tuple[str, ...]


ROUTE_GROUPS = (
    RouteGroup(
        "Минск — Минск и область",
        (
            "Молодечно",
            "Березино",
            "Дзержинск",
            "Клецк",
            "Копыль",
            "Борисов",
            "Вилейка",
            "Воложин",
            "Крупки",
            "Логойск",
            "Любань",
            "Жодино",
            "Мядель",
            "Несвиж",
            "Марьина Горка",
            "Слуцк",
            "Смолевичи",
            "Солигорск",
            "Старые Дороги",
            "Столбцы",
            "Узда",
            "Червень",
        ),
    ),
    RouteGroup(
        "Минск — Брест и область",
        (
            "Пружаны",
            "Пинск",
            "Малорита",
            "Ляховичи",
            "Лунинец",
            "Кобрин",
            "Каменец",
            "Ивацевичи",
            "Иваново",
            "Жабинка",
            "Дрогичин",
            "Ганцевичи",
            "Береза",
            "Барановичи",
            "Брест",
            "Столин",
        ),
    ),
    RouteGroup(
        "Минск — Витебск и область",
        (
            "Миоры",
            "Витебск",
            "Браслав",
            "Бешенковичи",
            "Верхнедвинск",
            "Глубокое",
            "Городок",
            "Докшицы",
            "Дубровно",
            "Лепель",
            "Лиозно",
            "Орша",
            "Полоцк",
            "Поставы",
            "Россоны",
            "Сенно",
            "Толочин",
            "Ушачи",
            "Чашники",
            "Шарковщина",
            "Шумилино",
        ),
    ),
    RouteGroup(
        "Минск — Гомель и область",
        (
            "Лельчицы",
            "Гомель",
            "Брагин",
            "Буда-Кошелёво",
            "Ветка",
            "Добруш",
            "Ельск",
            "Житковичи",
            "Жлобин",
            "Калинковичи",
            "Корма",
            "Хойники",
            "Лоев",
            "Мозырь",
            "Наровля",
            "Октябрьский",
            "Петриков",
            "Речица",
            "Рогачев",
            "Светлогорск",
            "Чечерск",
        ),
    ),
    RouteGroup(
        "Минск — Гродно и область",
        (
            "Лида",
            "Гродно",
            "Берестовица",
            "Волковыск",
            "Вороново",
            "Дятлово",
            "Зельва",
            "Ивье",
            "Кореличи",
            "Щучин",
            "Мосты",
            "Новогрудок",
            "Ошмяны",
            "Островец",
            "Свислочь",
            "Слоним",
            "Сморгонь",
        ),
    ),
    RouteGroup(
        "Минск — Могилёв и область",
        (
            "Кличев",
            "Чериков",
            "Могилёв",
            "Белыничи",
            "Бобруйск",
            "Быхов",
            "Горки",
            "Глуск",
            "Дрибин",
            "Кировск",
            "Климовичи",
            "Шклов",
            "Костюковичи",
            "Краснополье",
            "Кричев",
            "Круглое",
            "Мстиславль",
            "Осиповичи",
            "Славгород",
            "Хотимск",
            "Чаусы",
        ),
    ),
)


def all_routes() -> tuple[Route, ...]:
    """Return the deduplicated route order used by the approved block."""

    routes = tuple(
        Route(city=city, group_title=group.title)
        for group in ROUTE_GROUPS
        for city in group.cities
    )
    cities = [route.city for route in routes]
    if len(cities) != len(set(cities)):
        raise ValueError("The route catalogue contains duplicate destinations")
    return routes
